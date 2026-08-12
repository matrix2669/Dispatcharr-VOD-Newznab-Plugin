import fcntl
import logging
import os
import secrets
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen


PLUGIN_NAME = "Dispatcharr VOD Newznab"
ROOT = Path(__file__).resolve().parent
PLUGIN_KEY = ROOT.name.replace(" ", "_").lower()
PID_FILE = ROOT / ".servarr_service.pid"
LOCK_FILE = ROOT / ".servarr_service.lock"
LOG_FILE = ROOT / "servarr_service.log"
BOOTSTRAP_LOG_FILE = ROOT / "servarr_service_bootstrap.log"


class _PluginLogAdapter(logging.LoggerAdapter):
    """Prefix messages while retaining Dispatcharr's plugin logger namespace."""

    def process(self, msg, kwargs):
        return f"[{PLUGIN_NAME}] {msg}", kwargs


log = _PluginLogAdapter(logging.getLogger("apps.plugins.loader"), {})


class Plugin:
    name = PLUGIN_NAME
    version = "0.1.5"
    description = "Newznab + SABnzbd bridge for raw Dispatcharr VOD providers backed by Mustarrd."
    author = "matrix2669"

    fields = []  # plugin.json is authoritative
    actions = []

    def __init__(self):
        # The detached HTTP service initializes Django so it can use Dispatcharr's
        # ORM/models. If Dispatcharr's plugin autodiscovery is ever reached in that
        # child, never recursively start another copy of this service.
        if os.environ.get("DISPATCHARR_VOD_NEWZNAB_SERVICE", "").lower() in {"1", "true", "yes"}:
            return
        try:
            self._ensure_api_key()
            pid = self._ensure_service()
            log.info("Embedded Newznab/SAB service available (pid=%s)", pid)
        except Exception:
            log.exception("Unable to start embedded Newznab/SAB service")

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
            log.info("Generated Newznab/SAB API key")

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
        """Preserve Dispatcharr's import path in the standalone service child."""
        entries = []
        for value in list(sys.path) + [os.environ.get("PYTHONPATH", "")]:
            for entry in str(value or "").split(os.pathsep):
                entry = entry.strip()
                if not entry:
                    entry = os.getcwd()
                if entry not in entries:
                    entries.append(entry)
        return os.pathsep.join(entries)

    @staticmethod
    def _python_executable():
        """Return a real Python interpreter, never uWSGI's sys.executable.

        Dispatcharr runs the web app under uWSGI, where ``sys.executable`` may
        point at the uWSGI binary. Passing that to Popen makes uWSGI interpret
        service.py as a uWSGI configuration file instead of executing Python.
        Prefer Dispatcharr's configured virtualenv interpreter so Django and all
        installed dependencies are identical to the parent process.
        """
        candidates = [
            os.environ.get("DISPATCHARR_PYTHON"),
            "/dispatcharrpy/bin/python",
            str(Path(sys.prefix) / "bin" / "python"),
            shutil.which("python3"),
            shutil.which("python"),
        ]
        seen = set()
        for candidate in candidates:
            candidate = str(candidate or "").strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            try:
                path = Path(candidate)
                if path.is_file() and os.access(path, os.X_OK):
                    return str(path)
            except Exception:
                continue
        raise RuntimeError(
            "Could not find a Python interpreter for the embedded service "
            f"(parent sys.executable={sys.executable!r}, sys.prefix={sys.prefix!r})"
        )

    @staticmethod
    def _tail_file(path, max_bytes=8192):
        try:
            with Path(path).open("rb") as fh:
                fh.seek(0, os.SEEK_END)
                size = fh.tell()
                fh.seek(max(0, size - max_bytes), os.SEEK_SET)
                return fh.read().decode("utf-8", errors="replace").strip()
        except Exception:
            return ""

    @classmethod
    def _tail_log(cls, max_bytes=8192):
        main_tail = cls._tail_file(LOG_FILE, max_bytes=max_bytes)
        bootstrap_tail = cls._tail_file(BOOTSTRAP_LOG_FILE, max_bytes=max_bytes // 2)
        if main_tail and bootstrap_tail:
            return f"{main_tail}\n--- bootstrap ---\n{bootstrap_tail}"
        return main_tail or bootstrap_tail

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
                _, port, probe_host = self._service_settings()
                if self._health_ok(probe_host, port):
                    return pid
                log.warning("PID file references live pid=%s but service health check failed; restarting", pid)
                PID_FILE.unlink(missing_ok=True)

            env = os.environ.copy()
            env["DISPATCHARR_VOD_NEWZNAB_PLUGIN_KEY"] = PLUGIN_KEY
            env["DISPATCHARR_VOD_NEWZNAB_PLUGIN_DIR"] = str(ROOT)
            env["DISPATCHARR_VOD_NEWZNAB_SERVICE"] = "1"
            env["DISPATCHARR_SKIP_PLUGIN_AUTODISCOVERY"] = "1"
            env["PYTHONPATH"] = self._child_pythonpath()
            python_executable = self._python_executable()

            bootstrap_log = BOOTSTRAP_LOG_FILE.open("ab", buffering=0)
            try:
                process = subprocess.Popen(
                    [python_executable, str(ROOT / "service.py")],
                    cwd=os.getcwd(),
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=bootstrap_log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    close_fds=True,
                )
            finally:
                bootstrap_log.close()

            PID_FILE.write_text(str(process.pid))
            log.info("Started embedded service process pid=%s using %s", process.pid, python_executable)

            _, port, probe_host = self._service_settings()
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    PID_FILE.unlink(missing_ok=True)
                    detail = self._tail_log()
                    raise RuntimeError(
                        f"Embedded service exited with code {process.returncode}"
                        + (f":\n{detail}" if detail else "")
                    )
                if self._health_ok(probe_host, port):
                    log.info("Embedded service health check passed at %s:%s", probe_host, port)
                    return process.pid
                time.sleep(0.1)

            if process.poll() is None:
                log.warning(
                    "Embedded service pid=%s is still starting after 5 seconds; check %s",
                    process.pid,
                    LOG_FILE,
                )
                return process.pid

            PID_FILE.unlink(missing_ok=True)
            detail = self._tail_log()
            raise RuntimeError("Embedded service failed to start" + (f":\n{detail}" if detail else ""))

    def _stop_service(self):
        LOCK_FILE.touch(exist_ok=True)
        with LOCK_FILE.open("r+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            pid = self._read_pid()
            if not pid:
                return False
            if self._pid_alive(pid):
                log.info("Stopping embedded service pid=%s", pid)
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                deadline = time.monotonic() + 5
                while self._pid_alive(pid) and time.monotonic() < deadline:
                    time.sleep(0.1)
                if self._pid_alive(pid):
                    log.warning("Embedded service pid=%s did not stop cleanly; sending SIGKILL", pid)
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
            "bootstrap_log_file": str(BOOTSTRAP_LOG_FILE),
        }
        if not healthy:
            tail = self._tail_log(4096)
            if tail:
                result["log_tail"] = tail
        return result

    def run(self, action, params, context):
        settings = context.get("settings") or {}
        if action == "status":
            result = self._status(settings)
            log.info("Service status requested: %s", result.get("status"))
            return result
        if action == "restart":
            self._stop_service()
            pid = self._ensure_service()
            result = self._status(settings)
            result["pid"] = pid
            return result
        if action == "stop":
            self._stop_service()
            return {"status": "stopped"}
        log.warning("Unknown plugin action requested: %s", action)
        return {"status": "error", "message": f"Unknown action: {action}"}

    def stop(self, context=None):
        self._stop_service()
