from __future__ import annotations

from dataclasses import dataclass

from app.converter.pdf_reader import LineRaw, PageRaw, WordRaw
from app.converter.schema import TableCellData, TableData


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


def _bbox_overlap_ratio(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    a_area = max(1.0, (ax1 - ax0) * (ay1 - ay0))
    return inter / a_area


def _group_words_by_rows(words: list[WordRaw], y_tol: float = 8.0) -> list[list[WordRaw]]:
    ordered = sorted(words, key=lambda w: (w.bbox[1], w.bbox[0]))
    rows: list[list[WordRaw]] = []

    for word in ordered:
        wy = (word.bbox[1] + word.bbox[3]) / 2
        if not rows:
            rows.append([word])
            continue

        last_row = rows[-1]
        ry = sum((w.bbox[1] + w.bbox[3]) / 2 for w in last_row) / len(last_row)
        if abs(wy - ry) <= y_tol:
            last_row.append(word)
        else:
            rows.append([word])

    return [sorted(row, key=lambda w: w.bbox[0]) for row in rows]


def _cluster_col_anchors(words: list[WordRaw], x_tol: float = 20.0) -> list[float]:
    xs = sorted(word.bbox[0] for word in words)
    if not xs:
        return []

    anchors: list[list[float]] = [[xs[0]]]
    for x in xs[1:]:
        if abs(x - anchors[-1][-1]) <= x_tol:
            anchors[-1].append(x)
        else:
            anchors.append([x])

    return [sum(cluster) / len(cluster) for cluster in anchors]


def _build_table_from_word_rows(
    rows: list[list[WordRaw]],
    col_anchors: list[float],
    bbox: tuple[float, float, float, float],
    is_explicit_grid: bool,
    confidence: float,
) -> TableData:
    text_rows: list[list[str]] = []
    cell_rows: list[list[TableCellData]] = []
    row_heights: list[float] = []

    col_starts = sorted(col_anchors)
    if not col_starts:
        col_starts = [bbox[0]]
    if abs(col_starts[0] - bbox[0]) > 4:
        col_starts = [bbox[0], *col_starts]
    x_edges = [*col_starts, bbox[2]]
    col_widths = [max(6.0, x_edges[idx + 1] - x_edges[idx]) for idx in range(len(x_edges) - 1)]
    col_count = max(1, len(col_widths))

    for row in rows:
        if not row:
            continue
        buckets = ["" for _ in range(col_count)]
        row_y0 = min(word.bbox[1] for word in row)
        row_y1 = max(word.bbox[3] for word in row)
        row_heights.append(max(8.0, row_y1 - row_y0))

        for word in row:
            wx = word.bbox[0]
            col_idx = min(range(col_count), key=lambda idx: abs(wx - x_edges[idx]))
            buckets[col_idx] = (buckets[col_idx] + " " + word.text).strip()

        text_rows.append(buckets)
        cell_rows.append(
            [
                TableCellData(
                    text=buckets[col_idx],
                    align="left",
                    bbox=(x_edges[col_idx], row_y0, x_edges[min(col_idx + 1, len(x_edges) - 1)], row_y1),
                )
                for col_idx in range(col_count)
            ]
        )

    fallback_to_image = len(text_rows) > 30 or col_count > 8

    return TableData(
        bbox=bbox,
        rows=text_rows,
        cols_widths=col_widths,
        row_heights=row_heights,
        cells=cell_rows,
        is_explicit_grid=is_explicit_grid,
        confidence=confidence,
        fallback_to_image=fallback_to_image,
    )


def _explicit_tables(page_raw: PageRaw) -> list[TableData]:
    tables: list[TableData] = []
    for drawing in page_raw.drawings:
        x0, y0, x1, y1 = drawing.bbox
        w = max(0.0, x1 - x0)
        h = max(0.0, y1 - y0)

        if w < 80 or h < 36:
            continue

        in_box = [
            word
            for word in page_raw.words
            if word.bbox[0] >= x0 - 2 and word.bbox[2] <= x1 + 2 and word.bbox[1] >= y0 - 2 and word.bbox[3] <= y1 + 2
        ]
        if len(in_box) < 6:
            continue

        rows = _group_words_by_rows(in_box)
        col_anchors = _cluster_col_anchors(in_box)
        if len(rows) < 2 or len(col_anchors) < 2:
            continue

        confidence = 0.86
        tables.append(
            _build_table_from_word_rows(
                rows=rows,
                col_anchors=col_anchors,
                bbox=drawing.bbox,
                is_explicit_grid=True,
                confidence=confidence,
            )
        )

    return tables


def _looks_like_toc(rows: list[list[str]]) -> bool:
    if not rows:
        return False
    dotted = 0
    page_no_like = 0
    for row in rows:
        row_text = " ".join(row)
        if "..." in row_text or "···" in row_text:
            dotted += 1
        if row and row[-1].strip().isdigit():
            page_no_like += 1
    return dotted >= max(2, len(rows) // 2) and page_no_like >= max(2, len(rows) // 2)


def _implicit_tables(page_raw: PageRaw) -> list[TableData]:
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

            rows = [[cell for cell in row.cells] for row in group]
            if _looks_like_toc(rows):
                i = j
                continue

            row_heights = [max(8.0, row.bbox[3] - row.bbox[1]) for row in group]
            anchors = group[0].anchors
            x_edges = sorted(anchors)
            if abs(x_edges[0] - x0) > 4:
                x_edges = [x0, *x_edges]
            x_edges = [*x_edges, x1]
            col_widths = [max(6.0, x_edges[idx + 1] - x_edges[idx]) for idx in range(len(x_edges) - 1)]
            cell_rows = [
                [
                    TableCellData(
                        text=text,
                        align="left",
                        bbox=(x_edges[c_idx], row.bbox[1], x_edges[min(c_idx + 1, len(x_edges) - 1)], row.bbox[3]),
                    )
                    for c_idx, text in enumerate(row.cells)
                ]
                for row in group
            ]

            confidence = min(0.78, 0.55 + len(group) * 0.03)
            fallback_to_image = len(group) > 24 or avg_cols > 7
            if confidence >= 0.60:
                tables.append(
                    TableData(
                        bbox=(x0, y0, x1, y1),
                        rows=rows,
                        cols_widths=col_widths,
                        row_heights=row_heights,
                        cells=cell_rows,
                        is_explicit_grid=False,
                        confidence=confidence,
                        fallback_to_image=fallback_to_image,
                    )
                )
            i = j
            continue

        i += 1

    return tables


def detect_tables(page_raw: PageRaw) -> list[TableData]:
    explicit = _explicit_tables(page_raw)
    implicit = _implicit_tables(page_raw)

    tables = list(explicit)
    for table in implicit:
        overlap = max((_bbox_overlap_ratio(table.bbox, ex.bbox) for ex in explicit), default=0.0)
        if overlap < 0.45:
            tables.append(table)

    tables.sort(key=lambda t: (t.bbox[1], t.bbox[0]))
    return tables
