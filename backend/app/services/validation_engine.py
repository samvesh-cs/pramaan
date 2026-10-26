from datetime import datetime, timezone
from typing import Any
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.checklist.eoa_checklist import EOA_DOCUMENT_CHECKLIST
from app.models.application import Application
from app.models.document import Document
from app.models.extraction import ExtractionRun
from app.models.finding import Finding
from app.rules.base import BaseRule
from app.rules.cross_document_check import InstitutionNameConsistencyRule
from app.rules.expiry_check import ExpiryDateRule
from app.rules.field_completeness import FieldCompletenessRule
from app.rules.presence_check import DocumentPresenceRule
from app.schemas.application import OverallStatus
from app.schemas.finding import FindingResponse
from app.schemas.report import ReportResponse
from app.utils.id_generator import generate_id


def calculate_overall_status(findings: list[Finding | Any], documents: list[Document]) -> OverallStatus:
    """
    Calculate application overall status based on standard priority:
    processing_incomplete > missing_documents > discrepancies_found > unresolved_checks > checks_passed
    """
    # 1. Any document not processed?
    if not documents or any(d.processing_status != "processed" for d in documents):
        return "processing_incomplete"

    statuses = [f.status for f in findings]

    # 2. Priority checks
    if "missing" in statuses:
        return "missing_documents"
    if "flagged" in statuses:
        return "discrepancies_found"
    if "unresolved" in statuses:
        return "unresolved_checks"
    if findings and all(s in ("pass", "not_applicable") for s in statuses):
        return "checks_passed"

    return "processing_incomplete"


class ValidationEngine:
    def __init__(self):
        self.rules: list[BaseRule] = [
            DocumentPresenceRule(),
            FieldCompletenessRule(),
            ExpiryDateRule(),
            InstitutionNameConsistencyRule(),
        ]

    async def validate_application(
        self,
        db: AsyncSession,
        application_id: str,
    ) -> ReportResponse:
        """Run all validation rules, save findings, update application status, and return report."""
        # 1. Fetch application
        app_stmt = select(Application).where(Application.id == application_id)
        result = await db.execute(app_stmt)
        application = result.scalar_one_or_none()

        if not application:
            raise HTTPException(
                status_code=404,
                detail={"code": "APPLICATION_NOT_FOUND", "message": f"Application '{application_id}' not found.", "details": None},
            )

        # 2. Fetch documents
        docs_stmt = select(Document).where(Document.application_id == application_id)
        docs_result = await db.execute(docs_stmt)
        documents = list(docs_result.scalars().all())

        # 3. Fetch latest extraction run for each document
        extractions_by_doc_id: dict[str, ExtractionRun] = {}
        for doc in documents:
            ext_stmt = (
                select(ExtractionRun)
                .where(ExtractionRun.document_id == doc.id)
                .order_by(ExtractionRun.created_at.desc())
            )
            ext_res = await db.execute(ext_stmt)
            latest_ext = ext_res.scalars().first()
            if latest_ext:
                extractions_by_doc_id[doc.id] = latest_ext

        # 4. Clear prior findings for this application
        await db.execute(delete(Finding).where(Finding.application_id == application_id))

        # 5. Build context & evaluate rules
        context = {
            "application": application,
            "documents": documents,
            "extractions": extractions_by_doc_id,
        }

        generated_findings: list[Finding] = []
        for rule in self.rules:
            rule_findings = rule.evaluate(context)
            for rf in rule_findings:
                finding_model = Finding(
                    id=generate_id("finding"),
                    application_id=application_id,
                    document_id=rf.document_id,
                    rule_id=rf.rule_id,
                    status=rf.status,
                    title=rf.title,
                    reason=rf.reason,
                    document_name=rf.document_name,
                    evidence=rf.evidence,
                    next_action=rf.next_action,
                )
                db.add(finding_model)
                generated_findings.append(finding_model)

        # Flush to persist findings
        await db.flush()

        # 6. Calculate overall status
        new_status = calculate_overall_status(generated_findings, documents)
        application.overall_status = new_status
        await db.commit()

        # 7. Generate report response
        return self._build_report(application_id, new_status, generated_findings, documents)

    async def get_report(self, db: AsyncSession, application_id: str) -> ReportResponse:
        """Retrieve existing validation report."""
        app_stmt = select(Application).where(Application.id == application_id)
        result = await db.execute(app_stmt)
        application = result.scalar_one_or_none()

        if not application:
            raise HTTPException(
                status_code=404,
                detail={"code": "APPLICATION_NOT_FOUND", "message": f"Application '{application_id}' not found.", "details": None},
            )

        docs_stmt = select(Document).where(Document.application_id == application_id)
        docs_res = await db.execute(docs_stmt)
        documents = list(docs_res.scalars().all())

        findings_stmt = (
            select(Finding)
            .where(Finding.application_id == application_id)
            .order_by(Finding.created_at.asc())
        )
        findings_res = await db.execute(findings_stmt)
        findings = list(findings_res.scalars().all())

        return self._build_report(application_id, application.overall_status, findings, documents)

    def _build_report(
        self,
        application_id: str,
        overall_status: str,
        findings: list[Finding],
        documents: list[Document],
    ) -> ReportResponse:
        summary_counts = {
            "pass": sum(1 for f in findings if f.status == "pass"),
            "flagged": sum(1 for f in findings if f.status == "flagged"),
            "missing": sum(1 for f in findings if f.status == "missing"),
            "unresolved": sum(1 for f in findings if f.status == "unresolved"),
            "not_applicable": sum(1 for f in findings if f.status == "not_applicable"),
        }

        uploaded_types = {d.document_type for d in documents}
        missing_doc_types = [
            doc_type for doc_type in EOA_DOCUMENT_CHECKLIST.keys()
            if doc_type not in uploaded_types
        ]

        finding_responses = [FindingResponse.model_validate(f) for f in findings]

        return ReportResponse(
            application_id=application_id,
            overall_status=overall_status,
            summary=summary_counts,
            missing_document_types=missing_doc_types,
            findings=finding_responses,
            generated_at=datetime.now(timezone.utc),
        )


validation_engine = ValidationEngine()
