import fcntl
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
    version = "0.1.1"
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

    @staticmethod
    def _child_pythonpath():
        """Preserve Dispatcharr's import path in the standalone service child.

        Executing service.py directly makes Python use the plugin directory as
        sys.path[0]. Dispatcharr itself is normally imported from an application
        path injected by the parent process, so copy the parent's import search
        path into PYTHONPATH before launching the child.
        """
        entries = []
        for value in list(sys.path) + [os.environ.get("PYTHONPATH", "")]:
            for entry in str(value or "").split(os.pathsep):
                entry = entry.strip()
                if not entry:
                    # Empty sys.path entries mean the parent's current working
                    # directory; materialize it because the child has a script
                    # directory as sys.path[0].
                    entry = os.getcwd()
                if entry not in entries:
                    entries.append(entry)
        return os.pathsep.join(entries)

    @staticmethod
    def _tail_log(max_bytes=8192):
        try:
            with LOG_FILE.open("rb") as fh:
                fh.seek(0, os.SEEK_END)
                size = fh.tell()
                fh.seek(max(0, size - max_bytes), os.SEEK_SET)
                return fh.read().decode("utf-8", errors="replace").strip()
        except Exception:
            return ""

    def _service_settings(self):
        cfg = self._config()
        settings = dict(cfg.settings or {})
        host = str(settings.get("listen_host") or "0.0.0.0")
        port = int(settings.get("listen_port") or 9192)
        probe_host = "127.0.0.1" if host in {"0.0.0.0", "::", ""} else host
        return host, port, probe_host

    @staticmethod
    def _health_ok(host, port, timeout=0.5):
        try:
            with urlopen(f"http://{host}:{port}/health", timeout=timeout) as response:
                return response.status == 200
        except Exception:
            return False

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
            env["PYTHONPATH"] = self._child_pythonpath()

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

            # Do not report a successful start until the child either serves
            # /health or proves it has exited. This catches missing imports and
            # bind failures immediately instead of leaving a stale PID file.
            _, port, probe_host = self._service_settings()
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    PID_FILE.unlink(missing_ok=True)
                    detail = self._tail_log()
                    raise RuntimeError(
                        f"Embedded Newznab/SAB service exited with code {process.returncode}"
                        + (f":\n{detail}" if detail else "")
                    )
                if self._health_ok(probe_host, port):
                    return process.pid
                time.sleep(0.1)

            if process.poll() is None:
                # The service may still be initializing its Django imports. Keep
                # the live PID and let Service Status report 'starting'.
                return process.pid

            PID_FILE.unlink(missing_ok=True)
            detail = self._tail_log()
            raise RuntimeError(
                f"Embedded Newznab/SAB service failed to start"
                + (f":\n{detail}" if detail else "")
            )

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
        healthy = self._health_ok(probe_host, port, timeout=2) if running else False
        result = {
            "status": "ok" if healthy else ("starting" if running else "stopped"),
            "pid": pid if running else None,
            "listen": f"{host}:{port}",
            "newznab_path": "/api",
            "sab_path": "/api",
            "api_key": settings.get("api_key") or "",
            "log_file": str(LOG_FILE),
        }
        if not healthy:
            tail = self._tail_log(4096)
            if tail:
                result["log_tail"] = tail
        return result

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
