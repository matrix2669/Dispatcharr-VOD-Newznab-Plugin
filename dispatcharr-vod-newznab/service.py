import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


ROOT = Path(os.environ.get("DISPATCHARR_VOD_NEWZNAB_PLUGIN_DIR") or Path(__file__).resolve().parent)
STATE_DIR = Path(os.environ.get("DISPATCHARR_VOD_NEWZNAB_STATE_DIR") or "/data/dispatcharr_vod_newznab")
STATE_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = STATE_DIR / "servarr_service.log"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dispatcharr.settings")
os.environ["DISPATCHARR_VOD_NEWZNAB_STATE_DIR"] = str(STATE_DIR)


def _installed_version():
    try:
        payload = json.loads((ROOT / "plugin.json").read_text())
        return str(payload.get("version") or "").strip()
    except Exception:
        return ""


installed_version = _installed_version()
if installed_version:
    # The parent Dispatcharr worker may still have an older Plugin class loaded
    # immediately after an atomic plugin update. The child always trusts the
    # manifest currently installed on disk.
    os.environ["DISPATCHARR_VOD_NEWZNAB_RUNNING_VERSION"] = installed_version


def _configure_logging():
    """Give the detached service one predictable, bounded persistent log."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    logging.captureWarnings(True)
    logging.getLogger("django.db.backends").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


_configure_logging()
logger = logging.getLogger("dispatcharr_vod_newznab.service")
logger.info(
    "Starting embedded Newznab/SAB service version %s",
    os.environ.get("DISPATCHARR_VOD_NEWZNAB_RUNNING_VERSION", "unknown"),
)

try:
    import django
    django.setup()
except Exception:
    logger.exception("Django initialization failed")
    raise

_configure_logging()
logger = logging.getLogger("dispatcharr_vod_newznab.service")

try:
    from servarr_bridge.server import run_server
except Exception:
    logger.exception("Unable to import embedded server")
    raise


if __name__ == "__main__":
    try:
        run_server()
    except Exception:
        logger.exception("Embedded Newznab/SAB service terminated unexpectedly")
        raise
    finally:
        logger.info("Embedded Newznab/SAB service stopped")
