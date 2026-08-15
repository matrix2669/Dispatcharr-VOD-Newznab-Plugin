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
PID_FILE = STATE_DIR / ".servarr_service.pid"
LOCK_FILE = STATE_DIR / ".servarr_service.lock"
LOG_FILE = STATE_DIR / "servarr_service.log"
BOOTSTRAP_LOG_FILE = STATE_DIR / "servarr_service_bootstrap.log"
SERVICE_SCRIPT = (ROOT / "service.py").resolve()


class _PluginLogAdapter(logging.LoggerAdapter):
    """Prefix messages while retaining Dispatcharr's plugin logger namespace."""

    def process(self, msg, kwargs):
        return f"[{PLUGIN_NAME}] {msg}", kwargs


log = _PluginLogAdapter(logging.getLogger("apps.plugins.loader"), {})


def _installed_version():
    try:
        payload = json.loads((ROOT / "plugin.json").read_text())
        return str(payload.get("version") or "").strip()
    except Exception:
        return ""


def _dispatcharr_app_roots():
    """Return import roots that contain Dispatcharr's ``dispatcharr`` package.

    Dispatcharr images have used more than one application root (notably
    ``/app`` and ``/opt/dispatcharr``). The detached service cannot rely on the
    parent's in-memory imports, so discover the real root while still inside the
    Dispatcharr process and pass it through PYTHONPATH.
    """
    candidates = []

    module = sys.modules.get("dispatcharr")
    module_file = getattr(module, "__file__", None) if module else None
    if module_file:
        try:
            candidates.append(Path(module_file).resolve().parent.parent)
        except (OSError, RuntimeError):
            pass

    try:
        candidates.append(Path.cwd())
    except OSError:
        pass

    for entry in sys.path:
        if entry:
            candidates.append(Path(entry))

    # Compatibility fallbacks for known Dispatcharr layouts. They are only
    # accepted when the expected settings module actually exists there.
    candidates.extend((Path("/app"), Path("/opt/dispatcharr")))

    roots = []
    seen = set()
    for candidate in candidates:
        try:
            path = candidate.resolve()
        except (OSError, RuntimeError):
            continue

        if path.name == "dispatcharr" and (path / "settings.py").is_file():
            path = path.parent
        if not (path / "dispatcharr" / "settings.py").is_file():
            continue

        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        roots.append(path)
    return roots


def _dedupe_path_entries(entries):
    output = []
    seen = set()
    for entry in entries:
        text = str(entry or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


class Plugin:
    name = PLUGIN_NAME
    version = "0.1.15"
    description = "Newznab + SABnzbd bridge for raw Dispatcharr VOD providers backed by Mustarrd."
    author = "matrix2669"

    fields = []  # plugin.json is authoritative
    actions = []

    def __init__(self):
        if os.environ.get("DISPATCHARR_VOD_NEWZNAB_SERVICE", "").lower() in {"1", "true", "yes"}:
            return
        try:
            self._ensure_service()
        except Exception:
            # Keep the plugin itself loaded so Status/Restart remain available
            # and Dispatcharr does not misrepresent a child-service failure as
            # missing plugin files.
            log.exception(
                "Detached Newznab/SAB service failed to start; plugin remains loaded for diagnostics"
            )

    def _desired_version(self):
        return _installed_version() or self.version

    def _interpreter(self):
        candidates = [
            os.environ.get("DISPATCHARR_PYTHON"),
            "/dispatcharrpy/bin/python",
            str(Path(sys.prefix) / "bin" / "python"),
            shutil.which("python3"),
            shutil.which("python"),
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return str(candidate)
        raise RuntimeError("Unable to locate Python interpreter for detached service")

    def _child_pythonpath(self):
        roots = [str(ROOT)]
        roots.extend(str(path) for path in _dispatcharr_app_roots())
        current = os.environ.get("PYTHONPATH")
        if current:
            roots.extend(current.split(os.pathsep))
        return os.pathsep.join(_dedupe_path_entries(roots))

    def _read_pid(self):
        try:
            return int(PID_FILE.read_text().strip())
        except Exception:
            return None

    def _pid_is_service(self, pid):
        if not pid or pid <= 1:
            return False
        try:
            cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
        except Exception:
            return False
        return str(SERVICE_SCRIPT) in cmdline

    def _discover_service_pid(self):
        for proc in Path("/proc").iterdir():
            if not proc.name.isdigit():
                continue
            pid = int(proc.name)
            if self._pid_is_service(pid):
                return pid
        return None

    def _service_pid(self):
        pid = self._read_pid()
        if self._pid_is_service(pid):
            return pid
        discovered = self._discover_service_pid()
        if discovered:
            try:
                PID_FILE.write_text(str(discovered))
            except Exception:
                pass
        return discovered

    def _health(self):
        try:
            with urlopen("http://127.0.0.1:9192/health", timeout=2) as response:
                if response.status != 200:
                    return None
                payload = json.loads(response.read().decode("utf-8"))
                return payload if isinstance(payload, dict) else None
        except Exception:
            return None

    def _stop_pid(self, pid):
        if not self._pid_is_service(pid):
            return
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        deadline = time.time() + 8
        while time.time() < deadline:
            if not self._pid_is_service(pid):
                return
            time.sleep(0.2)
        if self._pid_is_service(pid):
            os.kill(pid, signal.SIGKILL)

    def _stop_service(self):
        pid = self._service_pid()
        if pid:
            self._stop_pid(pid)
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass

    def _start_service(self):
        interpreter = self._interpreter()
        app_roots = _dispatcharr_app_roots()
        env = os.environ.copy()
        env["DISPATCHARR_VOD_NEWZNAB_PLUGIN_KEY"] = PLUGIN_KEY
        env["DISPATCHARR_VOD_NEWZNAB_PLUGIN_DIR"] = str(ROOT)
        env["DISPATCHARR_VOD_NEWZNAB_STATE_DIR"] = str(STATE_DIR)
        env["DISPATCHARR_VOD_NEWZNAB_SERVICE"] = "1"
        env["DISPATCHARR_SKIP_PLUGIN_AUTODISCOVERY"] = "1"
        env["DISPATCHARR_VOD_NEWZNAB_RUNNING_VERSION"] = self._desired_version()
        env["PYTHONPATH"] = self._child_pythonpath()
        if app_roots:
            env["DISPATCHARR_APP_ROOT"] = str(app_roots[0])

        with BOOTSTRAP_LOG_FILE.open("ab", buffering=0) as bootstrap:
            process = subprocess.Popen(
                [interpreter, str(SERVICE_SCRIPT)],
                cwd=str(ROOT),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=bootstrap,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
        PID_FILE.write_text(str(process.pid))
        return process.pid

    def _ensure_service(self):
        with LOCK_FILE.open("a+") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            desired_version = self._desired_version()
            pid = self._service_pid()
            health = self._health() if pid else None
            running_version = str((health or {}).get("version") or "")

            if pid and health and running_version == desired_version:
                return

            if pid:
                if health:
                    log.info(
                        "Replacing stale detached service pid=%s running=%s installed=%s",
                        pid,
                        running_version or "unknown",
                        desired_version,
                    )
                self._stop_pid(pid)
                PID_FILE.unlink(missing_ok=True)

            self._start_service()
            deadline = time.time() + 12
            while time.time() < deadline:
                health = self._health()
                if health and str(health.get("version") or "") == desired_version:
                    return
                time.sleep(0.25)
            raise RuntimeError("Detached Newznab/SAB service failed health check after startup")

    def run(self, action_id, params=None, context=None):
        if action_id == "status":
            health = self._health()
            return {
                "status": bool(health),
                "service": health or {},
                "pid": self._service_pid(),
                "installed_version": self._desired_version(),
                "dispatcharr_app_roots": [str(path) for path in _dispatcharr_app_roots()],
                "log_file": str(LOG_FILE),
                "bootstrap_log_file": str(BOOTSTRAP_LOG_FILE),
            }
        if action_id == "restart":
            self._stop_service()
            self._ensure_service()
            return {"status": True, "message": "Service restarted", "service": self._health() or {}}
        if action_id == "stop":
            self._stop_service()
            return {"status": True, "message": "Service stopped"}
        raise ValueError(f"Unknown action: {action_id}")

    def stop(self, context=None):
        self._stop_service()
