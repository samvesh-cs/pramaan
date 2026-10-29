"""Issuing Authority and QR Digital Verification Rule (Pillar 3).

Rule ID: AUTHORITY_VERIFY_001
Evaluates document authenticity and metadata against issuing authorities and decoded QR codes.
"""

import logging
from typing import Any
from app.rules.base import BaseRule
from app.schemas.finding import FindingCreate
from app.services.authority_verification import verify_with_issuing_authority

logger = logging.getLogger(__name__)


def _extract_field_attr(field_entry: Any, attr: str = "value") -> Any:
    """Safely extract attribute from either a Pydantic object or dict."""
    if field_entry is None:
        return None
    if isinstance(field_entry, dict):
        return field_entry.get(attr)
    return getattr(field_entry, attr, None)


class IssuingAuthorityVerificationRule(BaseRule):
    rule_id = "AUTHORITY_VERIFY_001"
    title = "Issuing Authority & Digital Verification Check"

    def evaluate(self, context: dict[str, Any]) -> list[FindingCreate]:
        findings: list[FindingCreate] = []
        application = context.get("application")
        if not application:
            return findings

        uploaded_docs = context.get("documents", [])
        extractions = context.get("extractions", {})
        inst_name = (application.institution_name or "").strip()

        for doc in uploaded_docs:
            extraction = extractions.get(doc.id)
            if not extraction:
                continue
            proc_status = getattr(extraction, "processing_status", None) or (
                extraction.get("processing_status") if isinstance(extraction, dict) else None
            )
            if proc_status != "processed":
                continue

            fields = getattr(extraction, "fields", None) or (
                extraction.get("fields") if isinstance(extraction, dict) else {}
            ) or {}

            qr_field = fields.get("qr_code")
            cert_field = (
                fields.get("certificate_number")
                or fields.get("document_number")
                or fields.get("order_number")
                or fields.get("registration_number")
            )
            expiry_field = fields.get("expiry_date")

            cert_num = _extract_field_attr(cert_field, "value")
            exp_date = _extract_field_attr(expiry_field, "value")
            qr_payload = _extract_field_attr(qr_field, "value")

            # Run authority verification
            auth_res = verify_with_issuing_authority(
                document_type=doc.document_type,
                certificate_number=str(cert_num) if cert_num else None,
                institution_name=inst_name,
                expiry_date=str(exp_date) if exp_date else None,
                qr_payload=qr_payload,
            )

            qr_bbox = _extract_field_attr(qr_field, "bbox")
            cert_bbox = _extract_field_attr(cert_field, "bbox")
            target_bbox = qr_bbox or cert_bbox

            # Map 6 AICTE statuses to Finding status
            # 1. verified -> pass
            if auth_res.status == "verified":
                findings.append(
                    FindingCreate(
                        rule_id=self.rule_id,
                        status="pass",
                        title=f"Authority Verification: Record Confirmed ({doc.original_filename})",
                        reason=(
                            f"Authority records from {auth_res.authority_name} via {auth_res.source_channel} "
                            f"confirm active reference '{auth_res.reference_number}'."
                        ),
                        document_id=doc.id,
                        document_name=doc.original_filename,
                        evidence={
                            "authority_status": auth_res.status,
                            "authority_name": auth_res.authority_name,
                            "channel": auth_res.source_channel,
                            "timestamp": auth_res.verification_timestamp,
                            "reference_number": auth_res.reference_number,
                            "bbox": target_bbox,
                            "source_details": auth_res.source_details,
                        },
                        next_action="Authority verification satisfied. No manual intervention required.",
                    )
                )
            # 2. mismatch_detected -> flagged
            elif auth_res.status == "mismatch_detected":
                findings.append(
                    FindingCreate(
                        rule_id=self.rule_id,
                        status="flagged",
                        title=f"Authority Verification: Mismatch Detected ({doc.original_filename})",
                        reason=auth_res.discrepancy_reason or "Discrepancy detected between document text and issuing authority records.",
                        document_id=doc.id,
                        document_name=doc.original_filename,
                        evidence={
                            "authority_status": auth_res.status,
                            "authority_name": auth_res.authority_name,
                            "channel": auth_res.source_channel,
                            "timestamp": auth_res.verification_timestamp,
                            "reference_number": auth_res.reference_number,
                            "bbox": target_bbox,
                            "discrepancy": auth_res.discrepancy_reason,
                        },
                        next_action="Examine conflicting record details and confirm record details with original issuing authority.",
                    )
                )
            # 3. expired -> flagged
            elif auth_res.status == "expired":
                findings.append(
                    FindingCreate(
                        rule_id=self.rule_id,
                        status="flagged",
                        title=f"Authority Verification: Record Expired ({doc.original_filename})",
                        reason=auth_res.discrepancy_reason or "Issuing authority indicates that this document or license has expired.",
                        document_id=doc.id,
                        document_name=doc.original_filename,
                        evidence={
                            "authority_status": auth_res.status,
                            "authority_name": auth_res.authority_name,
                            "channel": auth_res.source_channel,
                            "timestamp": auth_res.verification_timestamp,
                            "reference_number": auth_res.reference_number,
                            "bbox": target_bbox,
                        },
                        next_action="Require applicant to upload an updated, renewed certificate.",
                    )
                )
            # 4. verification_pending / source_unavailable / manual_review_required -> unresolved
            else:
                findings.append(
                    FindingCreate(
                        rule_id=self.rule_id,
                        status="unresolved",
                        title=f"Authority Verification: Inconclusive ({doc.original_filename})",
                        reason=(
                            f"{auth_res.discrepancy_reason or 'Automated registry lookup was unavailable.'} "
                            f"Status: {auth_res.status}. Routed for manual scrutiny officer confirmation."
                        ),
                        document_id=doc.id,
                        document_name=doc.original_filename,
                        evidence={
                            "authority_status": auth_res.status,
                            "authority_name": auth_res.authority_name,
                            "channel": auth_res.source_channel,
                            "timestamp": auth_res.verification_timestamp,
                            "reference_number": auth_res.reference_number,
                            "bbox": target_bbox,
                        },
                        next_action="Scrutiny officer should manually confirm certificate reference with competent authority.",
                        advisory=True if not qr_payload else False,
                    )
                )

        return findings
