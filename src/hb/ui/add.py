"""Add homework: paste a message / pick a photo / type → review → save."""
from __future__ import annotations

import asyncio
import datetime as dt
import re

import flet as ft

from .. import config, images, parser
from . import common as ui


def _option(icon, title, subtitle, on_click, bg, fg, big=False) -> ft.Container:
    return ft.Container(
        on_click=on_click, ink=True, border_radius=18, padding=16,
        bgcolor=ui.ACCENT_SOFT if big else ui.CARD,
        border=ft.Border.all(2 if big else 1, ui.ACCENT if big else ui.LINE),
        content=ft.Row(spacing=14, controls=[
            ft.Container(ft.Icon(icon, color=fg, size=24), bgcolor=bg, width=48, height=48,
                         border_radius=14, alignment=ft.Alignment.CENTER),
            ft.Column(expand=True, spacing=3, controls=[
                ft.Text(title, size=16, weight=ft.FontWeight.W_700),
                ft.Text(subtitle, size=12, color=ui.MUTED, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
            ]),
        ]),
    )


async def _pick_photos(app) -> list[tuple[str, str]]:
    """Let the user pick photos; returns [(storage_path, local_path)]."""
    files = await app.picker.pick_files(
        dialog_title="Choose diary photo or screenshot",
        file_type=ft.FilePickerFileType.IMAGE, allow_multiple=True, with_data=True)
    out = []
    for f in files or []:
        data = f.bytes
        if data is None and f.path:
            with open(f.path, "rb") as fh:
                data = fh.read()
        if data:
            out.append(await asyncio.to_thread(images.save_photo, app.sync.family_id, data))
    return out


def add_menu(app) -> ft.Control:
    async def paste(e):
        text = await app.clipboard.get()
        if not text or not text.strip():
            app.toast("Clipboard is empty. Long-press the message in WhatsApp → Copy, then try again.", True)
            return
        app.open(lambda st=_ReviewState(app, text, []): review_view(app, st))

    async def photo(e):
        photos = await _pick_photos(app)
        if photos:
            app.open(lambda st=_ReviewState(app, "", photos): review_view(app, st))

    def manual(e):
        app.open(lambda st=_ReviewState(app, "", []): review_view(app, st))

    return ft.Container(expand=True, bgcolor=ui.BG, content=ft.Column(spacing=0, expand=True, controls=[
        ui.back_bar("Add homework", lambda e: app.back()),
        ft.ListView(expand=True, padding=20, spacing=14, controls=[
            ft.Text("The app splits the teacher's message into one item per subject.", size=14, color=ui.MUTED),
            _option(ft.Icons.CONTENT_PASTE, "Paste message",
                    "Copy the message in WhatsApp or the school app first", paste, ui.ACCENT, "#FFFFFF", big=True),
            _option(ft.Icons.PHOTO_LIBRARY, "Diary photo or screenshot",
                    "Pick from the gallery – you type or paste the subjects", photo, "#FEF3C7", "#92400E"),
            _option(ft.Icons.EDIT_NOTE, "Type it myself", "Write the homework subject by subject",
                    manual, "#DCFCE7", "#166534"),
            ft.Container(
                padding=14, border_radius=16, bgcolor="#F0FDF4", border=ft.Border.all(1, "#86C99A"),
                content=ft.Text(
                    "Tip: in the WhatsApp group, long-press the homework message → Copy. "
                    "Open HomeworkBuddy → Add homework → Paste message.",
                    size=13, color="#14532D")),
        ]),
    ]))


class _ReviewState:
    """Everything on the review screen, kept between redraws."""

    def __init__(self, app, text: str, photos: list[tuple[str, str]]):
        self.text = text
        self.photos = photos
        self.items: list[dict] = []
        self.child_id: str | None = None
        self.auto_child = False
        self.due = parser.next_school_day(dt.date.today(), config.SCHOOL_DAYS)
        self.split(app)

    def split(self, app):
        result = parser.parse(self.text or "")
        self.items = [
            {"subject": i.subject, "task": i.task, "language_level": i.language_level,
             "pages": i.pages, "unit": i.unit, "book": i.book, "action": i.action,
             "repeat_note": i.repeat_note, "is_test": i.is_test, "needs_check": i.needs_check}
            for i in result.items
        ]
        kids = app.children()
        guess = parser.guess_child(result, kids)
        if guess:
            self.child_id, self.auto_child = guess, True
        elif len(kids) == 1:
            self.child_id = kids[0]["id"]
        if not self.items and not self.text.strip():
            self.items.append(_blank_item())


def _blank_item() -> dict:
    return {"subject": "", "task": "", "pages": [], "is_test": False}


_TEST_NAME = re.compile(r"(slip\s*test|unit\s*test|[a-d]\s*/\s*[a-d]\s*test|revision\s*test|exam)", re.I)


def review_view(app, st: _ReviewState) -> ft.Control:
    kids = app.children()
    child = app.child(st.child_id)
    subjects = sorted(set((child or {}).get("subjects") or []) | set(parser.KNOWN_SUBJECTS))

    raw = ui.field("Teacher's message", st.text, multiline=True, min_lines=3, max_lines=8)

    def on_raw(e):
        st.text = raw.value

    raw.on_change = on_raw

    def resplit(e):
        st.text = raw.value or ""
        st.split(app)
        app.refresh()

    def pick_child(cid):
        def h(e):
            st.child_id, st.auto_child = cid, False
            app.refresh()
        return h

    def pick_date(e):
        def changed(ev):
            if ev.control.value:
                st.due = ev.control.value.date() if isinstance(ev.control.value, dt.datetime) else ev.control.value
                app.refresh()
        app.page.show_dialog(ft.DatePicker(
            value=dt.datetime.combine(st.due, dt.time()), first_date=dt.datetime(2024, 1, 1),
            last_date=dt.datetime(2030, 12, 31), on_change=changed))

    async def add_photo(e):
        st.photos += await _pick_photos(app)
        app.refresh()

    def remove_photo(i):
        def h(e):
            st.photos.pop(i)
            app.refresh()
        return h

    def add_item(e):
        st.items.append(_blank_item())
        app.refresh()

    def item_card(i: int, it: dict) -> ft.Control:
        def set_subject(e):
            it["subject"] = e.control.value

        def set_task(e):
            it["task"] = e.control.value

        def set_test(e):
            it["is_test"] = e.control.value

        def remove(e):
            st.items.pop(i)
            app.refresh()

        opts = subjects if not it["subject"] or it["subject"] in subjects else subjects + [it["subject"]]
        tags = [ui.tag(t) for t in parser.ParsedItem(
            subject=it["subject"], task=it.get("task", ""), pages=it.get("pages") or [], unit=it.get("unit"),
            book=it.get("book"), action=it.get("action"), repeat_note=it.get("repeat_note")).tags]
        return ui.card(ft.Column(spacing=10, controls=[
            ft.Row([
                ft.Dropdown(value=it["subject"] or None, label="Subject", expand=True, dense=True,
                            options=[ft.DropdownOption(key=s, text=s) for s in opts],
                            on_select=set_subject, border_radius=10),
                ft.IconButton(ft.Icons.CLOSE, on_click=remove, tooltip="Remove this subject"),
            ]),
            ui.field("Homework", it.get("task", ""), multiline=True, min_lines=1, max_lines=4,
                     on_change=set_task),
            *([ft.Row(tags, spacing=6, wrap=True)] if tags else []),
            *([ft.Text("Page number looks missing – check the message", size=12, color=ui.ORANGE_FG)]
              if it.get("needs_check") else []),
            ft.Checkbox(label="This is a test / exam (also add to Exams)", value=bool(it.get("is_test")),
                        on_change=set_test),
        ]))

    def save(e):
        if not st.child_id:
            app.toast("Choose which child this is for", True)
            return
        items = [it for it in st.items if (it.get("subject") or "").strip()]
        if not items and not st.photos:
            app.toast("Add at least one subject or a photo", True)
            return
        if not items:  # photo only
            items = [{"subject": "Diary", "task": "See photo", "pages": []}]
        fam = app.sync.family_id
        for storage_path, local in st.photos:
            app.store.queue_upload(storage_path, local)
        paths = [p for p, _ in st.photos]
        for it in items:
            app.store.save("homework", {
                "family_id": fam, "child_id": st.child_id, "subject": it["subject"].strip(),
                "language_level": it.get("language_level"), "task": (it.get("task") or "").strip(),
                "pages": it.get("pages") or [], "unit": it.get("unit"), "book": it.get("book"),
                "action": it.get("action"), "repeat_note": it.get("repeat_note"),
                "is_test": bool(it.get("is_test")), "due_date": st.due.isoformat(), "status": "pending",
                "image_paths": paths, "source_text": st.text or None, "created_by": app.api.user_id,
            })
            if it.get("is_test"):
                m = _TEST_NAME.search(it.get("task") or "")
                app.store.save("exams", {
                    "family_id": fam, "child_id": st.child_id, "subject": it["subject"].strip(),
                    "title": m.group(1).strip().capitalize() if m else "Test",
                    "exam_date": st.due.isoformat(), "portions": it.get("task"),
                    "image_path": paths[0] if paths else None,
                })
        app.toast(f"Saved {len(items)} item{'s' if len(items) > 1 else ''} · syncing to all phones")
        app._stack.clear()
        app.go_tab(0)
        app.page.run_task(app.sync_now, False)

    photo_row = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=8, controls=[
        *[ft.Stack(width=84, height=84, controls=[
            ft.Container(ft.Image(src=_read(local), fit=ft.BoxFit.COVER, width=84, height=84),
                         border_radius=12, clip_behavior=ft.ClipBehavior.ANTI_ALIAS),
            ft.Container(ft.IconButton(ft.Icons.CLOSE, icon_size=14, icon_color="#FFFFFF",
                                       on_click=remove_photo(i), tooltip="Remove photo"),
                         right=0, top=0, bgcolor="#99000000", border_radius=999, width=32, height=32),
        ]) for i, (_, local) in enumerate(st.photos)],
        ft.Container(ft.Icon(ft.Icons.PHOTO_LIBRARY, color=ui.MUTED), width=84, height=84,
                     border_radius=12, border=ft.Border.all(1.5, "#B8BDCC"), alignment=ft.Alignment.CENTER,
                     on_click=add_photo, ink=True, tooltip="Add photo"),
    ])

    child_chips = ft.Row(wrap=True, spacing=8, controls=[
        ui.choice_chip(k["name"] + (f" · {k['class_name']}" if k.get("class_name") else ""),
                       k["id"] == st.child_id, pick_child(k["id"]), k.get("color") or ui.INK) for k in kids])

    return ft.Container(expand=True, bgcolor=ui.BG, content=ft.Column(spacing=0, expand=True, controls=[
        ui.back_bar("Check before saving", lambda e: app.back()),
        ft.ListView(expand=True, padding=ft.Padding.only(left=16, right=16, top=14, bottom=24), spacing=14,
                    controls=[
            ui.card(ft.Column(spacing=10, controls=[
                raw,
                ft.Row([ui.secondary_button("Split into subjects", resplit, icon=ft.Icons.REFRESH, expand=True)]),
            ])),
            ui.section_label("Photos"), photo_row,
            ui.section_label("For"), child_chips,
            *([ft.Text("✓ Picked automatically from the subjects in the message", size=12, color="#166534")]
              if st.auto_child and st.child_id else []),
            ui.section_label("Due"),
            ft.Row([ui.secondary_button(ui.nice_date(st.due.isoformat()) + " · " + st.due.strftime("%a %d %b"),
                                        pick_date, icon=ft.Icons.CALENDAR_MONTH)]),
            ui.section_label(f"Subjects · {len(st.items)}"),
            *[item_card(i, it) for i, it in enumerate(st.items)],
            ft.TextButton("+ Add another subject", on_click=add_item),
            ft.Row([ui.primary_button("Save · syncs to all phones", save, icon=ft.Icons.CHECK, expand=True)]),
        ]),
    ]))


def _read(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()
