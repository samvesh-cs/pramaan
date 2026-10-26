from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.application import (
    ApplicationCreate,
    ApplicationDetailResponse,
    ApplicationResponse,
)
from app.services.application_service import application_service

router = APIRouter(prefix="/applications", tags=["Applications"])


@router.post(
    "",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create institutional application",
)
async def create_application(
    payload: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new institutional application record."""
    return await application_service.create_application(db, payload)


@router.get(
    "",
    response_model=list[ApplicationResponse],
    summary="List all applications",
)
async def list_applications(
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all institutional applications."""
    return await application_service.list_applications(db)


@router.get(
    "/{application_id}",
    response_model=ApplicationDetailResponse,
    summary="Get application details",
)
async def get_application(
    application_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get application details with documents and findings."""
    return await application_service.get_application(db, application_id)
