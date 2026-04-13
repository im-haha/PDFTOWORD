from __future__ import annotations

import re
from statistics import median

from app.converter.font_mapper import color_from_int, guess_bold, guess_italic, normalize_font_name
from app.converter.pdf_reader import LineRaw, PageRaw, SpanRaw
from app.converter.schema import ParagraphData, RunData


DEFAULT_MARGIN_PT = 36.0
LIST_PREFIX_RE = re.compile(r"^\s*(?:[\u2022\-\*]|\d+[\.、\)]|\(\d+\)|[一二三四五六七八九十]+、|（[一二三四五六七八九十]+）)")
TOC_RE = re.compile(r"\.{3,}\s*\d+\s*$")
URLISH_RE = re.compile(r"(https?://|www\.|@)", re.IGNORECASE)


def _is_cjk(ch: str) -> bool:
    if not ch:
        return False
    code = ord(ch)
    return (
        0x4E00 <= code <= 0x9FFF
        or 0x3400 <= code <= 0x4DBF
        or 0x3040 <= code <= 0x30FF
        or 0xAC00 <= code <= 0xD7AF
    )


def _line_height(line: LineRaw) -> float:
    x0, y0, x1, y1 = line.bbox
    return max(1.0, y1 - y0)


def _line_font_size(line: LineRaw) -> float:
    sizes = [span.size for span in line.spans]
    return float(median(sizes)) if sizes else 11.0


def _line_font_name(line: LineRaw) -> str:
    fonts = [span.font for span in line.spans if span.font]
    if not fonts:
        return ""
    return max(set(fonts), key=fonts.count)


def _line_text(line: LineRaw) -> str:
    return "".join(span.text for span in line.spans)


def _ends_natural(text: str) -> bool:
    text = text.rstrip()
    if not text:
        return True
    return text[-1] in ".,;:!?，。；：！？、)）】」』"


def _starts_list_prefix(text: str) -> bool:
    return bool(LIST_PREFIX_RE.match(text))


def _is_same_paragraph_score(prev_line: LineRaw, cur_line: LineRaw, page_width: float) -> float:
    px0, _, px1, py1 = prev_line.bbox
    cx0, cy0, cx1, _ = cur_line.bbox

    prev_h = _line_height(prev_line)
    cur_h = _line_height(cur_line)
    gap = max(0.0, cy0 - py1)
    gap_ratio = gap / max(1.0, max(prev_h, cur_h))

    left_delta = abs(px0 - cx0)
    right_delta = abs(px1 - cx1)
    size_delta = abs(_line_font_size(prev_line) - _line_font_size(cur_line))
    font_changed = _line_font_name(prev_line) != _line_font_name(cur_line)

    prev_text = _line_text(prev_line).rstrip()
    cur_text = _line_text(cur_line).lstrip()

    score = 1.0

    if gap_ratio > 1.3:
        score -= 0.70
    elif gap_ratio > 0.95:
        score -= 0.35

    if left_delta > 16:
        score -= 0.38
    elif left_delta > 9:
        score -= 0.22

    if right_delta > page_width * 0.10:
        score -= 0.18

    if size_delta > 1.6:
        score -= 0.30

    if font_changed:
        score -= 0.12

    if _starts_list_prefix(cur_text):
        score -= 0.45

    if _starts_list_prefix(prev_text) and left_delta > 3:
        score -= 0.25

    prev_near_full = (px1 - px0) >= page_width * 0.65
    if prev_near_full and not _ends_natural(prev_text) and left_delta <= 8:
        score += 0.16

    if prev_text.endswith("-") and cur_text[:1].isalpha():
        score += 0.14

    return max(0.0, min(1.0, score))


def _should_insert_space(prev_text: str, next_text: str) -> bool:
    prev_text = prev_text.rstrip()
    next_text = next_text.lstrip()
    if not prev_text or not next_text:
        return False

    pc = prev_text[-1]
    nc = next_text[0]

    if pc.isspace() or nc.isspace():
        return False
    if _is_cjk(pc) or _is_cjk(nc):
        return False
    if nc in ".,;:!?)]}%，。；：！？、":
        return False
    if pc in "([{'\"“‘":
        return False

    tail = prev_text[-32:]
    head = next_text[:32]
    if URLISH_RE.search(tail) or URLISH_RE.search(head):
        return False

    if pc.isalnum() and nc.isalnum():
        return True

    if pc in "/@._-" or nc in "/@._-":
        return False

    return True


def _lines_to_runs(lines: list[LineRaw]) -> list[RunData]:
    runs: list[RunData] = []
    for line_idx, line in enumerate(lines):
        for span in line.spans:
            text = span.text
            if not text:
                continue
            runs.append(_span_to_run(span, text=text))

        if line_idx >= len(lines) - 1 or not runs:
            continue

        prev_text = _line_text(line)
        next_text = _line_text(lines[line_idx + 1])
        prev_tail = prev_text.rstrip()
        next_head = next_text.lstrip()

        # Hyphenated word across visual lines.
        if prev_tail.endswith("-") and next_head[:1].isalpha():
            for idx in range(len(runs) - 1, -1, -1):
                if runs[idx].text:
                    runs[idx].text = runs[idx].text.rstrip()
                    if runs[idx].text.endswith("-"):
                        runs[idx].text = runs[idx].text[:-1]
                    break
            continue

        if _should_insert_space(prev_text, next_text):
            runs.append(
                RunData(
                    text=" ",
                    font_name=runs[-1].font_name,
                    font_size=runs[-1].font_size,
                    bold=runs[-1].bold,
                    italic=runs[-1].italic,
                    color=runs[-1].color,
                )
            )

    return [run for run in runs if run.text != ""]


def _span_to_run(span: SpanRaw, text: str | None = None) -> RunData:
    return RunData(
        text=text if text is not None else span.text,
        font_name=normalize_font_name(span.font),
        font_size=max(6.0, min(64.0, span.size)),
        bold=guess_bold(span.font, span.flags),
        italic=guess_italic(span.font, span.flags),
        color=color_from_int(span.color),
    )


def _detect_role(lines: list[LineRaw], page_height: float, base_font_size: float) -> str:
    text = " ".join(_line_text(line).strip() for line in lines if _line_text(line).strip())
    y0 = min(line.bbox[1] for line in lines)

    if y0 < page_height * 0.08:
        return "header"
    if y0 > page_height * 0.92:
        return "footer"
    if text and _starts_list_prefix(text):
        return "list_item"
    if TOC_RE.search(text):
        return "toc_line"
    if base_font_size <= 8.8 and re.match(r"^\s*(\d+|\*|\[\d+\])", text):
        return "footnote"
    if base_font_size >= 14.0:
        return "title"
    if base_font_size >= 12.2 and len(text) < 42:
        return "subtitle"
    return "body"


def _determine_align(block_bbox: tuple[float, float, float, float], page_width: float) -> str:
    x0, _, x1, _ = block_bbox
    block_width = max(1.0, x1 - x0)
    center = (x0 + x1) / 2
    left_gap = x0
    right_gap = page_width - x1

    if block_width > page_width * 0.72 and left_gap < 70 and right_gap < 42:
        return "justify"

    if (
        block_width < page_width * 0.62
        and abs(center - page_width / 2) <= 12
        and abs(left_gap - right_gap) <= 16
    ):
        return "center"

    if right_gap < 28 and left_gap > 120:
        return "right"

    return "left"


def _build_paragraph_from_lines(
    lines: list[LineRaw],
    block_bbox: tuple[float, float, float, float],
    page_width: float,
    page_height: float,
    merge_scores: list[float],
) -> ParagraphData:
    sizes = [_line_font_size(line) for line in lines]
    heights = [_line_height(line) for line in lines]

    min_x0 = min(line.bbox[0] for line in lines)
    max_x1 = max(line.bbox[2] for line in lines)
    align = _determine_align(block_bbox, page_width)

    left_indent = max(0.0, min_x0 - DEFAULT_MARGIN_PT)
    if align == "right":
        right_indent = max(0.0, (page_width - DEFAULT_MARGIN_PT) - max_x1)
    else:
        right_indent = 0.0
    first_line_indent = lines[0].bbox[0] - min_x0

    base_font_size = float(median(sizes)) if sizes else 11.0
    base_line_h = float(median(heights)) if heights else 13.0
    line_spacing = max(8.0, min(32.0, base_line_h))

    role = _detect_role(lines, page_height=page_height, base_font_size=base_font_size)
    keep_with_next = role in {"title", "subtitle", "header"}
    hanging_indent = 0.0
    tab_stops: list[float] = []

    if role == "list_item" and len(lines) >= 2:
        body_x0 = float(median(line.bbox[0] for line in lines[1:]))
        first_x0 = lines[0].bbox[0]
        hanging_indent = max(0.0, min(28.0, body_x0 - first_x0))
        if hanging_indent > 1.5:
            left_indent = max(0.0, body_x0 - DEFAULT_MARGIN_PT)
            first_line_indent = -hanging_indent

    block_ids = sorted({line.block_id for line in lines if line.block_id})
    confidence = float(median(merge_scores)) if merge_scores else 0.9

    return ParagraphData(
        bbox=(
            min(line.bbox[0] for line in lines),
            min(line.bbox[1] for line in lines),
            max(line.bbox[2] for line in lines),
            max(line.bbox[3] for line in lines),
        ),
        align=align,
        left_indent=left_indent,
        right_indent=right_indent,
        first_line_indent=first_line_indent,
        line_spacing=line_spacing,
        space_before=0.0,
        space_after=0.0,
        role=role,
        keep_with_next=keep_with_next,
        hanging_indent=hanging_indent,
        tab_stops=tab_stops,
        confidence=confidence,
        source_block_ids=block_ids,
        runs=_lines_to_runs(lines),
    )


def build_paragraphs(page_raw: PageRaw) -> list[ParagraphData]:
    paragraphs: list[ParagraphData] = []

    for block in page_raw.text_blocks:
        if not block.lines:
            continue

        current_lines: list[LineRaw] = [block.lines[0]]
        current_scores: list[float] = []
        for line in block.lines[1:]:
            score = _is_same_paragraph_score(current_lines[-1], line, page_width=page_raw.width)
            if score >= 0.55:
                current_lines.append(line)
                current_scores.append(score)
            else:
                paragraphs.append(
                    _build_paragraph_from_lines(
                        lines=current_lines,
                        block_bbox=block.bbox,
                        page_width=page_raw.width,
                        page_height=page_raw.height,
                        merge_scores=current_scores,
                    )
                )
                current_lines = [line]
                current_scores = []

        if current_lines:
            paragraphs.append(
                _build_paragraph_from_lines(
                    lines=current_lines,
                    block_bbox=block.bbox,
                    page_width=page_raw.width,
                    page_height=page_raw.height,
                    merge_scores=current_scores,
                )
            )

    paragraphs.sort(key=lambda p: (p.bbox[1], p.bbox[0]))
    return paragraphs
