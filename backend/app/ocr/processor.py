"""Document processing orchestrator.
Provides the primary interface: process_document(file_path) -> ExtractionResult
"""

import os
import logging
from pathlib import Path
from typing import Optional, Union

from .models import ExtractionResult, PageResult
from .pdf_processor import process_pdf, process_image_file
from .field_extractor import extract_fields

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


def infer_document_type(pages: list[PageResult]) -> Optional[str]:
    """Heuristic helper to guess document type from content if not explicitly supplied."""
    full_text = "\n".join(p.text.lower() for p in pages)
    if "fire" in full_text and ("safety" in full_text or "noc" in full_text):
        return "fire_safety_certificate"
    if "stability" in full_text or "structural" in full_text:
        return "structural_stability_certificate"
    if "deed" in full_text or "land" in full_text or "khasra" in full_text:
        return "land_title_deed"
    return None


def process_document(
    file_path: Union[str, Path],
    document_type: Optional[str] = None,
    document_id: Optional[str] = None
) -> ExtractionResult:
    """Process a document file (PDF, JPG, PNG) and return structured ExtractionResult.

    Complies with docs/API_CONTRACT.md section 5.
    Never crashes on invalid, corrupt, or unsupported files; returns
    processing_status="processing_failed" with error description.
    """
    path = Path(file_path)

    # 1. Check file existence
    if not path.exists() or not path.is_file():
        return ExtractionResult(
            document_id=document_id,
            document_type=document_type,
            processing_status="processing_failed",
            error=f"File not found: {file_path}"
        )

    # 2. Check supported extension
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return ExtractionResult(
            document_id=document_id,
            document_type=document_type,
            processing_status="processing_failed",
            error=f"Unsupported file type '{ext}'. Supported types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # 3. Process pages
    try:
        if ext == ".pdf":
            pages = process_pdf(path)
        else:
            pages = process_image_file(path)
    except Exception as e:
        logger.error("Processing failed for %s: %s", path.name, e)
        return ExtractionResult(
            document_id=document_id,
            document_type=document_type,
            processing_status="processing_failed",
            error=f"Document parsing error: {str(e)}"
        )

    # 4. Resolve document type
    resolved_type = document_type
    if not resolved_type:
        resolved_type = infer_document_type(pages) or "unknown"

    # 5. Extract fields
    try:
        fields = extract_fields(resolved_type, pages)
    except Exception as e:
        logger.warning("Field extraction encountered error: %s", e)
        fields = {}

    return ExtractionResult(
        document_id=document_id,
        document_type=resolved_type,
        processing_status="processed",
        pages=pages,
        fields=fields,
        error=None
    )
