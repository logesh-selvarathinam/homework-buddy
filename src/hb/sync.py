"""Keeps this phone's local copy and Supabase in step.

push: rows changed on this phone (dirty=1) and photos waiting to upload
pull: rows other phones changed since the last pull (by server updated_at)
"""
from __future__ import annotations

import os
import threading

import requests

from . import config
from .api import ApiError, Supabase
from .store import COLUMNS, SYNC_TABLES, Store

PAGE = 500


class Sync:
    def __init__(self, store: Store, api: Supabase):
        self.store = store
        self.api = api
        self._lock = threading.Lock()
        self.last_error: str | None = None

    # ---------------------------------------------------------------- family
    @property
    def family_id(self) -> str | None:
        return self.store.get("family_id")

    def create_family(self, family_name: str, display_name: str) -> str:
        res = self.api.rpc("create_family", {"family_name": family_name, "display_name": display_name})
        row = res[0] if isinstance(res, list) else res
        self._set_family(row["family_id"], family_name, row["join_code"], display_name)
        return row["join_code"]

    def join_family(self, code: str, display_name: str) -> None:
        fid = self.api.rpc("join_family", {"code": code.strip(), "display_name": display_name})
        fam = self.api.select("families", {"id": f"eq.{fid}", "select": "name,join_code"})
        self._set_family(fid, fam[0]["name"], fam[0]["join_code"], display_name)

    def _set_family(self, fid, name, code, display_name):
        self.store.set("family_id", fid)
        self.store.set("family_name", name)
        self.store.set("join_code", code)
        self.store.set("display_name", display_name)

    # ------------------------------------------------------------------ sync
    def sync(self) -> dict:
        """Push then pull. Safe to call often; returns counts."""
        if not self.family_id or not self.api.session:
            return {}
        if not self._lock.acquire(blocking=False):
            return {}  # a sync is already running
        try:
            pushed = self._push()
            self._upload_images()
            pulled = self._pull()
            self._pull_members()
            self.last_error = None
            return {"pushed": pushed, "pulled": pulled}
        except (ApiError, requests.RequestException) as e:
            self.last_error = str(e)
            raise
        finally:
            self._lock.release()

    def _push(self) -> int:
        n = 0
        for table in SYNC_TABLES:  # children first: homework/exams reference them
            rows = self.store.dirty_rows(table)
            if not rows:
                continue
            payload = []
            for r in rows:
                p = {c: r.get(c) for c in COLUMNS[table]}
                p["family_id"] = self.family_id
                # The server sets both timestamps. Dropping them from every row also
                # keeps all rows with the same keys, which Supabase needs for a batch.
                p.pop("created_at", None)
                p.pop("updated_at", None)
                payload.append(p)
            for i in range(0, len(payload), 100):
                saved = self.api.upsert(table, payload[i:i + 100])
                self.store.mark_clean(table, saved)
                n += len(saved)
        return n

    def _pull(self) -> int:
        n = 0
        for table in SYNC_TABLES:
            key = f"last_pull_{table}"
            since = self.store.get(key)
            while True:
                params = {
                    "select": "*",
                    "family_id": f"eq.{self.family_id}",
                    "order": "updated_at.asc",
                    "limit": str(PAGE),
                }
                if since:
                    params["updated_at"] = f"gt.{since}"
                rows = self.api.select(table, params)
                if not rows:
                    break
                n += self.store.apply_remote(table, rows)
                since = rows[-1]["updated_at"]
                self.store.set(key, since)
                if len(rows) < PAGE:
                    break
        return n

    def _pull_members(self) -> None:
        members = self.api.select("family_members", {
            "select": "user_id,display_name,joined_at",
            "family_id": f"eq.{self.family_id}",
            "order": "joined_at.asc",
        })
        self.store.set_members(members)

    # ---------------------------------------------------------------- images
    def _upload_images(self) -> None:
        for storage_path, local_file in self.store.pending_uploads():
            if not os.path.exists(local_file):
                self.store.upload_done(storage_path)
                continue
            with open(local_file, "rb") as f:
                self.api.upload(config.IMAGE_BUCKET, storage_path, f.read())
            self.store.upload_done(storage_path)

    def local_image(self, storage_path: str) -> str | None:
        """Path of the photo on this phone, downloading it the first time."""
        local = os.path.join(config.DATA_DIR, "images", storage_path)
        if os.path.exists(local):
            return local
        try:
            data = self.api.download(config.IMAGE_BUCKET, storage_path)
        except (ApiError, requests.RequestException):
            return None
        os.makedirs(os.path.dirname(local), exist_ok=True)
        with open(local, "wb") as f:
            f.write(data)
        return local
