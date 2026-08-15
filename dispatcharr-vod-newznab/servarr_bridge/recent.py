import email.utils
import logging
import re
import time

from .descriptors import encode_descriptor
from .releases import build_unprobed_episode_release, build_unprobed_movie_release


logger = logging.getLogger(__name__)


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _recency(value):
    if hasattr(value, "timestamp"):
        try:
            return int(value.timestamp())
        except Exception:
            return 0
    text = str(value or "").strip()
    if text.isdigit():
        return int(text)
    return 0


def _pubdate(value):
    ts = _recency(value) or int(time.time())
    return email.utils.formatdate(ts, usegmt=True)


def _tmdb(value):
    text = str(value or "").strip()
    match = re.search(r"(?:^|/)(\d+)(?:/?$)", text)
    return match.group(1) if match else ""


def _year(value):
    if isinstance(value, int) and 1900 <= value <= 2199:
        return value
    match = re.search(r"\b(19\d{2}|20\d{2}|21\d{2})\b", str(value or ""))
    return int(match.group(1)) if match else None


def _category_policy(account_ids, kind):
    """Return enabled VOD-category IDs for accounts that have category rules."""
    if not account_ids:
        return {}
    from apps.vod.models import M3UVODCategoryRelation

    policy = {}
    rows = M3UVODCategoryRelation.objects.filter(
        m3u_account_id__in=account_ids,
        category__category_type=kind,
    ).values_list("m3u_account_id", "category_id", "enabled")
    for account_id, category_id, enabled in rows:
        entry = policy.setdefault(int(account_id), set())
        if enabled:
            entry.add(int(category_id))
    return policy


def _category_allowed(policy, account_id, category_id):
    account_id = int(account_id)
    if account_id not in policy:
        return True
    return category_id is not None and int(category_id) in policy[account_id]


def _movie_result(account_id, stream_id, extension, title, year, tmdb_id, added, api_key):
    release = build_unprobed_movie_release(title, year)
    payload = {
        "version": 1,
        "kind": "movie",
        "dispatcharr_account_id": int(account_id),
        "media_id": str(stream_id),
        "container_extension": str(extension or "mp4").lstrip("."),
        "tmdb_id": str(tmdb_id or ""),
        "content_name": str(title or "Unknown"),
        "year": year,
        "release": release,
        "duration_minutes": 0,
    }
    token = encode_descriptor(payload, api_key)
    return {
        "title": release,
        "guid": f"dispatcharr-vod:movie:{account_id}:{stream_id}",
        "token": token,
        "pubdate": _pubdate(added),
        "category": "2000",
        "size": 0,
        "tmdb_id": str(tmdb_id or ""),
    }


def _episode_result(
    account_id,
    series_id,
    episode_id,
    extension,
    series_name,
    year,
    season,
    episode,
    tmdb_id,
    episode_title,
    added,
    api_key,
    duration_seconds=0,
):
    release = build_unprobed_episode_release(series_name, year, season, episode)
    payload = {
        "version": 1,
        "kind": "episode",
        "dispatcharr_account_id": int(account_id),
        "series_id": str(series_id or ""),
        "media_id": str(episode_id),
        "container_extension": str(extension or "mp4").lstrip("."),
        "tmdb_id": str(tmdb_id or ""),
        "content_name": str(series_name or "Unknown"),
        "year": year,
        "season": int(season),
        "episode": int(episode),
        "episode_title": str(episode_title or ""),
        "release": release,
        "duration_minutes": max(0, int(duration_seconds or 0) // 60),
    }
    token = encode_descriptor(payload, api_key)
    return {
        "title": release,
        "guid": f"dispatcharr-vod:episode:{account_id}:{episode_id}",
        "token": token,
        "pubdate": _pubdate(added),
        "category": "5000",
        "size": 0,
        "tmdb_id": str(tmdb_id or ""),
    }


def _local_movie_results(settings, result_limit):
    from apps.m3u.models import M3UAccount
    from apps.vod.models import M3UMovieRelation

    scan_limit = max(25, result_limit * 10)
    rows = list(
        M3UMovieRelation.objects.filter(
            m3u_account__is_active=True,
            m3u_account__account_type=M3UAccount.Types.XC,
        )
        .select_related("m3u_account", "movie", "category")
        .order_by("-last_seen", "-id")[:scan_limit]
    )
    policy = {}
    if settings.get("respect_enabled_vod_groups", True):
        policy = _category_policy({row.m3u_account_id for row in rows}, "movie")

    results = []
    for row in rows:
        if policy and not _category_allowed(policy, row.m3u_account_id, row.category_id):
            continue
        movie = row.movie
        results.append(
            _movie_result(
                row.m3u_account_id,
                row.stream_id,
                row.container_extension,
                movie.name,
                movie.year,
                movie.tmdb_id,
                row.last_seen,
                settings["api_key"],
            )
        )
        if len(results) >= result_limit:
            break
    return results


def _catalog_movie_results(settings, result_limit):
    """Fallback for providers whose movie relations are not materialized yet."""
    from .provider import _cached_catalog, active_xc_accounts

    candidates = []
    for account in active_xc_accounts():
        try:
            items = _cached_catalog(account, "movie", settings)
        except Exception:
            logger.exception("Unable to load movie catalog for recent feed account=%s", account.id)
            continue
        for item in items:
            stream_id = item.get("stream_id") or item.get("vod_id") or item.get("id")
            if stream_id is None:
                continue
            candidates.append((
                _recency(item.get("added") or item.get("last_modified")),
                account,
                item,
                str(stream_id),
            ))

    candidates.sort(key=lambda row: row[0], reverse=True)
    results = []
    for added, account, item, stream_id in candidates[: max(result_limit * 4, 20)]:
        title = item.get("name") or "Unknown"
        year = _year(item.get("year") or item.get("release_date") or title)
        tmdb_id = _tmdb(item.get("tmdb_id") or item.get("tmdb"))
        results.append(
            _movie_result(
                account.id,
                stream_id,
                item.get("container_extension") or "mp4",
                title,
                year,
                tmdb_id,
                added,
                settings["api_key"],
            )
        )
        if len(results) >= result_limit:
            break
    return results


def recent_movie_results(settings):
    """Return a fast real movie feed for Radarr validation/RSS polling.

    Prefer Dispatcharr's local provider relations so the request performs no
    Xtream catalog fetch, detail lookup, or ffprobe. If no local movie relation
    is available, fall back to the raw catalog only; still no per-title detail
    calls or media probes are performed.
    """
    started = time.monotonic()
    result_limit = min(5, max(1, int(settings.get("max_variants") or 20)))
    results = _local_movie_results(settings, result_limit)
    source = "local_relations"
    if not results:
        results = _catalog_movie_results(settings, result_limit)
        source = "provider_catalog"
    logger.info(
        "Built lightweight movie recent feed results=%s source=%s elapsed_ms=%s",
        len(results),
        source,
        int((time.monotonic() - started) * 1000),
    )
    return results


def _local_tv_results(settings, result_limit):
    from apps.m3u.models import M3UAccount
    from apps.vod.models import M3UEpisodeRelation

    scan_limit = max(25, result_limit * 10)
    rows = list(
        M3UEpisodeRelation.objects.filter(
            m3u_account__is_active=True,
            m3u_account__account_type=M3UAccount.Types.XC,
            episode__season_number__gte=0,
            episode__episode_number__gt=0,
        )
        .select_related(
            "m3u_account",
            "episode",
            "episode__series",
            "series_relation",
            "series_relation__category",
        )
        .order_by("-last_seen", "-id")[:scan_limit]
    )
    policy = {}
    if settings.get("respect_enabled_vod_groups", True):
        policy = _category_policy({row.m3u_account_id for row in rows}, "series")

    results = []
    for row in rows:
        category_id = row.series_relation.category_id if row.series_relation else None
        if policy and not _category_allowed(policy, row.m3u_account_id, category_id):
            continue
        episode = row.episode
        series = episode.series
        results.append(
            _episode_result(
                row.m3u_account_id,
                row.series_relation.external_series_id if row.series_relation else "",
                row.stream_id,
                row.container_extension,
                series.name,
                series.year,
                episode.season_number,
                episode.episode_number,
                series.tmdb_id,
                episode.name,
                row.last_seen,
                settings["api_key"],
                duration_seconds=episode.duration_secs or 0,
            )
        )
        if len(results) >= result_limit:
            break
    return results


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


def _provider_tv_fallback(settings):
    """Bounded fallback when Dispatcharr has no materialized episode relation."""
    from core.xtream_codes import Client as XtreamCodesClient
    from .provider import _cached_catalog, active_xc_accounts

    candidates = []
    for account in active_xc_accounts():
        try:
            items = _cached_catalog(account, "series", settings)
        except Exception:
            logger.exception("Unable to load series catalog for recent feed account=%s", account.id)
            continue
        for item in items:
            series_id = item.get("series_id") or item.get("stream_id") or item.get("id")
            if series_id is None:
                continue
            candidates.append((
                _recency(item.get("last_modified") or item.get("added")),
                account,
                item,
                str(series_id),
            ))
    candidates.sort(key=lambda row: row[0], reverse=True)

    # One real item is enough for Servarr validation. Keep this fallback tightly
    # bounded so an unqualified RSS request cannot turn into a provider crawl.
    for _, account, item, series_id in candidates[:3]:
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
            added, season, episode_number, episode_id, row = latest
            info = detail.get("info") if isinstance(detail, dict) else {}
            if not isinstance(info, dict):
                info = {}
            series_name = info.get("name") or item.get("name") or "Unknown"
            year = _year(
                info.get("release_date")
                or info.get("year")
                or item.get("release_date")
                or item.get("name")
            )
            tmdb_id = _tmdb(
                info.get("tmdb_id")
                or info.get("tmdb")
                or item.get("tmdb_id")
                or item.get("tmdb")
            )
            episode_info = row.get("info") if isinstance(row.get("info"), dict) else {}
            return [
                _episode_result(
                    account.id,
                    series_id,
                    episode_id,
                    row.get("container_extension") or "mp4",
                    series_name,
                    year,
                    season,
                    episode_number,
                    tmdb_id,
                    row.get("title") or episode_info.get("name") or "",
                    added or item.get("last_modified") or item.get("added"),
                    settings["api_key"],
                    duration_seconds=_int(episode_info.get("duration_secs"), 0),
                )
            ]
        except Exception:
            logger.exception(
                "Unable to build bounded TV fallback account=%s series_id=%s",
                account.id,
                series_id,
            )
    return []


def recent_tv_results(settings):
    """Return a fast real TV feed for Sonarr validation/RSS polling.

    Normal operation uses existing Dispatcharr episode relations and performs no
    provider calls or ffprobe. Only when no local relation exists do we perform
    a tightly bounded provider fallback (at most three series detail attempts),
    still without probing media.
    """
    started = time.monotonic()
    result_limit = min(5, max(1, int(settings.get("max_variants") or 20)))
    results = _local_tv_results(settings, result_limit)
    source = "local_relations"
    if not results:
        results = _provider_tv_fallback(settings)
        source = "bounded_provider_fallback"
    logger.info(
        "Built lightweight TV recent feed results=%s source=%s elapsed_ms=%s",
        len(results),
        source,
        int((time.monotonic() - started) * 1000),
    )
    return results
