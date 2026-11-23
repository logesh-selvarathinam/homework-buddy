"""Local SQLite copy of the family's data.

Every phone keeps a full copy, so the app opens and works without internet.
Rows changed on this phone are marked dirty=1 until sync.py pushes them.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid

# Server columns per table (local tables add a `dirty` flag).
COLUMNS: dict[str, list[str]] = {
    "children": ["id", "family_id", "name", "class_name", "color", "subjects",
                 "deleted", "created_at", "updated_at"],
    "homework": ["id", "family_id", "child_id", "subject", "language_level", "task",
                 "pages", "unit", "book", "action", "repeat_note", "is_test",
                 "due_date", "status", "done_at", "image_paths", "source_text",
                 "created_by", "deleted", "created_at", "updated_at"],
    "exams": ["id", "family_id", "child_id", "subject", "title", "exam_date",
              "portions", "image_path", "deleted", "created_at", "updated_at"],
}
ARRAY_COLS = {"subjects", "pages", "image_paths"}
BOOL_COLS = {"deleted", "is_test"}
SYNC_TABLES = ["children", "homework", "exams"]


def new_id() -> str:
    return str(uuid.uuid4())


class Store:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        self._lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._migrate()

    # ------------------------------------------------------------------ setup
    def _migrate(self):
        with self._lock, self.db:
            for table, cols in COLUMNS.items():
                defs = ", ".join(f"{c} TEXT" if c != "id" else "id TEXT PRIMARY KEY" for c in cols)
                self.db.execute(f"CREATE TABLE IF NOT EXISTS {table} ({defs}, dirty INTEGER DEFAULT 0)")
            self.db.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS uploads (storage_path TEXT PRIMARY KEY, local_file TEXT)")
            self.db.execute("CREATE TABLE IF NOT EXISTS members (user_id TEXT PRIMARY KEY, display_name TEXT, joined_at TEXT)")

    # ------------------------------------------------------------------- meta
    def get(self, key: str, default=None):
        with self._lock:
            r = self.db.execute("SELECT v FROM meta WHERE k=?", (key,)).fetchone()
        return json.loads(r["v"]) if r else default

    def set(self, key: str, value) -> None:
        with self._lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO meta (k, v) VALUES (?, ?)", (key, json.dumps(value)))

    def delete_meta(self, key: str) -> None:
        with self._lock, self.db:
            self.db.execute("DELETE FROM meta WHERE k=?", (key,))

    def reset_family_data(self) -> None:
        """Used when signing out: clear all local data on this phone."""
        with self._lock, self.db:
            for t in [*SYNC_TABLES, "meta", "uploads", "members"]:
                self.db.execute(f"DELETE FROM {t}")

    # ------------------------------------------------------------- conversion
    @staticmethod
    def _to_db(table: str, row: dict) -> dict:
        out = {}
        for c in COLUMNS[table]:
            v = row.get(c)
            if c in ARRAY_COLS:
                v = json.dumps(v or [], ensure_ascii=False)
            elif c in BOOL_COLS:
                v = "1" if v else "0"
            out[c] = v
        return out

    @staticmethod
    def _from_db(table: str, r: sqlite3.Row) -> dict:
        d = {}
        for c in COLUMNS[table]:
            v = r[c]
            if c in ARRAY_COLS:
                v = json.loads(v) if v else []
            elif c in BOOL_COLS:
                v = v == "1"
            d[c] = v
        d["dirty"] = bool(r["dirty"])
        return d

    # ------------------------------------------------------------ write/read
    def save(self, table: str, row: dict, dirty: bool = True) -> dict:
        """Insert or update a row changed on this phone."""
        row = dict(row)
        row.setdefault("id", new_id())
        row.setdefault("deleted", False)
        data = self._to_db(table, row)
        cols = list(data) + ["dirty"]
        with self._lock, self.db:
            self.db.execute(
                f"INSERT OR REPLACE INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                [*data.values(), 1 if dirty else 0],
            )
        return row

    def update(self, table: str, row_id: str, **changes) -> dict | None:
        row = self.get_row(table, row_id)
        if not row:
            return None
        row.update(changes)
        return self.save(table, row)

    def get_row(self, table: str, row_id: str) -> dict | None:
        with self._lock:
            r = self.db.execute(f"SELECT * FROM {table} WHERE id=?", (row_id,)).fetchone()
        return self._from_db(table, r) if r else None

    def rows(self, table: str, where: str = "1=1", params=(), order: str = "") -> list[dict]:
        sql = f"SELECT * FROM {table} WHERE deleted='0' AND ({where})"
        if order:
            sql += f" ORDER BY {order}"
        with self._lock:
            return [self._from_db(table, r) for r in self.db.execute(sql, params).fetchall()]

    # ---------------------------------------------------------- convenience
    def children(self) -> list[dict]:
        return self.rows("children", order="created_at, name")

    def homework_due(self, due_date: str, child_id: str | None = None) -> list[dict]:
        if child_id:
            return self.rows("homework", "due_date=? AND child_id=?", (due_date, child_id), "created_at")
        return self.rows("homework", "due_date=?", (due_date,), "child_id, created_at")

    def homework_overdue(self, today: str, child_id: str | None = None) -> list[dict]:
        where, params = "due_date<? AND status='pending'", [today]
        if child_id:
            where += " AND child_id=?"
            params.append(child_id)
        return self.rows("homework", where, params, "due_date")

    def homework_between(self, start: str, end: str, child_id: str | None = None) -> list[dict]:
        where, params = "due_date>=? AND due_date<=?", [start, end]
        if child_id:
            where += " AND child_id=?"
            params.append(child_id)
        return self.rows("homework", where, params, "due_date")

    def upcoming_dates(self, today: str, limit: int = 7) -> list[str]:
        with self._lock:
            rs = self.db.execute(
                "SELECT DISTINCT due_date FROM homework WHERE deleted='0' AND due_date>=? ORDER BY due_date LIMIT ?",
                (today, limit)).fetchall()
        return [r["due_date"] for r in rs]

    def exams(self) -> list[dict]:
        return self.rows("exams", order="exam_date IS NULL, exam_date")

    # ----------------------------------------------------------------- sync
    def dirty_rows(self, table: str) -> list[dict]:
        with self._lock:
            rs = self.db.execute(f"SELECT * FROM {table} WHERE dirty=1").fetchall()
        return [self._from_db(table, r) for r in rs]

    def mark_clean(self, table: str, server_rows: list[dict]) -> None:
        for r in server_rows:
            self.apply_remote(table, [r], force=True)

    def apply_remote(self, table: str, server_rows: list[dict], force: bool = False) -> int:
        """Store rows pulled from the server. A row this phone changed but has
        not pushed yet is kept (it will be pushed next)."""
        n = 0
        for r in server_rows:
            if not force:
                local = self.get_row(table, r["id"])
                if local and local["dirty"]:
                    continue
            self.save(table, r, dirty=False)
            n += 1
        return n

    def set_members(self, members: list[dict]) -> None:
        with self._lock, self.db:
            self.db.execute("DELETE FROM members")
            for m in members:
                self.db.execute("INSERT INTO members VALUES (?, ?, ?)",
                                (m["user_id"], m["display_name"], m.get("joined_at")))

    def members(self) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM members ORDER BY joined_at")]

    # --------------------------------------------------------------- images
    def queue_upload(self, storage_path: str, local_file: str) -> None:
        with self._lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO uploads VALUES (?, ?)", (storage_path, local_file))

    def pending_uploads(self) -> list[tuple[str, str]]:
        with self._lock:
            return [(r["storage_path"], r["local_file"]) for r in self.db.execute("SELECT * FROM uploads")]

    def upload_done(self, storage_path: str) -> None:
        with self._lock, self.db:
            self.db.execute("DELETE FROM uploads WHERE storage_path=?", (storage_path,))
