import logging
import os
import signal
import sys
from pathlib import Path

ROOT = Path(os.environ.get("DISPATCHARR_VOD_NEWZNAB_PLUGIN_DIR") or Path(__file__).resolve().parent)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dispatcharr.settings")

import django
django.setup()

from servarr_bridge.server import run_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

if __name__ == "__main__":
    run_server()
