import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


ROOT = Path(os.environ.get("DISPATCHARR_VOD_NEWZNAB_PLUGIN_DIR") or Path(__file__).resolve().parent)
LOG_FILE = ROOT / "servarr_service.log"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dispatcharr.settings")


def _configure_logging():
    """Give the detached service one predictable, bounded log destination."""
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

    # Keep request/library noise from drowning out search, SAB and provider logs.
    logging.getLogger("django.db.backends").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


_configure_logging()
logger = logging.getLogger("dispatcharr_vod_newznab.service")
logger.info("Starting embedded Newznab/SAB service")

try:
    import django
    django.setup()
except Exception:
    logger.exception("Django initialization failed")
    raise

# Django may apply its own LOGGING configuration during setup. Reassert the
# detached service's bounded file handler afterwards so all bridge modules and
# request failures consistently land in servarr_service.log.
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
