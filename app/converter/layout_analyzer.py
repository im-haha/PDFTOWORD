from __future__ import annotations

from app.converter.paragraph_builder import build_paragraphs
from app.converter.pdf_reader import PdfRawDocument
from app.converter.reading_order import analyze_reading_order
from app.converter.schema import DocumentLayout, ImageData, PageLayout, ParagraphData, TableData
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


def _union_bbox(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    if not boxes:
        return 0.0, 0.0, 0.0, 0.0
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _role_by_vertical_position(paragraph: ParagraphData, page_height: float) -> str:
    y0, y1 = paragraph.bbox[1], paragraph.bbox[3]
    if y1 <= page_height * 0.09:
        return "header"
    if y0 >= page_height * 0.91:
        return "footer"
    return paragraph.role


def _filter_paragraphs(
    paragraphs: list[ParagraphData],
    tables: list[TableData],
    layout_warnings: list[str],
) -> list[ParagraphData]:
    if not tables:
        return paragraphs

    kept: list[ParagraphData] = []
    for p in paragraphs:
        best_table: TableData | None = None
        best_overlap = 0.0

        for table in tables:
            overlap = _overlap_area_ratio(p.bbox, table.bbox)
            if overlap > best_overlap:
                best_overlap = overlap
                best_table = table

        if best_overlap <= 0.0 or not best_table:
            kept.append(p)
            continue

        if best_overlap >= 0.6 and best_table.confidence >= 0.75:
            # High-confidence table zone: remove overlapping paragraph to avoid
            # duplicate text in body and table.
            continue

        if best_overlap >= 0.35:
            p.role = "maybe_table"
            layout_warnings.append("kept overlapping paragraph in possible table zone")

        kept.append(p)

    return kept


def _apply_paragraph_spacing(paragraphs: list[ParagraphData], retain_layout: bool) -> None:
    if not paragraphs:
        return

    for idx, para in enumerate(paragraphs):
        if idx == 0:
            para.space_before = 0.0
            continue

        prev = paragraphs[idx - 1]
        same_row = abs(para.bbox[1] - prev.bbox[1]) <= 1.8
        gap = max(0.0, para.bbox[1] - prev.bbox[3])

        if same_row or gap <= 1.0:
            para.space_before = 0.0
        else:
            para.space_before = min(28.0, gap if retain_layout else gap * 0.55)

        if para.role in {"title", "subtitle"}:
            para.space_before = max(8.0, para.space_before)
            para.keep_with_next = True

        if prev.role in {"title", "subtitle"} and para.role == "body":
            para.space_before = max(5.0, para.space_before)


def _normalize_for_editability(paragraphs: list[ParagraphData]) -> None:
    for para in paragraphs:
        para.left_indent = min(para.left_indent, 28.0)
        para.right_indent = min(para.right_indent, 12.0)
        para.first_line_indent = max(-12.0, min(18.0, para.first_line_indent))
        para.hanging_indent = min(para.hanging_indent, 14.0)
        if para.role in {"header", "footer"}:
            para.keep_with_next = False


def _resolve_related_paragraph_index(paragraphs: list[ParagraphData], block_id: str | None, image_y: float) -> int | None:
    if not paragraphs:
        return None

    if block_id:
        for idx, para in enumerate(paragraphs):
            if block_id in para.source_block_ids:
                return idx

    nearest_idx = min(range(len(paragraphs)), key=lambda i: abs(paragraphs[i].bbox[1] - image_y))
    return int(nearest_idx)


def _build_page_regions(
    page_width: float,
    page_height: float,
    paragraphs: list[ParagraphData],
    tables: list[TableData],
    images: list[ImageData],
) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float] | None, tuple[float, float, float, float] | None]:
    header_boxes = [p.bbox for p in paragraphs if p.role == "header"]
    footer_boxes = [p.bbox for p in paragraphs if p.role == "footer"]

    body_boxes = [p.bbox for p in paragraphs if p.role not in {"header", "footer"}]
    body_boxes.extend(t.bbox for t in tables)
    body_boxes.extend(i.bbox for i in images if not i.is_icon)

    content_bbox = _union_bbox(body_boxes)
    if content_bbox == (0.0, 0.0, 0.0, 0.0):
        content_bbox = (36.0, page_height * 0.1, max(72.0, page_width - 36.0), page_height * 0.9)

    header_bbox = _union_bbox(header_boxes) if header_boxes else None
    footer_bbox = _union_bbox(footer_boxes) if footer_boxes else None

    return content_bbox, header_bbox, footer_bbox


def build_layout(
    raw_doc: PdfRawDocument,
    detect_tables_enabled: bool = True,
    retain_layout: bool = True,
) -> DocumentLayout:
    pages: list[PageLayout] = []

    for page_raw in raw_doc.pages:
        layout_warnings: list[str] = []
        tables = detect_tables(page_raw) if detect_tables_enabled else []

        paragraphs = build_paragraphs(page_raw)
        for para in paragraphs:
            para.role = _role_by_vertical_position(para, page_raw.height)

        paragraphs = _filter_paragraphs(paragraphs, tables, layout_warnings)

        order = analyze_reading_order(paragraphs, page_width=page_raw.width, page_height=page_raw.height)
        paragraphs = order.paragraphs
        layout_warnings.extend(order.warnings)

        _apply_paragraph_spacing(paragraphs, retain_layout=retain_layout)
        if not retain_layout:
            _normalize_for_editability(paragraphs)

        images: list[ImageData] = []
        for img in sorted(page_raw.image_blocks, key=lambda i: (i.bbox[1], i.bbox[0])):
            related_idx = _resolve_related_paragraph_index(paragraphs, img.related_text_block_id, img.bbox[1])
            images.append(
                ImageData(
                    bbox=img.bbox,
                    image_path=img.image_path,
                    anchor_x=img.bbox[0],
                    anchor_y=img.bbox[1],
                    inline_preferred=not img.is_icon,
                    related_paragraph_index=related_idx,
                    is_degraded_snapshot=False,
                    is_icon=img.is_icon,
                )
            )

        if any(img.is_icon for img in images):
            layout_warnings.append("small icon images detected and marked")

        content_bbox, header_bbox, footer_bbox = _build_page_regions(page_raw.width, page_raw.height, paragraphs, tables, images)

        pages.append(
            PageLayout(
                page_no=page_raw.page_no,
                width=page_raw.width,
                height=page_raw.height,
                rotation=page_raw.effective_rotation,
                content_bbox=content_bbox,
                header_bbox=header_bbox,
                footer_bbox=footer_bbox,
                column_count=order.column_count,
                column_bboxes=order.column_bboxes,
                layout_warnings=layout_warnings,
                paragraphs=paragraphs,
                tables=tables,
                images=images,
            )
        )

    return DocumentLayout(pages=pages)
