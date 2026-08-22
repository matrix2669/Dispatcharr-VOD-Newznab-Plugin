"""Mustarrd client used by Arr Stack Connector."""

import threading

import requests


class MustarrdClient:
    def __init__(self, settings):
        self.base_url = str(settings.get("mustarrd_url") or "").rstrip("/")
        self.username = str(settings.get("mustarrd_username") or "")
        self.password = str(settings.get("mustarrd_password") or "")
        self.account_id = int(settings.get("mustarrd_account_id") or 1)
        self.session = requests.Session()
        self.csrf_token = None
        self._authenticated = False
        # requests.Session mutates cookies and is not guaranteed thread-safe.
        # Radarr/Sonarr can poll queue/history concurrently, so serialize the
        # shared session as well as authentication refreshes.
        self._lock = threading.RLock()

    def _login_locked(self):
        if not self.base_url or not self.username or not self.password:
            raise RuntimeError("Mustarrd URL/username/password are not configured")

        csrf = self.session.get(f"{self.base_url}/api/auth/csrf", timeout=10)
        csrf.raise_for_status()
        token = csrf.json()["csrf_token"]
        response = self.session.post(
            f"{self.base_url}/api/auth/login-credentials",
            json={"username": self.username, "password": self.password},
            headers={"x-csrf-token": token},
            timeout=10,
        )
        response.raise_for_status()
        self.csrf_token = token
        self._authenticated = True
        return response.json()

    def login(self):
        with self._lock:
            return self._login_locked()

    def _request(self, method, path, *, json=None, retry_auth=True):
        with self._lock:
            if not self._authenticated:
                self._login_locked()

            headers = {}
            if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
                headers["x-csrf-token"] = self.csrf_token

            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                json=json,
                headers=headers,
                timeout=30,
            )

            if retry_auth and response.status_code in {401, 403}:
                self._authenticated = False
                self.csrf_token = None
                self._login_locked()
                headers = {}
                if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
                    headers["x-csrf-token"] = self.csrf_token
                response = self.session.request(
                    method,
                    f"{self.base_url}{path}",
                    json=json,
                    headers=headers,
                    timeout=30,
                )

            response.raise_for_status()
            if not response.content:
                return {}
            return response.json()

    def close(self):
        with self._lock:
            self.session.close()
            self._authenticated = False
            self.csrf_token = None

    def create_external(self, *, media_id, title, source_url, relative_output_path, duration_minutes=0):
        return self._request(
            "POST",
            "/api/vod/external/download",
            json={
                "account_id": self.account_id,
                "media_id": str(media_id),
                "title": title,
                "source_url": source_url,
                "relative_output_path": relative_output_path,
                "duration_minutes": int(duration_minutes or 0),
            },
        )

    def queue(self):
        return self._request("GET", "/api/downloads/queue")

    def history(self):
        return self._request("GET", "/api/downloads/history")

    def get(self, download_id):
        return self._request("GET", f"/api/downloads/{int(download_id)}")

    def delete(self, download_id):
        return self._request("DELETE", f"/api/downloads/{int(download_id)}")

    def retry(self, download_id):
        return self._request("POST", f"/api/downloads/{int(download_id)}/retry")


_SHARED_LOCK = threading.RLock()
_SHARED_CLIENT = None
_SHARED_KEY = None


def _client_key(settings):
    return (
        str(settings.get("mustarrd_url") or "").rstrip("/"),
        str(settings.get("mustarrd_username") or ""),
        str(settings.get("mustarrd_password") or ""),
        int(settings.get("mustarrd_account_id") or 1),
    )


def shared_client(settings):
    """Return one authenticated Mustarrd client for this service process.

    Servarr polls queue and history frequently. Recreating a client for every
    request causes a fresh credential login each time and trips Mustarrd's login
    rate limit. The cached client keeps its authenticated cookie/CSRF state until
    Mustarrd actually returns 401/403 or the configured connection settings change.
    """
    global _SHARED_CLIENT, _SHARED_KEY

    key = _client_key(settings)
    with _SHARED_LOCK:
        if _SHARED_CLIENT is None or _SHARED_KEY != key:
            if _SHARED_CLIENT is not None:
                _SHARED_CLIENT.close()
            _SHARED_CLIENT = MustarrdClient(settings)
            _SHARED_KEY = key
        return _SHARED_CLIENT
