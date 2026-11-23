"""Family tab: join code, phones, children, reminders, app updates."""
from __future__ import annotations

import flet as ft

from .. import config, parser
from . import common as ui


def child_editor(app, child_id: str | None) -> ft.Control:
    c = app.store.get_row("children", child_id) if child_id else None
    used = {k.get("color") for k in app.children()}
    state = {
        "color": (c or {}).get("color") or next((x for x in config.CHILD_COLORS if x not in used),
                                                 config.CHILD_COLORS[0]),
        "subjects": list((c or {}).get("subjects") or []),
    }
    name = ui.field("Name", (c or {}).get("name") or "", autofocus=not c)
    class_name = ui.field("Class (e.g. 5-A)", (c or {}).get("class_name") or "")
    extra = ui.field("Other subject")

    def toggle(s):
        def h(e):
            if s in state["subjects"]:
                state["subjects"].remove(s)
            else:
                state["subjects"].append(s)
            redraw_subjects()
        return h

    subj_row = ft.Row(wrap=True, spacing=8)

    def redraw_subjects():
        all_s = sorted(set(parser.KNOWN_SUBJECTS) | set(state["subjects"]))
        subj_row.controls = [ui.choice_chip(s, s in state["subjects"], toggle(s), ui.ACCENT) for s in all_s]
        ui.safe_update(subj_row)

    def add_extra(e):
        v = (extra.value or "").strip()
        if v and v not in state["subjects"]:
            state["subjects"].append(v)
            extra.value = ""
            extra.update()
            redraw_subjects()

    def pick_color(col):
        def h(e):
            state["color"] = col
            for box in color_row.controls:
                box.border = ft.Border.all(3, ui.INK if box.data == col else "#FFFFFF")
            color_row.update()
        return h

    color_row = ft.Row(spacing=10, controls=[
        ft.Container(width=40, height=40, border_radius=999, bgcolor=col, data=col, on_click=pick_color(col),
                     border=ft.Border.all(3, ui.INK if col == state["color"] else "#FFFFFF"))
        for col in config.CHILD_COLORS])
    redraw_subjects()

    def save(e):
        if not (name.value or "").strip():
            app.toast("Enter the child's name", True)
            return
        row = dict(c or {}, family_id=app.sync.family_id, name=name.value.strip(),
                   class_name=(class_name.value or "").strip().upper().replace(" ", "") or None,
                   color=state["color"], subjects=state["subjects"])
        row.pop("dirty", None)
        app.store.save("children", row)
        app.back()
        app.changed()

    def delete(e):
        def yes(ev):
            app.page.pop_dialog()
            app.store.update("children", child_id, deleted=True)
            app.back()
            app.changed()
        app.page.show_dialog(ft.AlertDialog(
            title=ft.Text(f"Remove {c['name']}?"),
            content=ft.Text("Their homework stays in the cloud but is hidden on all phones."),
            actions=[ft.TextButton("Cancel", on_click=lambda ev: app.page.pop_dialog()),
                     ft.TextButton("Remove", on_click=yes, style=ft.ButtonStyle(color="#B91C1C"))]))

    return ft.Container(expand=True, bgcolor=ui.BG, content=ft.Column(spacing=0, expand=True, controls=[
        ui.back_bar("Edit child" if c else "Add child", lambda e: app.back(),
                    [ft.IconButton(ft.Icons.DELETE_OUTLINE, on_click=delete, tooltip="Remove")] if c else None),
        ft.ListView(expand=True, padding=16, spacing=14, controls=[
            name, class_name,
            ft.Text("The class is matched with school-app messages like \"Grade 5 - A\".", size=12, color=ui.MUTED),
            ui.section_label("Colour"), color_row,
            ui.section_label("Subjects"),
            ft.Text("Pick the subjects this child studies. A subject only one child has (like Hindi) "
                    "tells the app which child a message is for.", size=12, color=ui.MUTED),
            subj_row,
            ft.Row([ft.Container(extra, expand=True), ft.IconButton(ft.Icons.ADD, on_click=add_extra)]),
            ft.Row([ui.primary_button("Save", save, icon=ft.Icons.CHECK, expand=True)]),
        ]),
    ]))


def view(app) -> ft.Control:
    code = app.store.get("join_code") or "------"
    me = app.api.user_id

    def copy(e):
        app.page.run_task(app.clipboard.set, code)
        app.toast("Code copied")

    async def share(e):
        await ft.Share().share_text(
            f"Join our family on HomeworkBuddy: install the app, sign in, tap \"Join family\" and enter {code}")

    async def toggle_reminders(e):
        if e.control.value:
            ok = await app.turn_reminders_on()
            if not ok:
                e.control.value = False
                e.control.update()
            else:
                app.toast("Reminders on: 7 pm the evening before homework and exams")
        else:
            await app.turn_reminders_off()

    async def check_updates(e):
        await app.check_update(True)

    def sign_out(e):
        def yes(ev):
            app.page.pop_dialog()
            app.sign_out()
        app.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Sign out on this phone?"),
            content=ft.Text("Changes not yet synced will be lost. The family's data stays in the cloud."),
            actions=[ft.TextButton("Cancel", on_click=lambda ev: app.page.pop_dialog()),
                     ft.TextButton("Sign out", on_click=yes)]))

    digits = ft.Row(spacing=6, controls=[
        ft.Container(ft.Text(d, size=22, weight=ft.FontWeight.W_800, color="#FFFFFF"), expand=True, height=48,
                     bgcolor="#2C3042", border_radius=10, alignment=ft.Alignment.CENTER) for d in code])

    members = app.store.members()
    member_rows = [ft.ListTile(
        leading=ft.Icon(ft.Icons.PHONE_ANDROID, color=ui.ACCENT),
        title=ft.Text(m["display_name"] + (" (this phone)" if m["user_id"] == me else ""),
                      weight=ft.FontWeight.W_700),
    ) for m in members] or [ft.Text("Sync once to see the phones in your family.", size=13, color=ui.MUTED)]

    kid_cards = [ui.card(
        on_click=lambda e, cid=k["id"]: app.open(lambda: child_editor(app, cid)),
        content=ft.Row(spacing=12, controls=[
            ft.Container(ft.Text(k["name"][:1].upper(), size=18, weight=ft.FontWeight.W_800, color=k["color"]),
                         width=44, height=44, border_radius=999, alignment=ft.Alignment.CENTER,
                         bgcolor=ft.Colors.with_opacity(0.14, k["color"])),
            ft.Column(expand=True, spacing=2, controls=[
                ft.Text(k["name"] + (f" · {k['class_name']}" if k.get("class_name") else ""),
                        size=15, weight=ft.FontWeight.W_700),
                ft.Text(", ".join(k.get("subjects") or []) or "No subjects yet", size=12, color=ui.MUTED),
            ]),
        ])) for k in app.children()]

    return ft.Column(spacing=0, expand=True, controls=[
        ui.header(app.store.get("family_name") or "Family", "Shared by everyone in the family"),
        ft.ListView(expand=True, spacing=12, padding=ft.Padding.only(left=16, right=16, top=14, bottom=30),
                    controls=[
            ft.Container(bgcolor=ui.INK, border_radius=20, padding=18, content=ft.Column(spacing=12, controls=[
                ft.Text("Family join code", size=13, weight=ft.FontWeight.W_600, color="#C9CCDA"),
                digits,
                ft.Row([
                    ft.FilledButton("Copy code", icon=ft.Icons.COPY, on_click=copy, expand=True,
                                    bgcolor="#FFFFFF", color=ui.INK),
                    ft.OutlinedButton("Share", icon=ft.Icons.SHARE, on_click=share, expand=True,
                                      style=ft.ButtonStyle(color="#FFFFFF")),
                ]),
                ft.Text("On another phone: install the app → create an account → Join family → enter this code.",
                        size=12, color="#C9CCDA"),
            ])),
            ui.section_label(f"Phones ({len(members)})"),
            ui.card(ft.Column(member_rows, spacing=0), padding=4),
            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ui.section_label("Children"),
                ft.TextButton("+ Add child", on_click=lambda e: app.open(lambda: child_editor(app, None))),
            ]),
            *kid_cards,
            ui.section_label("Settings"),
            ui.card(ft.Column(spacing=0, controls=[
                ft.ListTile(leading=ft.Icon(ft.Icons.NOTIFICATIONS_ACTIVE, color=ui.ACCENT),
                            title=ft.Text("Evening reminders"),
                            subtitle=ft.Text("7 pm before homework and exams"),
                            trailing=ft.Switch(value=bool(app.store.get("reminders_on", False)),
                                               on_change=toggle_reminders)),
                ft.ListTile(leading=ft.Icon(ft.Icons.SYSTEM_UPDATE, color=ui.ACCENT),
                            title=ft.Text("Check for updates"),
                            subtitle=ft.Text(f"Version {app.app_version} (build {app.app_build})"),
                            on_click=check_updates),
                ft.ListTile(leading=ft.Icon(ft.Icons.LOGOUT, color="#B91C1C"),
                            title=ft.Text("Sign out"), subtitle=ft.Text(app.api.email or ""),
                            on_click=sign_out),
            ]), padding=4),
        ]),
    ])
