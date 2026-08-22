import os
import re
import secrets
from pathlib import Path


PLUGIN_KEY = os.environ.get("ARR_STACK_CONNECTOR_PLUGIN_KEY", "arr_stack_connector")
PLUGIN_DIR = Path(os.environ.get("ARR_STACK_CONNECTOR_PLUGIN_DIR") or Path(__file__).resolve().parents[1])
STATE_DIR = Path(os.environ.get("ARR_STACK_CONNECTOR_STATE_DIR") or "/data/arr_stack_connector")

DEFAULTS = {
    "listen_host": "0.0.0.0",
    "listen_port": 9192,
    "api_key": "",
    "dispatcharr_url": "",
    "mustarrd_url": "http://mustarrd:4177",
    "mustarrd_username": "",
    "mustarrd_password": "",
    "mustarrd_account_id": 1,
    "servarr_completed_dir": "/completed",
    "sonarr_category": "sonarr",
    "radarr_category": "radarr",
    "ffprobe_path": "/usr/bin/ffprobe",
    "probe_timeout": 20,
    "catalog_cache_seconds": 300,
    "max_variants": 20,
    "respect_enabled_vod_groups": True,
}


def _new_api_key():
    """Return a cryptographically strong URL-safe API key."""
    return secrets.token_urlsafe(32)


def _settings_with_api_key(cfg):
    """Return persisted plugin settings, generating an API key only if blank."""
    current = dict(cfg.settings or {})
    if str(current.get("api_key") or "").strip():
        return current

    from django.db import transaction
    from apps.plugins.models import PluginConfig

    with transaction.atomic():
        locked = PluginConfig.objects.select_for_update().get(pk=cfg.pk)
        current = dict(locked.settings or {})
        if str(current.get("api_key") or "").strip():
            return current

        current["api_key"] = _new_api_key()
        locked.settings = current
        locked.save(update_fields=["settings", "updated_at"])
        return current


def get_settings():
    from apps.plugins.models import PluginConfig

    cfg = PluginConfig.objects.get(key=PLUGIN_KEY)
    persisted = _settings_with_api_key(cfg)

    values = dict(DEFAULTS)
    values.update(persisted)
    if not str(values.get("ffprobe_path") or "").strip():
        values["ffprobe_path"] = DEFAULTS["ffprobe_path"]
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


def extension_token(value):
    return re.sub(r"[^A-Za-z0-9]", "", str(value or "mkv")).lower() or "mkv"


def sab_category_dir(category):
    return f"mustarrd/{sanitize_component(category, fallback='default')}"


def sab_output_path(category, release, extension):
    category_dir = sab_category_dir(category)
    release_name = release_token(release)
    ext = extension_token(extension)
    return f"{category_dir}/{release_name}/{release_name}.{ext}"


def infer_sab_state_from_output_path(output_path):
    text = str(output_path or "").strip().replace("\\", "/")
    if not text:
        return {}
    parts = [part for part in text.split("/") if part]
    marker = None
    for index in range(len(parts) - 1, -1, -1):
        if parts[index] == "mustarrd":
            marker = index
            break
    if marker is None or marker + 2 >= len(parts):
        return {}

    category = parts[marker + 1]
    release = parts[marker + 2]
    if not category or not release:
        return {}
    return {
        "category": category,
        "title": release,
        "relative_output_path": "/".join(parts[marker:]),
    }
