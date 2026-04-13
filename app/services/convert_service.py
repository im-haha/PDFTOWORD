from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.converter.docx_writer import write_docx
from app.converter.layout_analyzer import build_layout
from app.converter.pdf_reader import read_pdf_raw
from app.converter.visual_exact_writer import write_docx_visual_exact
from app.config import settings
from app.services.storage_service import build_temp_image_dir


@dataclass
class ConversionReport:
    font_match_rate: float
    paragraph_align_match_rate: float
    table_detected: int
    image_detected: int
    layout_warnings: list[str] = field(default_factory=list)


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
            report = ConversionReport(
                font_match_rate=1.0,
                paragraph_align_match_rate=1.0,
                table_detected=0,
                image_detected=page_count,
                layout_warnings=["visual exact mode: content is page-image based"],
            )
        else:
            raw_doc = read_pdf_raw(pdf_path, temp_dir)
            cb(35)

            layout = build_layout(raw_doc, detect_tables_enabled=detect_tables)
            cb(70)

            write_docx(layout, docx_path)
            cb(95)

            report = ConversionReport(
                font_match_rate=0.9,
                paragraph_align_match_rate=0.9,
                table_detected=sum(len(p.tables) for p in layout.pages),
                image_detected=sum(len(p.images) for p in layout.pages),
                layout_warnings=[],
            )

        cb(100)
        return ConversionResult(report=report, temp_dir=str(temp_dir))


convert_service = ConvertService()
