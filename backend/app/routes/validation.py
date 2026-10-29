from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    get_current_user,
    require_application_access,
    require_role,
)
from app.database import get_db
from app.models.application import Application
from app.models.finding import Finding
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
    if application.status == "review_completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REVIEW_FINALIZED",
                "message": "Scrutiny has been finalized. The report is read-only.",
                "details": None,
            },
        )

    if current_user.role == "INSTITUTION" and application.status == "submitted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "APPLICATION_LOCKED",
                "message": "Application has been submitted and is locked for review.",
                "details": None,
            },
        )

    if current_user.role == "REVIEWER" and application.status == "submitted":
        existing_decision = await db.scalar(
            select(Finding.id)
            .where(
                Finding.application_id == application.id,
                or_(Finding.reviewer_decision.is_not(None), Finding.reviewed_at.is_not(None)),
            )
            .limit(1)
        )
        if existing_decision:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "SCRUTINY_HAS_REVIEW_DECISIONS",
                    "message": "Checks cannot be rerun after a reviewer decision is recorded because rerunning would replace the audit findings.",
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the reviewer workspace, or the finalized report for the owning institution."""
    if current_user.role == "INSTITUTION" and application.status != "review_completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SCRUTINY_PENDING",
                "message": "The reviewer has not finalized scrutiny. The report will be available after review is complete.",
                "details": None,
            },
        )
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
    if application.status == "review_completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "REVIEW_FINALIZED", "message": "Scrutiny has been finalized. Reviewer decisions are read-only.", "details": None},
        )
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
    if application.status == "review_completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "REVIEW_FINALIZED", "message": "Scrutiny has been finalized. Reviewer decisions are read-only.", "details": None},
        )
    return await validation_engine.acknowledge_duplicate(
        db=db,
        application_id=application.id,
        finding_id=finding_id,
        reviewer_notes=payload.reviewer_notes,
        reviewed_by=current_user.email,
    )
