"""One homework item: photos, status, edit, delete."""
from __future__ import annotations

import asyncio
import datetime as dt
import os

import flet as ft

from .. import config
from . import common as ui

_loading: set[str] = set()


def photo_control(app, storage_path: str, height: int = 260) -> ft.Control:
    """Shows a stored photo, downloading it in the background the first time."""
    local = os.path.join(config.DATA_DIR, "images", storage_path)
    if os.path.exists(local):
        with open(local, "rb") as f:
            data = f.read()
        return ft.Container(
            ft.InteractiveViewer(content=ft.Image(src=data, fit=ft.BoxFit.CONTAIN), max_scale=5),
            height=height, bgcolor="#000000", border_radius=16, clip_behavior=ft.ClipBehavior.ANTI_ALIAS)

    if storage_path not in _loading:
        _loading.add(storage_path)

        async def fetch():
            got = await asyncio.to_thread(app.sync.local_image, storage_path)
            _loading.discard(storage_path)
            if got:
                app.refresh()

        app.page.run_task(fetch)
    return ft.Container(
        ft.Column([ft.ProgressRing(), ft.Text("Loading photo…", size=12, color=ui.MUTED)],
                  horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True),
        height=height, bgcolor="#EEF0F5", border_radius=16, alignment=ft.Alignment.CENTER)


def detail_view(app, hw_id: str) -> ft.Control:
    h = app.store.get_row("homework", hw_id)
    if not h or h["deleted"]:
        return ft.Container(expand=True, content=ft.Column([
            ui.back_bar("Homework", lambda e: app.back()),
            ui.empty_state(ft.Icons.DELETE_OUTLINE, "This homework was deleted", "Maybe on another phone."),
        ]))
    child = app.child(h["child_id"])

    def set_status(s):
        def handler(e):
            changes = {"status": s}
            if s != "pending" and not h.get("done_at"):
                changes["done_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
            if s == "pending":
                changes["done_at"] = None
            app.store.update("homework", hw_id, **changes)
            app.changed()
        return handler

    task = ui.field("Homework", h.get("task") or "", multiline=True, min_lines=2, max_lines=6)

    def save_text(e):
        app.store.update("homework", hw_id, task=task.value or "")
        app.toast("Saved")
        app.changed()

    def pick_date(e):
        def changed(ev):
            v = ev.control.value
            if v:
                d = v.date() if isinstance(v, dt.datetime) else v
                app.store.update("homework", hw_id, due_date=d.isoformat())
                app.changed()
        app.page.show_dialog(ft.DatePicker(
            value=dt.datetime.fromisoformat(h["due_date"]), first_date=dt.datetime(2024, 1, 1),
            last_date=dt.datetime(2030, 12, 31), on_change=changed))

    def delete(e):
        def yes(ev):
            app.page.pop_dialog()
            app.store.update("homework", hw_id, deleted=True)
            app.back()
            app.changed()

        app.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Delete this homework?"),
            content=ft.Text("It will be removed from all phones."),
            actions=[ft.TextButton("Cancel", on_click=lambda ev: app.page.pop_dialog()),
                     ft.TextButton("Delete", on_click=yes, style=ft.ButtonStyle(color="#B91C1C"))]))

    status_defs = [("pending", "Pending", ui.ORANGE_FG), ("done", "Done", ui.GREEN), ("checked", "Checked ✓", ui.ACCENT)]
    status_row = ft.Row(spacing=8, controls=[
        ft.Container(expand=True, content=ui.choice_chip(label, h["status"] == key, set_status(key), color))
        for key, label, color in status_defs])

    who = next((m["display_name"] for m in app.store.members() if m["user_id"] == h.get("created_by")), None)
    tags = [ui.tag(t) for t in filter(None, [
        h.get("action"), h.get("book"), f"Unit {h['unit']}" if h.get("unit") else None,
        "p. " + ", ".join(h["pages"]) if h.get("pages") else None, h.get("repeat_note"),
        h.get("language_level")])]

    return ft.Container(expand=True, bgcolor=ui.BG, content=ft.Column(spacing=0, expand=True, controls=[
        ui.back_bar("Homework", lambda e: app.back(),
                    [ft.IconButton(ft.Icons.DELETE_OUTLINE, on_click=delete, tooltip="Delete")]),
        ft.ListView(expand=True, padding=16, spacing=14, controls=[
            *[photo_control(app, p) for p in h.get("image_paths") or []],
            ui.card(ft.Column(spacing=10, controls=[
                ft.Row([ui.subject_pill(h["subject"]), ui.kid_pill(child),
                        *([ui.pill("Test", ui.ORANGE_SOFT, ui.ORANGE_FG, 11)] if h.get("is_test") else [])],
                       spacing=6, wrap=True),
                task,
                *([ft.Row(tags, wrap=True, spacing=6)] if tags else []),
                ft.Row([ui.secondary_button("Save text", save_text, expand=True),
                        ui.secondary_button(ui.nice_date(h["due_date"]), pick_date,
                                            icon=ft.Icons.CALENDAR_MONTH, expand=True)]),
            ])),
            ui.section_label("Status"), status_row,
            *([ui.card(ft.Text(h["source_text"], size=13, color=ui.MUTED, selectable=True))]
              if h.get("source_text") else []),
            ft.Text(f"Added by {who}" if who else "", size=12, color=ui.MUTED),
        ]),
    ]))
