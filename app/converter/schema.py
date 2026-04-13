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
    runs: list[RunData] = field(default_factory=list)


@dataclass
class TableData:
    bbox: tuple[float, float, float, float]
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class ImageData:
    bbox: tuple[float, float, float, float]
    image_path: str


@dataclass
class PageLayout:
    page_no: int
    width: float
    height: float
    rotation: int
    paragraphs: list[ParagraphData] = field(default_factory=list)
    tables: list[TableData] = field(default_factory=list)
    images: list[ImageData] = field(default_factory=list)


@dataclass
class DocumentLayout:
    pages: list[PageLayout] = field(default_factory=list)
