"""Plans the phone's local reminders from the homework and exams on it.

Re-planned after every sync, so a change on another phone updates the
reminders here too (once this phone has synced).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from . import config
from .store import Store


@dataclass
class Reminder:
    id: int
    when: dt.datetime
    title: str
    body: str


def _day_name(d: dt.date) -> str:
    return d.strftime("%a %d %b")


def plan(store: Store, now: dt.datetime, days_ahead: int = 7) -> list[Reminder]:
    out: list[Reminder] = []
    kids = {c["id"]: c["name"] for c in store.children()}
    today = now.date()

    # Homework: the evening before it is due
    for i in range(0, days_ahead + 1):
        due = today + dt.timedelta(days=i)
        pending = [h for h in store.homework_due(due.isoformat()) if h["status"] == "pending"]
        if not pending:
            continue
        when = dt.datetime.combine(due - dt.timedelta(days=1), dt.time(config.EVENING_REMINDER_HOUR))
        if when <= now:
            continue
        per_kid: dict[str, list[str]] = {}
        for h in pending:
            per_kid.setdefault(kids.get(h["child_id"], "Child"), []).append(h["subject"])
        body = " · ".join(f"{k}: {', '.join(v)}" for k, v in per_kid.items())
        out.append(Reminder(
            id=int(due.strftime("1%y%m%d")),
            when=when,
            title=f"{len(pending)} homework pending for tomorrow",
            body=body,
        ))

    # Exams: 2 days before and the evening before
    for n, ex in enumerate(store.exams()):
        if not ex.get("exam_date"):
            continue
        day = dt.date.fromisoformat(ex["exam_date"])
        for before, label in ((2, "in 2 days"), (1, "tomorrow")):
            when = dt.datetime.combine(day - dt.timedelta(days=before), dt.time(config.EVENING_REMINDER_HOUR))
            if when <= now:
                continue
            out.append(Reminder(
                id=int(day.strftime("%y%m%d")) * 100 + (n % 49) * 2 + before,
                when=when,
                title=f"{ex['subject']} {ex['title']} {label}",
                body=f"{kids.get(ex['child_id'], 'Child')} · {ex.get('portions') or _day_name(day)}",
            ))
    # unique ids
    seen, uniq = set(), []
    for r in out:
        while r.id in seen:
            r.id += 1
        seen.add(r.id)
        uniq.append(r)
    return uniq


async def apply(notifications, store: Store) -> int:
    """Replace this phone's scheduled reminders. Returns how many were set."""
    reminders = plan(store, dt.datetime.now())
    await notifications.cancel_all_pending()
    for r in reminders:
        await notifications.schedule(r.id, when=r.when, title=r.title, body=r.body, payload="home")
    return len(reminders)
