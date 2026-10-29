from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    require_application_access,
    require_role,
)
from app.database import get_db
from app.models.application import Application
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.services.document_service import document_service

router = APIRouter(prefix="/applications/{application_id}/documents", tags=["Documents"])


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload supporting document",
)
async def upload_document(
    application_id: str,
    file: UploadFile,
    document_type: str = Form(..., description="Document type code (e.g. fire_safety_certificate)"),
    application: Application = Depends(require_application_access),
    current_user: User = Depends(require_role("INSTITUTION")),
    db: AsyncSession = Depends(get_db),
):
    """Upload a supporting document (PDF, JPG, or PNG) for the given application."""
    if application.status in ("submitted", "review_completed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "APPLICATION_LOCKED",
                "message": "Application is locked for review and cannot accept new documents.",
                "details": None,
            },
        )

    return await document_service.upload_document(
        db=db,
        application_id=application.id,
        file=file,
        document_type=document_type,
    )


@router.get(
    "",
    response_model=list[DocumentResponse],
    summary="List uploaded documents",
)
async def list_documents(
    application_id: str,
    application: Application = Depends(require_application_access),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all uploaded documents for the application."""
    return await document_service.list_documents(db, application.id)


@router.get(
    "/{document_id}/file",
    summary="Stream document file for in-app preview",
)
async def get_document_file(
    application_id: str,
    document_id: str,
    application: Application = Depends(require_application_access),
    db: AsyncSession = Depends(get_db),
):
    """Serve uploaded document file (PDF, PNG, JPG) with inline content-disposition."""
    file_path, mime_type, filename = await document_service.get_document_file(
        db=db,
        application_id=application.id,
        document_id=document_id,
    )
    return FileResponse(
        path=file_path,
        media_type=mime_type,
        filename=filename,
        content_disposition_type="inline",
    )


@router.get(
    "/{document_id}/pages-info",
    summary="Get multi-page metadata and dimensions for high-resolution document viewer",
)
async def get_document_pages_info(
    application_id: str,
    document_id: str,
    application: Application = Depends(require_application_access),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve total page count and individual page dimensions for multi-page document navigation."""
    file_path, mime_type, filename = await document_service.get_document_file(
        db=db,
        application_id=application.id,
        document_id=document_id,
    )

    if mime_type.startswith("image/"):
        return {
            "document_id": document_id,
            "total_pages": 1,
            "pages": [{"page_number": 1, "width": 800.0, "height": 1100.0}],
        }

    import pymupdf as fitz
    try:
        doc = fitz.open(file_path)
        total_pages = len(doc)
        pages = [
            {
                "page_number": idx + 1,
                "width": round(doc[idx].rect.width, 2),
                "height": round(doc[idx].rect.height, 2),
            }
            for idx in range(total_pages)
        ]
        doc.close()
        return {
            "document_id": document_id,
            "total_pages": total_pages,
            "pages": pages,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read document pages info: {e}")


@router.get(
    "/{document_id}/page-image",
    summary="Render document page as high-resolution image for pinpoint evidence inspection",
)
async def get_document_page_image(
    application_id: str,
    document_id: str,
    page: int = 1,
    dpi: int = 150,
    application: Application = Depends(require_application_access),
    db: AsyncSession = Depends(get_db),
):
    """Render a specific document page as a high-resolution PNG image for visual evidence overlays."""
    file_path, mime_type, filename = await document_service.get_document_file(
        db=db,
        application_id=application.id,
        document_id=document_id,
    )

    if mime_type.startswith("image/"):
        return FileResponse(
            path=file_path,
            media_type=mime_type,
            filename=filename,
            headers={
                "X-Total-Pages": "1",
                "X-Current-Page": "1",
                "Access-Control-Expose-Headers": "X-Page-Width, X-Page-Height, X-Image-Width, X-Image-Height, X-Total-Pages, X-Current-Page",
            },
        )

    import pymupdf as fitz
    try:
        doc = fitz.open(file_path)
        total_pages = len(doc)
        if total_pages == 0:
            raise HTTPException(status_code=400, detail="Document contains no readable pages.")
        page_idx = max(0, min(page - 1, total_pages - 1))
        target_page = doc[page_idx]
        target_dpi = max(72, min(dpi, 300))
        pix = target_page.get_pixmap(dpi=target_dpi)
        png_bytes = pix.tobytes("png")
        page_width = round(target_page.rect.width, 2)
        page_height = round(target_page.rect.height, 2)
        doc.close()
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={
                "X-Page-Width": str(page_width),
                "X-Page-Height": str(page_height),
                "X-Image-Width": str(pix.width),
                "X-Image-Height": str(pix.height),
                "X-Total-Pages": str(total_pages),
                "X-Current-Page": str(page_idx + 1),
                "Access-Control-Expose-Headers": "X-Page-Width, X-Page-Height, X-Image-Width, X-Image-Height, X-Total-Pages, X-Current-Page",
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to render document page: {e}")
