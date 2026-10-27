from datetime import datetime, timezone
from typing import Any
from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.checklist.eoa_checklist import EOA_DOCUMENT_CHECKLIST
from app.models.application import Application
from app.models.document import Document
from app.models.extraction import ExtractionRun
from app.models.finding import Finding
from app.rules.base import BaseRule
from app.rules.building_age_check import BuildingAgeStructuralStabilityRule
from app.rules.cross_document_check import InstitutionNameConsistencyRule
from app.rules.duplicate_check import DuplicateDocumentRule
from app.rules.expiry_check import ExpiryDateRule
from app.rules.field_completeness import FieldCompletenessRule
from app.rules.presence_check import DocumentPresenceRule
from app.rules.ter_payment_check import TerPaymentRule
from app.schemas.application import OverallStatus
from app.schemas.finding import FindingResponse, FindingReviewUpdate
from app.schemas.report import ReportResponse
from app.utils.id_generator import generate_id


def calculate_overall_status(findings: list[Finding | Any], documents: list[Document]) -> OverallStatus:
    """
    Calculate application overall status based on standard priority:
    processing_incomplete > missing_documents > discrepancies_found > unresolved_checks > checks_passed / ready_for_review
    Accounts for human reviewer verification overrides per D-002, D-011, and APH 2024-2027 Scrutiny Desk.
    """
    # 1. Any document not processed?
    if not documents or any(d.processing_status != "processed" for d in documents):
        return "processing_incomplete"

    effective_statuses: list[str] = []
    has_reviewer_override = False

    for f in findings:
        decision = getattr(f, "reviewer_decision", None)
        status = f.status

        if decision == "verified":
            effective_statuses.append("pass")
            has_reviewer_override = True
        elif decision == "confirmed_discrepancy":
            effective_statuses.append("flagged")
        elif decision == "requested_resubmission":
            effective_statuses.append("missing")
        else:
            effective_statuses.append(status)

    # 2. Priority checks
    if "missing" in effective_statuses:
        return "missing_documents"
    if "flagged" in effective_statuses:
        return "discrepancies_found"
    if "unresolved" in effective_statuses:
        return "unresolved_checks"
    if findings and all(s in ("pass", "not_applicable") for s in effective_statuses):
        return "ready_for_review" if has_reviewer_override else "checks_passed"

    return "processing_incomplete"


class ValidationEngine:
    def __init__(self):
        self.rules: list[BaseRule] = [
            DocumentPresenceRule(),
            FieldCompletenessRule(),
            ExpiryDateRule(),
            InstitutionNameConsistencyRule(),
            TerPaymentRule(),
            BuildingAgeStructuralStabilityRule(),
            DuplicateDocumentRule(),
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

        # Fetch all documents in system for cross-institution & cross-app duplicate checks
        all_docs_stmt = select(Document).options(selectinload(Document.application))
        all_docs_res = await db.execute(all_docs_stmt)
        all_system_documents = list(all_docs_res.scalars().all())

        # 4. Clear prior findings for this application
        await db.execute(delete(Finding).where(Finding.application_id == application_id))

        # 5. Build context & evaluate rules
        context = {
            "application": application,
            "documents": documents,
            "extractions": extractions_by_doc_id,
            "all_system_documents": all_system_documents,
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

    async def review_finding(
        self,
        db: AsyncSession,
        application_id: str,
        finding_id: str,
        review_data: FindingReviewUpdate,
    ) -> FindingResponse:
        """Record auditor verification decision and justification notes, recalculating overall status."""
        stmt = select(Finding).where(Finding.id == finding_id, Finding.application_id == application_id)
        res = await db.execute(stmt)
        finding = res.scalar_one_or_none()

        if not finding:
            raise HTTPException(
                status_code=404,
                detail={"code": "FINDING_NOT_FOUND", "message": f"Finding '{finding_id}' not found for application '{application_id}'.", "details": None},
            )

        finding.reviewer_decision = review_data.reviewer_decision
        finding.reviewer_notes = review_data.reviewer_notes
        finding.reviewed_by = review_data.reviewed_by
        finding.reviewed_at = datetime.now(timezone.utc)
        await db.flush()

        # Recalculate application overall status
        app_stmt = select(Application).where(Application.id == application_id)
        app_res = await db.execute(app_stmt)
        application = app_res.scalar_one_or_none()

        if application:
            docs_stmt = select(Document).where(Document.application_id == application_id)
            docs_res = await db.execute(docs_stmt)
            documents = list(docs_res.scalars().all())

            findings_stmt = select(Finding).where(Finding.application_id == application_id)
            findings_res = await db.execute(findings_stmt)
            all_findings = list(findings_res.scalars().all())

            new_status = calculate_overall_status(all_findings, documents)
            application.overall_status = new_status

        await db.commit()
        await db.refresh(finding)
        return FindingResponse.model_validate(finding)

    async def acknowledge_duplicate(
        self,
        db: AsyncSession,
        application_id: str,
        finding_id: str,
        reviewer_notes: str,
        reviewed_by: str = "AICTE Scrutiny Committee Auditor",
    ) -> dict[str, Any]:
        """
        Acknowledge a duplicate warning after reviewer review.
        After acknowledgment, the report can be generated and will still show the duplicate note.
        """
        stmt = select(Finding).where(Finding.id == finding_id, Finding.application_id == application_id)
        res = await db.execute(stmt)
        finding = res.scalar_one_or_none()

        if not finding:
            raise HTTPException(
                status_code=404,
                detail={"code": "FINDING_NOT_FOUND", "message": f"Finding '{finding_id}' not found for application '{application_id}'.", "details": None},
            )

        if finding.rule_id not in ("DUPLICATE_DOC_001", "DUPLICATE_DOC_001"):
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_FINDING_TYPE", "message": f"Finding '{finding_id}' is not a duplicate check.", "details": None},
            )

        # Record the acknowledgment
        finding.reviewer_decision = "verified"
        finding.reviewer_notes = reviewer_notes
        finding.reviewed_by = reviewed_by
        finding.reviewed_at = datetime.now(timezone.utc)
        await db.flush()

        # Recalculate application overall status
        app_stmt = select(Application).where(Application.id == application_id)
        app_res = await db.execute(app_stmt)
        application = app_res.scalar_one_or_none()

        if application:
            docs_stmt = select(Document).where(Document.application_id == application_id)
            docs_res = await db.execute(docs_stmt)
            documents = list(docs_res.scalars().all())

            findings_stmt = select(Finding).where(Finding.application_id == application_id)
            findings_res = await db.execute(findings_stmt)
            all_findings = list(findings_res.scalars().all())

            new_status = calculate_overall_status(all_findings, documents)
            application.overall_status = new_status

        await db.commit()
        await db.refresh(finding)
        return {
            "acknowledged": True,
            "finding_id": finding_id,
            "message": "Duplicate warning acknowledged by reviewer. Report can now be generated. The report will still show the duplicate note.",
        }

    def _build_report(
        self,
        application_id: str,
        overall_status: str,
        findings: list[Finding],
        documents: list[Document],
    ) -> ReportResponse:
        # Check for unresolved duplicate warnings that block report generation
        unresolved_duplicates = [
            f for f in findings
            if f.rule_id.startswith("DUPLICATE_") and f.status in ("flagged", "unresolved")
            and not f.reviewer_decision
        ]

        if unresolved_duplicates:
            # Collect duplicate details for the 409 response
            duplicate_details = []
            for f in unresolved_duplicates:
                evidence = f.evidence or {}
                duplicate_type = evidence.get("type", "unknown")
                msg = getattr(f, "reason", "")
                if duplicate_type == "same_file_in_application":
                    duplicate_details.append({
                        "type": "same_file_in_application",
                        "message": msg,
                        "evidence": evidence,
                        "document_id": f.document_id,
                        "action": "Delete or replace the duplicate document.",
                    })
                elif duplicate_type == "cross_institution_duplicate_file":
                    duplicate_details.append({
                        "type": "same_file_other_application",
                        "message": msg,
                        "evidence": evidence,
                        "document_id": f.document_id,
                        "related_application": evidence.get("matched_application_id"),
                        "related_document": evidence.get("matched_document_id"),
                        "action": "Delete or replace the duplicate document, or acknowledge after review.",
                    })
                elif duplicate_type == "cross_institution_duplicate_certificate_number":
                    duplicate_details.append({
                        "type": "same_certificate_number",
                        "message": msg,
                        "evidence": evidence,
                        "document_id": f.document_id,
                        "related_application": evidence.get("matched_application_id"),
                        "related_document": evidence.get("matched_document_id"),
                        "action": "Acknowledge after reviewer review, or delete/replace the document.",
                    })
                else:
                    duplicate_details.append({
                        "type": duplicate_type,
                        "message": msg,
                        "evidence": evidence,
                        "document_id": f.document_id,
                        "action": "Review and resolve the duplicate.",
                    })

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "DUPLICATES_UNRESOLVED",
                    "message": "Validation report cannot be generated until all duplicate warnings are resolved.",
                    "details": {
                        "unresolved_duplicates": duplicate_details,
                        "instruction": "Resolve each duplicate by either deleting/replacing the document or providing an authorized reviewer acknowledgment.",
                    },
                },
            )

        summary_counts = {
            "pass": sum(1 for f in findings if f.status == "pass"),
            "flagged": sum(1 for f in findings if f.status == "flagged"),
            "missing": sum(1 for f in findings if f.status == "missing"),
            "unresolved": sum(1 for f in findings if f.status == "unresolved"),
            "not_applicable": sum(1 for f in findings if f.status == "not_applicable"),
        }

        uploaded_types = {d.document_type for d in documents}
        missing_doc_types = [
            doc_type for doc_type, info in EOA_DOCUMENT_CHECKLIST.items()
            if info.get("applicability") == "required" and doc_type not in uploaded_types
        ]
        # Also include conditional documents if flagged as missing in findings
        for f in findings:
            if f.rule_id == "STRUCTURAL_STABILITY_001" and f.status == "missing":
                if "structural_stability_certificate" not in missing_doc_types:
                    missing_doc_types.append("structural_stability_certificate")

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
