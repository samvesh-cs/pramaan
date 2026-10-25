import uuid
from pathlib import Path
from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.checklist.eoa_checklist import EOA_MVP_DOCUMENT_TYPES
from app.config import settings
from app.models.application import Application
from app.models.document import Document
from app.models.extraction import ExtractionRun
from app.schemas.document import DocumentResponse
from app.services.ocr_service import extraction_service
from app.utils.file_validation import (
    FileValidationError,
    validate_file_metadata,
    validate_pdf_content,
)
from app.utils.id_generator import generate_id


class DocumentService:
    async def upload_document(
        self,
        db: AsyncSession,
        application_id: str,
        file: UploadFile,
        document_type: str,
    ) -> DocumentResponse:
        # 1. Verify application exists
        app_stmt = select(Application).where(Application.id == application_id)
        res = await db.execute(app_stmt)
        application = res.scalar_one_or_none()

        if not application:
            raise HTTPException(
                status_code=404,
                detail={"code": "APPLICATION_NOT_FOUND", "message": f"Application '{application_id}' not found.", "details": None},
            )

        # 2. Verify document_type is allowed
        if document_type not in EOA_MVP_DOCUMENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "INVALID_DOCUMENT_TYPE",
                    "message": f"Document type '{document_type}' is not supported for EoA. Supported types: {', '.join(EOA_MVP_DOCUMENT_TYPES)}.",
                    "details": None,
                },
            )

        # 3. Read content and validate metadata
        content = await file.read()
        file_size = len(content)
        original_filename = file.filename or "uploaded_file"
        content_type = file.content_type or "application/octet-stream"

        validate_file_metadata(original_filename, content_type, file_size)

        # 4. Save to uploads/ with secure non-traversable filename
        doc_id = generate_id("doc")
        ext = Path(original_filename).suffix.lower()
        stored_filename = f"{doc_id}_{uuid.uuid4().hex[:12]}{ext}"
        saved_path = settings.upload_path / stored_filename

        with open(saved_path, "wb") as f:
            f.write(content)

        # 5. Additional PDF content validation
        if ext == ".pdf":
            try:
                validate_pdf_content(saved_path)
            except FileValidationError:
                # Remove file if invalid
                if saved_path.exists():
                    saved_path.unlink()
                raise

        # 6. Insert document record
        doc_model = Document(
            id=doc_id,
            application_id=application_id,
            document_type=document_type,
            original_filename=original_filename,
            stored_filename=stored_filename,
            mime_type=content_type,
            file_size_bytes=file_size,
            processing_status="processing",
        )
        db.add(doc_model)
        await db.commit()
        await db.refresh(doc_model)

        # 7. Run extraction
        try:
            extraction_result = await extraction_service.extract(
                file_path=saved_path,
                document_type=document_type,
                institution_name=application.institution_name,
            )
            extraction_status = extraction_result.get("processing_status", "processed")
            extraction_error = extraction_result.get("error")
        except Exception as e:
            extraction_status = "processing_failed"
            extraction_error = str(e)
            extraction_result = {"pages": [], "fields": {}, "error": str(e)}

        # 8. Record extraction run
        run_model = ExtractionRun(
            id=generate_id("run"),
            document_id=doc_id,
            processing_status=extraction_status,
            pages=extraction_result.get("pages", []),
            fields=extraction_result.get("fields", {}),
            error=extraction_error,
        )
        db.add(run_model)

        # 9. Update document processing status
        doc_model.processing_status = extraction_status
        await db.commit()
        await db.refresh(doc_model)

        return DocumentResponse.model_validate(doc_model)

    async def list_documents(
        self,
        db: AsyncSession,
        application_id: str,
    ) -> list[DocumentResponse]:
        # Verify application exists
        app_stmt = select(Application).where(Application.id == application_id)
        res = await db.execute(app_stmt)
        if not res.scalar_one_or_none():
            raise HTTPException(
                status_code=404,
                detail={"code": "APPLICATION_NOT_FOUND", "message": f"Application '{application_id}' not found.", "details": None},
            )

        stmt = (
            select(Document)
            .where(Document.application_id == application_id)
            .order_by(Document.created_at.asc())
        )
        docs_res = await db.execute(stmt)
        docs = docs_res.scalars().all()
        return [DocumentResponse.model_validate(d) for d in docs]


document_service = DocumentService()
