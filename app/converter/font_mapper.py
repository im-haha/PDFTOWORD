from __future__ import annotations

import re


FONT_MAP = {
    "TimesNewRomanPSMT": "Times New Roman",
    "TimesNewRoman": "Times New Roman",
    "ArialMT": "Arial",
    "Helvetica": "Arial",
    "SimSun": "SimSun",
    "Songti": "SimSun",
    "MicrosoftYaHei": "Microsoft YaHei",
    "Calibri": "Calibri",
}


SUBSET_PREFIX = re.compile(r"^[A-Z]{6}\+")


def normalize_font_name(raw_name: str | None) -> str:
    if not raw_name:
        return "Calibri"

    clean = SUBSET_PREFIX.sub("", raw_name).replace("-", "").replace(" ", "")
    for key, mapped in FONT_MAP.items():
        if key.lower() in clean.lower():
            return mapped
    return raw_name


def guess_bold(raw_name: str | None, flags: int | None) -> bool:
    if raw_name and "bold" in raw_name.lower():
        return True
    if flags is None:
        return False
    return bool(flags & (1 << 4))


def guess_italic(raw_name: str | None, flags: int | None) -> bool:
    if raw_name and ("italic" in raw_name.lower() or "oblique" in raw_name.lower()):
        return True
    if flags is None:
        return False
    return bool(flags & (1 << 1))


def color_from_int(value: int | None) -> tuple[int, int, int] | None:
    if value is None:
        return None
    if value < 0:
        return None
    r = (value >> 16) & 0xFF
    g = (value >> 8) & 0xFF
    b = value & 0xFF
    return r, g, b
