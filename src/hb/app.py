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

        self.body = ft.Container(expand=True)
        self.nav = ft.NavigationBar(
            selected_index=0, on_change=lambda e: self.go_tab(e.control.selected_index),
            bgcolor=ui.CARD, indicator_color=ui.ACCENT_SOFT,
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME, label="Home"),
                ft.NavigationBarDestination(icon=ft.Icons.ASSIGNMENT_TURNED_IN_OUTLINED, label="Exams"),
                ft.NavigationBarDestination(icon=ft.Icons.INSIGHTS, label="Summary"),
                ft.NavigationBarDestination(icon=ft.Icons.GROUP_OUTLINED, label="Family"),
            ],
        )

    # ---------------------------------------------------------------- start
    async def start(self):
        p = self.page
        p.title = "HomeworkBuddy"
        p.bgcolor = ui.BG
        p.padding = 0
        p.theme_mode = ft.ThemeMode.LIGHT
        p.theme = ft.Theme(color_scheme_seed=ui.ACCENT)
        p.on_view_pop = lambda e: self.back()
        p.add(ft.SafeArea(content=self.body, expand=True))
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
    def show_current(self):
        from .ui import auth, exams, family, home, summary
        self._stack.clear()
        if not self.api.session:
            self._set_body(auth.login_view(self), nav=False)
        elif not self.sync.family_id:
            self._set_body(auth.family_setup_view(self), nav=False)
        else:
            view = [home.view, exams.view, summary.view, family.view][self.tab](self)
            self._set_body(view, nav=True)

    def go_tab(self, index: int):
        self.tab = index
        self.nav.selected_index = index
        self.show_current()

    def open(self, build):
        """Open a sub-screen. build() returns the control; it is rebuilt on refresh."""
        self._stack.append(build)
        self._set_body(build(), nav=False)

    def back(self):
        if self._stack:
            self._stack.pop()
        if self._stack:
            self._set_body(self._stack[-1](), nav=False)
        else:
            self.show_current()

    def refresh(self):
        """Redraw whatever is on screen (after a sync or an edit)."""
        if self._stack:
            self._set_body(self._stack[-1](), nav=False)
        else:
            self.show_current()

    def _set_body(self, control, nav: bool):
        self.body.content = control
        self.page.navigation_bar = self.nav if nav else None
        self.page.floating_action_button = getattr(control, "data", None) if nav and isinstance(
            getattr(control, "data", None), ft.FloatingActionButton) else None
        self.page.update()

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
                self.toast(f"Sync failed: {e}", True)
        except Exception as e:  # no internet etc.
            self.sync_state = "offline"
            if show_result:
                self.toast("No internet – changes are saved on this phone and will sync later", True)
            print("sync error:", e)

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
        self.nav.selected_index = 0
        self.show_current()


def today_iso() -> str:
    return dt.date.today().isoformat()
