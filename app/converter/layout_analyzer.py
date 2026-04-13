from __future__ import annotations

from app.converter.paragraph_builder import build_paragraphs
from app.converter.pdf_reader import PdfRawDocument
from app.converter.schema import DocumentLayout, ImageData, PageLayout, ParagraphData
from app.converter.table_detector import detect_tables


def _overlap_area_ratio(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b

    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)

    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0

    inter = (ix1 - ix0) * (iy1 - iy0)
    area = max(1.0, (ax1 - ax0) * (ay1 - ay0))
    return inter / area


def _filter_paragraphs(paragraphs: list[ParagraphData], table_bboxes: list[tuple[float, float, float, float]]) -> list[ParagraphData]:
    if not table_bboxes:
        return paragraphs

    kept: list[ParagraphData] = []
    for p in paragraphs:
        overlap = max((_overlap_area_ratio(p.bbox, tbox) for tbox in table_bboxes), default=0.0)
        if overlap < 0.5:
            kept.append(p)
    return kept


def _apply_paragraph_spacing(paragraphs: list[ParagraphData]) -> None:
    for idx in range(1, len(paragraphs)):
        prev = paragraphs[idx - 1]
        cur = paragraphs[idx]
        gap = max(0.0, cur.bbox[1] - prev.bbox[3])
        if gap <= 2:
            cur.space_before = 0.0
        else:
            cur.space_before = min(18.0, gap * 0.45)


def build_layout(raw_doc: PdfRawDocument, detect_tables_enabled: bool = True) -> DocumentLayout:
    pages: list[PageLayout] = []

    for page_raw in raw_doc.pages:
        tables = detect_tables(page_raw) if detect_tables_enabled else []
        table_bboxes = [t.bbox for t in tables]

        paragraphs = build_paragraphs(page_raw)
        paragraphs = _filter_paragraphs(paragraphs, table_bboxes)
        _apply_paragraph_spacing(paragraphs)

        images = [
            ImageData(bbox=img.bbox, image_path=img.image_path)
            for img in sorted(page_raw.image_blocks, key=lambda i: (i.bbox[1], i.bbox[0]))
        ]

        pages.append(
            PageLayout(
                page_no=page_raw.page_no,
                width=page_raw.width,
                height=page_raw.height,
                rotation=page_raw.rotation,
                paragraphs=paragraphs,
                tables=tables,
                images=images,
            )
        )

    return DocumentLayout(pages=pages)
