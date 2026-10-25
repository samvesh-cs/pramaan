from fastapi import APIRouter, Depends, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
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
    db: AsyncSession = Depends(get_db),
):
    """Upload a supporting document (PDF, JPG, or PNG) for the given application."""
    return await document_service.upload_document(
        db=db,
        application_id=application_id,
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
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all uploaded documents for the application."""
    return await document_service.list_documents(db, application_id)
