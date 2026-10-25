from pathlib import Path
from fastapi import HTTPException
import pymupdf

from app.config import settings

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
}


class FileValidationError(HTTPException):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(
            status_code=status_code,
            detail={"code": code, "message": message, "details": None},
        )


def validate_file_metadata(filename: str, content_type: str, file_size: int) -> None:
    # 1. Extension check
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            code="UNSUPPORTED_FILE_TYPE",
            message=f"Unsupported file extension '{ext}'. Upload a PDF, JPG, or PNG file.",
        )

    # 2. Content type check
    if content_type.lower() not in ALLOWED_MIME_TYPES:
        raise FileValidationError(
            code="UNSUPPORTED_FILE_TYPE",
            message=f"Unsupported MIME type '{content_type}'. Upload a PDF, JPG, or PNG file.",
        )

    # 3. File size check
    if file_size > settings.max_file_size_bytes:
        raise FileValidationError(
            code="FILE_TOO_LARGE",
            message=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB} MB.",
        )


def validate_pdf_content(file_path: Path) -> int:
    """Validate PDF integrity and verify page count limits."""
    try:
        doc = pymupdf.open(file_path)
        page_count = len(doc)
        doc.close()
    except Exception as e:
        raise FileValidationError(
            code="INVALID_FILE_CONTENT",
            message=f"Corrupt or unreadable PDF document: {e}",
        )

    if page_count > settings.MAX_PAGES:
        raise FileValidationError(
            code="FILE_TOO_LARGE",
            message=f"PDF has {page_count} pages, which exceeds the maximum of {settings.MAX_PAGES} pages.",
        )

    return page_count
