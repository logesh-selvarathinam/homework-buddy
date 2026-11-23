"""Exams tab: tests with countdowns."""
from __future__ import annotations

import datetime as dt

import flet as ft

from .. import parser
from . import common as ui


def exam_editor(app, exam_id: str | None) -> ft.Control:
    ex = app.store.get_row("exams", exam_id) if exam_id else None
    kids = app.children()
    state = {
        "child_id": (ex or {}).get("child_id") or (kids[0]["id"] if kids else None),
        "date": dt.date.fromisoformat(ex["exam_date"]) if ex and ex.get("exam_date") else None,
    }
    child = app.child(state["child_id"])
    subjects = sorted(set((child or {}).get("subjects") or []) | set(parser.KNOWN_SUBJECTS))
    subject = ft.Dropdown(label="Subject", value=(ex or {}).get("subject"), border_radius=12,
                          options=[ft.DropdownOption(key=s, text=s) for s in subjects], expand=True)
    title = ui.field("Test name (e.g. Slip test, Unit test)", (ex or {}).get("title") or "")
    portions = ui.field("Portions", (ex or {}).get("portions") or "", multiline=True, min_lines=2, max_lines=5)
    date_btn = ui.secondary_button(state["date"].strftime("%a, %d %b %Y") if state["date"] else "Set exam date",
                                   None, icon=ft.Icons.CALENDAR_MONTH, expand=True)

    def pick_date(e):
        def changed(ev):
            v = ev.control.value
            if v:
                state["date"] = v.date() if isinstance(v, dt.datetime) else v
                date_btn.content = ft.Text(state["date"].strftime("%a, %d %b %Y"), size=14,
                                           weight=ft.FontWeight.W_700)
                date_btn.update()
        app.page.show_dialog(ft.DatePicker(
            value=dt.datetime.combine(state["date"] or dt.date.today(), dt.time()),
            first_date=dt.datetime(2024, 1, 1), last_date=dt.datetime(2030, 12, 31), on_change=changed))

    date_btn.on_click = pick_date

    def pick_child(cid):
        def h(e):
            state["child_id"] = cid
            for c, k in zip(kid_row.controls, kids):
                sel = k["id"] == cid
                c.bgcolor = (k.get("color") or ui.INK) if sel else ui.CARD
                c.content.color = "#FFFFFF" if sel else ui.INK
            kid_row.update()
        return h

    kid_row = ft.Row(wrap=True, spacing=8, controls=[
        ui.choice_chip(k["name"], k["id"] == state["child_id"], pick_child(k["id"]), k.get("color") or ui.INK)
        for k in kids])

    def save(e):
        if not state["child_id"] or not subject.value:
            app.toast("Choose the child and subject", True)
            return
        row = dict(ex or {}, family_id=app.sync.family_id, child_id=state["child_id"], subject=subject.value,
                   title=(title.value or "").strip() or "Test", portions=portions.value or None,
                   exam_date=state["date"].isoformat() if state["date"] else None)
        row.pop("dirty", None)
        app.store.save("exams", row)
        app.back()
        app.changed()

    def delete(e):
        app.store.update("exams", exam_id, deleted=True)
        app.back()
        app.changed()

    return ft.Container(expand=True, bgcolor=ui.BG, content=ft.Column(spacing=0, expand=True, controls=[
        ui.back_bar("Edit exam" if ex else "Add exam", lambda e: app.back(),
                    [ft.IconButton(ft.Icons.DELETE_OUTLINE, on_click=delete, tooltip="Delete")] if ex else None),
        ft.ListView(expand=True, padding=16, spacing=14, controls=[
            ui.section_label("For"), kid_row,
            ft.Row([subject]), title, ft.Row([date_btn]), portions,
            ft.Row([ui.primary_button("Save", save, icon=ft.Icons.CHECK, expand=True)]),
        ]),
    ]))


def view(app) -> ft.Control:
    t = ui.today()
    upcoming, past = [], []
    for ex in app.store.exams():
        if ex.get("exam_date") and dt.date.fromisoformat(ex["exam_date"]) < t:
            past.append(ex)
        else:
            upcoming.append(ex)

    def exam_card(ex):
        child = app.child(ex["child_id"])
        if ex.get("exam_date"):
            days = (dt.date.fromisoformat(ex["exam_date"]) - t).days
            big, small = (str(days), "day left" if days == 1 else "days left") if days > 0 else (
                ("Today", "") if days == 0 else ("Done", ""))
            box_bg, box_fg = (ui.ORANGE_SOFT, ui.ORANGE_FG) if 0 <= days <= 2 else ("#EEF0F5", ui.INK)
        else:
            big, small, box_bg, box_fg = "?", "no date", "#F5F6FA", ui.MUTED
        return ui.card(
            on_click=lambda e: app.open(lambda: exam_editor(app, ex["id"])),
            content=ft.Row(spacing=14, vertical_alignment=ft.CrossAxisAlignment.START, controls=[
                ft.Container(width=66, height=66, bgcolor=box_bg, border_radius=14, alignment=ft.Alignment.CENTER,
                             content=ft.Column(spacing=0, tight=True,
                                               horizontal_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                                 ft.Text(big, size=22 if len(big) < 4 else 15, weight=ft.FontWeight.W_800,
                                         color=box_fg),
                                 *([ft.Text(small, size=10, weight=ft.FontWeight.W_700, color=box_fg)]
                                   if small else []),
                             ])),
                ft.Column(expand=True, spacing=5, controls=[
                    ft.Row([ui.subject_pill(ex["subject"]), ui.kid_pill(child)], spacing=6, wrap=True),
                    ft.Text(ex["title"], size=16, weight=ft.FontWeight.W_700),
                    *([ft.Text(ex["portions"], size=13, color="#3F4455", max_lines=3,
                               overflow=ft.TextOverflow.ELLIPSIS)] if ex.get("portions") else []),
                    ft.Text(dt.date.fromisoformat(ex["exam_date"]).strftime("%a, %d %b") if ex.get("exam_date")
                            else "Tap to set the exam date", size=12, color=ui.MUTED),
                ]),
            ]))

    controls: list[ft.Control] = []
    if upcoming:
        controls.append(ui.section_label("Coming up"))
        controls += [exam_card(x) for x in upcoming]
    if past:
        controls.append(ui.section_label("Finished"))
        controls += [exam_card(x) for x in reversed(past[-10:])]
    if not controls:
        controls.append(ui.empty_state(ft.Icons.QUIZ_OUTLINED, "No exams yet",
                                       "Tests in homework messages (\"slip test\", \"A/B test\") are added here "
                                       "when you save them. You can also add one yourself."))
    fab = ft.FloatingActionButton(icon=ft.Icons.ADD, content=ft.Text("Add exam", weight=ft.FontWeight.W_700),
                                  bgcolor=ui.ACCENT, foreground_color="#FFFFFF",
                                  on_click=lambda e: app.open(lambda: exam_editor(app, None))) \
        if app.children() else None
    return ft.Container(expand=True, data=fab, content=ft.Column(spacing=0, expand=True, controls=[
        ui.header("Exams & tests", "Both children"),
        ft.ListView(expand=True, controls=controls, spacing=10,
                    padding=ft.Padding.only(left=16, right=16, top=14, bottom=100)),
    ]))
