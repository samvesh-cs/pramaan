import uuid
import hashlib
from pathlib import Path
from fastapi import HTTPException, UploadFile, status
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

        file_hash = hashlib.sha256(content).hexdigest()

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
            file_hash=file_hash,
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

        # 10. Detect duplicate documents
        duplicate_warnings = await self._detect_duplicates(
            db, doc_model, application_id, extraction_result.get("fields", {})
        )

        response = DocumentResponse.model_validate(doc_model)
        response.fields = extraction_result.get("fields", {})
        if duplicate_warnings:
            response.duplicate_warnings = duplicate_warnings
        return response

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

    async def get_document_file(
        self,
        db: AsyncSession,
        application_id: str,
        document_id: str,
    ) -> tuple[Path, str, str]:
        """Retrieve stored document file path, mime type, and original filename."""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.application_id == application_id,
        )
        res = await db.execute(stmt)
        doc = res.scalar_one_or_none()

        if not doc:
            raise HTTPException(
                status_code=404,
                detail={"code": "DOCUMENT_NOT_FOUND", "message": f"Document '{document_id}' not found.", "details": None},
            )

        file_path = settings.upload_path / doc.stored_filename
        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail={"code": "FILE_NOT_FOUND", "message": "Document file is missing from storage.", "details": None},
            )

        return file_path, doc.mime_type, doc.original_filename

    async def _detect_duplicates(
        self,
        db: AsyncSession,
        new_doc: Document,
        application_id: str,
        extracted_fields: dict[str, any],
    ) -> list[dict[str, any]]:
        """
        Detect duplicate documents:
        (a) Same SHA-256 file hash within the same application
        (b) Same file hash across other applications
        (c) Same certificate_number / document_number across applications (when extracted)
        Returns a list of warning dicts, empty list if no duplicates found.
        Each warning dict contains: type, title, message, evidence, next_action
        """
        warnings: list[dict[str, any]] = []

        # Get all documents in the system except the new one
        all_docs_stmt = select(Document).where(Document.id != new_doc.id)
        all_docs_res = await db.execute(all_docs_stmt)
        all_system_docs = all_docs_res.scalars().all()

        # Get documents in the same application except the new one
        same_app_docs_stmt = (
            select(Document)
            .where(
                Document.application_id == application_id,
                Document.id != new_doc.id,
            )
        )
        same_app_res = await db.execute(same_app_docs_stmt)
        same_app_docs = same_app_res.scalars().all()

        # (a) Check same file hash within the same application
        same_hash_in_app = [
            d for d in same_app_docs if d.file_hash == new_doc.file_hash
        ]
        if same_hash_in_app:
            for d in same_hash_in_app:
                warnings.append(
                    {
                        "type": "same_file_in_application",
                        "title": "Possible Duplicate Document",
                        "message": (
                            f"'{new_doc.original_filename}' has the same file hash as "
                            f"'{d.original_filename}' in this application. "
                            f"Both documents appear to be identical."
                        ),
                        "evidence": {
                            "file_hash": new_doc.file_hash,
                            "related_document_id": d.id,
                            "related_document_name": d.original_filename,
                        },
                        "next_action": "Upload a different copy or replace the existing document.",
                    }
                )

        # (b) Check same file hash across other applications
        same_hash_other_app = [
            d for d in all_system_docs if d.file_hash == new_doc.file_hash and d.application_id != application_id
        ]
        if same_hash_other_app:
            for d in same_hash_other_app:
                warnings.append(
                    {
                        "type": "same_file_other_application",
                        "title": "Possible Duplicate Across Applications",
                        "message": (
                            f"'{new_doc.original_filename}' has the same file hash as "
                            f"'{d.original_filename}' in application '{d.application_id}'. "
                            f"This may be a duplicate submission."
                        ),
                        "evidence": {
                            "file_hash": new_doc.file_hash,
                            "related_application_id": d.application_id,
                            "related_document_id": d.id,
                            "related_document_name": d.original_filename,
                        },
                        "next_action": "Verify if this is an intentional duplicate or a different document.",
                    }
                )

        # (c) Check for same certificate_number / document_number when fields are extracted
        doc_type = new_doc.document_type
        # Map document types to their expected field names for certificate number
        cert_field_map = {
            "fire_safety_certificate": "certificate_number",
            "building_completion_certificate": "certificate_number",
            "affidavit_2": "affidavit_date",  # using affidavit_date as identifier
            "ter_payment_receipt": "receipt_number",
            "structural_stability_certificate": "certificate_number",
        }
        cert_field = cert_field_map.get(doc_type)

        if cert_field and cert_field in extracted_fields:
            new_field_value = extracted_fields[cert_field].get("value")
            if new_field_value:
                # Search all other documents for the same certificate number / receipt number
                for d in all_system_docs:
                    if d.id == new_doc.id:
                        continue
                    # Find the latest extraction run for this document
                    ext_stmt = (
                        select(ExtractionRun)
                        .where(ExtractionRun.document_id == d.id)
                        .order_by(ExtractionRun.created_at.desc())
                    )
                    ext_res = await db.execute(ext_stmt)
                    latest_ext = ext_res.scalars().first()
                    if latest_ext and latest_ext.fields:
                        fields_dict = latest_ext.fields
                        if doc_type in fields_dict and isinstance(fields_dict[doc_type], dict):
                            fields_dict = fields_dict[doc_type]
                        if cert_field in fields_dict and isinstance(fields_dict[cert_field], dict):
                            existing_field_value = fields_dict[cert_field].get("value")
                            if existing_field_value and str(existing_field_value).strip().lower() == str(new_field_value).strip().lower():
                                warnings.append(
                                    {
                                        "type": "same_certificate_number",
                                        "title": "Same Certificate/Receipt Number",
                                        "message": (
                                            f"'{new_doc.original_filename}' has the same {cert_field.replace('_', ' ')} "
                                            f"('{new_field_value}') as '{d.original_filename}' in application '{d.application_id}'. "
                                            f"Please verify these are not duplicate submissions."
                                        ),
                                        "evidence": {
                                            "certificate_number": new_field_value,
                                            "related_application_id": d.application_id,
                                            "related_document_id": d.id,
                                            "related_document_name": d.original_filename,
                                        },
                                        "next_action": "Verify if this is an intentional duplicate or a different application. "
                                                       "An authorized reviewer can acknowledge the duplicate after review.",
                                    }
                                )

        return warnings


document_service = DocumentService()