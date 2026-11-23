"""Weekly numbers for the Summary tab."""
from __future__ import annotations

import datetime as dt

from .store import Store


def week_bounds(day: dt.date) -> tuple[dt.date, dt.date]:
    start = day - dt.timedelta(days=day.weekday())
    return start, start + dt.timedelta(days=6)


def _done_on_time(h: dict) -> bool:
    if not h.get("done_at"):
        return True  # ticked on an older version without a time: count as on time
    done_day = dt.datetime.fromisoformat(h["done_at"].replace("Z", "+00:00")).astimezone().date()
    return done_day <= dt.date.fromisoformat(h["due_date"])


def compute(store: Store, child_id: str, start: dt.date, end: dt.date, today: dt.date) -> dict:
    hw = store.homework_between(start.isoformat(), end.isoformat(), child_id)
    total = on_time = late = pending = upcoming = 0
    subjects: dict[str, dict] = {}
    for h in hw:
        s = subjects.setdefault(h["subject"], {"total": 0, "on_time": 0, "late": 0, "pending": 0})
        due = dt.date.fromisoformat(h["due_date"])
        if h["status"] == "pending":
            if due >= today:
                upcoming += 1      # not due yet: not counted as missed
                continue
            pending += 1
            s["pending"] += 1
        elif _done_on_time(h):
            on_time += 1
            s["on_time"] += 1
        else:
            late += 1
            s["late"] += 1
        total += 1
        s["total"] += 1
    weak = [name for name, s in subjects.items() if s["total"] and (s["late"] + s["pending"]) / s["total"] >= 0.4]
    return {
        "total": total, "on_time": on_time, "late": late, "pending": pending, "upcoming": upcoming,
        "pct": round(on_time / total * 100) if total else None,
        "subjects": dict(sorted(subjects.items())),
        "weak": weak,
    }
