from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.application import Application
from app.schemas.application import (
    ApplicationCreate,
    ApplicationDetailResponse,
    ApplicationResponse,
)
from app.utils.id_generator import generate_id


class ApplicationService:
    async def create_application(
        self,
        db: AsyncSession,
        data: ApplicationCreate,
    ) -> ApplicationResponse:
        app_id = generate_id("app")
        app_obj = Application(
            id=app_id,
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

        return ApplicationDetailResponse.model_validate(app_obj)

    async def list_applications(
        self,
        db: AsyncSession,
    ) -> list[ApplicationResponse]:
        stmt = select(Application).order_by(Application.created_at.desc())
        res = await db.execute(stmt)
        apps = res.scalars().all()
        return [ApplicationResponse.model_validate(a) for a in apps]


application_service = ApplicationService()
