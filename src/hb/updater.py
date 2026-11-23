"""In-app update check.

Each GitHub build uploads `latest.json` to the public `app-updates` bucket:

    {"version": "1.0.3", "build": 4,
     "apk_url": "https://…/app-updates/homeworkbuddy-1.0.3.apk",
     "notes": "What changed", "mandatory": false}

The app compares it with its own version and offers the new APK.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class UpdateInfo:
    version: str
    build: int
    apk_url: str
    notes: str = ""
    mandatory: bool = False


def version_key(version: str, build: int | str | None = 0) -> tuple:
    nums = [int(x) for x in re.findall(r"\d+", version or "0")[:3]]
    nums += [0] * (3 - len(nums))
    try:
        b = int(build or 0)
    except (TypeError, ValueError):
        b = 0
    return (*nums, b)


def parse_manifest(data: dict) -> UpdateInfo:
    return UpdateInfo(
        version=str(data["version"]),
        build=int(data.get("build") or 0),
        apk_url=str(data["apk_url"]),
        notes=str(data.get("notes") or ""),
        mandatory=bool(data.get("mandatory")),
    )


def newer_than(info: UpdateInfo, current_version: str, current_build) -> bool:
    return version_key(info.version, info.build) > version_key(current_version, current_build)


def check(fetch_json, manifest_url: str, current_version: str, current_build) -> UpdateInfo | None:
    """fetch_json(url) -> dict. Returns UpdateInfo if a newer APK exists."""
    info = parse_manifest(fetch_json(manifest_url))
    return info if newer_than(info, current_version, current_build) else None
