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
        self._lock = threading.RLock()

    def login(self):
        if not self.base_url or not self.username or not self.password:
            raise RuntimeError("Mustarrd URL/username/password are not configured")
        with self._lock:
            csrf = self.session.get(f"{self.base_url}/api/auth/csrf", timeout=10)
            csrf.raise_for_status()
            self.csrf_token = csrf.json()["csrf_token"]
            response = self.session.post(
                f"{self.base_url}/api/auth/login-credentials",
                json={"username": self.username, "password": self.password},
                headers={"x-csrf-token": self.csrf_token},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()

    def _request(self, method, path, *, json=None, retry_auth=True):
        if not self.csrf_token:
            self.login()
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
            self.login()
            return self._request(method, path, json=json, retry_auth=False)
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()

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
