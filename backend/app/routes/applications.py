from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_user,
    require_application_access,
    require_role,
)
from app.database import get_db
from app.models.application import Application
from app.models.user import User
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
    current_user: User = Depends(require_role("INSTITUTION")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new institutional application record."""
    return await application_service.create_application(
        db, payload, owner_id=current_user.id
    )


@router.get(
    "",
    response_model=list[ApplicationResponse],
    summary="List all applications (scoped by user role)",
)
async def list_applications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve applications scoped by user role: institution sees own, reviewer sees submitted."""
    if current_user.role == "INSTITUTION":
        return await application_service.list_applications(db, owner_id=current_user.id)
    elif current_user.role == "REVIEWER":
        return await application_service.list_applications(db, status_filter="submitted")
    return []


@router.get(
    "/{application_id}",
    response_model=ApplicationDetailResponse,
    summary="Get application details",
)
async def get_application(
    application_id: str,
    application: Application = Depends(require_application_access),
    db: AsyncSession = Depends(get_db),
):
    """Get application details with documents and findings (scoped by role and ownership)."""
    return await application_service.get_application(db, application.id)


@router.post(
    "/{application_id}/submit",
    response_model=ApplicationResponse,
    summary="Submit institutional application for AICTE review",
)
async def submit_application(
    application_id: str,
    current_user: User = Depends(require_role("INSTITUTION")),
    db: AsyncSession = Depends(get_db),
):
    """Submit application for review. Application becomes locked for institution edits."""
    return await application_service.submit_application(
        db, application_id, owner_id=current_user.id
    )


@router.post(
    "/{application_id}/finalize-review",
    response_model=ApplicationResponse,
    summary="Finalize reviewer scrutiny",
)
async def finalize_application_review(
    application_id: str,
    current_user: User = Depends(require_role("REVIEWER")),
    db: AsyncSession = Depends(get_db),
):
    """Finalize a submitted application after every generated finding has a reviewer decision."""
    application = await db.get(Application, application_id)
    if not application or application.status not in ("submitted", "review_completed"):
        raise HTTPException(
            status_code=404,
            detail={"code": "APPLICATION_NOT_FOUND", "message": f"Application '{application_id}' not found or not submitted.", "details": None},
        )
    return await application_service.finalize_review(db, application_id)

