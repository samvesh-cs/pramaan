from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
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
        app_obj = await db.scalar(select(Application).where(Application.id == application_id))
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

        app_obj.status = "submitted"
        await db.commit()
        await db.refresh(app_obj)

        from app.models.finding import Finding
        existing_findings_count = await db.scalar(
            select(func.count()).select_from(Finding).where(Finding.application_id == app_obj.id)
        )
        if not existing_findings_count:
            from app.services.validation_engine import validation_engine
            await validation_engine.validate_application(db, app_obj.id)
            await db.refresh(app_obj)

        return ApplicationResponse.model_validate(app_obj)


application_service = ApplicationService()

