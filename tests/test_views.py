"""Builds every screen with sample data (no device needed) to catch API mistakes."""
import datetime as dt
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import flet as ft  # noqa: E402

from hb.store import Store  # noqa: E402
from hb.ui import add, auth, detail, exams, family, home, summary  # noqa: E402


class FakePage:
    def __init__(self):
        self.dialogs, self.tasks = [], []

    def show_dialog(self, d):
        self.dialogs.append(d)

    def pop_dialog(self):
        pass

    def run_task(self, fn, *a):
        self.tasks.append(fn)

    def update(self):
        pass


def make_app(tmp_path):
    store = Store(str(tmp_path / "v.db"))
    store.set("family_id", "fam1")
    store.set("join_code", "482719")
    store.set("family_name", "Our family")
    store.set_members([{"user_id": "u1", "display_name": "Amma", "joined_at": "1"},
                       {"user_id": "u2", "display_name": "Appa", "joined_at": "2"}])
    c1 = store.save("children", {"family_id": "fam1", "name": "Child 1", "class_name": "5-A", "color": "#C2410C",
                                 "subjects": ["English", "Tamil", "Maths", "Social", "Science"], "created_at": "1"})
    c2 = store.save("children", {"family_id": "fam1", "name": "Child 2", "color": "#0F766E",
                                 "subjects": ["English", "Tamil", "Hindi", "Maths", "EVS"], "created_at": "2"})
    t = dt.date.today()
    tom = (t + dt.timedelta(days=1)).isoformat()
    store.save("homework", {"child_id": c1["id"], "subject": "Social", "task": "Read 5-mark questions",
                            "pages": ["27", "28"], "book": "Course book", "is_test": True, "due_date": tom,
                            "status": "pending", "image_paths": ["fam1/a.jpg"], "created_by": "u1",
                            "source_text": "social: slip test"})
    hw2 = store.save("homework", {"child_id": c2["id"], "subject": "Hindi", "task": "Matra p 28",
                                  "due_date": tom, "status": "done",
                                  "done_at": dt.datetime.now(dt.timezone.utc).isoformat()})
    store.save("homework", {"child_id": c2["id"], "subject": "Maths", "task": "old",
                            "due_date": (t - dt.timedelta(days=2)).isoformat(), "status": "pending"})
    store.save("exams", {"child_id": c1["id"], "subject": "Social", "title": "Slip test", "exam_date": tom,
                         "portions": "p 27, 28"})
    store.save("exams", {"child_id": c2["id"], "subject": "Maths", "title": "A/B test", "exam_date": None})

    app = types.SimpleNamespace()
    app.page = FakePage()
    app.store = store
    app.api = types.SimpleNamespace(user_id="u1", email="amma@example.com", session={"x": 1})
    app.sync = types.SimpleNamespace(family_id="fam1", local_image=lambda p: None)
    app.kid_filter = "all"
    app.sync_state = "idle"
    app.app_version, app.app_build = "1.0.0", 1
    app.children = store.children
    app.child = lambda cid: store.get_row("children", cid) if cid else None
    app.open = app.back = app.refresh = app.changed = app.toast = lambda *a, **k: None
    app._stack = []
    return app, c1, c2, hw2


def walk(control, seen=None):
    """Touch every nested control so dataclass validation runs."""
    seen = seen if seen is not None else []
    seen.append(control)
    for attr in ("content", "controls", "leading", "title", "subtitle", "trailing"):
        v = getattr(control, attr, None)
        if isinstance(v, list):
            for c in v:
                if isinstance(c, ft.Control):
                    walk(c, seen)
        elif isinstance(v, ft.Control):
            walk(v, seen)
    return seen


def test_all_views(tmp_path):
    app, c1, c2, hw2 = make_app(tmp_path)
    for name, build in [
        ("home", lambda: home.view(app)),
        ("exams", lambda: exams.view(app)),
        ("summary", lambda: summary.view(app)),
        ("family", lambda: family.view(app)),
        ("login", lambda: auth.login_view(app)),
        ("family_setup", lambda: auth.family_setup_view(app)),
        ("add_menu", lambda: add.add_menu(app)),
        ("detail", lambda: detail.detail_view(app, hw2["id"])),
        ("exam_editor_new", lambda: exams.exam_editor(app, None)),
        ("child_editor", lambda: family.child_editor(app, c1["id"])),
        ("child_editor_new", lambda: family.child_editor(app, None)),
    ]:
        ctl = build()
        assert len(walk(ctl)) > 3, name

    app.kid_filter = c2["id"]
    assert len(walk(home.view(app))) > 3


def test_review_screen(tmp_path):
    app, c1, c2, _ = make_app(tmp_path)
    msg = "Today's Home Fun\nMaths: Complete Pages 50 & 51 in WB.\nHindi L3 : Read and write Matra – Page 28"
    st = add._ReviewState(app, msg, [])
    assert st.child_id == c2["id"] and st.auto_child
    assert [i["subject"] for i in st.items] == ["Maths", "Hindi"]
    walk(add.review_view(app, st))
    st2 = add._ReviewState(app, "", [])
    assert st2.items and st2.items[0]["subject"] == ""
    walk(add.review_view(app, st2))
