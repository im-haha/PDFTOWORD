from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import fitz


@dataclass
class CharRaw:
    text: str
    bbox: tuple[float, float, float, float]


@dataclass
class WordRaw:
    text: str
    bbox: tuple[float, float, float, float]
    block_no: int
    line_no: int
    word_no: int


@dataclass
class DrawingRaw:
    kind: str
    bbox: tuple[float, float, float, float]
    stroke_width: float


@dataclass
class SpanRaw:
    text: str
    bbox: tuple[float, float, float, float]
    font: str
    size: float
    flags: int
    color: int
    chars: list[CharRaw] = field(default_factory=list)
    block_id: str = ""
    line_id: str = ""
    span_id: str = ""


@dataclass
class LineRaw:
    bbox: tuple[float, float, float, float]
    spans: list[SpanRaw] = field(default_factory=list)
    block_id: str = ""
    line_id: str = ""
    text: str = ""


@dataclass
class TextBlockRaw:
    bbox: tuple[float, float, float, float]
    lines: list[LineRaw] = field(default_factory=list)
    block_id: str = ""


@dataclass
class ImageBlockRaw:
    bbox: tuple[float, float, float, float]
    image_path: str
    page_no: int
    is_icon: bool = False
    related_text_block_id: str | None = None


@dataclass
class PageRaw:
    page_no: int
    width: float
    height: float
    rotation: int
    effective_rotation: int
    text_blocks: list[TextBlockRaw] = field(default_factory=list)
    image_blocks: list[ImageBlockRaw] = field(default_factory=list)
    words: list[WordRaw] = field(default_factory=list)
    drawings: list[DrawingRaw] = field(default_factory=list)


@dataclass
class PdfRawDocument:
    pages: list[PageRaw] = field(default_factory=list)


def _bbox_to_tuple(bbox: list[float] | tuple[float, float, float, float] | fitz.Rect) -> tuple[float, float, float, float]:
    if isinstance(bbox, fitz.Rect):
        return float(bbox.x0), float(bbox.y0), float(bbox.x1), float(bbox.y1)
    x0, y0, x1, y1 = bbox
    return float(x0), float(y0), float(x1), float(y1)


def _union_bbox(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    if not boxes:
        return 0.0, 0.0, 0.0, 0.0
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _save_image_clip(page: fitz.Page, bbox: tuple[float, float, float, float], output_path: Path) -> bool:
    rect = fitz.Rect(*bbox)
    if rect.width <= 1 or rect.height <= 1:
        return False
    pix = page.get_pixmap(clip=rect, dpi=160, alpha=False)
    if pix.width <= 1 or pix.height <= 1:
        return False
    pix.save(str(output_path))
    return True


def _extract_chars(span: dict) -> list[CharRaw]:
    chars: list[CharRaw] = []
    for char in span.get("chars", []):
        text = char.get("c", "")
        if text == "":
            continue
        chars.append(CharRaw(text=text, bbox=_bbox_to_tuple(char.get("bbox", [0.0, 0.0, 0.0, 0.0]))))
    return chars


def _is_tiny_icon(bbox: tuple[float, float, float, float]) -> bool:
    w = max(0.0, bbox[2] - bbox[0])
    h = max(0.0, bbox[3] - bbox[1])
    return w < 18.0 and h < 18.0


def _find_related_text_block_id(
    image_bbox: tuple[float, float, float, float],
    text_blocks: list[TextBlockRaw],
) -> str | None:
    if not text_blocks:
        return None

    ix0, iy0, ix1, iy1 = image_bbox
    icy = (iy0 + iy1) / 2

    best_id: str | None = None
    best_score = float("inf")
    for block in text_blocks:
        bx0, by0, bx1, by1 = block.bbox
        bcy = (by0 + by1) / 2
        v_dist = abs(icy - bcy)

        # Prefer nearby blocks with horizontal overlap.
        h_gap = max(0.0, max(bx0 - ix1, ix0 - bx1))
        score = v_dist * 1.2 + h_gap * 0.35
        if score < best_score:
            best_score = score
            best_id = block.block_id

    return best_id


def _drawing_bbox(drawing: dict) -> tuple[float, float, float, float] | None:
    rect = drawing.get("rect")
    if rect is not None:
        return _bbox_to_tuple(rect)

    boxes: list[tuple[float, float, float, float]] = []
    for item in drawing.get("items", []):
        for value in item:
            if isinstance(value, fitz.Point):
                boxes.append((value.x, value.y, value.x, value.y))
            elif isinstance(value, fitz.Rect):
                boxes.append(_bbox_to_tuple(value))
            elif isinstance(value, tuple) and len(value) == 2 and all(isinstance(v, (int, float)) for v in value):
                x, y = value
                boxes.append((float(x), float(y), float(x), float(y)))
    if not boxes:
        return None
    return _union_bbox(boxes)


def read_pdf_raw(pdf_path: str, temp_image_dir: Path) -> PdfRawDocument:
    temp_image_dir.mkdir(parents=True, exist_ok=True)

    pages: list[PageRaw] = []
    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc):
            raw_dict = page.get_text("rawdict")
            words_raw = page.get_text("words")
            drawings_raw = page.get_drawings()
            effective_rotation = int(page.rotation) % 360

            page_raw = PageRaw(
                page_no=page_index + 1,
                width=float(page.rect.width),
                height=float(page.rect.height),
                rotation=int(page.rotation),
                effective_rotation=effective_rotation,
            )

            for b_idx, block in enumerate(raw_dict.get("blocks", [])):
                if block.get("type") != 0:
                    continue

                block_id = f"p{page_index + 1}_b{b_idx}"
                text_block = TextBlockRaw(
                    bbox=_bbox_to_tuple(block.get("bbox", [0.0, 0.0, 0.0, 0.0])),
                    block_id=block_id,
                )
                for l_idx, line in enumerate(block.get("lines", [])):
                    line_id = f"{block_id}_l{l_idx}"
                    line_raw = LineRaw(
                        bbox=_bbox_to_tuple(line.get("bbox", [0.0, 0.0, 0.0, 0.0])),
                        block_id=block_id,
                        line_id=line_id,
                    )
                    for s_idx, span in enumerate(line.get("spans", [])):
                        chars = _extract_chars(span)
                        text = span.get("text", "")
                        if not text and chars:
                            text = "".join(ch.text for ch in chars)
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
                                chars=chars,
                                block_id=block_id,
                                line_id=line_id,
                                span_id=f"{line_id}_s{s_idx}",
                            )
                        )

                    if line_raw.spans:
                        line_raw.text = "".join(span.text for span in line_raw.spans)
                        text_block.lines.append(line_raw)

                if text_block.lines:
                    page_raw.text_blocks.append(text_block)

            image_seq = 0
            for block in raw_dict.get("blocks", []):
                if block.get("type") != 1:
                    continue

                bbox = _bbox_to_tuple(block.get("bbox", [0.0, 0.0, 0.0, 0.0]))
                image_seq += 1
                image_path = temp_image_dir / f"p{page_index + 1:04d}_img{image_seq:03d}.png"
                saved = _save_image_clip(page, bbox, image_path)
                if not saved:
                    continue

                page_raw.image_blocks.append(
                    ImageBlockRaw(
                        bbox=bbox,
                        image_path=str(image_path),
                        page_no=page_index + 1,
                        is_icon=_is_tiny_icon(bbox),
                        related_text_block_id=_find_related_text_block_id(bbox, page_raw.text_blocks),
                    )
                )

            for item in words_raw:
                if len(item) < 8:
                    continue
                x0, y0, x1, y1, text, block_no, line_no, word_no = item[:8]
                if not text:
                    continue
                page_raw.words.append(
                    WordRaw(
                        text=str(text),
                        bbox=(float(x0), float(y0), float(x1), float(y1)),
                        block_no=int(block_no),
                        line_no=int(line_no),
                        word_no=int(word_no),
                    )
                )

            for drawing in drawings_raw:
                bbox = _drawing_bbox(drawing)
                if not bbox:
                    continue
                w = max(0.0, bbox[2] - bbox[0])
                h = max(0.0, bbox[3] - bbox[1])
                if w < 2.0 or h < 2.0:
                    continue
                page_raw.drawings.append(
                    DrawingRaw(
                        kind=str(drawing.get("type", "path")),
                        bbox=bbox,
                        stroke_width=float(drawing.get("width", 1.0) or 1.0),
                    )
                )

            pages.append(page_raw)

    return PdfRawDocument(pages=pages)
