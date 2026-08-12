import logging

from core.xtream_codes import Client as XtreamCodesClient

from .descriptors import encode_descriptor
from .newznab import _category, _estimated_size, _pubdate
from .probe import probe_media
from .provider import _cached_catalog, _tmdb, _year, active_xc_accounts
from .releases import build_episode_release


logger = logging.getLogger(__name__)


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _recency(value):
    text = str(value or "").strip()
    if text.isdigit():
        return int(text)
    return 0


def _episode_rows(detail):
    episodes = detail.get("episodes") if isinstance(detail, dict) else None
    rows = []
    if isinstance(episodes, dict):
        for season_key, season_rows in episodes.items():
            if isinstance(season_rows, dict):
                season_rows = list(season_rows.values())
            if not isinstance(season_rows, list):
                continue
            for row in season_rows:
                if isinstance(row, dict):
                    rows.append((season_key, row))
    elif isinstance(episodes, list):
        rows = [(None, row) for row in episodes if isinstance(row, dict)]
    return rows


def _latest_episode(detail):
    candidates = []
    for season_hint, row in _episode_rows(detail):
        season = _int(row.get("season") or season_hint, 0)
        episode = _int(row.get("episode_num") or row.get("episode"), 0)
        episode_id = row.get("id") or row.get("stream_id") or row.get("episode_id")
        if episode_id is None or season < 0 or episode <= 0:
            continue
        candidates.append((
            _recency(row.get("added")),
            season,
            episode,
            str(episode_id),
            row,
        ))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    return candidates[0]


def _series_candidates(settings, scan_limit):
    candidates = []
    for account in active_xc_accounts():
        for item in _cached_catalog(account, "series", settings):
            series_id = item.get("series_id") or item.get("stream_id") or item.get("id")
            if series_id is None:
                continue
            candidates.append((
                _recency(item.get("last_modified") or item.get("added")),
                account,
                item,
                str(series_id),
            ))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[:scan_limit]


def recent_tv_results(settings):
    """Return a small real TV recent feed for Sonarr's unqualified tvsearch.

    Sonarr uses ``t=tvsearch`` without season/episode parameters for both indexer
    validation and RSS/recent polling. Raw Xtream providers do not expose one
    unified episode feed, so inspect a bounded set of the most recently changed
    series and publish each series' latest episode as a normal downloadable
    MUSTARRD Newznab result.
    """
    result_limit = min(5, max(1, int(settings.get("max_variants") or 20)))
    scan_limit = max(10, result_limit * 4)
    results = []

    for _, account, item, series_id in _series_candidates(settings, scan_limit):
        try:
            with XtreamCodesClient(
                account.server_url,
                account.username,
                account.password,
                account.get_user_agent_string(),
            ) as client:
                detail = client.get_series_info(series_id) or {}
                latest = _latest_episode(detail)
                if latest is None:
                    continue

                added, season, episode, episode_id, row = latest
                extension = str(row.get("container_extension") or "mp4").lstrip(".")
                url = client.get_episode_stream_url(episode_id, extension)

            series_info = detail.get("info") if isinstance(detail, dict) else {}
            if not isinstance(series_info, dict):
                series_info = {}
            episode_info = row.get("info") if isinstance(row.get("info"), dict) else {}
            video = episode_info.get("video") if isinstance(episode_info.get("video"), dict) else {}
            audio = episode_info.get("audio") if isinstance(episode_info.get("audio"), dict) else {}
            size = _estimated_size(episode_info)
            duration_seconds = _int(episode_info.get("duration_secs"), 0)

            # Some providers omit codec metadata from get_series_info. Probe only
            # those entries, keeping the normal recent path cheap when metadata is
            # already present.
            if not video:
                probed = probe_media(url, settings)
                if probed.get("status") != "ok" or not probed.get("video"):
                    continue
                video = probed["video"]
                audio = probed.get("audio") or audio
                size = int(probed.get("size") or size)
                duration_seconds = int(probed.get("duration") or duration_seconds)

            series_name = series_info.get("name") or item.get("name") or "Unknown"
            year = _year(
                series_info.get("release_date")
                or series_info.get("year")
                or item.get("release_date")
                or item.get("name")
            )
            tmdb_id = _tmdb(
                series_info.get("tmdb_id")
                or series_info.get("tmdb")
                or item.get("tmdb_id")
                or item.get("tmdb")
            )
            release = build_episode_release(series_name, year, season, episode, video, audio)
            payload = {
                "version": 1,
                "kind": "episode",
                "dispatcharr_account_id": int(account.id),
                "series_id": series_id,
                "media_id": episode_id,
                "container_extension": extension,
                "tmdb_id": tmdb_id,
                "content_name": series_name,
                "year": year,
                "season": season,
                "episode": episode,
                "release": release,
                "duration_minutes": int(duration_seconds / 60),
            }
            token = encode_descriptor(payload, settings["api_key"])
            results.append({
                "title": release,
                "guid": f"dispatcharr-vod:episode:{account.id}:{episode_id}",
                "token": token,
                "pubdate": _pubdate(added or item.get("last_modified") or item.get("added")),
                "category": _category(video, "tv"),
                "size": int(size or 0),
                "tmdb_id": tmdb_id,
                "_sort_added": added or _recency(item.get("last_modified") or item.get("added")),
            })
            if len(results) >= result_limit:
                break
        except Exception:
            logger.exception(
                "Unable to build recent TV result account=%s series_id=%s",
                account.id,
                series_id,
            )

    results.sort(key=lambda row: int(row.pop("_sort_added", 0) or 0), reverse=True)
    return results
