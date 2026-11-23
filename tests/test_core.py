import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from hb import parser, reminders, updater  # noqa: E402
from hb.store import Store  # noqa: E402
from hb.sync import Sync  # noqa: E402

S1 = """Today’s Home Fun
 Maths: Complete Pages 50 & 51 in WB.
 English: Complete the incomplete pages in Unit 2 in WB.
 Hindi L3 : Read and write Matra (मात्रा) – Page 28, one time."""
S2 = """Today's home fun
 Tamil : ப எண்: 105 எழுதி வரவும்.
 Maths : Complete the pgno, in WB
 EVS : unit, 2, Read Q/A (1,2)pgno, 21 in WB."""
S3 = """ Home fun :
 EVS complete assessment (set 1,2) and unit 2
 Maths : completepgno 52, 53 in WB.
 தமிழ்: ப எண் 106, முடித்து வரவும்"""
S4 = """Home fun:
 Maths : Read units of measurement.
 English : Read unit 2, Q/A (1,2)in WB."""
APP = """Grade 5 - A
Home fun

English :complete page number 32, 33 in assessment book.

L2 Tamil : Read card number : 2 and write page number 124 question and answer I classwork.

Maths: complete IA and IB in assessment book refer page number 12 .

social: slip test .Read 5 marks question refer page number 27,28 in course book"""

KIDS = [
    {"id": "c1", "class_name": "5-A", "subjects": ["English", "Tamil", "Maths", "Social", "Science"]},
    {"id": "c2", "class_name": None, "subjects": ["English", "Tamil", "Hindi", "Maths", "EVS"]},
]


def subj(r):
    return [i.subject for i in r.items]


def test_sample1():
    r = parser.parse(S1)
    assert subj(r) == ["Maths", "English", "Hindi"] and not r.unmatched
    assert r.items[0].pages == ["50", "51"] and r.items[0].book == "Workbook"
    assert r.items[1].unit == "2" and not r.items[1].needs_check
    h = r.items[2]
    assert (h.language_level, h.action, h.pages, h.repeat_note) == ("L3", "Read & write", ["28"], "one time")
    assert parser.guess_child(r, KIDS) == "c2"


def test_sample2():
    r = parser.parse(S2)
    assert subj(r) == ["Tamil", "Maths", "EVS"]
    assert r.items[0].pages == ["105"] and r.items[0].action == "Write"
    assert r.items[1].needs_check
    assert r.items[2].unit == "2" and r.items[2].pages == ["21"]
    assert parser.guess_child(r, KIDS) == "c2"


def test_sample3_and_4():
    r = parser.parse(S3)
    assert subj(r) == ["EVS", "Maths", "Tamil"] and not r.unmatched
    assert r.items[1].pages == ["52", "53"] and r.items[2].action == "Complete"
    r = parser.parse(S4)
    assert subj(r) == ["Maths", "English"] and r.items[0].unit is None


def test_school_app():
    r = parser.parse(APP)
    assert r.class_name == "5-A" and subj(r) == ["English", "Tamil", "Maths", "Social"]
    assert r.items[1].pages == ["124"] and r.items[1].language_level == "L2"
    assert r.items[3].is_test and not any(i.is_test for i in r.items[:3])
    assert parser.guess_child(r, KIDS) == "c1"


def test_next_school_day():
    assert parser.next_school_day(dt.date(2026, 11, 23)) == dt.date(2026, 11, 24)
    assert parser.next_school_day(dt.date(2026, 11, 28)) == dt.date(2026, 11, 30)


def test_updater():
    info = updater.parse_manifest({"version": "1.0.10", "build": 3, "apk_url": "x"})
    assert updater.newer_than(info, "1.0.9", 9)
    assert not updater.newer_than(info, "1.0.10", 3)
    assert updater.newer_than(info, "1.0.10", 2)
    assert updater.check(lambda u: {"version": "1.0.0", "apk_url": "x"}, "u", "1.0.0", 1) is None


# ---------------------------------------------------------------- fake server
class FakeApi:
    """In-memory stand-in for Supabase: two phones share one FakeServer."""

    def __init__(self, server, uid):
        self.server, self.session, self.user_id = server, {"access_token": "t"}, uid

    def rpc(self, name, p):
        if name == "create_family":
            self.server.family = {"id": "fam1", "name": p["family_name"], "join_code": "482719"}
            self.server.members = [{"user_id": self.user_id, "display_name": p["display_name"], "joined_at": "1"}]
            return [{"family_id": "fam1", "join_code": "482719"}]
        if name == "join_family":
            assert p["code"] == "482719"
            self.server.members.append({"user_id": self.user_id, "display_name": p["display_name"], "joined_at": "2"})
            return "fam1"

    def select(self, table, params):
        if table == "families":
            return [self.server.family]
        if table == "family_members":
            return self.server.members
        rows = sorted(self.server.tables.setdefault(table, {}).values(), key=lambda r: r["updated_at"])
        since = params.get("updated_at", "gt.")[3:]
        return [dict(r) for r in rows if r["updated_at"] > since][: int(params["limit"])]

    def upsert(self, table, rows):
        out = []
        for r in rows:
            self.server.clock += 1
            assert "created_at" not in r and "updated_at" not in r
            old = self.server.tables.get(table, {}).get(r["id"], {})
            r = dict(r, updated_at=f"2026-11-23T00:00:{self.server.clock:06d}", created_at=old.get("created_at") or "c")
            self.server.tables.setdefault(table, {})[r["id"]] = r
            out.append(dict(r))
        return out

    def upload(self, *a):
        self.server.uploads.append(a[1])


class FakeServer:
    def __init__(self):
        self.tables, self.clock, self.uploads, self.family, self.members = {}, 0, [], None, []


def test_two_phones_sync(tmp_path):
    server = FakeServer()
    a = Sync(Store(str(tmp_path / "a.db")), FakeApi(server, "ua"))
    b = Sync(Store(str(tmp_path / "b.db")), FakeApi(server, "ub"))
    code = a.create_family("Home", "Amma")
    b.join_family(code, "Appa")

    kid = a.store.save("children", {"family_id": "fam1", "name": "Child 1", "subjects": ["Maths"], "color": "#C2410C"})
    hw = a.store.save("homework", {"family_id": "fam1", "child_id": kid["id"], "subject": "Maths",
                                   "task": "p 50", "pages": ["50"], "due_date": "2026-11-24", "status": "pending"})
    img = tmp_path / "x.jpg"
    img.write_bytes(b"jpg")
    a.store.queue_upload("fam1/x.jpg", str(img))
    assert a.sync()["pushed"] == 2
    assert server.uploads == ["fam1/x.jpg"] and not a.store.dirty_rows("homework")

    b.sync()
    got = b.store.homework_due("2026-11-24")
    assert len(got) == 1 and got[0]["pages"] == ["50"] and b.store.children()[0]["name"] == "Child 1"
    assert [m["display_name"] for m in b.store.members()] == ["Amma", "Appa"]

    # phone B ticks it done, phone A sees it
    b.store.update("homework", hw["id"], status="done")
    b.sync()
    a.sync()
    assert a.store.get_row("homework", hw["id"])["status"] == "done"

    # unsynced local change is not overwritten by an older server copy
    a.store.update("homework", hw["id"], status="checked")
    a.store.apply_remote("homework", [dict(server.tables["homework"][hw["id"]])])
    assert a.store.get_row("homework", hw["id"])["status"] == "checked"


def test_reminders(tmp_path):
    s = Store(str(tmp_path / "r.db"))
    k = s.save("children", {"name": "Child 2", "subjects": []})
    s.save("homework", {"child_id": k["id"], "subject": "Hindi", "due_date": "2026-11-24", "status": "pending"})
    s.save("homework", {"child_id": k["id"], "subject": "EVS", "due_date": "2026-11-24", "status": "done"})
    s.save("exams", {"child_id": k["id"], "subject": "Social", "title": "Slip test", "exam_date": "2026-11-27"})
    s.save("exams", {"child_id": k["id"], "subject": "Maths", "title": "A/B test", "exam_date": None})
    rs = reminders.plan(s, dt.datetime(2026, 11, 23, 16, 0))
    assert [(r.when.isoformat(), r.title) for r in rs] == [
        ("2026-11-23T19:00:00", "1 homework pending for tomorrow"),
        ("2026-11-25T19:00:00", "Social Slip test in 2 days"),
        ("2026-11-26T19:00:00", "Social Slip test tomorrow"),
    ]
    assert rs[0].body == "Child 2: Hindi"
    assert len({r.id for r in rs}) == 3 and all(r.id < 2**31 for r in rs)
