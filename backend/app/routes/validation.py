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
from app.schemas.finding import (
    AcknowledgeDuplicateRequest,
    FindingResponse,
    FindingReviewUpdate,
)
from app.schemas.report import ReportResponse
from app.services.validation_engine import validation_engine
from app.schemas.document import DocumentResponse

router = APIRouter(prefix="/applications/{application_id}", tags=["Validation"])


@router.post(
    "/validate",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger validation pipeline",
)
async def validate_application(
    application_id: str,
    application: Application = Depends(require_application_access),
    current_user: User = Depends(require_role("INSTITUTION", "REVIEWER")),
    db: AsyncSession = Depends(get_db),
):
    """Run all validation rules for an application and return the compliance report."""
    if current_user.role == "INSTITUTION" and application.status == "submitted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "APPLICATION_LOCKED",
                "message": "Application has been submitted and is locked for review.",
                "details": None,
            },
        )

    return await validation_engine.validate_application(db, application.id)


@router.get(
    "/report",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get validation report",
)
async def get_application_report(
    application_id: str,
    application: Application = Depends(require_application_access),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the current validation report for an application (scoped by ownership/role)."""
    return await validation_engine.get_report(db, application.id)


@router.patch(
    "/findings/{finding_id}",
    response_model=FindingResponse,
    status_code=status.HTTP_200_OK,
    summary="Record reviewer decision and justification notes on finding",
)
async def review_finding(
    application_id: str,
    finding_id: str,
    payload: FindingReviewUpdate,
    application: Application = Depends(require_application_access),
    current_user: User = Depends(require_role("REVIEWER")),
    db: AsyncSession = Depends(get_db),
):
    """Update finding with human reviewer verification or discrepancy confirmation (REVIEWER only)."""
    # Actor is strictly the authenticated reviewer user, never a client-supplied reviewed_by (D-021)
    payload.reviewed_by = current_user.email

    return await validation_engine.review_finding(
        db=db,
        application_id=application.id,
        finding_id=finding_id,
        review_data=payload,
    )

@router.post(
    "/duplicates/{finding_id}/acknowledge",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Acknowledge a duplicate warning after reviewer review",
)
async def acknowledge_duplicate(
    application_id: str,
    finding_id: str,
    payload: AcknowledgeDuplicateRequest,
    application: Application = Depends(require_application_access),
    current_user: User = Depends(require_role("REVIEWER")),
    db: AsyncSession = Depends(get_db),
):
    """Record an authorized reviewer acknowledgment of a duplicate warning.
    After acknowledgment, the validation report can be generated and will still show the duplicate note.
    """
    return await validation_engine.acknowledge_duplicate(
        db=db,
        application_id=application.id,
        finding_id=finding_id,
        reviewer_notes=payload.reviewer_notes,
        reviewed_by=current_user.email,
    )
