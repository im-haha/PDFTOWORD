from __future__ import annotations

from statistics import median

from app.converter.font_mapper import color_from_int, guess_bold, guess_italic, normalize_font_name
from app.converter.pdf_reader import LineRaw, PageRaw, SpanRaw
from app.converter.schema import ParagraphData, RunData


DEFAULT_MARGIN_PT = 36.0


def _determine_align(block_bbox: tuple[float, float, float, float], page_width: float) -> str:
    x0, _, x1, _ = block_bbox
    center = (x0 + x1) / 2
    left_gap = x0
    right_gap = page_width - x1

    if abs(center - page_width / 2) <= 12 and abs(left_gap - right_gap) <= 16:
        return "center"
    if right_gap < 28 and left_gap > 120:
        return "right"
    return "left"


def _line_height(line: LineRaw) -> float:
    x0, y0, x1, y1 = line.bbox
    return max(1.0, y1 - y0)


def _line_font_size(line: LineRaw) -> float:
    sizes = [span.size for span in line.spans]
    return float(median(sizes)) if sizes else 11.0


def _is_same_paragraph(prev_line: LineRaw, cur_line: LineRaw) -> bool:
    _, py0, _, py1 = prev_line.bbox
    _, cy0, _, _ = cur_line.bbox

    prev_h = _line_height(prev_line)
    cur_h = _line_height(cur_line)
    gap = max(0.0, cy0 - py1)

    left_delta = abs(prev_line.bbox[0] - cur_line.bbox[0])
    size_delta = abs(_line_font_size(prev_line) - _line_font_size(cur_line))

    return gap <= max(prev_h, cur_h) * 0.85 and left_delta <= 8 and size_delta <= 1.2


def _lines_to_runs(lines: list[LineRaw]) -> list[RunData]:
    runs: list[RunData] = []
    for line_idx, line in enumerate(lines):
        for span_idx, span in enumerate(line.spans):
            text = span.text
            if line_idx < len(lines) - 1 and span_idx == len(line.spans) - 1:
                text += "\n"
            if not text:
                continue

            runs.append(_span_to_run(span, text=text))
    return runs


def _span_to_run(span: SpanRaw, text: str | None = None) -> RunData:
    return RunData(
        text=text if text is not None else span.text,
        font_name=normalize_font_name(span.font),
        font_size=max(6.0, min(64.0, span.size)),
        bold=guess_bold(span.font, span.flags),
        italic=guess_italic(span.font, span.flags),
        color=color_from_int(span.color),
    )


def _build_paragraph_from_lines(
    lines: list[LineRaw],
    block_bbox: tuple[float, float, float, float],
    page_width: float,
) -> ParagraphData:
    sizes = [_line_font_size(line) for line in lines]
    heights = [_line_height(line) for line in lines]

    left_indent = max(0.0, lines[0].bbox[0] - DEFAULT_MARGIN_PT)
    right_indent = max(0.0, (page_width - DEFAULT_MARGIN_PT) - lines[-1].bbox[2])
    first_line_indent = max(0.0, lines[0].bbox[0] - block_bbox[0])

    base_font_size = float(median(sizes)) if sizes else 11.0
    base_line_h = float(median(heights)) if heights else 13.0
    line_spacing = min(2.0, max(1.0, base_line_h / max(1.0, base_font_size)))

    return ParagraphData(
        bbox=(
            min(line.bbox[0] for line in lines),
            min(line.bbox[1] for line in lines),
            max(line.bbox[2] for line in lines),
            max(line.bbox[3] for line in lines),
        ),
        align=_determine_align(block_bbox, page_width),
        left_indent=left_indent,
        right_indent=right_indent,
        first_line_indent=first_line_indent,
        line_spacing=line_spacing,
        space_before=0.0,
        space_after=max(1.0, base_font_size * 0.35),
        runs=_lines_to_runs(lines),
    )


def build_paragraphs(page_raw: PageRaw) -> list[ParagraphData]:
    paragraphs: list[ParagraphData] = []

    for block in page_raw.text_blocks:
        if not block.lines:
            continue

        current_lines: list[LineRaw] = [block.lines[0]]
        for line in block.lines[1:]:
            if _is_same_paragraph(current_lines[-1], line):
                current_lines.append(line)
            else:
                paragraphs.append(
                    _build_paragraph_from_lines(
                        lines=current_lines,
                        block_bbox=block.bbox,
                        page_width=page_raw.width,
                    )
                )
                current_lines = [line]

        if current_lines:
            paragraphs.append(
                _build_paragraph_from_lines(
                    lines=current_lines,
                    block_bbox=block.bbox,
                    page_width=page_raw.width,
                )
            )

    paragraphs.sort(key=lambda p: (p.bbox[1], p.bbox[0]))
    return paragraphs
