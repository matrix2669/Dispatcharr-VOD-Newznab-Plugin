import email.utils
import time
import xml.etree.ElementTree as ET
from urllib.parse import quote

from .config import movie_output_path, tv_output_path
from .descriptors import descriptor_nzb, encode_descriptor
from .probe import probe_media, resolution_label
from .provider import movie_candidates, movie_detail_and_url, series_candidates, series_episode_variants
from .releases import build_episode_release, build_movie_release

NEWZNAB_NS = "http://www.newznab.com/DTD/2010/feeds/attributes/"
ET.register_namespace("newznab", NEWZNAB_NS)


def caps_xml():
    caps = ET.Element("caps")
    ET.SubElement(caps, "server", version="1.0", title="Dispatcharr VOD Newznab")
    ET.SubElement(caps, "limits", max="100", default="100")
    ET.SubElement(caps, "registration", available="no", open="no")
    searching = ET.SubElement(caps, "searching")
    ET.SubElement(searching, "search", available="yes", supportedParams="q")
    ET.SubElement(searching, "movie-search", available="yes", supportedParams="q,tmdbid")
    ET.SubElement(searching, "tv-search", available="yes", supportedParams="q,tmdbid,season,ep")
    categories = ET.SubElement(caps, "categories")
    movie = ET.SubElement(categories, "category", id="2000", name="Movies")
    ET.SubElement(movie, "subcat", id="2040", name="Movies/HD")
    ET.SubElement(movie, "subcat", id="2045", name="Movies/UHD")
    tv = ET.SubElement(categories, "category", id="5000", name="TV")
    ET.SubElement(tv, "subcat", id="5040", name="TV/HD")
    ET.SubElement(tv, "subcat", id="5045", name="TV/UHD")
    return ET.tostring(caps, encoding="utf-8", xml_declaration=True)


def _pubdate(value):
    try:
        ts = int(value)
    except (TypeError, ValueError):
        ts = int(time.time())
    return email.utils.formatdate(ts, usegmt=True)


def _category(video, kind):
    uhd = resolution_label(video) == "2160p"
    return ("2045" if uhd else "2040") if kind == "movie" else ("5045" if uhd else "5040")


def _estimated_size(info):
    try:
        bitrate = int(float(info.get("bitrate") or 0))
        duration = int(float(info.get("duration_secs") or 0))
    except (TypeError, ValueError):
        return 0
    bps = bitrate * 1000 if bitrate and bitrate < 1_000_000 else bitrate
    return int((bps * duration) / 8) if bps and duration else 0


def _movie_result(candidate, settings):
    detail = movie_detail_and_url(candidate)
    probed = probe_media(detail["url"], settings)
    if probed.get("status") != "ok" or not probed.get("video"):
        return None
    video = probed["video"]
    audio = probed.get("audio") or {}
    release = build_movie_release(detail["name"], detail["year"], video, audio)
    relpath = movie_output_path(
        settings,
        title=detail["name"],
        year=detail["year"],
        tmdb_id=detail["tmdb_id"],
        release=release,
        extension=detail["extension"],
    )
    payload = {
        "version": 1,
        "kind": "movie",
        "dispatcharr_account_id": int(detail["account"].id),
        "media_id": detail["stream_id"],
        "container_extension": detail["extension"],
        "tmdb_id": detail["tmdb_id"],
        "content_name": detail["name"],
        "year": detail["year"],
        "release": release,
        "relative_output_path": relpath,
        "duration_minutes": int((probed.get("duration") or 0) / 60),
    }
    token = encode_descriptor(payload, settings["api_key"])
    return {
        "title": release,
        "guid": f"dispatcharr-vod:movie:{detail['account'].id}:{detail['stream_id']}",
        "token": token,
        "pubdate": _pubdate(detail.get("added")),
        "category": _category(video, "movie"),
        "size": int(probed.get("size") or 0),
        "tmdb_id": detail["tmdb_id"],
    }


def search_movies(tmdbid, query, settings):
    candidates = movie_candidates(tmdbid, query, settings)
    if not candidates:
        return []
    results = []
    for candidate in candidates:
        try:
            result = _movie_result(candidate, settings)
        except Exception:
            result = None
        if result:
            results.append(result)
    results.sort(key=lambda row: row["size"], reverse=True)
    return results


def search_tv(tmdbid, query, season, episode, settings):
    if season is None:
        return []
    results = []
    max_variants = max(1, int(settings.get("max_variants") or 20))
    for candidate in series_candidates(tmdbid, query, settings):
        try:
            variants = series_episode_variants(candidate, int(season), int(episode) if episode is not None else None)
        except Exception:
            continue
        for variant in variants:
            info = variant.get("episode_info") or {}
            video = info.get("video") if isinstance(info.get("video"), dict) else {}
            audio = info.get("audio") if isinstance(info.get("audio"), dict) else {}
            size = _estimated_size(info)
            duration_seconds = int(info.get("duration_secs") or 0) if str(info.get("duration_secs") or "").isdigit() else 0
            if episode is not None:
                probed = probe_media(variant["url"], settings)
                if probed.get("status") == "ok" and probed.get("video"):
                    video = probed["video"]
                    audio = probed.get("audio") or audio
                    size = int(probed.get("size") or size)
                    duration_seconds = int(probed.get("duration") or duration_seconds)
            if not video:
                continue
            release = build_episode_release(
                variant["series_name"], variant["year"], variant["season"], variant["episode"], video, audio
            )
            relpath = tv_output_path(
                settings,
                series=variant["series_name"],
                year=variant["year"],
                tmdb_id=variant["tmdb_id"],
                season=variant["season"],
                episode=variant["episode"],
                release=release,
                extension=variant["extension"],
            )
            payload = {
                "version": 1,
                "kind": "episode",
                "dispatcharr_account_id": int(variant["account"].id),
                "series_id": variant["series_id"],
                "media_id": variant["episode_id"],
                "container_extension": variant["extension"],
                "tmdb_id": variant["tmdb_id"],
                "content_name": variant["series_name"],
                "year": variant["year"],
                "season": variant["season"],
                "episode": variant["episode"],
                "release": release,
                "relative_output_path": relpath,
                "duration_minutes": int(duration_seconds / 60),
            }
            token = encode_descriptor(payload, settings["api_key"])
            results.append({
                "title": release,
                "guid": f"dispatcharr-vod:episode:{variant['account'].id}:{variant['episode_id']}",
                "token": token,
                "pubdate": _pubdate(variant.get("added")),
                "category": _category(video, "tv"),
                "size": size,
                "tmdb_id": variant["tmdb_id"],
            })
            if len(results) >= max_variants:
                return results
    return results


def rss_xml(results, base_url, api_key, offset=0, limit=100):
    total = len(results)
    page = results[offset:offset + limit]
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Dispatcharr VOD"
    ET.SubElement(channel, "description").text = "Raw Dispatcharr VOD Interactive Search"
    ET.SubElement(channel, "link").text = base_url
    ET.SubElement(channel, f"{{{NEWZNAB_NS}}}response", offset=str(offset), total=str(total))
    for result in page:
        item = ET.SubElement(channel, "item")
        grab = f"{base_url}/grab/{quote(result['token'], safe='')}.nzb?apikey={quote(api_key, safe='')}"
        ET.SubElement(item, "title").text = result["title"]
        ET.SubElement(item, "guid", isPermaLink="false").text = result["guid"]
        ET.SubElement(item, "link").text = grab
        ET.SubElement(item, "pubDate").text = result["pubdate"]
        ET.SubElement(item, "category").text = result["category"]
        ET.SubElement(item, "description").text = result["title"]
        ET.SubElement(item, "enclosure", url=grab, length=str(result["size"]), type="application/x-nzb")
        for name, value in (("category", result["category"]), ("size", result["size"]), ("tmdbid", result.get("tmdb_id"))):
            if value not in {None, ""}:
                ET.SubElement(item, f"{{{NEWZNAB_NS}}}attr", name=name, value=str(value))
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)


def grab_nzb(token, settings):
    from .descriptors import decode_descriptor
    payload = decode_descriptor(token, settings["api_key"])
    return descriptor_nzb(token, payload.get("release") or "Mustarrd.VOD")
