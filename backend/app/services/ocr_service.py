from pathlib import Path
from typing import Any

from app.ocr.processor import process_document


class ExtractionService:
    """
    Service integrating Person 2's OCR / extraction pipeline (app.ocr).
    Provides OCR extraction via PyMuPDF + PaddleOCR fallback, returning
    standard extraction structures matching API_CONTRACT.md §5.
    """

    async def extract(
        self,
        file_path: Path,
        document_type: str,
    ) -> dict[str, Any]:
        """
        Extract text, bounding regions, and key-value fields from a document.
        Returns a dictionary conforming to API_CONTRACT.md §5.
        """
        result = process_document(
            file_path=file_path,
            document_type=document_type,
        )

        pages_data = []
        for p in result.pages:
            pages_data.append({
                "page_number": p.page_number,
                "text": p.text,
                "regions": [
                    {
                        "text": r.text,
                        "confidence": r.confidence,
                        "bbox": r.bbox,
                    }
                    for r in p.regions
                ],
            })

        fields_data: dict[str, Any] = {}
        for fname, fval in result.fields.items():
            fields_data[fname] = {
                "value": fval.value,
                "normalized_value": fval.normalized_value,
                "raw_text": fval.raw_text,
                "confidence": fval.confidence,
                "page_number": fval.page_number,
                "bbox": fval.bbox,
                "status": fval.status,
            }

        return {
            "document_id": result.document_id or "",
            "document_type": result.document_type or document_type,
            "processing_status": result.processing_status,
            "pages": pages_data,
            "fields": fields_data,
            "error": result.error,
        }


extraction_service = ExtractionService()
