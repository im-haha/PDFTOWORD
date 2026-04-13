from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.converter.docx_writer import write_docx
from app.converter.font_mapper import get_font_substitutions, reset_font_substitutions
from app.converter.layout_analyzer import build_layout
from app.converter.pdf_reader import read_pdf_raw
from app.converter.quality_report import build_quality_report
from app.converter.visual_exact_writer import write_docx_visual_exact
from app.config import settings
from app.services.storage_service import build_temp_image_dir


@dataclass
class ConversionReport:
    mode: str
    paragraph_count: int
    table_detected: int
    image_detected: int
    font_substitution_count: int
    fallback_block_count: int
    layout_warning_count: int
    layout_warnings: list[str] = field(default_factory=list)
    page_reports: list[dict[str, Any]] = field(default_factory=list)
    font_substitutions: dict[str, Any] = field(default_factory=dict)
    degraded_tables: int = 0
    warnings: list[str] = field(default_factory=list)
    quality_grade: str = "B"
    font_match_rate: float = 0.0
    paragraph_align_match_rate: float = 0.0

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ConversionReport":
        font_sub_count = int(payload.get("fontSubstitutionCount", 0))
        warning_count = int(payload.get("layoutWarningCount", 0))
        fallback_count = int(payload.get("fallbackBlockCount", 0))

        font_match_rate = max(0.5, 1.0 - min(0.5, font_sub_count / 200))
        align_match_rate = max(0.5, 1.0 - min(0.5, (warning_count + fallback_count) / 200))

        return cls(
            mode=str(payload.get("mode", "editable")),
            paragraph_count=int(payload.get("paragraphCount", 0)),
            table_detected=int(payload.get("tableCount", 0)),
            image_detected=int(payload.get("imageCount", 0)),
            font_substitution_count=font_sub_count,
            fallback_block_count=fallback_count,
            layout_warning_count=warning_count,
            layout_warnings=list(payload.get("warnings", [])),
            page_reports=list(payload.get("pageReports", [])),
            font_substitutions=dict(payload.get("fontSubstitutions", {})),
            degraded_tables=int(payload.get("degradedTables", 0)),
            warnings=list(payload.get("warnings", [])),
            quality_grade=str(payload.get("qualityGrade", "B")),
            font_match_rate=font_match_rate,
            paragraph_align_match_rate=align_match_rate,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "paragraphCount": self.paragraph_count,
            "tableCount": self.table_detected,
            "imageCount": self.image_detected,
            "fontSubstitutionCount": self.font_substitution_count,
            "fallbackBlockCount": self.fallback_block_count,
            "layoutWarningCount": self.layout_warning_count,
            "warnings": self.warnings,
            "pageReports": self.page_reports,
            "fontSubstitutions": self.font_substitutions,
            "degradedTables": self.degraded_tables,
            "qualityGrade": self.quality_grade,
            # compatibility fields
            "fontMatchRate": self.font_match_rate,
            "paragraphAlignMatchRate": self.paragraph_align_match_rate,
        }


@dataclass
class ConversionResult:
    report: ConversionReport
    temp_dir: str


class ConvertService:
    def run(
        self,
        task_id: str,
        pdf_path: str,
        docx_path: str,
        progress_callback: Callable[[int], None] | None = None,
        conversion_mode: str = "visual_exact",
        detect_tables: bool = True,
        retain_layout: bool = True,
    ) -> ConversionResult:
        cb = progress_callback or (lambda _progress: None)

        cb(5)
        temp_dir = build_temp_image_dir(task_id)

        if conversion_mode == "visual_exact":
            page_count = write_docx_visual_exact(
                pdf_path=pdf_path,
                output_path=docx_path,
                temp_dir=temp_dir,
                dpi=settings.visual_exact_dpi,
            )
            cb(95)
            payload = build_quality_report(
                mode="visual_exact",
                raw_doc=None,
                layout=None,
                font_substitutions={},
                warnings=[f"rendered {page_count} pages as image snapshots"],
            )
            payload["imageCount"] = page_count
            payload["fallbackBlockCount"] = page_count
            payload["layoutWarningCount"] = page_count
            payload["pageReports"] = [
                {
                    "pageNo": idx + 1,
                    "columnCount": 1,
                    "paragraphCount": 0,
                    "tableCount": 0,
                    "imageCount": 1,
                    "layoutWarnings": ["page rendered as image"],
                }
                for idx in range(page_count)
            ]
            report = ConversionReport.from_payload(payload)
        else:
            reset_font_substitutions()
            raw_doc = read_pdf_raw(pdf_path, temp_dir)
            cb(35)

            layout = build_layout(raw_doc, detect_tables_enabled=detect_tables, retain_layout=retain_layout)
            cb(70)

            write_docx(layout, docx_path)
            cb(95)

            font_substitutions = get_font_substitutions()
            payload = build_quality_report(
                mode="editable",
                raw_doc=raw_doc,
                layout=layout,
                font_substitutions=font_substitutions,
                warnings=[] if retain_layout else ["retainLayout disabled: semantic flow prioritized"],
            )
            report = ConversionReport.from_payload(payload)

        cb(100)
        return ConversionResult(report=report, temp_dir=str(temp_dir))


convert_service = ConvertService()
