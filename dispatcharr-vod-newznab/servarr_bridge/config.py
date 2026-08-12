import os
import re
from pathlib import Path


PLUGIN_KEY = os.environ.get("DISPATCHARR_VOD_NEWZNAB_PLUGIN_KEY", "dispatcharr-vod-newznab-plugin")
PLUGIN_DIR = Path(os.environ.get("DISPATCHARR_VOD_NEWZNAB_PLUGIN_DIR") or Path(__file__).resolve().parents[1])

DEFAULTS = {
    "listen_host": "0.0.0.0",
    "listen_port": 9192,
    "api_key": "",
    "mustarrd_url": "http://mustarrd:4177",
    "mustarrd_username": "",
    "mustarrd_password": "",
    "mustarrd_account_id": 1,
    "servarr_completed_dir": "/completed",
    "sonarr_category": "sonarr",
    "radarr_category": "radarr",
    "movie_template": "mustarrd/Movies/{title} ({year}) {tmdb_tag}/{release}.{ext}",
    "tv_template": "mustarrd/TV Shows/{series} ({year}) {tmdb_tag}/Season {season:02d}/{release}.{ext}",
    "ffprobe_path": "ffprobe",
    "probe_timeout": 20,
    "catalog_cache_seconds": 300,
    "max_variants": 20,
    "respect_enabled_vod_groups": True,
}


def get_settings():
    from apps.plugins.models import PluginConfig
    cfg = PluginConfig.objects.get(key=PLUGIN_KEY)
    values = dict(DEFAULTS)
    values.update(cfg.settings or {})
    return values


def normalized_api_key(settings=None):
    settings = settings or get_settings()
    return str(settings.get("api_key") or "").strip()


def sanitize_component(value, fallback="Unknown"):
    text = str(value or "").strip()
    if not text:
        text = fallback
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text)
    text = re.sub(r"\s+", " ", text).strip(" .") or fallback
    encoded = text.encode("utf-8")
    if len(encoded) > 200:
        text = encoded[:200].decode("utf-8", errors="ignore").rstrip(" .") or fallback
    return text


def release_token(value):
    text = str(value or "Unknown")
    text = re.sub(r"[^A-Za-z0-9._+\-]+", ".", text)
    text = re.sub(r"\.{2,}", ".", text).strip(".")
    return text or "Unknown"


def tmdb_tag(tmdb_id):
    value = re.sub(r"\D", "", str(tmdb_id or ""))
    return f"{{tmdb-{value}}}" if value else ""


def _render_relative(template, context):
    rendered = str(template).format_map(context)
    rendered = rendered.replace("\\", "/")
    components = []
    for raw in rendered.split("/"):
        raw = re.sub(r"\s{2,}", " ", raw).strip()
        raw = re.sub(r"\s*\(\s*\)\s*", " ", raw).strip()
        if not raw or raw == ".":
            continue
        if raw == "..":
            raise ValueError("Template generated an unsafe parent path")
        components.append(sanitize_component(raw))
    if not components:
        raise ValueError("Template generated an empty output path")
    return "/".join(components)


def movie_output_path(settings, *, title, year, tmdb_id, release, extension):
    context = {
        "title": sanitize_component(title),
        "year": str(year or ""),
        "tmdb_id": str(tmdb_id or ""),
        "tmdb_tag": tmdb_tag(tmdb_id),
        "release": release_token(release),
        "ext": re.sub(r"[^A-Za-z0-9]", "", str(extension or "mkv")).lower() or "mkv",
    }
    return _render_relative(settings.get("movie_template") or DEFAULTS["movie_template"], context)


def tv_output_path(settings, *, series, year, tmdb_id, season, episode, release, extension):
    context = {
        "series": sanitize_component(series),
        "year": str(year or ""),
        "tmdb_id": str(tmdb_id or ""),
        "tmdb_tag": tmdb_tag(tmdb_id),
        "season": int(season or 0),
        "episode": int(episode or 0),
        "release": release_token(release),
        "ext": re.sub(r"[^A-Za-z0-9]", "", str(extension or "mkv")).lower() or "mkv",
    }
    return _render_relative(settings.get("tv_template") or DEFAULTS["tv_template"], context)
