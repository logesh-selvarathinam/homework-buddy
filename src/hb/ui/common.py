"""Shared look: colours, small building blocks."""
from __future__ import annotations

import datetime as dt

import flet as ft

from .. import config

INK = "#1A1D29"
MUTED = "#5B6070"
BG = "#F5F6FA"
CARD = "#FFFFFF"
LINE = "#E4E6EE"
ACCENT = "#3B4CCA"
ACCENT_SOFT = "#EEF0FF"
GREEN = "#16A34A"
GREEN_SOFT = "#DCFCE7"
ORANGE_FG = "#9A3412"
ORANGE_SOFT = "#FFEDD5"


def safe_update(control: ft.Control) -> None:
    """update() only if the control is on screen (Flet raises otherwise)."""
    try:
        control.update()
    except RuntimeError:
        pass


def today() -> dt.date:
    return dt.date.today()


def nice_date(iso: str | None) -> str:
    if not iso:
        return "No date"
    d = dt.date.fromisoformat(iso)
    diff = (d - today()).days
    if diff == 0:
        return "Today"
    if diff == 1:
        return "Tomorrow"
    if diff == -1:
        return "Yesterday"
    return d.strftime("%a, %d %b")


def pill(text: str, bg: str, fg: str, size: int = 12) -> ft.Container:
    return ft.Container(
        content=ft.Text(text, size=size, weight=ft.FontWeight.W_700, color=fg),
        bgcolor=bg, border_radius=999, padding=ft.Padding.symmetric(horizontal=10, vertical=3),
    )


def subject_pill(subject: str) -> ft.Container:
    bg, fg = config.SUBJECT_COLORS.get(subject, config.DEFAULT_SUBJECT_COLOR)
    return pill(subject, bg, fg)


def kid_pill(child: dict | None) -> ft.Container:
    if not child:
        return pill("?", "#EEF0F5", MUTED, 11)
    color = child.get("color") or config.CHILD_COLORS[0]
    return pill(child["name"], ft.Colors.with_opacity(0.14, color), color, 11)


def tag(text: str) -> ft.Container:
    return ft.Container(
        content=ft.Text(text, size=11, weight=ft.FontWeight.W_600, color="#3F4455"),
        bgcolor="#EEF0F5", border_radius=6, padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


def section_label(text: str) -> ft.Text:
    return ft.Text(text.upper(), size=12, weight=ft.FontWeight.W_700, color=MUTED)


def card(content: ft.Control, on_click=None, padding: int = 14) -> ft.Container:
    return ft.Container(
        content=content, bgcolor=CARD, border=ft.Border.all(1, LINE), border_radius=16,
        padding=padding, on_click=on_click, ink=on_click is not None,
    )


def header(title: str, subtitle: str | None = None, trailing: ft.Control | None = None) -> ft.Container:
    col = ft.Column(spacing=2, controls=[
        *([ft.Text(subtitle, size=13, color=MUTED)] if subtitle else []),
        ft.Text(title, size=24, weight=ft.FontWeight.W_800, color=INK),
    ])
    return ft.Container(
        content=ft.Row([col, trailing] if trailing else [col],
                       alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        bgcolor=CARD, padding=ft.Padding.only(left=20, right=12, top=16, bottom=14),
        border=ft.Border.only(bottom=ft.BorderSide(1, LINE)),
    )


def back_bar(title: str, on_back, trailing: list[ft.Control] | None = None) -> ft.Container:
    return ft.Container(
        content=ft.Row([
            ft.IconButton(ft.Icons.ARROW_BACK, on_click=on_back, tooltip="Back"),
            ft.Text(title, size=18, weight=ft.FontWeight.W_800, expand=True),
            *(trailing or []),
        ]),
        bgcolor=CARD, padding=ft.Padding.symmetric(horizontal=4, vertical=6),
        border=ft.Border.only(bottom=ft.BorderSide(1, LINE)),
    )


def primary_button(text: str, on_click, icon=None, expand=False) -> ft.FilledButton:
    return ft.FilledButton(
        content=ft.Text(text, size=15, weight=ft.FontWeight.W_700), icon=icon, on_click=on_click,
        height=52, expand=expand, bgcolor=ACCENT,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)),
    )


def secondary_button(text: str, on_click, icon=None, expand=False) -> ft.OutlinedButton:
    return ft.OutlinedButton(
        content=ft.Text(text, size=14, weight=ft.FontWeight.W_700), icon=icon, on_click=on_click,
        height=48, expand=expand,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
    )


def choice_chip(label: str, selected: bool, on_click, color: str = INK) -> ft.Container:
    return ft.Container(
        content=ft.Text(label, size=14, weight=ft.FontWeight.W_700,
                        color="#FFFFFF" if selected else INK),
        bgcolor=color if selected else CARD,
        border=ft.Border.all(1, color if selected else "#D5D8E2"),
        border_radius=12, padding=ft.Padding.symmetric(horizontal=14, vertical=11),
        on_click=on_click, ink=True,
    )


def field(label: str, value: str = "", **kw) -> ft.TextField:
    return ft.TextField(label=label, value=value, border_radius=12, filled=True,
                        fill_color=CARD, **kw)


def empty_state(icon, title: str, text: str, action: ft.Control | None = None) -> ft.Container:
    return ft.Container(
        content=ft.Column([
            ft.Icon(icon, size=44, color="#B8BDCC"),
            ft.Text(title, size=17, weight=ft.FontWeight.W_700, text_align=ft.TextAlign.CENTER),
            ft.Text(text, size=13, color=MUTED, text_align=ft.TextAlign.CENTER),
            *([action] if action else []),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
        padding=ft.Padding.symmetric(horizontal=24, vertical=40), alignment=ft.Alignment.CENTER,
    )
