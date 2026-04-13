from __future__ import annotations

from dataclasses import dataclass

import fitz

from app.config import settings


@dataclass
class PdfPrecheckResult:
    page_count: int
    sampled_pages: int
    total_chars: int
    total_words: int
    total_spans: int
    avg_image_coverage: float
    is_text_pdf: bool
    reason: str


@dataclass
class ComplexityResult:
    too_complex: bool
    score: int
    reason: str


def _image_coverage_from_rawdict(rawdict: dict, page_area: float) -> float:
    if page_area <= 0:
        return 0.0
    image_area = 0.0
    for block in rawdict.get("blocks", []):
        if block.get("type") != 1:
            continue
        bbox = block.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        x0, y0, x1, y1 = bbox
        image_area += max(0.0, (x1 - x0) * (y1 - y0))
    return max(0.0, min(1.0, image_area / page_area))


def precheck_text_pdf(pdf_path: str, sample_pages: int | None = None) -> PdfPrecheckResult:
    sample_pages = sample_pages or settings.precheck_pages
    with fitz.open(pdf_path) as doc:
        page_count = doc.page_count
        pages_to_check = min(page_count, max(1, sample_pages))

        total_chars = 0
        total_words = 0
        total_spans = 0
        total_coverage = 0.0

        for page_idx in range(pages_to_check):
            page = doc[page_idx]
            text = page.get_text("text")
            total_chars += len(text.strip())

            words = page.get_text("words")
            total_words += len(words)

            rawdict = page.get_text("rawdict")
            for block in rawdict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    total_spans += len(line.get("spans", []))

            page_area = float(page.rect.width * page.rect.height)
            total_coverage += _image_coverage_from_rawdict(rawdict, page_area)

    avg_coverage = total_coverage / pages_to_check

    low_text = total_chars < (pages_to_check * 60) and total_words < (pages_to_check * 12)
    weak_structure = total_spans < (pages_to_check * 8)
    heavy_image = avg_coverage > 0.7

    is_text_pdf = not (low_text and weak_structure and heavy_image)
    reason = "ok" if is_text_pdf else "non-text pdf detected"

    return PdfPrecheckResult(
        page_count=page_count,
        sampled_pages=pages_to_check,
        total_chars=total_chars,
        total_words=total_words,
        total_spans=total_spans,
        avg_image_coverage=avg_coverage,
        is_text_pdf=is_text_pdf,
        reason=reason,
    )


def inspect_complexity(pdf_path: str, max_score: int | None = None) -> ComplexityResult:
    max_score = max_score or settings.worker_complexity_limit
    score = 0

    with fitz.open(pdf_path) as doc:
        for page in doc:
            rawdict = page.get_text("rawdict")
            blocks = rawdict.get("blocks", [])
            score += len(blocks) * 20
            for block in blocks:
                if block.get("type") == 0:
                    lines = block.get("lines", [])
                    score += len(lines) * 10
                    for line in lines:
                        spans = line.get("spans", [])
                        score += len(spans) * 4
                        for span in spans:
                            score += len(span.get("text", ""))
                elif block.get("type") == 1:
                    score += 60

            if score > max_score:
                return ComplexityResult(
                    too_complex=True,
                    score=score,
                    reason="page complexity limit exceeded",
                )

    return ComplexityResult(too_complex=False, score=score, reason="ok")
