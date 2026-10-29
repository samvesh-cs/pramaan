"""Document processing orchestrator.
Provides the primary interface: process_document(file_path) -> ExtractionResult
"""

import os
import logging
from pathlib import Path
from typing import Optional, Union

from .models import ExtractionResult, PageResult, ExtractedField
from .pdf_processor import process_pdf, process_image_file
from .field_extractor import extract_fields
from .qr_processor import extract_qr_from_document

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


def infer_document_type(pages: list[PageResult]) -> Optional[str]:
    """Heuristic helper to guess document type from content if not explicitly supplied."""
    full_text = "\n".join(p.text.lower() for p in pages)
    if "fire" in full_text and ("safety" in full_text or "noc" in full_text or "rescue" in full_text):
        return "fire_safety_certificate"
    if "affidavit" in full_text or "deponent" in full_text or "sworn" in full_text or "notary" in full_text:
        return "affidavit_2"
    if "completion" in full_text or "occupancy" in full_text or "building license" in full_text or "form d" in full_text:
        return "building_completion_certificate"
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

    Complies with docs/API_CONTRACT.md section 5 and SIH 2026 PS 26261.
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

    # 2b. Skip OCR processing for presence-only document types (no required extraction fields)
    from app.checklist.eoa_checklist import EOA_DOCUMENT_CHECKLIST
    chk_entry = EOA_DOCUMENT_CHECKLIST.get(document_type or "")
    if chk_entry and chk_entry.get("required_fields") == []:
        return ExtractionResult(
            document_id=document_id,
            document_type=document_type,
            processing_status="processed",
            pages=[],
            fields={},
            error=None,
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

    if not any(page.text.strip() for page in pages):
        return ExtractionResult(
            document_id=document_id,
            document_type=document_type,
            processing_status="processing_failed",
            pages=pages,
            error="No readable text could be extracted from the document.",
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

    # 6. Extract QR code (Pillar 3 digital issuing authority verification)
    try:
        qr_data = extract_qr_from_document(path)
        if qr_data and qr_data.get("detected"):
            fields["qr_code"] = ExtractedField(
                value=qr_data.get("parsed"),
                raw_text=qr_data.get("raw_text"),
                confidence=1.0,
                page_number=qr_data.get("page_number", 1),
                bbox=qr_data.get("bbox"),
                status="extracted",
            )
            # If certificate number was missing from text OCR but present in QR code, augment it
            parsed = qr_data.get("parsed") or {}
            if "certificate_number" in fields and not fields["certificate_number"].value and parsed.get("certificate_number"):
                fields["certificate_number"] = ExtractedField(
                    value=parsed["certificate_number"],
                    raw_text=qr_data.get("raw_text"),
                    confidence=1.0,
                    page_number=qr_data.get("page_number", 1),
                    bbox=qr_data.get("bbox"),
                    status="extracted",
                )
    except Exception as e:
        logger.warning("QR code extraction encountered error: %s", e)

    return ExtractionResult(
        document_id=document_id,
        document_type=resolved_type,
        processing_status="processed",
        pages=pages,
        fields=fields,
        error=None
    )
