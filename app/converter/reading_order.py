from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

from app.converter.schema import ParagraphData


@dataclass
class ReadingOrderResult:
    paragraphs: list[ParagraphData] = field(default_factory=list)
    column_count: int = 1
    column_bboxes: list[tuple[float, float, float, float]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _sorted(items: list[ParagraphData]) -> list[ParagraphData]:
    return sorted(items, key=lambda p: (p.bbox[1], p.bbox[0]))


def _bbox_union(items: list[ParagraphData]) -> tuple[float, float, float, float]:
    return (
        min(p.bbox[0] for p in items),
        min(p.bbox[1] for p in items),
        max(p.bbox[2] for p in items),
        max(p.bbox[3] for p in items),
    )


def analyze_reading_order(
    paragraphs: list[ParagraphData],
    page_width: float,
    page_height: float,
) -> ReadingOrderResult:
    if not paragraphs:
        return ReadingOrderResult(paragraphs=[])

    body = [p for p in paragraphs if p.role not in {"header", "footer", "footnote"}]
    if len(body) < 8:
        return ReadingOrderResult(paragraphs=_sorted(paragraphs))

    split_x = page_width * 0.5
    left = [p for p in body if (p.bbox[0] + p.bbox[2]) / 2 <= split_x]
    right = [p for p in body if (p.bbox[0] + p.bbox[2]) / 2 > split_x]

    if len(left) < 4 or len(right) < 4:
        return ReadingOrderResult(paragraphs=_sorted(paragraphs))

    left_x1 = median(p.bbox[2] for p in left)
    right_x0 = median(p.bbox[0] for p in right)
    left_y0 = min(p.bbox[1] for p in left)
    left_y1 = max(p.bbox[3] for p in left)
    right_y0 = min(p.bbox[1] for p in right)
    right_y1 = max(p.bbox[3] for p in right)
    y_overlap = max(0.0, min(left_y1, right_y1) - max(left_y0, right_y0))

    # Guard against false positives from occasional right-aligned snippets.
    if right_x0 - left_x1 < 18 or y_overlap < page_height * 0.25:
        return ReadingOrderResult(paragraphs=_sorted(paragraphs))

    left_ids = {id(p) for p in left}
    right_ids = {id(p) for p in right}
    headers = [p for p in paragraphs if p.role == "header"]
    footers = [p for p in paragraphs if p.role == "footer"]
    others = [
        p
        for p in paragraphs
        if id(p) not in left_ids and id(p) not in right_ids and p.role not in {"header", "footer"}
    ]

    ordered: list[ParagraphData] = []
    ordered.extend(_sorted(headers))
    ordered.extend(_sorted(left))
    ordered.extend(_sorted(right))
    ordered.extend(_sorted(others))
    ordered.extend(_sorted(footers))

    columns = [
        _bbox_union(left),
        _bbox_union(right),
    ]

    return ReadingOrderResult(
        paragraphs=ordered,
        column_count=2,
        column_bboxes=columns,
        warnings=["detected multi-column page; restored reading order by columns"],
    )
