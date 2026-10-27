from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.finding import FindingResponse, FindingReviewUpdate, AcknowledgeDuplicateRequest
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
    db: AsyncSession = Depends(get_db),
):
    """Run all validation rules for an application and return the compliance report."""
    return await validation_engine.validate_application(db, application_id)


@router.get(
    "/report",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get validation report",
)
async def get_application_report(
    application_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the current validation report for an application."""
    return await validation_engine.get_report(db, application_id)


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
    db: AsyncSession = Depends(get_db),
):
    """Update finding with human reviewer verification or discrepancy confirmation."""
    return await validation_engine.review_finding(
        db=db,
        application_id=application_id,
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
    db: AsyncSession = Depends(get_db),
):
    """Record an authorized reviewer acknowledgment of a duplicate warning.
    After acknowledgment, the validation report can be generated and will still show the duplicate note.
    """
    return await validation_engine.acknowledge_duplicate(
        db=db,
        application_id=application_id,
        finding_id=finding_id,
        reviewer_notes=payload.reviewer_notes,
        reviewed_by=payload.reviewed_by or "AICTE Scrutiny Committee Auditor",
    )
