import fcntl
import json
import logging
import os
import secrets
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen


log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent
PLUGIN_KEY = ROOT.name.replace(" ", "_").lower()
PID_FILE = ROOT / ".servarr_service.pid"
LOCK_FILE = ROOT / ".servarr_service.lock"
LOG_FILE = ROOT / "servarr_service.log"


class Plugin:
    name = "Dispatcharr VOD Newznab"
    version = "0.1.0"
    description = "Newznab + SABnzbd bridge for raw Dispatcharr VOD providers backed by Mustarrd."
    author = "matrix2669"

    fields = []  # plugin.json is authoritative
    actions = []

    def __init__(self):
        try:
            self._ensure_api_key()
            self._ensure_service()
        except Exception:
            log.exception("Unable to start Dispatcharr VOD Newznab service")

    @staticmethod
    def _config():
        from apps.plugins.models import PluginConfig
        return PluginConfig.objects.get(key=PLUGIN_KEY)

    def _ensure_api_key(self):
        cfg = self._config()
        settings = dict(cfg.settings or {})
        if not str(settings.get("api_key") or "").strip():
            settings["api_key"] = secrets.token_urlsafe(32)
            cfg.settings = settings
            cfg.save(update_fields=["settings", "updated_at"])

    @staticmethod
    def _pid_alive(pid):
        try:
            os.kill(int(pid), 0)
            return True
        except (OSError, TypeError, ValueError):
            return False

    @classmethod
    def _read_pid(cls):
        try:
            return int(PID_FILE.read_text().strip())
        except Exception:
            return None

    def _ensure_service(self):
        LOCK_FILE.touch(exist_ok=True)
        with LOCK_FILE.open("r+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            pid = self._read_pid()
            if pid and self._pid_alive(pid):
                return pid
            PID_FILE.unlink(missing_ok=True)

            env = os.environ.copy()
            env["DISPATCHARR_VOD_NEWZNAB_PLUGIN_KEY"] = PLUGIN_KEY
            env["DISPATCHARR_VOD_NEWZNAB_PLUGIN_DIR"] = str(ROOT)
            logfile = LOG_FILE.open("ab", buffering=0)
            try:
                process = subprocess.Popen(
                    [sys.executable, str(ROOT / "service.py")],
                    cwd=os.getcwd(),
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=logfile,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    close_fds=True,
                )
            finally:
                logfile.close()
            PID_FILE.write_text(str(process.pid))
            return process.pid

    def _stop_service(self):
        LOCK_FILE.touch(exist_ok=True)
        with LOCK_FILE.open("r+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            pid = self._read_pid()
            if not pid:
                return False
            if self._pid_alive(pid):
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                deadline = time.monotonic() + 5
                while self._pid_alive(pid) and time.monotonic() < deadline:
                    time.sleep(0.1)
                if self._pid_alive(pid):
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            PID_FILE.unlink(missing_ok=True)
            return True

    def _status(self, settings):
        pid = self._read_pid()
        running = bool(pid and self._pid_alive(pid))
        host = str(settings.get("listen_host") or "0.0.0.0")
        port = int(settings.get("listen_port") or 9192)
        probe_host = "127.0.0.1" if host in {"0.0.0.0", "::", ""} else host
        healthy = False
        if running:
            try:
                with urlopen(f"http://{probe_host}:{port}/health", timeout=2) as response:
                    healthy = response.status == 200
            except Exception:
                healthy = False
        return {
            "status": "ok" if healthy else ("starting" if running else "stopped"),
            "pid": pid if running else None,
            "listen": f"{host}:{port}",
            "newznab_path": "/api",
            "sab_path": "/api",
            "api_key": settings.get("api_key") or "",
            "log_file": str(LOG_FILE),
        }

    def run(self, action, params, context):
        settings = context.get("settings") or {}
        if action == "status":
            return self._status(settings)
        if action == "restart":
            self._stop_service()
            pid = self._ensure_service()
            result = self._status(settings)
            result["pid"] = pid
            return result
        if action == "stop":
            self._stop_service()
            return {"status": "stopped"}
        return {"status": "error", "message": f"Unknown action: {action}"}

    def stop(self, context=None):
        self._stop_service()
