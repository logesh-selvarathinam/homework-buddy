"""Small Supabase client using plain HTTP (requests).

Plain requests keeps the APK small and avoids native dependencies.
"""
from __future__ import annotations

import time
from typing import Callable

import requests

TIMEOUT = 20


class ApiError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _error_message(resp: requests.Response) -> str:
    try:
        j = resp.json()
    except ValueError:
        return resp.text[:200] or f"HTTP {resp.status_code}"
    for key in ("msg", "message", "error_description", "error", "hint"):
        if isinstance(j, dict) and j.get(key):
            return str(j[key])
    return str(j)[:200]


class Supabase:
    def __init__(self, url: str, anon_key: str,
                 session: dict | None = None,
                 on_session: Callable[[dict | None], None] | None = None):
        self.url = url.rstrip("/")
        self.key = anon_key
        self.session = session          # {access_token, refresh_token, expires_at, user}
        self.on_session = on_session
        self.http = requests.Session()

    # ------------------------------------------------------------------ auth
    @property
    def user_id(self) -> str | None:
        return (self.session or {}).get("user", {}).get("id")

    @property
    def email(self) -> str | None:
        return (self.session or {}).get("user", {}).get("email")

    def _save_session(self, data: dict | None):
        if data and "access_token" in data:
            data = {
                "access_token": data["access_token"],
                "refresh_token": data["refresh_token"],
                "expires_at": data.get("expires_at") or int(time.time()) + int(data.get("expires_in", 3600)),
                "user": {"id": data["user"]["id"], "email": data["user"].get("email")},
            }
        self.session = data
        if self.on_session:
            self.on_session(data)

    def _auth_post(self, path: str, body: dict) -> dict:
        r = self.http.post(f"{self.url}/auth/v1/{path}", json=body,
                           headers={"apikey": self.key}, timeout=TIMEOUT)
        if r.status_code >= 400:
            raise ApiError(_error_message(r), r.status_code)
        return r.json()

    def sign_up(self, email: str, password: str) -> bool:
        """Returns True if signed in straight away, False if the email must
        be confirmed first (Supabase 'Confirm email' setting)."""
        data = self._auth_post("signup", {"email": email, "password": password})
        if data.get("access_token"):
            self._save_session(data)
            return True
        return False

    def sign_in(self, email: str, password: str) -> None:
        self._save_session(self._auth_post("token?grant_type=password",
                                           {"email": email, "password": password}))

    def refresh(self) -> None:
        if not self.session:
            raise ApiError("Not signed in", 401)
        try:
            data = self._auth_post("token?grant_type=refresh_token",
                                   {"refresh_token": self.session["refresh_token"]})
        except ApiError as e:
            if e.status in (400, 401):
                self._save_session(None)
            raise
        self._save_session(data)

    def sign_out(self) -> None:
        if self.session:
            try:
                self.http.post(f"{self.url}/auth/v1/logout", timeout=TIMEOUT,
                               headers=self._headers())
            except requests.RequestException:
                pass
        self._save_session(None)

    # --------------------------------------------------------------- request
    def _headers(self, extra: dict | None = None) -> dict:
        h = {"apikey": self.key}
        if self.session:
            h["Authorization"] = f"Bearer {self.session['access_token']}"
        if extra:
            h.update(extra)
        return h

    def _request(self, method: str, path: str, **kw) -> requests.Response:
        if self.session and self.session.get("expires_at", 0) - 60 < time.time():
            self.refresh()
        extra = kw.pop("headers", None)
        r = self.http.request(method, f"{self.url}{path}", headers=self._headers(extra),
                              timeout=TIMEOUT, **kw)
        if r.status_code == 401 and self.session:
            self.refresh()
            r = self.http.request(method, f"{self.url}{path}", headers=self._headers(extra),
                                  timeout=TIMEOUT, **kw)
        if r.status_code >= 400:
            raise ApiError(_error_message(r), r.status_code)
        return r

    # -------------------------------------------------------------- database
    def rpc(self, name: str, params: dict):
        return self._request("POST", f"/rest/v1/rpc/{name}", json=params).json()

    def select(self, table: str, params: dict) -> list[dict]:
        return self._request("GET", f"/rest/v1/{table}", params=params).json()

    def upsert(self, table: str, rows: list[dict]) -> list[dict]:
        if not rows:
            return []
        r = self._request("POST", f"/rest/v1/{table}", json=rows, params={"on_conflict": "id"},
                          headers={"Prefer": "resolution=merge-duplicates,return=representation"})
        return r.json()

    # --------------------------------------------------------------- storage
    def upload(self, bucket: str, path: str, data: bytes, content_type: str = "image/jpeg") -> None:
        try:
            self._request("POST", f"/storage/v1/object/{bucket}/{path}", data=data,
                          headers={"Content-Type": content_type})
        except ApiError as e:
            if e.status == 409 or "exists" in str(e).lower() or "duplicate" in str(e).lower():
                return  # uploaded before; file names are unique
            raise

    def download(self, bucket: str, path: str) -> bytes:
        return self._request("GET", f"/storage/v1/object/authenticated/{bucket}/{path}").content

    # ----------------------------------------------------------------- public
    def get_public_json(self, url: str) -> dict:
        r = self.http.get(url, timeout=TIMEOUT, params={"t": int(time.time())})
        if r.status_code >= 400:
            raise ApiError(_error_message(r), r.status_code)
        return r.json()
