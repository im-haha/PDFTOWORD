from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import fitz


@dataclass
class SpanRaw:
    text: str
    bbox: tuple[float, float, float, float]
    font: str
    size: float
    flags: int
    color: int


@dataclass
class LineRaw:
    bbox: tuple[float, float, float, float]
    spans: list[SpanRaw] = field(default_factory=list)


@dataclass
class TextBlockRaw:
    bbox: tuple[float, float, float, float]
    lines: list[LineRaw] = field(default_factory=list)


@dataclass
class ImageBlockRaw:
    bbox: tuple[float, float, float, float]
    image_path: str


@dataclass
class PageRaw:
    page_no: int
    width: float
    height: float
    rotation: int
    text_blocks: list[TextBlockRaw] = field(default_factory=list)
    image_blocks: list[ImageBlockRaw] = field(default_factory=list)


@dataclass
class PdfRawDocument:
    pages: list[PageRaw] = field(default_factory=list)


def _bbox_to_tuple(bbox: list[float] | tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = bbox
    return float(x0), float(y0), float(x1), float(y1)


def _save_image_clip(page: fitz.Page, bbox: tuple[float, float, float, float], output_path: Path) -> bool:
    rect = fitz.Rect(*bbox)
    if rect.width <= 1 or rect.height <= 1:
        return False
    pix = page.get_pixmap(clip=rect, dpi=160, alpha=False)
    if pix.width <= 1 or pix.height <= 1:
        return False
    pix.save(str(output_path))
    return True


def read_pdf_raw(pdf_path: str, temp_image_dir: Path) -> PdfRawDocument:
    temp_image_dir.mkdir(parents=True, exist_ok=True)

    pages: list[PageRaw] = []
    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc):
            text_dict = page.get_text("dict")
            page_raw = PageRaw(
                page_no=page_index + 1,
                width=float(page.rect.width),
                height=float(page.rect.height),
                rotation=int(page.rotation),
            )

            image_seq = 0
            for block in text_dict.get("blocks", []):
                btype = block.get("type")
                bbox = _bbox_to_tuple(block.get("bbox", [0.0, 0.0, 0.0, 0.0]))

                if btype == 0:
                    text_block = TextBlockRaw(bbox=bbox)
                    for line in block.get("lines", []):
                        line_bbox = _bbox_to_tuple(line.get("bbox", [0.0, 0.0, 0.0, 0.0]))
                        line_raw = LineRaw(bbox=line_bbox)
                        for span in line.get("spans", []):
                            text = span.get("text", "")
                            if text == "":
                                continue
                            line_raw.spans.append(
                                SpanRaw(
                                    text=text,
                                    bbox=_bbox_to_tuple(span.get("bbox", [0.0, 0.0, 0.0, 0.0])),
                                    font=span.get("font", ""),
                                    size=float(span.get("size", 11.0)),
                                    flags=int(span.get("flags", 0)),
                                    color=int(span.get("color", 0)),
                                )
                            )
                        if line_raw.spans:
                            text_block.lines.append(line_raw)
                    if text_block.lines:
                        page_raw.text_blocks.append(text_block)

                elif btype == 1:
                    image_seq += 1
                    image_path = temp_image_dir / f"p{page_index + 1:04d}_img{image_seq:03d}.png"
                    saved = _save_image_clip(page, bbox, image_path)
                    if saved:
                        page_raw.image_blocks.append(ImageBlockRaw(bbox=bbox, image_path=str(image_path)))

            pages.append(page_raw)

    return PdfRawDocument(pages=pages)
