from __future__ import annotations

import re
from collections import Counter
from contextvars import ContextVar


FONT_MAP = {
    # Latin
    "TimesNewRomanPSMT": "Times New Roman",
    "TimesNewRoman": "Times New Roman",
    "ArialMT": "Arial",
    "Helvetica": "Arial",
    "Calibri": "Calibri",
    "Cambria": "Cambria",
    "Garamond": "Garamond",
    "CourierNew": "Courier New",
    "SourceHanSans": "Microsoft YaHei",
    "SourceHanSerif": "SimSun",
    "NotoSans": "Arial",
    # CJK
    "SimSun": "SimSun",
    "NSimSun": "SimSun",
    "Songti": "SimSun",
    "STSong": "SimSun",
    "FangSong": "FangSong",
    "KaiTi": "KaiTi",
    "SimHei": "SimHei",
    "Heiti": "SimHei",
    "MicrosoftYaHei": "Microsoft YaHei",
    "PingFangSC": "Microsoft YaHei",
    "HiraginoSansGB": "Microsoft YaHei",
    "DengXian": "DengXian",
}


SUBSET_PREFIX = re.compile(r"^[A-Z]{6}\+")
FONT_SUBSTITUTIONS: ContextVar[Counter[str]] = ContextVar("font_substitutions", default=Counter())


def reset_font_substitutions() -> None:
    FONT_SUBSTITUTIONS.set(Counter())


def get_font_substitutions() -> dict[str, object]:
    counter = FONT_SUBSTITUTIONS.get()
    total = int(sum(counter.values()))
    top = [{"fromTo": key, "count": int(value)} for key, value in counter.most_common(20)]
    return {
        "total": total,
        "items": top,
    }


def _record_font_substitution(src: str, dst: str) -> None:
    if not src or not dst or src == dst:
        return
    counter = FONT_SUBSTITUTIONS.get().copy()
    counter[f"{src} -> {dst}"] += 1
    FONT_SUBSTITUTIONS.set(counter)


def normalize_font_name(raw_name: str | None) -> str:
    if not raw_name:
        _record_font_substitution("", "Calibri")
        return "Calibri"

    src_name = raw_name
    clean = SUBSET_PREFIX.sub("", raw_name).replace("-", "").replace(" ", "")
    for key, mapped in FONT_MAP.items():
        if key.lower() in clean.lower():
            _record_font_substitution(src_name, mapped)
            return mapped

    # Unknown names with subset prefix often map poorly in Word.
    if SUBSET_PREFIX.search(src_name):
        _record_font_substitution(src_name, "Calibri")
        return "Calibri"

    return src_name


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
