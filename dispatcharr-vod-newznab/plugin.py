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
PID_FILE = ROOT / ".servarr_service.pid"
LOCK_FILE = ROOT / ".servarr_service.lock"
LOG_FILE = ROOT / "servarr_service.log"
BOOTSTRAP_LOG_FILE = ROOT / "servarr_service_bootstrap.log"
SERVICE_SCRIPT = (ROOT / "service.py").resolve()


class _PluginLogAdapter(logging.LoggerAdapter):
    """Prefix messages while retaining Dispatcharr's plugin logger namespace."""

    def process(self, msg, kwargs):
        return f"[{PLUGIN_NAME}] {msg}", kwargs


log = _PluginLogAdapter(logging.getLogger("apps.plugins.loader"), {})


class Plugin:
    name = PLUGIN_NAME
    version = "0.1.7"
    description = "Newznab + SABnzbd bridge for raw Dispatcharr VOD providers backed by Mustarrd."
    author = "matrix2669"

    fields = []  # plugin.json is authoritative
    actions = []

    def __init__(self):
        if os.environ.get("DISPATCHARR_VOD_NEWZNAB_SERVICE", "").lower() in {"1", "true", "yes"}:
            return
        try:
            self._ensure_api_key()
            pid = self._ensure_service()
            log.info("Embedded Newznab/SAB service available (pid=%s, version=%s)", pid, self.version)
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
        pids = []
        try:
            proc_entries = Path("/proc").iterdir()
        except Exception:
            return pids
        for entry in proc_entries:
            if not entry.name.isdigit():
                continue
            try:
                pid = int(entry.name)
            except ValueError:
                continue
            if cls._process_is_ours(pid):
                pids.append(pid)
        return sorted(set(pids))

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
        """Return a real Python interpreter, never uWSGI's sys.executable."""
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
    def _service_health(host, port, timeout=0.5):
        try:
            with urlopen(f"http://{host}:{port}/health", timeout=timeout) as response:
                if response.status != 200:
                    return None
                payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict) or payload.get("status") != "ok":
                    return None
                return payload
        except Exception:
            return None

    @classmethod
    def _terminate_pid(cls, pid):
        if not cls._process_is_ours(pid):
            log.warning("Refusing to terminate pid=%s because it is not this plugin's service.py", pid)
            return False

        log.info("Stopping embedded service pid=%s", pid)
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return True

        deadline = time.monotonic() + 5.0
        while cls._pid_alive(pid) and time.monotonic() < deadline:
            time.sleep(0.1)

        if cls._pid_alive(pid):
            log.warning("Embedded service pid=%s did not stop cleanly; sending SIGKILL", pid)
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
        pid_file_value = self._read_pid()
        if pid_file_value and self._process_is_ours(pid_file_value):
            candidates.add(pid_file_value)
        try:
            health_pid = int((health or {}).get("pid"))
        except (TypeError, ValueError):
            health_pid = None
        if health_pid and self._process_is_ours(health_pid):
            candidates.add(health_pid)

        for pid in sorted(candidates):
            self._terminate_pid(pid)
        PID_FILE.unlink(missing_ok=True)
        return bool(candidates)

    def _ensure_service(self):
        LOCK_FILE.touch(exist_ok=True)
        with LOCK_FILE.open("r+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            _, port, probe_host = self._service_settings()
            health = self._service_health(probe_host, port)
            running_version = str((health or {}).get("version") or "")

            if health and running_version == self.version:
                try:
                    health_pid = int(health.get("pid"))
                except (TypeError, ValueError):
                    health_pid = None
                if health_pid and self._process_is_ours(health_pid):
                    PID_FILE.write_text(str(health_pid))
                    return health_pid
                own_pids = self._find_service_pids()
                if len(own_pids) == 1:
                    PID_FILE.write_text(str(own_pids[0]))
                    return own_pids[0]
                raise RuntimeError(
                    "Embedded service reports the current version but its process cannot be identified safely"
                )

            if health:
                log.info(
                    "Embedded service version mismatch: running=%s installed=%s; restarting",
                    running_version or "legacy/unknown",
                    self.version,
                )
                if not self._stop_known_service_processes(health):
                    raise RuntimeError(
                        "A service is listening on the configured port but its process cannot be identified safely"
                    )
            else:
                pid_file_value = self._read_pid()
                own_pids = self._find_service_pids()
                if pid_file_value and self._pid_alive(pid_file_value) and not self._process_is_ours(pid_file_value):
                    log.warning("Ignoring stale PID file referencing unrelated pid=%s", pid_file_value)
                    PID_FILE.unlink(missing_ok=True)
                if own_pids:
                    log.warning("Found unhealthy embedded service process(es) %s; restarting", own_pids)
                    self._stop_known_service_processes()

            env = os.environ.copy()
            env["DISPATCHARR_VOD_NEWZNAB_PLUGIN_KEY"] = PLUGIN_KEY
            env["DISPATCHARR_VOD_NEWZNAB_PLUGIN_DIR"] = str(ROOT)
            env["DISPATCHARR_VOD_NEWZNAB_SERVICE"] = "1"
            env["DISPATCHARR_VOD_NEWZNAB_RUNNING_VERSION"] = self.version
            env["DISPATCHARR_SKIP_PLUGIN_AUTODISCOVERY"] = "1"
            env["PYTHONPATH"] = self._child_pythonpath()
            python_executable = self._python_executable()

            bootstrap_log = BOOTSTRAP_LOG_FILE.open("ab", buffering=0)
            try:
                process = subprocess.Popen(
                    [python_executable, str(SERVICE_SCRIPT)],
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
                if health and str(health.get("version") or "") == self.version:
                    reported_pid = health.get("pid")
                    if str(reported_pid) != str(process.pid):
                        log.warning(
                            "Health endpoint reported pid=%s while newly started pid=%s",
                            reported_pid,
                            process.pid,
                        )
                    log.info(
                        "Embedded service health check passed at %s:%s version=%s",
                        probe_host,
                        port,
                        self.version,
                    )
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
            _, port, probe_host = self._service_settings()
            health = self._service_health(probe_host, port)
            return self._stop_known_service_processes(health)

    def _status(self, settings):
        pid = self._read_pid()
        host = str(settings.get("listen_host") or "0.0.0.0")
        port = int(settings.get("listen_port") or 9192)
        probe_host = "127.0.0.1" if host in {"0.0.0.0", "::", ""} else host
        health = self._service_health(probe_host, port, timeout=2)
        running_version = str((health or {}).get("version") or "")
        running = bool(health)
        healthy = bool(health and running_version == self.version)
        try:
            health_pid = int((health or {}).get("pid"))
        except (TypeError, ValueError):
            health_pid = None
        result = {
            "status": "ok" if healthy else ("stale" if running else "stopped"),
            "pid": health_pid or (pid if pid and self._process_is_ours(pid) else None),
            "listen": f"{host}:{port}",
            "installed_version": self.version,
            "running_version": running_version or None,
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
