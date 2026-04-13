from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RunData:
    text: str
    font_name: str
    font_size: float
    bold: bool
    italic: bool
    color: tuple[int, int, int] | None


@dataclass
class ParagraphData:
    bbox: tuple[float, float, float, float]
    align: str
    left_indent: float
    right_indent: float
    first_line_indent: float
    line_spacing: float
    space_before: float
    space_after: float
    role: str = "body"
    keep_with_next: bool = False
    hanging_indent: float = 0.0
    tab_stops: list[float] = field(default_factory=list)
    confidence: float = 0.0
    source_block_ids: list[str] = field(default_factory=list)
    runs: list[RunData] = field(default_factory=list)


@dataclass
class TableCellData:
    text: str
    rowspan: int = 1
    colspan: int = 1
    align: str = "left"
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


@dataclass
class TableData:
    bbox: tuple[float, float, float, float]
    rows: list[list[str]] = field(default_factory=list)
    cols_widths: list[float] = field(default_factory=list)
    row_heights: list[float] = field(default_factory=list)
    cells: list[list[TableCellData]] = field(default_factory=list)
    is_explicit_grid: bool = False
    confidence: float = 0.0
    fallback_to_image: bool = False


@dataclass
class ImageData:
    bbox: tuple[float, float, float, float]
    image_path: str
    anchor_x: float = 0.0
    anchor_y: float = 0.0
    inline_preferred: bool = True
    related_paragraph_index: int | None = None
    is_degraded_snapshot: bool = False
    is_icon: bool = False


@dataclass
class PageLayout:
    page_no: int
    width: float
    height: float
    rotation: int
    content_bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    header_bbox: tuple[float, float, float, float] | None = None
    footer_bbox: tuple[float, float, float, float] | None = None
    column_count: int = 1
    column_bboxes: list[tuple[float, float, float, float]] = field(default_factory=list)
    layout_warnings: list[str] = field(default_factory=list)
    paragraphs: list[ParagraphData] = field(default_factory=list)
    tables: list[TableData] = field(default_factory=list)
    images: list[ImageData] = field(default_factory=list)


@dataclass
class DocumentLayout:
    pages: list[PageLayout] = field(default_factory=list)
