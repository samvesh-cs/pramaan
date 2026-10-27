"""Seed an idempotent synthetic reviewer demo using the real OCR and rules."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings
from app.auth.password import hash_password
from app.database import Base, effective_db_url
from app.models import Application, Document, ExtractionRun, Finding, Institution, User
from app.ocr.processor import process_document
from app.services.validation_engine import ValidationEngine, calculate_overall_status

SAMPLE_ROOT = BACKEND_ROOT / "tests" / "demo_samples"
UPLOAD_ROOT = settings.upload_path
APPLICATION_ID = "app_demo_sih2026"
INSTITUTION_NAME = "Synthetic ABC Institute of Technology"
SCENARIO_ID = "scenario_3_expired"


def sync_database_url(url: str) -> str:
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    raise RuntimeError(f"Unsupported database driver for synchronous demo seed: {url.split(':', 1)[0]}")


def seed() -> dict:
    if not settings.DEBUG or not effective_db_url.startswith("sqlite"):
        raise RuntimeError("Refusing to seed unless DEBUG is true and the configured target is local SQLite.")

    manifest = json.loads((SAMPLE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    scenario = next(item for item in manifest["scenarios"] if item["id"] == SCENARIO_ID)
    engine = create_engine(sync_database_url(effective_db_url))
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        application = db.get(Application, APPLICATION_ID)
        if application:
            documents = list(db.scalars(select(Document).where(Document.application_id == APPLICATION_ID)))
            findings = list(db.scalars(select(Finding).where(Finding.application_id == APPLICATION_ID)))
            if application.status in {"submitted", "review_completed"} and len(documents) == 3 and findings:
                return summary(application, documents, findings, created=False)
            raise RuntimeError("A partial showcase application already exists; refusing to overwrite it.")

        email = settings.DEMO_INSTITUTION_EMAIL.strip().lower()
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, password_hash=hash_password(settings.DEMO_INSTITUTION_PASSWORD), role="INSTITUTION", is_active=True)
            db.add(user)
            db.flush()
        elif user.role != "INSTITUTION":
            raise RuntimeError("Configured demo institution email belongs to a non-institution account.")
        user.password_hash = hash_password(settings.DEMO_INSTITUTION_PASSWORD)
        user.is_active = True

        reviewer_email = settings.REVIEWER_EMAIL.strip().lower()
        reviewer = db.scalar(select(User).where(User.email == reviewer_email))
        if reviewer is None:
            reviewer = User(email=reviewer_email, password_hash=hash_password(settings.REVIEWER_PASSWORD), role="REVIEWER", is_active=True)
            db.add(reviewer)
        elif reviewer.role != "REVIEWER":
            raise RuntimeError("Configured reviewer email belongs to a non-reviewer account.")
        reviewer.password_hash = hash_password(settings.REVIEWER_PASSWORD)
        reviewer.is_active = True

        institution = db.scalar(select(Institution).where(Institution.user_id == user.id))
        if institution is None:
            institution = Institution(user_id=user.id, display_name=INSTITUTION_NAME)
            db.add(institution)
        else:
            institution.display_name = INSTITUTION_NAME

        app = Application(id=APPLICATION_ID, owner_id=user.id, status="draft", institution_name=INSTITUTION_NAME,
                          application_category=manifest["category"], academic_year=manifest["academic_year"],
                          overall_status="processing_incomplete")
        db.add(app)
        db.flush()

        document_rows, extraction_maps = [], {}
        for item in scenario["documents"]:
            source = SAMPLE_ROOT / item["file"]
            result = process_document(source, document_type=item["type"])
            if result.processing_status != "processed":
                raise RuntimeError(f"Processing failed for {source.name}: {result.error}")
            document_id = "doc_demo_" + item["type"]
            stored_name = document_id + source.suffix.lower()
            destination = UPLOAD_ROOT / stored_name
            shutil.copyfile(source, destination)
            content = source.read_bytes()
            doc = Document(id=document_id, application_id=APPLICATION_ID, document_type=item["type"],
                           original_filename=source.name, stored_filename=stored_name, mime_type="application/pdf",
                           file_size_bytes=len(content), file_hash=hashlib.sha256(content).hexdigest(), processing_status="processed")
            db.add(doc)
            extraction = ExtractionRun(id="ext_demo_" + item["type"], document_id=document_id,
                                       processing_status=result.processing_status,
                                       pages=[page.model_dump(mode="json") for page in result.pages],
                                       fields={key: field.model_dump(mode="json") for key, field in result.fields.items()}, error=result.error)
            db.add(extraction)
            document_rows.append(doc)
            extraction_maps[document_id] = extraction

        db.flush()
        context = {"application": app, "documents": document_rows, "extractions": extraction_maps,
                   "all_system_documents": document_rows}
        generated = [finding for rule in ValidationEngine().rules for finding in rule.evaluate(context)]
        if not any(f.rule_id == "EXPIRY_001" and f.status == "flagged" for f in generated):
            raise RuntimeError("Real validation rules did not flag the expired synthetic fire certificate.")
        for index, finding in enumerate(generated, start=1):
            db.add(Finding(id=f"finding_demo_{index:03d}", application_id=APPLICATION_ID,
                           document_id=finding.document_id, rule_id=finding.rule_id, status=finding.status,
                           title=finding.title, reason=finding.reason, document_name=finding.document_name,
                           evidence=finding.evidence, next_action=finding.next_action))
        app.overall_status = calculate_overall_status(generated, document_rows)
        if app.overall_status != scenario["expected_status"]:
            raise RuntimeError(f"Unexpected validation status: {app.overall_status}")
        app.status = "submitted"
        db.commit()
        db.refresh(app)
        return summary(app, document_rows, generated, created=True)


def summary(application, documents, findings, *, created: bool) -> dict:
    return {"created_in_this_run": created, "application_id": application.id,
            "institution_name": application.institution_name, "academic_year": application.academic_year,
            "application_status": application.status, "overall_status": application.overall_status,
            "documents": [{"document_type": d.document_type, "filename": d.original_filename,
                           "processing_status": d.processing_status} for d in documents],
            "findings": [{"rule_id": f.rule_id, "status": f.status, "title": f.title,
                          "document_name": f.document_name, "has_evidence": bool(f.evidence)} for f in findings]}


if __name__ == "__main__":
    print(json.dumps(seed(), indent=2))

