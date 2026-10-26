"""OCR and Document Extraction Package.
Exports process_document and models matching docs/API_CONTRACT.md section 5.
"""

from .models import ExtractionResult, PageResult, Region, ExtractedField
from .processor import process_document
from .ocr_service import run_ocr_on_image
from .pdf_processor import process_pdf, process_image_file
from .field_extractor import extract_fields

__all__ = [
    "process_document",
    "ExtractionResult",
    "PageResult",
    "Region",
    "ExtractedField",
    "run_ocr_on_image",
    "process_pdf",
    "process_image_file",
    "extract_fields",
]
