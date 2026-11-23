"""Summary tab: weekly completion per child."""
from __future__ import annotations

import datetime as dt

import flet as ft

from .. import stats
from . import common as ui


def _stat(value, label, color=ui.INK) -> ft.Column:
    return ft.Column(spacing=0, expand=True, controls=[
        ft.Text(str(value), size=22, weight=ft.FontWeight.W_800, color=color),
        ft.Text(label, size=12, color=ui.MUTED, weight=ft.FontWeight.W_600),
    ])


def _bar(s: dict) -> ft.Control:
    t = s["total"] or 1
    parts = [(s["on_time"], ui.ACCENT), (s["late"], "#F59E0B"), (s["pending"], "#EF4444")]
    return ft.Container(
        height=10, border_radius=999, bgcolor="#EEF0F5", clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Row(spacing=0, controls=[
            ft.Container(expand=n, bgcolor=c) for n, c in parts if n
        ] + ([ft.Container(expand=t - sum(n for n, _ in parts))] if sum(n for n, _ in parts) < t else [])),
    )


def view(app) -> ft.Control:
    kids = app.children()
    if not kids:
        return ft.Column(expand=True, controls=[ui.header("Weekly summary"),
                                                ui.empty_state(ft.Icons.INSIGHTS, "No children yet", "")])
    sel = app.store.get("summary_child")
    if sel not in {k["id"] for k in kids}:
        sel = kids[0]["id"]
    weeks_back = app.store.get("summary_weeks_back", 0)
    today = ui.today()
    start, end = stats.week_bounds(today - dt.timedelta(weeks=weeks_back))
    s = stats.compute(app.store, sel, start, end, today)

    def pick(cid):
        def h(e):
            app.store.set("summary_child", cid)
            app.refresh()
        return h

    def week(delta):
        def h(e):
            app.store.set("summary_weeks_back", max(0, weeks_back + delta))
            app.refresh()
        return h

    ring = ft.Stack(width=96, height=96, controls=[
        ft.ProgressRing(value=(s["pct"] or 0) / 100, width=96, height=96, stroke_width=10,
                        color=ui.GREEN, bgcolor=ui.LINE),
        ft.Container(width=96, height=96, alignment=ft.Alignment.CENTER, content=ft.Column(
            tight=True, spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                ft.Text(f"{s['pct']}%" if s["pct"] is not None else "–", size=22, weight=ft.FontWeight.W_800),
                ft.Text("on time", size=10, weight=ft.FontWeight.W_700, color=ui.MUTED)])),
    ])

    subject_rows = []
    for name, v in s["subjects"].items():
        label = f"{v['on_time']} on time" + (f" · {v['late']} late" if v["late"] else "") + \
                (f" · {v['pending']} missed" if v["pending"] else "") + f" / {v['total']}"
        subject_rows.append(ft.Column(spacing=6, controls=[
            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ft.Text(name, size=13, weight=ft.FontWeight.W_700),
                ft.Text(label, size=12, color=ui.MUTED)]),
            _bar(v)]))

    week_label = "This week" if weeks_back == 0 else ("Last week" if weeks_back == 1 else f"{weeks_back} weeks ago")

    body = [
        ft.Row(wrap=True, spacing=8, controls=[
            ui.choice_chip(k["name"], k["id"] == sel, pick(k["id"]), k.get("color") or ui.INK) for k in kids]),
        ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
            ft.IconButton(ft.Icons.CHEVRON_LEFT, on_click=week(1), tooltip="Previous week"),
            ft.Text(f"{week_label} · {start.strftime('%d %b')} – {end.strftime('%d %b')}",
                    size=14, weight=ft.FontWeight.W_700),
            ft.IconButton(ft.Icons.CHEVRON_RIGHT, on_click=week(-1), tooltip="Next week",
                          disabled=weeks_back == 0),
        ]),
    ]
    if s["total"] == 0:
        body.append(ui.empty_state(ft.Icons.INSIGHTS, "Nothing to count yet",
                                   f"{s['upcoming']} item(s) are still to come this week." if s["upcoming"]
                                   else "No homework was due in this week."))
    else:
        body += [
            ui.card(ft.Row(spacing=18, controls=[
                ring,
                ft.Column(expand=True, spacing=10, controls=[
                    ft.Row([_stat(s["total"], "Homework due"), _stat(s["on_time"], "On time", "#166534")]),
                    ft.Row([_stat(s["late"], "Done late", ui.ORANGE_FG), _stat(s["pending"], "Missed", "#B91C1C")]),
                ]),
            ]), padding=18),
            ui.card(ft.Column(spacing=14, controls=[
                ft.Text("By subject", size=15, weight=ft.FontWeight.W_700), *subject_rows]), padding=18),
        ]
        if s["weak"]:
            body.append(ft.Container(
                padding=14, border_radius=16, bgcolor="#FFF7ED", border=ft.Border.all(1, "#FED7AA"),
                content=ft.Row(vertical_alignment=ft.CrossAxisAlignment.START, controls=[
                    ft.Icon(ft.Icons.WARNING_AMBER, color=ui.ORANGE_FG, size=20),
                    ft.Text(f"Often late or missed: {', '.join(s['weak'])}.", size=13, color="#7C2D12",
                            weight=ft.FontWeight.W_600, expand=True)])))
        if s["upcoming"]:
            body.append(ft.Text(f"{s['upcoming']} more item(s) due later this week are not counted yet.",
                                size=12, color=ui.MUTED))

    return ft.Column(spacing=0, expand=True, controls=[
        ui.header("Weekly summary"),
        ft.ListView(expand=True, controls=body, spacing=12, padding=16),
    ])
