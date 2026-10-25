from fastapi import APIRouter

from app.routes.applications import router as applications_router
from app.routes.documents import router as documents_router
from app.routes.validation import router as validation_router

api_router = APIRouter()

api_router.include_router(applications_router)
api_router.include_router(documents_router)
api_router.include_router(validation_router)

__all__ = ["api_router"]
