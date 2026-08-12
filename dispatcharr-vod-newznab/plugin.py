import fcntl
import json
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
STATE_DIR = Path(os.environ.get("DISPATCHARR_VOD_NEWZNAB_STATE_DIR") or "/data/dispatcharr_vod_newznab")
STATE_DIR.mkdir(parents=True, exist_ok=True)
PID_FILE = STATE_DIR / "servarr_service.pid"
LOCK_FILE = STATE_DIR / "servarr_service.lock"
LOG_FILE = STATE_DIR / "servarr_service.log"
BOOTSTRAP_LOG_FILE = STATE_DIR / "servarr_service_bootstrap.log"
SERVICE_SCRIPT = (ROOT / "service.py").resolve()


def _manifest_version():
    try:
        payload = json.loads((ROOT / "plugin.json").read_text())
        return str(payload.get("version") or "").strip()
    except Exception:
        return ""


class _PluginLogAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return f"[{PLUGIN_NAME}] {msg}", kwargs


log = _PluginLogAdapter(logging.getLogger("apps.plugins.loader"), {})


class Plugin:
    name = PLUGIN_NAME
    version = _manifest_version() or "0.1.11"
    description = "Newznab + SABnzbd bridge for raw Dispatcharr VOD providers backed by Mustarrd."
    author = "matrix2669"
    fields = []
    actions = []

    def __init__(self):
        if os.environ.get("DISPATCHARR_VOD_NEWZNAB_SERVICE", "").lower() in {"1", "true", "yes"}:
            return
        try:
            self._ensure_api_key()
            pid = self._ensure_service()
            log.info("Embedded Newznab/SAB service available (pid=%s, version=%s)", pid, self._desired_version())
        except Exception:
            log.exception("Unable to start embedded Newznab/SAB service")

    @staticmethod
    def _config():
        from apps.plugins.models import PluginConfig
        return PluginConfig.objects.get(key=PLUGIN_KEY)

    @classmethod
    def _desired_version(cls):
        # Read the installed manifest every time. Dispatcharr may still hold an
        # older Plugin class in memory immediately after an atomic plugin update.
        return _manifest_version() or cls.version

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
    def _cmdline(pid):
        try:
            raw = Path(f"/proc/{int(pid)}/cmdline").read_bytes()
            return [part.decode("utf-8", errors="replace") for part in raw.split(b"\x00") if part]
        except Exception:
            return []

    @classmethod
    def _process_is_ours(cls, pid):
        if not cls._pid_alive(pid):
            return False
        for arg in cls._cmdline(pid):
            try:
                if Path(arg).resolve() == SERVICE_SCRIPT:
                    return True
            except Exception:
                continue
        return False

    @classmethod
    def _find_service_pids(cls):
        result = []
        try:
            entries = Path("/proc").iterdir()
        except Exception:
            return result
        for entry in entries:
            if not entry.name.isdigit():
                continue
            pid = int(entry.name)
            if cls._process_is_ours(pid):
                result.append(pid)
        return sorted(set(result))

    @staticmethod
    def _child_pythonpath():
        entries = []
        for value in list(sys.path) + [os.environ.get("PYTHONPATH", "")]:
            for entry in str(value or "").split(os.pathsep):
                entry = entry.strip() or os.getcwd()
                if entry not in entries:
                    entries.append(entry)
        return os.pathsep.join(entries)

    @staticmethod
    def _python_executable():
        candidates = [
            os.environ.get("DISPATCHARR_PYTHON"),
            "/dispatcharrpy/bin/python",
            str(Path(sys.prefix) / "bin" / "python"),
            shutil.which("python3"),
            shutil.which("python"),
        ]
        for candidate in dict.fromkeys(str(v or "").strip() for v in candidates):
            if not candidate:
                continue
            path = Path(candidate)
            if path.is_file() and os.access(path, os.X_OK):
                return str(path)
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
        main = cls._tail_file(LOG_FILE, max_bytes)
        bootstrap = cls._tail_file(BOOTSTRAP_LOG_FILE, max_bytes // 2)
        if main and bootstrap:
            return f"{main}\n--- bootstrap ---\n{bootstrap}"
        return main or bootstrap

    def _service_settings(self):
        settings = dict(self._config().settings or {})
        host = str(settings.get("listen_host") or "0.0.0.0")
        port = int(settings.get("listen_port") or 9192)
        probe_host = "127.0.0.1" if host in {"0.0.0.0", "::", ""} else host
        return host, port, probe_host

    @staticmethod
    def _service_health(host, port, timeout=0.5):
        try:
            with urlopen(f"http://{host}:{port}/health", timeout=timeout) as response:
                if response.status != 200:
                    return None
                payload = json.loads(response.read().decode("utf-8"))
                if isinstance(payload, dict) and payload.get("status") == "ok":
                    return payload
        except Exception:
            pass
        return None

    @classmethod
    def _terminate_pid(cls, pid):
        if not cls._process_is_ours(pid):
            log.warning("Refusing to terminate pid=%s because it is not this plugin's service.py", pid)
            return False
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return True
        deadline = time.monotonic() + 5.0
        while cls._pid_alive(pid) and time.monotonic() < deadline:
            time.sleep(0.1)
        if cls._pid_alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            deadline = time.monotonic() + 2.0
            while cls._pid_alive(pid) and time.monotonic() < deadline:
                time.sleep(0.05)
        return not cls._pid_alive(pid)

    def _stop_known_service_processes(self, health=None):
        candidates = set(self._find_service_pids())
        pid = self._read_pid()
        if pid and self._process_is_ours(pid):
            candidates.add(pid)
        try:
            health_pid = int((health or {}).get("pid"))
        except (TypeError, ValueError):
            health_pid = None
        if health_pid and self._process_is_ours(health_pid):
            candidates.add(health_pid)
        for candidate in sorted(candidates):
            self._terminate_pid(candidate)
        PID_FILE.unlink(missing_ok=True)
        return bool(candidates)

    def _ensure_service(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        LOCK_FILE.touch(exist_ok=True)
        with LOCK_FILE.open("r+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            _, port, probe_host = self._service_settings()
            desired_version = self._desired_version()
            health = self._service_health(probe_host, port)
            running_version = str((health or {}).get("version") or "")

            if health and running_version == desired_version:
                try:
                    pid = int(health.get("pid"))
                except (TypeError, ValueError):
                    pid = None
                if pid and self._process_is_ours(pid):
                    PID_FILE.write_text(str(pid))
                    return pid

            if health:
                log.info(
                    "Embedded service version mismatch: running=%s installed=%s; restarting",
                    running_version or "legacy/unknown",
                    desired_version,
                )
                if not self._stop_known_service_processes(health):
                    raise RuntimeError("Service port is occupied by a process that cannot be identified safely")
            else:
                own_pids = self._find_service_pids()
                if own_pids:
                    self._stop_known_service_processes()

            env = os.environ.copy()
            env["DISPATCHARR_VOD_NEWZNAB_PLUGIN_KEY"] = PLUGIN_KEY
            env["DISPATCHARR_VOD_NEWZNAB_PLUGIN_DIR"] = str(ROOT)
            env["DISPATCHARR_VOD_NEWZNAB_STATE_DIR"] = str(STATE_DIR)
            env["DISPATCHARR_VOD_NEWZNAB_SERVICE"] = "1"
            env["DISPATCHARR_VOD_NEWZNAB_RUNNING_VERSION"] = desired_version
            env["DISPATCHARR_SKIP_PLUGIN_AUTODISCOVERY"] = "1"
            env["PYTHONPATH"] = self._child_pythonpath()

            bootstrap_log = BOOTSTRAP_LOG_FILE.open("ab", buffering=0)
            try:
                process = subprocess.Popen(
                    [self._python_executable(), str(SERVICE_SCRIPT)],
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
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    PID_FILE.unlink(missing_ok=True)
                    detail = self._tail_log()
                    raise RuntimeError(
                        f"Embedded service exited with code {process.returncode}"
                        + (f":\n{detail}" if detail else "")
                    )
                health = self._service_health(probe_host, port)
                if health and str(health.get("version") or "") == desired_version:
                    return process.pid
                time.sleep(0.1)
            if process.poll() is None:
                return process.pid
            raise RuntimeError("Embedded service failed to start")

    def _stop_service(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        LOCK_FILE.touch(exist_ok=True)
        with LOCK_FILE.open("r+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            _, port, probe_host = self._service_settings()
            return self._stop_known_service_processes(self._service_health(probe_host, port))

    def _status(self, settings):
        host = str(settings.get("listen_host") or "0.0.0.0")
        port = int(settings.get("listen_port") or 9192)
        probe_host = "127.0.0.1" if host in {"0.0.0.0", "::", ""} else host
        health = self._service_health(probe_host, port, timeout=2)
        desired_version = self._desired_version()
        running_version = str((health or {}).get("version") or "")
        return {
            "status": "ok" if health and running_version == desired_version else ("stale" if health else "stopped"),
            "pid": (health or {}).get("pid") or self._read_pid(),
            "listen": f"{host}:{port}",
            "installed_version": desired_version,
            "running_version": running_version or None,
            "newznab_path": "/api",
            "sab_path": "/api",
            "api_key": settings.get("api_key") or "",
            "state_dir": str(STATE_DIR),
            "log_file": str(LOG_FILE),
            "bootstrap_log_file": str(BOOTSTRAP_LOG_FILE),
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
