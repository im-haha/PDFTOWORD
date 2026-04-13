from __future__ import annotations

from pathlib import Path
from statistics import median

from docx import Document
from docx.enum.section import WD_ORIENTATION, WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from app.converter.schema import DocumentLayout, ImageData, PageLayout, ParagraphData, TableCellData, TableData


DEFAULT_MARGIN_PT = 36.0


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _set_section_size(section, page: PageLayout) -> None:
    page_w = page.width
    page_h = page.height
    if page.rotation in {90, 270}:
        page_w, page_h = page_h, page_w

    section.orientation = WD_ORIENTATION.LANDSCAPE if page_w > page_h else WD_ORIENTATION.PORTRAIT
    section.page_width = Pt(page_w)
    section.page_height = Pt(page_h)

    cx0, cy0, cx1, cy1 = page.content_bbox
    if page.content_bbox == (0.0, 0.0, 0.0, 0.0):
        section.left_margin = Pt(DEFAULT_MARGIN_PT)
        section.right_margin = Pt(DEFAULT_MARGIN_PT)
        section.top_margin = Pt(DEFAULT_MARGIN_PT)
        section.bottom_margin = Pt(DEFAULT_MARGIN_PT)
        return

    left_margin = _clamp(cx0, 18.0, 72.0)
    right_margin = _clamp(page.width - cx1, 18.0, 72.0)
    top_margin = _clamp(cy0, 18.0, 90.0)
    bottom_margin = _clamp(page.height - cy1, 18.0, 90.0)

    section.left_margin = Pt(left_margin)
    section.right_margin = Pt(right_margin)
    section.top_margin = Pt(top_margin)
    section.bottom_margin = Pt(bottom_margin)


def _set_alignment(paragraph, align: str) -> None:
    if align == "center":
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align == "right":
        paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    elif align == "justify":
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    else:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT


def _append_run(paragraph, run_data) -> None:
    if run_data.text == "":
        return
    run = paragraph.add_run(run_data.text)
    run.font.name = run_data.font_name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), run_data.font_name)
    run.font.size = Pt(run_data.font_size)
    run.bold = run_data.bold
    run.italic = run_data.italic
    if run_data.color:
        r, g, b = run_data.color
        run.font.color.rgb = RGBColor(r, g, b)


def _apply_paragraph_format(paragraph, data: ParagraphData) -> None:
    fmt = paragraph.paragraph_format
    fmt.left_indent = Pt(data.left_indent)
    fmt.right_indent = Pt(max(0.0, data.right_indent))
    if data.hanging_indent > 0:
        fmt.first_line_indent = Pt(-data.hanging_indent)
    else:
        fmt.first_line_indent = Pt(data.first_line_indent)
    fmt.space_before = Pt(max(0.0, data.space_before))
    fmt.space_after = Pt(max(0.0, data.space_after))
    fmt.line_spacing = Pt(max(1.0, data.line_spacing))
    fmt.keep_with_next = bool(data.keep_with_next)

    for tab_pos in data.tab_stops:
        if tab_pos > 0:
            fmt.tab_stops.add_tab_stop(Pt(tab_pos))


def _write_paragraph(document: Document, data: ParagraphData) -> None:
    p = document.add_paragraph()
    _apply_paragraph_format(p, data)
    _set_alignment(p, data.align)

    for run_data in data.runs:
        _append_run(p, run_data)


def _vertical_overlap_ratio(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ay0, ay1 = a[1], a[3]
    by0, by1 = b[1], b[3]
    inter = max(0.0, min(ay1, by1) - max(ay0, by0))
    ah = max(1.0, ay1 - ay0)
    bh = max(1.0, by1 - by0)
    return inter / min(ah, bh)


def _same_row(a: ParagraphData, b: ParagraphData) -> bool:
    if abs(a.bbox[1] - b.bbox[1]) > 1.8:
        return False
    return _vertical_overlap_ratio(a.bbox, b.bbox) >= 0.6


def _group_paragraph_rows(paragraphs: list[ParagraphData]) -> list[list[ParagraphData]]:
    if not paragraphs:
        return []

    ordered = sorted(paragraphs, key=lambda p: (p.bbox[1], p.bbox[0]))
    rows: list[list[ParagraphData]] = []
    current: list[ParagraphData] = [ordered[0]]

    for para in ordered[1:]:
        if _same_row(current[0], para):
            current.append(para)
        else:
            rows.append(sorted(current, key=lambda p: p.bbox[0]))
            current = [para]

    if current:
        rows.append(sorted(current, key=lambda p: p.bbox[0]))

    return rows


def _looks_like_right_value(text: str) -> bool:
    plain = text.strip()
    if len(plain) > 16:
        return False
    return plain.replace(".", "").replace(",", "").replace("-", "").isdigit() or plain.endswith("%")


def _row_merge_confidence(row: list[ParagraphData]) -> float:
    if len(row) <= 1:
        return 1.0
    if any(item.role in {"list_item", "toc_line", "maybe_table"} for item in row):
        return 0.0

    conf = min(item.confidence for item in row)
    overlap = min(_vertical_overlap_ratio(row[idx].bbox, row[idx + 1].bbox) for idx in range(len(row) - 1))
    gap_penalty = max(0.0, max(row[idx + 1].bbox[0] - row[idx].bbox[2] for idx in range(len(row) - 1)))

    score = conf * 0.65 + overlap * 0.35
    if gap_penalty > 260:
        score -= 0.18
    return max(0.0, min(1.0, score))


def _write_row_paragraph(document: Document, row: list[ParagraphData], page: PageLayout) -> None:
    if len(row) == 1 or _row_merge_confidence(row) < 0.74:
        for item in row:
            _write_paragraph(document, item)
        return

    first = row[0]
    p = document.add_paragraph()
    _apply_paragraph_format(p, first)
    p.paragraph_format.left_indent = Pt(max(0.0, first.bbox[0] - DEFAULT_MARGIN_PT))
    p.paragraph_format.right_indent = Pt(0.0)
    p.paragraph_format.first_line_indent = Pt(0.0)
    p.paragraph_format.line_spacing = Pt(max(1.0, median(item.line_spacing for item in row)))
    p.paragraph_format.space_before = Pt(max(item.space_before for item in row))
    p.paragraph_format.space_after = Pt(max(item.space_after for item in row))
    _set_alignment(p, "left")

    for run_data in first.runs:
        _append_run(p, run_data)

    for idx, item in enumerate(row[1:], start=1):
        tab_pos = max(1.0, item.bbox[0] - DEFAULT_MARGIN_PT)
        is_last = idx == len(row) - 1
        item_text = "".join(run.text for run in item.runs)
        if is_last and _looks_like_right_value(item_text) and item.bbox[2] > page.width * 0.72:
            p.paragraph_format.tab_stops.add_tab_stop(Pt(tab_pos), alignment=WD_TAB_ALIGNMENT.RIGHT)
        else:
            p.paragraph_format.tab_stops.add_tab_stop(Pt(tab_pos), alignment=WD_TAB_ALIGNMENT.LEFT)
        p.add_run("\t")
        for run_data in item.runs:
            _append_run(p, run_data)


def _apply_cell_paragraph_style(cell, align: str) -> None:
    for paragraph in cell.paragraphs:
        if align == "center":
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif align == "right":
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        else:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)


def _write_table(document: Document, data: TableData) -> None:
    if not data.rows:
        return

    rows = len(data.rows)
    cols = max(len(row) for row in data.rows)
    if cols <= 0:
        return

    table = document.add_table(rows=rows, cols=cols)
    table.style = "Table Grid"
    table.autofit = False

    for c_idx, width in enumerate(data.cols_widths[:cols]):
        for row in table.rows:
            row.cells[c_idx].width = Pt(max(12.0, width))

    for r_idx in range(rows):
        if r_idx < len(data.row_heights):
            table.rows[r_idx].height = Pt(max(10.0, data.row_heights[r_idx]))

        for c_idx in range(cols):
            text = data.rows[r_idx][c_idx] if c_idx < len(data.rows[r_idx]) else ""
            table.cell(r_idx, c_idx).text = text

    if data.cells:
        for r_idx, cell_row in enumerate(data.cells):
            for c_idx, cell_data in enumerate(cell_row):
                if r_idx >= rows or c_idx >= cols:
                    continue
                cell = table.cell(r_idx, c_idx)
                cell.text = cell_data.text
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                _apply_cell_paragraph_style(cell, cell_data.align)

                if cell_data.rowspan > 1 or cell_data.colspan > 1:
                    end_r = min(rows - 1, r_idx + max(1, cell_data.rowspan) - 1)
                    end_c = min(cols - 1, c_idx + max(1, cell_data.colspan) - 1)
                    if end_r != r_idx or end_c != c_idx:
                        cell.merge(table.cell(end_r, end_c))


def _write_image(document: Document, page: PageLayout, image: ImageData) -> None:
    if image.is_icon:
        return

    img_path = Path(image.image_path)
    if not img_path.exists():
        return

    p = document.add_paragraph()
    if not image.inline_preferred:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    run = p.add_run()
    available_width = max(40.0, page.width - (DEFAULT_MARGIN_PT * 2))
    image_width = max(20.0, min(available_width, image.bbox[2] - image.bbox[0]))
    run.add_picture(str(img_path), width=Pt(image_width))


def _is_same_size(a: PageLayout, b: PageLayout) -> bool:
    return abs(a.width - b.width) < 1.0 and abs(a.height - b.height) < 1.0 and a.rotation == b.rotation


def write_docx(layout: DocumentLayout, output_path: str) -> None:
    document = Document()

    if not layout.pages:
        document.save(output_path)
        return

    current_section = document.sections[0]
    _set_section_size(current_section, layout.pages[0])

    for page_index, page in enumerate(layout.pages):
        if page_index > 0:
            prev_page = layout.pages[page_index - 1]
            if _is_same_size(prev_page, page):
                document.add_page_break()
            else:
                current_section = document.add_section(WD_SECTION.NEW_PAGE)
                _set_section_size(current_section, page)

        elements: list[tuple[float, str, object]] = []
        paragraph_rows = _group_paragraph_rows(page.paragraphs)
        for row in paragraph_rows:
            elements.append((min(item.bbox[1] for item in row), "paragraph_row", row))
        for table in page.tables:
            elements.append((table.bbox[1], "table", table))
        for image in page.images:
            elements.append((image.anchor_y if image.anchor_y else image.bbox[1], "image", image))

        elements.sort(key=lambda x: x[0])

        for _, kind, payload in elements:
            if kind == "paragraph_row":
                _write_row_paragraph(document, payload, page)  # type: ignore[arg-type]
            elif kind == "table":
                _write_table(document, payload)  # type: ignore[arg-type]
            elif kind == "image":
                _write_image(document, page, payload)  # type: ignore[arg-type]

    document.save(output_path)
