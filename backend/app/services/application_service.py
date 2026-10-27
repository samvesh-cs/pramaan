from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.checklist.eoa_checklist import EOA_DOCUMENT_CHECKLIST
from app.models.application import Application
from app.models.document import Document
from app.models.finding import Finding
from app.utils.review_policy import finding_has_recorded_decision, finding_requires_reviewer_decision
from app.schemas.application import (
    ApplicationCreate,
    ApplicationDetailResponse,
    ApplicationResponse,
)
from app.schemas.document import DocumentResponse
from app.utils.id_generator import generate_id


class ApplicationService:
    async def create_application(
        self,
        db: AsyncSession,
        data: ApplicationCreate,
        owner_id: str | None = None,
    ) -> ApplicationResponse:
        app_id = generate_id("app")
        app_obj = Application(
            id=app_id,
            owner_id=owner_id,
            status="draft",
            institution_name=data.institution_name,
            application_category=data.application_category,
            academic_year=data.academic_year,
            overall_status="processing_incomplete",
        )
        db.add(app_obj)
        await db.commit()
        await db.refresh(app_obj)
        return ApplicationResponse.model_validate(app_obj)

    async def get_application(
        self,
        db: AsyncSession,
        application_id: str,
    ) -> ApplicationDetailResponse:
        stmt = (
            select(Application)
            .where(Application.id == application_id)
            .options(
                selectinload(Application.documents),
                selectinload(Application.findings),
            )
        )
        res = await db.execute(stmt)
        app_obj = res.scalar_one_or_none()

        if not app_obj:
            raise HTTPException(
                status_code=404,
                detail={"code": "APPLICATION_NOT_FOUND", "message": f"Application '{application_id}' not found.", "details": None},
            )

        response = ApplicationDetailResponse.model_validate(app_obj)
        response.documents = []
        for document in app_obj.documents:
            latest_extraction = max(
                document.extractions,
                key=lambda extraction: extraction.created_at,
                default=None,
            )
            document_response = DocumentResponse.model_validate(document)
            document_response.fields = latest_extraction.fields or {} if latest_extraction else {}
            response.documents.append(document_response)
        if app_obj.status != "review_completed":
            response.findings = []
        return response

    async def list_applications(
        self,
        db: AsyncSession,
        owner_id: str | None = None,
        status_filter: str | None = None,
    ) -> list[ApplicationResponse]:
        stmt = select(Application)
        if owner_id:
            stmt = stmt.where(Application.owner_id == owner_id)
        if status_filter:
            stmt = stmt.where(Application.status == status_filter)

        stmt = stmt.order_by(Application.created_at.desc())
        res = await db.execute(stmt)
        apps = res.scalars().all()
        return [ApplicationResponse.model_validate(a) for a in apps]

    async def submit_application(
        self,
        db: AsyncSession,
        application_id: str,
        owner_id: str,
    ) -> ApplicationResponse:
        app_obj = await db.scalar(
            select(Application).where(Application.id == application_id).with_for_update()
        )
        if not app_obj:
            raise HTTPException(
                status_code=404,
                detail={"code": "APPLICATION_NOT_FOUND", "message": f"Application '{application_id}' not found.", "details": None},
            )

        if app_obj.owner_id != owner_id:
            raise HTTPException(
                status_code=404,
                detail={"code": "APPLICATION_NOT_FOUND", "message": f"Application '{application_id}' not found.", "details": None},
            )

        if app_obj.status != "draft":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "APPLICATION_ALREADY_SUBMITTED",
                    "message": "This application has already been submitted and is locked for review.",
                    "details": None,
                },
            )

        required_types = {
            doc_type
            for doc_type, info in EOA_DOCUMENT_CHECKLIST.items()
            if info.get("applicability") == "required"
        }
        uploaded_types = set(
            (await db.scalars(
                select(Document.document_type).where(Document.application_id == app_obj.id)
            )).all()
        )
        missing_types = sorted(required_types - uploaded_types)
        if missing_types:
            labels = [EOA_DOCUMENT_CHECKLIST[doc_type]["display_name"] for doc_type in missing_types]
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "REQUIRED_DOCUMENTS_MISSING",
                    "message": f"Upload all required document types before submission: {', '.join(labels)}.",
                    "details": {"missing_document_types": missing_types},
                },
            )

        app_obj.status = "submitted"
        await db.commit()
        await db.refresh(app_obj)
        return ApplicationResponse.model_validate(app_obj)

    async def finalize_review(
        self,
        db: AsyncSession,
        application_id: str,
    ) -> ApplicationResponse:
        app_obj = await db.scalar(
            select(Application).where(Application.id == application_id).with_for_update()
        )
        if not app_obj:
            raise HTTPException(
                status_code=404,
                detail={"code": "APPLICATION_NOT_FOUND", "message": f"Application '{application_id}' not found.", "details": None},
            )
        if app_obj.status != "submitted":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "APPLICATION_NOT_PENDING_REVIEW",
                    "message": "Only an application pending review can be finalized.",
                    "details": None,
                },
            )

        findings = list((await db.scalars(
            select(Finding).where(Finding.application_id == application_id)
        )).all())
        if not findings:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "SCRUTINY_NOT_RUN",
                    "message": "Run scrutiny checks before finalizing this review.",
                    "details": None,
                },
            )

        pending_findings = [
            finding
            for finding in findings
            if finding_requires_reviewer_decision(finding)
            and not finding_has_recorded_decision(finding)
        ]
        if pending_findings:
            pending_count = len(pending_findings)
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "FINDINGS_PENDING_REVIEW",
                    "message": f"Review all {pending_count} remaining finding{'s' if pending_count != 1 else ''} before finalizing.",
                    "details": {
                        "pending_findings": pending_count,
                        "pending_finding_ids": [finding.id for finding in pending_findings],
                    },
                },
            )

        app_obj.status = "review_completed"
        await db.commit()
        await db.refresh(app_obj)
        return ApplicationResponse.model_validate(app_obj)


application_service = ApplicationService()

