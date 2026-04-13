from __future__ import annotations

from dataclasses import dataclass

from app.converter.pdf_reader import LineRaw, PageRaw
from app.converter.schema import TableData


MIN_COLS = 3
MIN_ROWS = 3
LINE_JOIN_GAP = 20.0
COL_SPLIT_GAP = 22.0


@dataclass
class LineCells:
    bbox: tuple[float, float, float, float]
    cells: list[str]
    anchors: list[float]


def _line_to_cells(line: LineRaw) -> LineCells | None:
    spans = sorted(line.spans, key=lambda s: s.bbox[0])
    if not spans:
        return None

    cells: list[str] = []
    anchors: list[float] = []
    current = spans[0].text
    current_anchor = spans[0].bbox[0]
    prev_x1 = spans[0].bbox[2]

    for span in spans[1:]:
        gap = span.bbox[0] - prev_x1
        if gap > COL_SPLIT_GAP:
            cells.append(current.strip())
            anchors.append(current_anchor)
            current = span.text
            current_anchor = span.bbox[0]
        else:
            current += span.text
        prev_x1 = span.bbox[2]

    cells.append(current.strip())
    anchors.append(current_anchor)

    if len(cells) < MIN_COLS:
        return None

    return LineCells(bbox=line.bbox, cells=cells, anchors=anchors)


def _anchors_similar(a: list[float], b: list[float]) -> bool:
    if len(a) != len(b):
        return False
    if len(a) < MIN_COLS:
        return False
    return all(abs(x - y) <= 16 for x, y in zip(a, b))


def detect_tables(page_raw: PageRaw) -> list[TableData]:
    line_cells: list[LineCells] = []
    for block in page_raw.text_blocks:
        for line in block.lines:
            parsed = _line_to_cells(line)
            if parsed:
                line_cells.append(parsed)

    line_cells.sort(key=lambda l: (l.bbox[1], l.bbox[0]))

    tables: list[TableData] = []
    i = 0
    while i < len(line_cells):
        group = [line_cells[i]]
        j = i + 1
        while j < len(line_cells):
            prev = group[-1]
            cur = line_cells[j]
            v_gap = cur.bbox[1] - prev.bbox[3]
            if v_gap > LINE_JOIN_GAP:
                break
            if _anchors_similar(prev.anchors, cur.anchors):
                group.append(cur)
                j += 1
            else:
                break

        if len(group) >= MIN_ROWS:
            avg_cols = sum(len(row.cells) for row in group) / max(1, len(group))
            if avg_cols < MIN_COLS:
                i += 1
                continue

            x0 = min(row.bbox[0] for row in group)
            y0 = min(row.bbox[1] for row in group)
            x1 = max(row.bbox[2] for row in group)
            y1 = max(row.bbox[3] for row in group)

            tables.append(
                TableData(
                    bbox=(x0, y0, x1, y1),
                    rows=[[cell for cell in row.cells] for row in group],
                )
            )
            i = j
            continue

        i += 1

    return tables
