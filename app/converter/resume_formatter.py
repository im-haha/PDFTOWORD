from __future__ import annotations

from typing import Any

from docx import Document

import format_resume


def format_resume_docx(input_path: str, output_path: str) -> dict[str, Any]:
    """
    Apply the exact resume formatting pipeline defined in format_resume.py.
    """
    source_doc = Document(input_path)
    content = format_resume.extract_content(source_doc)
    output_doc = format_resume.build_resume(content)
    output_doc.save(output_path)
    return {
        "position": content.get("position", ""),
        "name": content.get("name", ""),
        "workExperienceCount": len(content.get("work_experience", [])),
        "skillCount": len(content.get("skills", [])),
        "projectCount": len(content.get("projects", [])),
    }
