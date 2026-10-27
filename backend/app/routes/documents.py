from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
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

