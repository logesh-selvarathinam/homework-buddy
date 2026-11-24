"""App shell: start-up, navigation, background sync, reminders and updates."""
from __future__ import annotations

import asyncio
import datetime as dt
import os

import flet as ft

from . import config, reminders, updater
from .api import ApiError, Supabase
from .store import Store
from .sync import Sync
from .ui import common as ui

SYNC_EVERY_SECONDS = 20

try:  # reminders need the flet-notifications extension (in pyproject.toml)
    import flet_notifications as ftn
except ImportError:  # pragma: no cover
    ftn = None


class App:
    def __init__(self, page: ft.Page):
        self.page = page
        self.store = Store(os.path.join(config.DATA_DIR, "homeworkbuddy.db"))
        self.api = Supabase(config.SUPABASE_URL, config.SUPABASE_ANON_KEY,
                            session=self.store.get("session"),
                            on_session=lambda s: self.store.set("session", s))
        self.sync = Sync(self.store, self.api)

        # services (register with the page when created)
        self.clipboard = ft.Clipboard()
        self.picker = ft.FilePicker()
        self.launcher = ft.UrlLauncher()
        self.notifications = ftn.Notifications(on_tap=lambda e: self.go_tab(0)) if ftn else None

        self.tab = 0
        self.kid_filter = "all"
        self.sync_state = "idle"      # idle | syncing | offline | error
        self.app_version, self.app_build = "0.0.0", 0
        self._stack: list = []        # sub-screens opened on top of a tab

        self._render_lock = False

    # ---------------------------------------------------------------- start
    async def start(self):
        p = self.page
        p.title = "HomeworkBuddy"
        p.bgcolor = ui.BG
        p.padding = 0
        p.theme_mode = ft.ThemeMode.LIGHT
        p.theme = ft.Theme(color_scheme_seed=ui.ACCENT)
        p.on_view_pop = lambda e: self.back()
        try:
            info = await p.get_package_info()
            self.app_version, self.app_build = info.version, info.build_number
        except Exception:
            pass
        self.show_current()
        if self.ready:
            p.run_task(self.sync_loop)
        p.run_task(self.check_update, False)

    @property
    def ready(self) -> bool:
        return bool(self.api.session and self.sync.family_id)

    # ----------------------------------------------------------- navigation
    # Android's Back button pops the top View. Every open screen is its own
    # View (Home at the bottom, then another tab, then sub-screens), so Back
    # closes one screen at a time and only leaves the app from Home.
    def _nav_bar(self) -> ft.NavigationBar:
        return ft.NavigationBar(
            selected_index=self.tab, on_change=lambda e: self.go_tab(e.control.selected_index),
            bgcolor=ui.CARD, indicator_color=ui.ACCENT_SOFT,
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME, label="Home"),
                ft.NavigationBarDestination(icon=ft.Icons.ASSIGNMENT_TURNED_IN_OUTLINED, label="Exams"),
                ft.NavigationBarDestination(icon=ft.Icons.INSIGHTS, label="Summary"),
                ft.NavigationBarDestination(icon=ft.Icons.GROUP_OUTLINED, label="Family"),
            ],
        )

    def _layers(self) -> list[tuple]:
        """(builder, is_tab) from the bottom of the stack to the top."""
        from .ui import auth, exams, family, home, summary
        if not self.api.session:
            return [(lambda: auth.login_view(self), False)]
        if not self.sync.family_id:
            return [(lambda: auth.family_setup_view(self), False)]
        tabs = [home.view, exams.view, summary.view, family.view]
        layers = [(lambda: home.view(self), True)]
        if self.tab:
            layers.append((lambda t=tabs[self.tab]: t(self), True))
        layers += [(b, False) for b in self._stack]
        return layers

    def render(self):
        views = []
        layers = self._layers()
        for i, (build, is_tab) in enumerate(layers):
            top = i == len(layers) - 1
            # Lower layers are only seen during the back animation: build the one
            # right under the top for a smooth transition, keep the rest empty.
            if top or i == len(layers) - 2:
                control = build()
            else:
                control = ft.Container()
            fab = getattr(control, "data", None)
            views.append(ft.View(
                route="/" if i == 0 else f"/{i}",
                controls=[ft.SafeArea(content=control, expand=True)],
                padding=0, spacing=0, bgcolor=ui.BG,
                navigation_bar=self._nav_bar() if is_tab else None,
                floating_action_button=fab if is_tab and isinstance(fab, ft.FloatingActionButton) else None,
            ))
        self.page.views.clear()
        self.page.views.extend(views)
        self.page.update()

    def show_current(self):
        self._stack.clear()
        self.render()

    def go_tab(self, index: int):
        self.tab = index
        self._stack.clear()
        self.render()

    def open(self, build):
        """Open a sub-screen. build() returns the control; it is rebuilt on refresh."""
        self._stack.append(build)
        self.render()

    def back(self):
        if self._stack:
            self._stack.pop()
        elif self.tab:
            self.tab = 0
        self.render()

    def refresh(self):
        """Redraw whatever is on screen (after a sync or an edit)."""
        self.render()

    def toast(self, text: str, error: bool = False):
        self.page.show_dialog(ft.SnackBar(
            content=ft.Text(text, color="#FFFFFF"),
            bgcolor="#B91C1C" if error else ui.INK, duration=3000))

    # ---------------------------------------------------------------- data
    def children(self) -> list[dict]:
        return self.store.children()

    def child(self, child_id: str | None) -> dict | None:
        return self.store.get_row("children", child_id) if child_id else None

    def changed(self):
        """Call after saving anything on this phone: redraw, then sync soon."""
        self.refresh()
        self.page.run_task(self.sync_now, False)

    # ----------------------------------------------------------------- sync
    async def sync_loop(self):
        if getattr(self, "_loop_running", False):
            return
        self._loop_running = True
        try:
            while self.ready:
                await self.sync_now(False)
                await asyncio.sleep(SYNC_EVERY_SECONDS)
        finally:
            self._loop_running = False

    async def sync_now(self, show_result: bool = True):
        if not self.ready:
            return
        before = self.sync_state
        self.sync_state = "syncing"
        try:
            res = await asyncio.to_thread(self.sync.sync)
            self.sync_state = "idle"
            if res.get("pulled") or before != "idle" or show_result:
                self.refresh()
            if show_result:
                self.toast("Up to date on this phone")
            await self.update_reminders()
        except ApiError as e:
            self.sync_state = "error"
            if e.status == 401 and not self.api.session:
                self.toast("Please sign in again", True)
                self.show_current()
            elif show_result:
                self.show_sync_error()
        except Exception as e:  # no internet etc.
            import requests
            self.sync.last_error = self.sync.last_error or f"{type(e).__name__}: {e}"
            self.sync_state = "offline" if isinstance(e, requests.ConnectionError) else "error"
            if show_result:
                self.show_sync_error()
            print("sync error:", e)

    def show_sync_error(self):
        err = self.sync.last_error or "Unknown error"

        async def retry(e):
            self.page.pop_dialog()
            await self.sync_now(True)

        self.page.show_dialog(ft.AlertDialog(
            icon=ft.Icon(ft.Icons.WARNING_AMBER, color="#B91C1C"),
            title=ft.Text("Sync problem"),
            content=ft.Column(tight=True, spacing=8, controls=[
                ft.Text("Your changes are safe on this phone. Error details:", size=13),
                ft.Text(err, size=12, selectable=True, color="#7F1D1D"),
            ]),
            actions=[ft.TextButton("Close", on_click=lambda e: self.page.pop_dialog()),
                     ft.FilledButton("Try again", on_click=retry, bgcolor=ui.ACCENT)],
        ))

    # ------------------------------------------------------------ reminders
    async def update_reminders(self):
        if not self.notifications or not self.store.get("reminders_on", False):
            return
        try:
            await reminders.apply(self.notifications, self.store)
        except Exception as e:
            print("reminders:", e)

    async def turn_reminders_on(self) -> bool:
        if not self.notifications:
            self.toast("Reminders are not available in this build", True)
            return False
        try:
            ok = await self.notifications.request_permissions()
        except Exception as e:
            self.toast(f"Reminders not supported here: {e}", True)
            return False
        if not ok:
            self.toast("Allow notifications for HomeworkBuddy in Android settings", True)
            return False
        self.store.set("reminders_on", True)
        await self.update_reminders()
        return True

    async def turn_reminders_off(self):
        self.store.set("reminders_on", False)
        if self.notifications:
            try:
                await self.notifications.cancel_all_pending()
            except Exception:
                pass

    # -------------------------------------------------------------- updates
    async def check_update(self, manual: bool = True):
        try:
            info = await asyncio.to_thread(
                updater.check, self.api.get_public_json, config.UPDATE_MANIFEST_URL,
                self.app_version, self.app_build)
        except Exception as e:
            if manual:
                self.toast(f"Could not check for updates: {e}", True)
            return
        if not info:
            if manual:
                self.toast(f"You have the latest version ({self.app_version})")
            return
        if not manual and self.store.get("skipped_update") == f"{info.version}+{info.build}" and not info.mandatory:
            return
        self.show_update_dialog(info)

    def show_update_dialog(self, info: updater.UpdateInfo):
        async def install(e):
            self.page.pop_dialog()
            await self.launcher.launch_url(info.apk_url, mode=ft.LaunchMode.EXTERNAL_APPLICATION)
            self.toast("Downloading… open the file when it finishes and tap Update")

        def later(e):
            self.store.set("skipped_update", f"{info.version}+{info.build}")
            self.page.pop_dialog()

        actions = [ft.FilledButton("Download & install", on_click=install, bgcolor=ui.ACCENT)]
        if not info.mandatory:
            actions.insert(0, ft.TextButton("Later", on_click=later))
        self.page.show_dialog(ft.AlertDialog(
            modal=info.mandatory,
            icon=ft.Icon(ft.Icons.SYSTEM_UPDATE, color=ui.ACCENT),
            title=ft.Text(f"Update available · {info.version}"),
            content=ft.Column(tight=True, spacing=8, controls=[
                ft.Text(info.notes or "A new version of HomeworkBuddy is ready."),
                ft.Text(f"You have {self.app_version}. Your homework data stays on the phone and in the cloud.",
                        size=12, color=ui.MUTED),
            ]),
            actions=actions,
        ))

    # ----------------------------------------------------------------- auth
    def after_sign_in(self):
        self.show_current()
        if self.ready:
            self.page.run_task(self.sync_loop)

    def sign_out(self):
        self.api.sign_out()
        self.store.reset_family_data()
        self.tab = 0
        self.show_current()


def today_iso() -> str:
    return dt.date.today().isoformat()
