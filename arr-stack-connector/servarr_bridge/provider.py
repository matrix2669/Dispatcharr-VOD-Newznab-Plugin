"""Dispatcharr VOD provider integration for Arr Stack Connector."""

import logging
import re
import threading
import time
import uuid
from urllib.parse import urlencode

from django.utils import timezone

from core.xtream_codes import Client as XtreamCodesClient
from apps.m3u.models import M3UAccount
from apps.vod.models import (
    Episode,
    M3UEpisodeRelation,
    M3UMovieRelation,
    M3USeriesRelation,
    M3UVODCategoryRelation,
    Movie,
    Series,
)


logger = logging.getLogger(__name__)
_cache = {}
_cache_lock = threading.RLock()


def _tmdb(value):
    text = str(value or "").strip()
    match = re.search(r"(?:^|/)(\d+)(?:/?$)", text)
    return match.group(1) if match else ""


def _year(value):
    match = re.search(r"\b(19\d{2}|20\d{2}|21\d{2})\b", str(value or ""))
    return int(match.group(1)) if match else None


def _matches_query(name, query):
    tokens = re.findall(r"[a-z0-9]+", str(query or "").lower())
    if not tokens:
        return True
    haystack = " ".join(re.findall(r"[a-z0-9]+", str(name or "").lower()))
    return all(token in haystack for token in tokens)


def active_xc_accounts():
    return list(
        M3UAccount.objects.filter(is_active=True, account_type=M3UAccount.Types.XC)
        .select_related("user_agent")
        .order_by("-priority", "id")
    )


def get_account(account_id):
    return M3UAccount.objects.select_related("user_agent").get(
        id=int(account_id), is_active=True, account_type=M3UAccount.Types.XC
    )


def _enabled_category_names(account, category_type):
    relations = M3UVODCategoryRelation.objects.filter(
        m3u_account=account,
        category__category_type=category_type,
    ).select_related("category")
    rows = list(relations)
    if not rows:
        return None
    return {row.category.name for row in rows if row.enabled}


def _provider_category_map(client, kind):
    categories = client.get_vod_categories() if kind == "movie" else client.get_series_categories()
    return {
        str(row.get("category_id")): str(row.get("category_name") or "Uncategorized")
        for row in categories or []
        if isinstance(row, dict) and row.get("category_id") is not None
    }


def _allowed_item(item, category_map, enabled_names):
    if enabled_names is None:
        return True
    category_id = str(item.get("category_id") or "")
    category_name = category_map.get(category_id, "Uncategorized")
    return category_name in enabled_names


def _cached_catalog(account, kind, settings):
    ttl = max(0, int(settings.get("catalog_cache_seconds") or 0))
    respect_groups = bool(settings.get("respect_enabled_vod_groups", True))
    key = (int(account.id), kind, respect_groups)
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(key)
        if cached and now - cached[0] <= ttl:
            return cached[1]

    with XtreamCodesClient(
        account.server_url,
        account.username,
        account.password,
        account.get_user_agent_string(),
    ) as client:
        items = client.get_vod_streams() if kind == "movie" else client.get_series()
        items = [item for item in (items or []) if isinstance(item, dict)]
        if respect_groups:
            enabled = _enabled_category_names(account, kind)
            category_map = _provider_category_map(client, kind)
            items = [item for item in items if _allowed_item(item, category_map, enabled)]

    with _cache_lock:
        _cache[key] = (now, items)
    return items


def clear_cache():
    with _cache_lock:
        _cache.clear()


def movie_candidates(tmdb_id, query, settings):
    wanted_tmdb = _tmdb(tmdb_id)
    limit = max(1, int(settings.get("max_variants") or 20))
    matches = []
    for account in active_xc_accounts():
        for item in _cached_catalog(account, "movie", settings):
            if wanted_tmdb:
                if _tmdb(item.get("tmdb_id") or item.get("tmdb")) != wanted_tmdb:
                    continue
            elif not _matches_query(item.get("name"), query):
                continue
            stream_id = item.get("stream_id") or item.get("vod_id") or item.get("id")
            if stream_id is None:
                continue
            matches.append({"account": account, "item": item, "stream_id": str(stream_id)})
            if len(matches) >= limit:
                return matches
    return matches


def series_candidates(tmdb_id, query, settings):
    wanted_tmdb = _tmdb(tmdb_id)
    limit = max(1, int(settings.get("max_variants") or 20))
    matches = []
    for account in active_xc_accounts():
        for item in _cached_catalog(account, "series", settings):
            if wanted_tmdb:
                if _tmdb(item.get("tmdb_id") or item.get("tmdb")) != wanted_tmdb:
                    continue
            elif not _matches_query(item.get("name"), query):
                continue
            series_id = item.get("series_id") or item.get("stream_id") or item.get("id")
            if series_id is None:
                continue
            matches.append({"account": account, "item": item, "series_id": str(series_id)})
            if len(matches) >= limit:
                return matches
    return matches


def movie_detail_and_url(candidate):
    account = candidate["account"]
    item = candidate["item"]
    stream_id = candidate["stream_id"]
    extension = str(item.get("container_extension") or "mp4").lstrip(".")
    with XtreamCodesClient(
        account.server_url, account.username, account.password, account.get_user_agent_string()
    ) as client:
        try:
            detail = client.get_vod_info(stream_id) or {}
        except Exception:
            detail = {}
        url = client.get_vod_stream_url(stream_id, extension)
    info = detail.get("info") if isinstance(detail, dict) else {}
    if not isinstance(info, dict):
        info = {}
    return {
        "account": account,
        "stream_id": stream_id,
        "extension": extension,
        "url": url,
        "name": info.get("name") or item.get("name") or "Unknown",
        "year": _year(info.get("year") or info.get("release_date") or item.get("year") or item.get("name")),
        "tmdb_id": _tmdb(info.get("tmdb_id") or info.get("tmdb") or item.get("tmdb_id") or item.get("tmdb")),
        "added": item.get("added"),
        "item": item,
        "detail": detail,
    }


def _season_items(detail, season):
    episodes = detail.get("episodes") if isinstance(detail, dict) else None
    if isinstance(episodes, dict):
        rows = episodes.get(str(season)) or episodes.get(season) or []
    elif isinstance(episodes, list):
        rows = episodes
    else:
        rows = []
    if isinstance(rows, dict):
        rows = list(rows.values())
    return [row for row in rows if isinstance(row, dict)]


def series_episode_variants(candidate, season, episode=None):
    account = candidate["account"]
    item = candidate["item"]
    series_id = candidate["series_id"]
    with XtreamCodesClient(
        account.server_url, account.username, account.password, account.get_user_agent_string()
    ) as client:
        detail = client.get_series_info(series_id) or {}
        info = detail.get("info") or {}
        if not isinstance(info, dict):
            info = {}
        rows = []
        for row in _season_items(detail, int(season)):
            try:
                row_season = int(row.get("season") or season)
                row_episode = int(row.get("episode_num") or row.get("episode") or 0)
            except (TypeError, ValueError):
                continue
            if row_season != int(season):
                continue
            if episode is not None and row_episode != int(episode):
                continue
            episode_id = row.get("id") or row.get("stream_id") or row.get("episode_id")
            if episode_id is None:
                continue
            extension = str(row.get("container_extension") or "mp4").lstrip(".")
            rows.append({
                "account": account,
                "series_id": series_id,
                "episode_id": str(episode_id),
                "extension": extension,
                "url": client.get_episode_stream_url(str(episode_id), extension),
                "series_name": info.get("name") or item.get("name") or "Unknown",
                "year": _year(info.get("release_date") or info.get("year") or item.get("release_date") or item.get("name")),
                "tmdb_id": _tmdb(info.get("tmdb_id") or info.get("tmdb") or item.get("tmdb_id") or item.get("tmdb")),
                "season": row_season,
                "episode": row_episode,
                "episode_title": row.get("title") or (row.get("info") or {}).get("name") or "",
                "episode_info": row.get("info") if isinstance(row.get("info"), dict) else {},
                "added": row.get("added"),
            })
        return rows


def _movie_relation_for_proxy(account, payload, extension):
    stream_id = str(payload["media_id"])
    relation = (
        M3UMovieRelation.objects
        .filter(m3u_account=account, stream_id=stream_id)
        .select_related("movie")
        .first()
    )
    if relation:
        if extension and relation.container_extension != extension:
            relation.container_extension = extension
            relation.last_seen = timezone.now()
            relation.save(update_fields=["container_extension", "last_seen", "updated_at"])
        return relation

    tmdb_id = _tmdb(payload.get("tmdb_id"))
    movie = Movie.objects.filter(tmdb_id=tmdb_id).first() if tmdb_id else None
    if movie is None:
        title = str(payload.get("content_name") or "").strip()
        year = payload.get("year")
        query = Movie.objects.all()
        if title:
            query = query.filter(name__iexact=title)
        if year:
            query = query.filter(year=int(year))
        movie = query.first() if title else None
    if movie is None:
        raise ValueError(
            f"Dispatcharr movie object not found for TMDB {tmdb_id or 'unknown'}; "
            f"cannot proxy raw stream {stream_id}"
        )

    relation = M3UMovieRelation.objects.create(
        m3u_account=account,
        movie=movie,
        stream_id=stream_id,
        container_extension=extension or "mp4",
        custom_properties={"mustarrd_vod_newznab": {"materialized": True}},
        last_seen=timezone.now(),
    )
    logger.info(
        "Materialized missing Dispatcharr movie relation account=%s stream_id=%s movie=%s",
        account.id,
        stream_id,
        movie.id,
    )
    return relation


def _episode_relation_for_proxy(account, payload, extension):
    stream_id = str(payload["media_id"])
    relation = (
        M3UEpisodeRelation.objects
        .filter(m3u_account=account, stream_id=stream_id)
        .select_related("episode", "episode__series")
        .first()
    )
    if relation:
        if extension and relation.container_extension != extension:
            relation.container_extension = extension
            relation.last_seen = timezone.now()
            relation.save(update_fields=["container_extension", "last_seen", "updated_at"])
        return relation

    tmdb_id = _tmdb(payload.get("tmdb_id"))
    series = Series.objects.filter(tmdb_id=tmdb_id).first() if tmdb_id else None
    if series is None:
        raise ValueError(
            f"Dispatcharr series object not found for TMDB {tmdb_id or 'unknown'}; "
            f"cannot proxy raw episode stream {stream_id}"
        )

    season = int(payload.get("season") or 0)
    episode_number = int(payload.get("episode") or 0)
    episode = Episode.objects.filter(
        series=series,
        season_number=season,
        episode_number=episode_number,
    ).first()
    if episode is None:
        episode_title = str(payload.get("episode_title") or "").strip() or f"Episode {episode_number}"
        try:
            duration_secs = max(0, int(payload.get("duration_minutes") or 0) * 60)
        except (TypeError, ValueError):
            duration_secs = 0
        episode, created = Episode.objects.get_or_create(
            series=series,
            season_number=season,
            episode_number=episode_number,
            defaults={
                "name": episode_title,
                "duration_secs": duration_secs or None,
                "custom_properties": {
                    "mustarrd_vod_newznab": {
                        "materialized": True,
                        "provider_stream_id": stream_id,
                    }
                },
            },
        )
        if created:
            logger.info(
                "Materialized missing Dispatcharr episode TMDB=%s S%02dE%02d episode=%s for raw stream %s",
                tmdb_id,
                season,
                episode_number,
                episode.id,
                stream_id,
            )

    series_relation = None
    external_series_id = str(payload.get("series_id") or "").strip()
    if external_series_id:
        series_relation = M3USeriesRelation.objects.filter(
            m3u_account=account,
            external_series_id=external_series_id,
        ).first()
    if series_relation is None:
        series_relation = M3USeriesRelation.objects.filter(
            m3u_account=account,
            series=series,
        ).order_by("-updated_at").first()

    relation = M3UEpisodeRelation.objects.create(
        m3u_account=account,
        episode=episode,
        series_relation=series_relation,
        stream_id=stream_id,
        container_extension=extension or "mp4",
        custom_properties={"mustarrd_vod_newznab": {"materialized": True}},
        last_seen=timezone.now(),
    )
    logger.info(
        "Materialized missing Dispatcharr episode relation account=%s stream_id=%s episode=%s",
        account.id,
        stream_id,
        episode.id,
    )
    return relation


def dispatcharr_proxy_source(payload, settings):
    """Return a native Dispatcharr VOD proxy URL for the exact raw provider variant.

    Supplying a session ID in the path intentionally bypasses Dispatcharr's
    first-request Redirect behavior. The request therefore enters the native
    VOD proxy/connection manager even when the global default stream profile is
    Redirect, which keeps Mustarrd downloads visible in Dispatcharr VOD stats.
    """
    base_url = str(settings.get("dispatcharr_url") or "").strip().rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        raise ValueError("Dispatcharr URL seen by Mustarrd must be an absolute HTTP(S) URL")

    kind = str(payload.get("kind") or "").lower()
    account = get_account(payload["dispatcharr_account_id"])
    extension = str(payload.get("container_extension") or "mp4").lstrip(".")

    if kind == "movie":
        relation = _movie_relation_for_proxy(account, payload, extension)
        content_type = "movie"
        content_uuid = relation.movie.uuid
    elif kind == "episode":
        relation = _episode_relation_for_proxy(account, payload, extension)
        content_type = "episode"
        content_uuid = relation.episode.uuid
    else:
        raise ValueError(f"Unsupported VOD kind for Dispatcharr proxy: {kind}")

    session_id = f"mustarrd_{uuid.uuid4().hex}"
    query = urlencode({
        "m3u_account_id": int(account.id),
        "stream_id": str(payload["media_id"]),
    })
    url = f"{base_url}/proxy/vod/{content_type}/{content_uuid}/{session_id}?{query}"
    logger.info(
        "Resolved Mustarrd source through Dispatcharr VOD proxy kind=%s account=%s stream_id=%s session=%s",
        kind,
        account.id,
        payload["media_id"],
        session_id,
    )
    return url


def resolve_source(kind, account_id, media_id, extension):
    """Legacy direct-provider resolver retained for compatibility/debugging."""
    account = get_account(account_id)
    with XtreamCodesClient(
        account.server_url, account.username, account.password, account.get_user_agent_string()
    ) as client:
        if kind == "movie":
            return client.get_vod_stream_url(str(media_id), extension)
        return client.get_episode_stream_url(str(media_id), extension)
