from __future__ import annotations

from typing import Any

from app.converter.pdf_reader import PdfRawDocument
from app.converter.schema import DocumentLayout


def build_quality_report(
    *,
    mode: str,
    raw_doc: PdfRawDocument | None,
    layout: DocumentLayout | None,
    font_substitutions: dict[str, Any],
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    warnings = warnings or []

    if mode == "visual_exact":
        page_count = len(raw_doc.pages) if raw_doc else 0
        return {
            "mode": mode,
            "paragraphCount": 0,
            "tableCount": 0,
            "imageCount": page_count,
            "fontSubstitutionCount": 0,
            "fallbackBlockCount": page_count,
            "layoutWarningCount": page_count,
            "warnings": [
                "visual_exact uses page snapshots; deep text editing is not guaranteed",
                *warnings,
            ],
            "pageReports": [
                {
                    "pageNo": idx + 1,
                    "columnCount": 1,
                    "paragraphCount": 0,
                    "tableCount": 0,
                    "imageCount": 1,
                    "layoutWarnings": ["page rendered as image"],
                }
                for idx in range(page_count)
            ],
            "fontSubstitutions": {},
            "degradedTables": 0,
            "fallbackRegions": page_count,
            "qualityGrade": "C",
        }

    if not layout:
        return {
            "mode": mode,
            "paragraphCount": 0,
            "tableCount": 0,
            "imageCount": 0,
            "fontSubstitutionCount": 0,
            "fallbackBlockCount": 0,
            "layoutWarningCount": len(warnings),
            "warnings": warnings,
            "pageReports": [],
            "fontSubstitutions": font_substitutions,
            "degradedTables": 0,
            "fallbackRegions": 0,
            "qualityGrade": "D",
        }

    paragraph_count = sum(len(page.paragraphs) for page in layout.pages)
    table_count = sum(len(page.tables) for page in layout.pages)
    image_count = sum(len(page.images) for page in layout.pages)
    degraded_tables = sum(1 for page in layout.pages for table in page.tables if table.fallback_to_image)
    fallback_regions = degraded_tables + sum(1 for page in layout.pages for img in page.images if img.is_degraded_snapshot)
    page_warning_count = sum(len(page.layout_warnings) for page in layout.pages)
    font_sub_count = int(font_substitutions.get("total", 0)) if font_substitutions else 0

    page_reports = [
        {
            "pageNo": page.page_no,
            "columnCount": page.column_count,
            "paragraphCount": len(page.paragraphs),
            "tableCount": len(page.tables),
            "imageCount": len(page.images),
            "layoutWarnings": page.layout_warnings,
        }
        for page in layout.pages
    ]

    all_warnings = [*warnings]
    for page in layout.pages:
        all_warnings.extend(page.layout_warnings)

    quality_grade = "A"
    risk_score = 0
    risk_score += min(3, degraded_tables)
    risk_score += min(3, fallback_regions)
    risk_score += min(3, page_warning_count // 2)
    risk_score += min(3, font_sub_count // 8)
    if risk_score >= 7:
        quality_grade = "C"
    elif risk_score >= 4:
        quality_grade = "B"

    return {
        "mode": mode,
        "paragraphCount": paragraph_count,
        "tableCount": table_count,
        "imageCount": image_count,
        "fontSubstitutionCount": font_sub_count,
        "fallbackBlockCount": fallback_regions,
        "layoutWarningCount": page_warning_count,
        "warnings": all_warnings,
        "pageReports": page_reports,
        "fontSubstitutions": font_substitutions,
        "degradedTables": degraded_tables,
        "fallbackRegions": fallback_regions,
        "qualityGrade": quality_grade,
    }
