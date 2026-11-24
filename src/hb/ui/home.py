"""Home tab: homework by due date, per child."""
from __future__ import annotations

import datetime as dt

import flet as ft

from . import common as ui


def _sync_chip(app) -> ft.Container:
    state = app.sync_state
    n = len(app.store.members()) or 1
    look = {
        "idle": (ft.Icons.CLOUD_DONE, f"Synced · {n} phone{'s' if n > 1 else ''}", "#166534", ui.GREEN_SOFT),
        "syncing": (ft.Icons.SYNC, "Syncing…", ui.ACCENT, ui.ACCENT_SOFT),
        "offline": (ft.Icons.CLOUD_OFF, "Offline · saved here", ui.ORANGE_FG, ui.ORANGE_SOFT),
        "error": (ft.Icons.WARNING_AMBER, "Sync problem · tap", "#B91C1C", "#FEE2E2"),
    }[state]

    async def tap(e):
        await app.sync_now(True)

    return ft.Container(
        content=ft.Row([ft.Icon(look[0], size=15, color=look[2]),
                        ft.Text(look[1], size=12, weight=ft.FontWeight.W_600, color=look[2])],
                       spacing=5, tight=True),
        bgcolor=look[3], border_radius=999, padding=ft.Padding.symmetric(horizontal=10, vertical=7),
        on_click=tap, ink=True, tooltip="Sync now",
    )


def homework_card(app, h: dict, show_kid: bool) -> ft.Container:
    from .detail import detail_view
    done = h["status"] != "pending"

    def toggle(e):
        new = "pending" if done else "done"
        changes = {"status": new}
        if new == "done" and not h.get("done_at"):
            changes["done_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        if new == "pending":
            changes["done_at"] = None
        app.store.update("homework", h["id"], **changes)
        app.changed()

    check = ft.Container(
        content=ft.Icon(ft.Icons.CHECK, size=18, color="#FFFFFF") if done else None,
        width=30, height=30, border_radius=999,
        bgcolor=(ui.ACCENT if h["status"] == "checked" else ui.GREEN) if done else ui.CARD,
        border=ft.Border.all(2, ui.GREEN if done else "#C4C8D4"),
        alignment=ft.Alignment.CENTER, on_click=toggle, ink=True,
        tooltip="Mark pending" if done else "Mark done",
    )
    pills = [ui.subject_pill(h["subject"])]
    if h.get("is_test"):
        pills.append(ui.pill("Test", ui.ORANGE_SOFT, ui.ORANGE_FG, 11))
    if show_kid:
        pills.append(ui.kid_pill(app.child(h["child_id"])))
    if h.get("image_paths"):
        pills.append(ft.Icon(ft.Icons.PHOTO_LIBRARY, size=16, color=ui.MUTED))
    meta = []
    if h.get("book"):
        meta.append(h["book"])
    if h.get("pages"):
        meta.append("p. " + ", ".join(h["pages"]))
    if h["status"] == "checked":
        meta.append("Checked ✓")

    return ui.card(
        on_click=lambda e: app.open(lambda: detail_view(app, h["id"])),
        content=ft.Row(vertical_alignment=ft.CrossAxisAlignment.START, spacing=12, controls=[
            check,
            ft.Column(expand=True, spacing=6, controls=[
                ft.Row(pills, spacing=6, wrap=True),
                ft.Text(h.get("task") or h["subject"], size=15, weight=ft.FontWeight.W_600,
                        color="#8A8FA0" if done else ui.INK,
                        style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH) if done else None),
                *([ft.Text(" · ".join(meta), size=12, color=ui.MUTED)] if meta else []),
            ]),
        ]),
    )


def _kid_selector(app, kids: list[dict]) -> ft.Row:
    def pick(cid):
        def handler(e):
            app.kid_filter = cid
            app.refresh()
        return handler

    chips = [ui.choice_chip("All", app.kid_filter == "all", pick("all"))]
    for k in kids:
        label = k["name"] + (f" · {k['class_name']}" if k.get("class_name") else "")
        chips.append(ui.choice_chip(label, app.kid_filter == k["id"], pick(k["id"]), k.get("color") or ui.INK))
    return ft.Row(chips, spacing=8, scroll=ft.ScrollMode.AUTO)


def view(app) -> ft.Control:
    from .add import add_menu
    from .family import child_editor

    kids = app.children()
    if app.kid_filter != "all" and app.kid_filter not in {k["id"] for k in kids}:
        app.kid_filter = "all"
    kid = None if app.kid_filter == "all" else app.kid_filter
    t = ui.today()

    top = ft.Container(
        bgcolor=ui.CARD, border=ft.Border.only(bottom=ft.BorderSide(1, ui.LINE)),
        padding=ft.Padding.only(left=20, right=20, top=16, bottom=12),
        content=ft.Column(spacing=12, controls=[
            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ft.Column(spacing=2, controls=[
                    ft.Text(t.strftime("%A, %d %b"), size=13, color=ui.MUTED),
                    ft.Text("HomeworkBuddy", size=24, weight=ft.FontWeight.W_800),
                ]),
                ft.Row(spacing=0, tight=True, controls=[
                    _sync_chip(app),
                    ft.IconButton(ft.Icons.HISTORY, tooltip="Past homework",
                                  on_click=lambda e: app.open(lambda: history_view(app))),
                ]),
            ]),
            *([_kid_selector(app, kids)] if kids else []),
        ]),
    )

    items: list[ft.Control] = []
    if not kids:
        items.append(ui.empty_state(
            ft.Icons.PERSON_ADD, "Add your children first",
            "Add each child with their class and subjects. The app uses the subjects to pick the right child "
            "automatically.",
            ui.primary_button("Add a child", lambda e: app.open(lambda: child_editor(app, None)))))
    else:
        show_kid = kid is None
        two_weeks = (t - dt.timedelta(days=14)).isoformat()
        overdue = [h for h in app.store.homework_overdue(t.isoformat(), kid) if h["due_date"] >= two_weeks]
        if overdue:
            items.append(ui.section_label(f"Overdue · {len(overdue)}"))
            items += [homework_card(app, h, show_kid) for h in overdue]

        dates = [d for d in app.store.upcoming_dates(t.isoformat(), 10)]
        shown = 0
        for d in dates:
            hw = app.store.homework_due(d, kid)
            if not hw:
                continue
            hw.sort(key=lambda h: h["status"] != "pending")  # pending first, done at the bottom
            done = sum(1 for h in hw if h["status"] != "pending")
            items.append(ft.Container(height=4))
            items.append(ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ft.Column(spacing=0, controls=[
                    ui.section_label("Due " + ui.nice_date(d).lower() if ui.nice_date(d) in ("Today", "Tomorrow")
                                     else "Due"),
                    ft.Text(dt.date.fromisoformat(d).strftime("%a, %d %b"), size=18, weight=ft.FontWeight.W_700),
                ]),
                ft.Text(f"{done} of {len(hw)} done", size=13, weight=ft.FontWeight.W_600, color=ui.MUTED),
            ]))
            items.append(ft.ProgressBar(value=done / len(hw), color=ui.GREEN, bgcolor=ui.LINE,
                                        bar_height=8, border_radius=999))
            items += [homework_card(app, h, show_kid) for h in hw]
            shown += 1
        if not shown and not overdue:
            items.append(ui.empty_state(
                ft.Icons.ASSIGNMENT_TURNED_IN_OUTLINED, "No homework yet",
                "Copy the teacher's message in WhatsApp, then tap Add homework → Paste message."))

    fab = ft.FloatingActionButton(
        icon=ft.Icons.ADD, content=ft.Text("Add homework", weight=ft.FontWeight.W_700),
        bgcolor=ui.ACCENT, foreground_color="#FFFFFF",
        on_click=lambda e: app.open(lambda: add_menu(app)),
    ) if kids else None

    return ft.Container(
        expand=True, data=fab,
        content=ft.Column(spacing=0, expand=True, controls=[
            top,
            ft.Container(expand=True, content=ft.ListView(
                controls=items, spacing=10, padding=ft.Padding.only(left=16, right=16, top=14, bottom=100))),
        ]),
    )


def history_view(app) -> ft.Control:
    """Past homework (last 60 days), newest first."""
    t = ui.today()
    kid = None if app.kid_filter == "all" else app.kid_filter
    rows = app.store.homework_between((t - dt.timedelta(days=60)).isoformat(),
                                      (t - dt.timedelta(days=1)).isoformat(), kid)
    rows.sort(key=lambda h: h["due_date"], reverse=True)
    items: list[ft.Control] = []
    last = None
    for h in rows:
        if h["due_date"] != last:
            last = h["due_date"]
            items.append(ft.Container(height=4))
            items.append(ui.section_label(dt.date.fromisoformat(last).strftime("%a, %d %b")))
        items.append(homework_card(app, h, kid is None))
    if not items:
        items.append(ui.empty_state(ft.Icons.HISTORY, "No past homework", "Homework from the last 60 days shows here."))
    return ft.Container(expand=True, bgcolor=ui.BG, content=ft.Column(spacing=0, expand=True, controls=[
        ui.back_bar("Past homework", lambda e: app.back()),
        ft.ListView(expand=True, controls=items, spacing=10, padding=16),
    ]))
