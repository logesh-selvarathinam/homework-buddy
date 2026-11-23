"""Sign in, then create or join a family."""
from __future__ import annotations

import asyncio

import flet as ft

from ..api import ApiError
from . import common as ui


def _describe(ex: Exception) -> str:
    """Readable reason for an unexpected error (shown on screen)."""
    import requests
    if isinstance(ex, requests.ConnectionError):
        return f"Can't reach the server. Check internet. ({type(ex).__name__}: {str(ex)[:150]})"
    return f"Something went wrong: {type(ex).__name__}: {str(ex)[:200]}"


def _busy(btn: ft.FilledButton, busy: bool):
    btn.disabled = busy
    ui.safe_update(btn)


def login_view(app) -> ft.Control:
    email = ui.field("Email", keyboard_type=ft.KeyboardType.EMAIL, autofocus=True)
    password = ui.field("Password", password=True, can_reveal_password=True)
    msg = ft.Text("", color="#B91C1C", size=13, selectable=True)

    async def submit(create: bool):
        msg.value = ""
        e_, p_ = (email.value or "").strip(), password.value or ""
        if "@" not in e_ or len(p_) < 6:
            msg.value = "Enter your email and a password of at least 6 characters."
            msg.update()
            return
        _busy(sign_in_btn, True)
        try:
            if create:
                signed_in = await asyncio.to_thread(app.api.sign_up, e_, p_)
                if not signed_in:
                    msg.value = "Check your email and tap the confirmation link, then sign in here."
                    msg.color = ui.ACCENT
                    msg.update()
                    return
            else:
                await asyncio.to_thread(app.api.sign_in, e_, p_)
            app.after_sign_in()
        except ApiError as e:
            msg.value = str(e)
            msg.update()
        except Exception as ex:
            msg.value = _describe(ex)
            msg.update()
        finally:
            _busy(sign_in_btn, False)

    async def do_sign_in(e):
        await submit(False)

    async def do_create(e):
        await submit(True)

    sign_in_btn = ui.primary_button("Sign in", do_sign_in, expand=True)

    return ft.Container(
        expand=True, padding=24, bgcolor=ui.BG,
        content=ft.Column(scroll=ft.ScrollMode.AUTO, spacing=14, controls=[
            ft.Container(height=30),
            ft.Container(
                content=ft.Icon(ft.Icons.EDIT_NOTE, size=40, color="#FFFFFF"),
                bgcolor=ui.ACCENT, width=72, height=72, border_radius=20, alignment=ft.Alignment.CENTER),
            ft.Text("HomeworkBuddy", size=28, weight=ft.FontWeight.W_800),
            ft.Text("Your children's homework, on every phone in the family.", size=15, color=ui.MUTED),
            ft.Container(height=8),
            email, password, msg,
            ft.Row([sign_in_btn]),
            ft.Row([ui.secondary_button("Create a new account", do_create, expand=True)]),
            ft.Text("Each phone signs in with its own email. Then join the same family with a 6-digit code.",
                    size=12, color=ui.MUTED),
        ]),
    )


def family_setup_view(app) -> ft.Control:
    your_name = ui.field("Your name (shown to the family)", value=(app.api.email or "").split("@")[0])
    family_name = ui.field("Family name", value="Our family")
    code = ui.field("6-digit family code", keyboard_type=ft.KeyboardType.NUMBER, max_length=6)
    msg = ft.Text("", color="#B91C1C", size=13, selectable=True)

    def fail(text):
        msg.value = text
        msg.update()

    async def create(e):
        if not (your_name.value or "").strip():
            return fail("Enter your name.")
        try:
            join_code = await asyncio.to_thread(
                app.sync.create_family, family_name.value.strip() or "Our family", your_name.value.strip())
        except ApiError as ex:
            return fail(str(ex))
        except Exception as ex:
            return fail(_describe(ex))
        app.toast(f"Family created. Code: {join_code}")
        app.after_sign_in()

    async def join(e):
        if not (your_name.value or "").strip():
            return fail("Enter your name.")
        if len((code.value or "").strip()) != 6:
            return fail("The family code has 6 digits.")
        try:
            await asyncio.to_thread(app.sync.join_family, code.value, your_name.value.strip())
        except ApiError as ex:
            return fail(str(ex))
        except Exception as ex:
            return fail(_describe(ex))
        app.toast("Joined! Loading your family's homework…")
        app.after_sign_in()

    return ft.Container(
        expand=True, padding=24, bgcolor=ui.BG,
        content=ft.Column(scroll=ft.ScrollMode.AUTO, spacing=14, controls=[
            ft.Container(height=20),
            ft.Text("Set up your family", size=26, weight=ft.FontWeight.W_800),
            ft.Text(f"Signed in as {app.api.email}", size=13, color=ui.MUTED),
            your_name, msg,
            ui.card(ft.Column(spacing=12, controls=[
                ft.Text("First phone in the family?", size=16, weight=ft.FontWeight.W_700),
                family_name,
                ft.Row([ui.primary_button("Create family", create, expand=True)]),
            ])),
            ui.card(ft.Column(spacing=12, controls=[
                ft.Text("Already have a code?", size=16, weight=ft.FontWeight.W_700),
                ft.Text("Find it on the other phone: Family tab → family join code.", size=13, color=ui.MUTED),
                code,
                ft.Row([ui.secondary_button("Join family", join, expand=True)]),
            ])),
            ft.TextButton("Sign out", on_click=lambda e: app.sign_out()),
        ]),
    )
