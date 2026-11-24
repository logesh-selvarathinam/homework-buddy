"""Split a school homework message into one item per subject.

    result = parse(text)
    for item in result.items: ...
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

ALIASES: dict[str, str] = {
    "maths": "Maths", "math": "Maths", "mahts": "Maths", "mathematics": "Maths",
    "english": "English", "eng": "English",
    "tamil": "Tamil", "தமிழ்": "Tamil",
    "hindi": "Hindi", "हिंदी": "Hindi",
    "evs": "EVS", "e.v.s": "EVS", "environmental studies": "EVS",
    "social": "Social", "social science": "Social", "social studies": "Social", "sst": "Social",
    "science": "Science",
    "computer": "Computer", "computers": "Computer",
    "gk": "GK",
}

_HEADER = re.compile(
    r"^((today'?s\s+)?home\s*(fun|work)|remarks|general(\s+diary)?|grade\s*\d+\s*[-–]?\s*[a-z]?)\s*[:：]?\s*$",
    re.I,
)
_SUBJECT_COLON = re.compile(r"^\s*([^:：]{1,30}?)\s*[:：]\s*(.*)$")
_SUBJECT_NO_COLON = re.compile(r"^(\S+(?:\s+L\s*\d)?)\s+(.+)$")
_LANG = re.compile(r"\bL\s*([1-3])\b", re.I)
_CLASS = re.compile(r"Grade\s*(\d+)\s*[-–]\s*([A-Z])\b", re.I)
_PAGE_KW = r"(?:pages?\s*(?:number|no\.?)?|pg\.?\s*no\.?|pgno|pg|p\.|பக்க\s*எண்|ப\.?\s*எண்)"
_NUMS = r"(\d+(?:\s*(?:,|&|and|to|-)\s*\d+)*)"
_PAGES = re.compile(_PAGE_KW + r"\s*[:.,]?\s*" + _NUMS, re.I)
_PAGE_WORD = re.compile(r"\bpg|page|ப\.?\s*எண்", re.I)
_UNIT = re.compile(r"\bunit\s*[,:]?\s*(\d+)", re.I)
_REPEAT = re.compile(r"\b(one|1|two|2|three|3)\s*-?\s*times?\b", re.I)
_TEST = re.compile(r"slip\s*test|unit\s*test|\b[a-d]\s*/\s*[a-d]\s*test\b|\btest\b|\bexam\b", re.I)
_BOOKS = [
    (re.compile(r"\bWB\b|work\s*book", re.I), "Workbook"),
    (re.compile(r"assessment\s*book", re.I), "Assessment book"),
    (re.compile(r"course\s*book|\bCB\b", re.I), "Course book"),
    (re.compile(r"class\s*work|\bCW\b", re.I), "Classwork"),
    (re.compile(r"note\s*book|\bNB\b", re.I), "Notebook"),
]

_BULLET = re.compile(r"^(?:[*•\-–·>]+|\d{1,2}[.)])\s*")
_TAMIL = re.compile(r"[\u0B80-\u0BFF]")
_DEVANAGARI = re.compile(r"[\u0900-\u097F]")

KNOWN_SUBJECTS = sorted(set(ALIASES.values()))


@dataclass
class ParsedItem:
    subject: str
    task: str
    language_level: str | None = None
    pages: list[str] = field(default_factory=list)
    unit: str | None = None
    book: str | None = None
    action: str | None = None
    repeat_note: str | None = None
    is_test: bool = False
    needs_check: bool = False

    @property
    def tags(self) -> list[str]:
        t = []
        if self.action: t.append(self.action)
        if self.book: t.append(self.book)
        if self.unit: t.append(f"Unit {self.unit}")
        if self.pages: t.append("p. " + ", ".join(self.pages))
        if self.repeat_note: t.append(self.repeat_note)
        return t


@dataclass
class ParseResult:
    items: list[ParsedItem]
    class_name: str | None = None
    unmatched: list[str] = field(default_factory=list)


def _subject_of(prefix: str, aliases: dict[str, str] = ALIASES) -> tuple[str | None, str | None]:
    lang = _LANG.search(prefix)
    p = _LANG.sub(" ", prefix)
    p = re.sub(r"[^A-Za-z0-9_஀-௿ऀ-ॿ. ]", " ", p).strip().lower()
    p = re.sub(r"\s+", " ", p)
    subject = aliases.get(p) or aliases.get(p.rstrip("."))
    return subject, (f"L{lang.group(1)}" if lang else None)


def _split_nums(s: str) -> list[str]:
    out = []
    for part in re.split(r"\s*(?:,|&|and)\s*", s):
        if not part:
            continue
        m = re.match(r"^(\d+)\s*(?:to|-)\s*(\d+)$", part)
        out.append(f"{m.group(1)}-{m.group(2)}" if m else part)
    return out


def _action_of(t: str) -> str | None:
    tl = t.lower()
    read = "read" in tl or "படித்" in t
    write = "write" in tl or "எழுத" in t
    if read and write:
        return "Read & write"
    if "complete" in tl or "finish" in tl or "முடித்" in t:
        return "Complete"
    if read:
        return "Read"
    if write:
        return "Write"
    if "learn" in tl or "study" in tl:
        return "Learn"
    return None


def parse(text: str, extra_aliases: dict[str, str] | None = None) -> ParseResult:
    """extra_aliases: the family's own spellings, e.g. {"mat": "Maths"}."""
    aliases = {**ALIASES, **{k.strip().lower(): v for k, v in (extra_aliases or {}).items() if k.strip()}}
    text = text.replace("\r", "").replace("’", "'")
    cls = _CLASS.search(text)
    drafts: list[list] = []  # [subject, level, task]
    unmatched: list[str] = []

    for raw in text.split("\n"):
        line = _BULLET.sub("", raw.strip())
        if not line or _HEADER.match(line):
            continue
        subject = level = rest = None
        m = _SUBJECT_COLON.match(line)
        if m:
            subject, level = _subject_of(m.group(1), aliases)
            rest = m.group(2)
        if not subject:
            w = _SUBJECT_NO_COLON.match(line)
            if w:
                subject, level = _subject_of(w.group(1), aliases)
                rest = w.group(2)
        if subject:
            drafts.append([subject, level, (rest or "").strip()])
        elif drafts:
            drafts[-1][2] += " " + line
        else:
            unmatched.append(line)

    if not drafts and unmatched:
        # No "Subject:" line (e.g. "write kaa இலிருந்து naa க்கு எழுது"):
        # keep the whole message as one item, guessing the subject from the script.
        whole = " ".join(unmatched)
        guess = "Tamil" if _TAMIL.search(whole) else "Hindi" if _DEVANAGARI.search(whole) else ""
        drafts.append([guess, None, whole])
        unmatched = []

    items = []
    for subject, level, t in drafts:
        pages = [p for m in _PAGES.finditer(t) for p in _split_nums(m.group(1))]
        unit = _UNIT.search(t)
        rep = _REPEAT.search(t)
        book = next((name for rx, name in _BOOKS if rx.search(t)), None)
        items.append(ParsedItem(
            subject=subject,
            language_level=level,
            task=t,
            pages=pages,
            unit=unit.group(1) if unit else None,
            book=book,
            action=_action_of(t),
            repeat_note=rep.group(0) if rep else None,
            is_test=bool(_TEST.search(t)),
            needs_check=(not t) or (not pages and not unit and bool(_PAGE_WORD.search(t))),
        ))
    return ParseResult(
        items=items,
        class_name=f"{cls.group(1)}-{cls.group(2).upper()}" if cls else None,
        unmatched=unmatched,
    )


def guess_child(result: ParseResult, children: list[dict]) -> str | None:
    """children: dicts with id, class_name, subjects. Returns a child id or None."""
    if result.class_name:
        for c in children:
            if (c.get("class_name") or "").replace(" ", "").upper() == result.class_name:
                return c["id"]
    scores = {c["id"]: 0 for c in children}
    for item in result.items:
        owners = [c for c in children if item.subject in (c.get("subjects") or [])]
        if len(owners) == 1:
            scores[owners[0]["id"]] += 1
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if not ranked or ranked[0][1] == 0:
        return None
    if len(ranked) > 1 and ranked[1][1] == ranked[0][1]:
        return None
    return ranked[0][0]


def next_school_day(start: dt.date, school_days: set[int] = frozenset({0, 1, 2, 3, 4, 5})) -> dt.date:
    """school_days uses date.weekday(): 0 = Mon … 6 = Sun. Default Mon–Sat."""
    d = start + dt.timedelta(days=1)
    while d.weekday() not in school_days:
        d += dt.timedelta(days=1)
    return d
