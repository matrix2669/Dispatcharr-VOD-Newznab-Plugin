import os
import re
import secrets
from pathlib import Path


PLUGIN_KEY = os.environ.get("DISPATCHARR_VOD_NEWZNAB_PLUGIN_KEY", "dispatcharr-vod-newznab-plugin")
PLUGIN_DIR = Path(os.environ.get("DISPATCHARR_VOD_NEWZNAB_PLUGIN_DIR") or Path(__file__).resolve().parents[1])
STATE_DIR = Path(os.environ.get("DISPATCHARR_VOD_NEWZNAB_STATE_DIR") or "/data/dispatcharr_vod_newznab")

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
    """Return persisted plugin settings, generating an API key only if blank.

    The initial read avoids taking a row lock on every service request. If the
    key is blank, re-read under SELECT ... FOR UPDATE so concurrent plugin
    loaders or requests cannot race and persist different keys.
    """
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
    # v0.1.0 used the PATH-dependent literal "ffprobe" as its default. Treat
    # that exact legacy value (and blank values) as the old default so existing
    # installations automatically use Dispatcharr's system ffprobe location.
    if str(values.get("ffprobe_path") or "").strip() in {"", "ffprobe"}:
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
    """Relative completed-dir root exposed by the emulated SAB category."""
    return f"mustarrd/{sanitize_component(category, fallback='default')}"


def sab_output_path(category, release, extension):
    """Return SAB-style job/file layout for a Servarr grab.

    A real SAB category has its own completed directory and job folders enabled.
    Mirror that layout so Servarr sees:

      mustarrd/<category>/<release>/<release>.<ext>
    """
    category_dir = sab_category_dir(category)
    release_name = release_token(release)
    ext = extension_token(extension)
    return f"{category_dir}/{release_name}/{release_name}.{ext}"


def infer_sab_state_from_output_path(output_path):
    """Recover SAB metadata from a Mustarrd output path.

    External Servarr jobs always use:

      .../mustarrd/<category>/<release>/<release>.<ext>

    This makes queue/history self-healing if the small bridge state file is
    missing or was created by an older plugin version. Ordinary Mustarrd DVR
    recordings do not contain the ``mustarrd`` path component and are ignored.
    """
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
