from datetime import datetime, timezone
import re
from typing import Any
from app.rules.base import BaseRule, OCR_CONFIDENCE_REVIEW_THRESHOLD
from app.schemas.finding import FindingCreate


class BuildingAgeStructuralStabilityRule(BaseRule):
    rule_id = "STRUCTURAL_STABILITY_001"
    title = "Building Age & Structural Stability Verification"

    def evaluate(self, context: dict[str, Any]) -> list[FindingCreate]:
        findings: list[FindingCreate] = []
        uploaded_docs = context.get("documents", [])
        extractions_by_doc_id = context.get("extractions", {})

        # 1. Locate building completion certificate
        building_doc = next(
            (d for d in uploaded_docs if d.document_type == "building_completion_certificate"),
            None,
        )

        if not building_doc:
            findings.append(
                FindingCreate(
                    rule_id=self.rule_id,
                    status="unresolved",
                    title="Building Age Undetermined (Building Certificate Missing)",
                    reason="Building age cannot be determined because Building Completion Certificate has not been uploaded.",
                    next_action="Upload Building Completion Certificate / Occupancy Certificate to establish building vintage.",
                )
            )
            return findings

        b_extraction = extractions_by_doc_id.get(building_doc.id)
        if not b_extraction or b_extraction.processing_status != "processed":
            findings.append(
                FindingCreate(
                    rule_id=self.rule_id,
                    status="unresolved",
                    title="Building Completion Certificate Extraction Incomplete",
                    reason="Cannot determine building age until Building Completion Certificate OCR extraction completes.",
                    document_id=building_doc.id,
                    document_name=building_doc.original_filename,
                    next_action="Wait for OCR processing to complete.",
                )
            )
            return findings

        b_fields = b_extraction.fields or {}
        issue_date_field = b_fields.get("issue_date")
        if not issue_date_field or not issue_date_field.get("value"):
            findings.append(
                FindingCreate(
                    rule_id=self.rule_id,
                    status="unresolved",
                    title="Building Completion Date Indeterminate",
                    reason="Building Completion Certificate does not have a readable issue date to compute building age.",
                    document_id=building_doc.id,
                    document_name=building_doc.original_filename,
                    next_action="Upload a clear Building Completion Certificate showing the official completion or issue date.",
                )
            )
            return findings

        if issue_date_field.get("status") == "uncertain" or (
            issue_date_field.get("confidence") is not None
            and issue_date_field.get("confidence") < OCR_CONFIDENCE_REVIEW_THRESHOLD
        ):
            findings.append(
                FindingCreate(
                    rule_id=self.rule_id,
                    status="unresolved",
                    title="Building Completion Date Low OCR Confidence",
                    reason=f"Building completion date '{issue_date_field.get('raw_text')}' has low confidence ({issue_date_field.get('confidence', 0):.2f}).",
                    document_id=building_doc.id,
                    document_name=building_doc.original_filename,
                    evidence={"raw_text": issue_date_field.get("raw_text"), "confidence": issue_date_field.get("confidence")},
                    next_action="Verify building completion date manually.",
                )
            )
            return findings

        date_str = str(issue_date_field.get("value"))
        year_match = re.search(r"(\d{4})", date_str)
        if not year_match:
            findings.append(
                FindingCreate(
                    rule_id=self.rule_id,
                    status="unresolved",
                    title="Invalid Building Completion Date Format",
                    reason=f"Could not parse year from building completion date '{date_str}'.",
                    document_id=building_doc.id,
                    document_name=building_doc.original_filename,
                    next_action="Review building completion certificate date format.",
                )
            )
            return findings

        completion_year = int(year_match.group(1))
        current_year = datetime.now(timezone.utc).year
        building_age = current_year - completion_year

        # 2. Check 30-year threshold per Annexure-2 §2.1(iv)
        if building_age <= 30:
            findings.append(
                FindingCreate(
                    rule_id=self.rule_id,
                    status="not_applicable",
                    title="Structural Stability Certificate Not Applicable (<= 30 Years)",
                    reason=(
                        f"Building was completed in {completion_year} (approx. {building_age} years old). "
                        f"Annexure-2 §2.1(iv) requires a Structural Stability Certificate only for buildings older than 30 years."
                    ),
                    document_id=building_doc.id,
                    document_name=building_doc.original_filename,
                    evidence={
                        "completion_date": date_str,
                        "completion_year": completion_year,
                        "current_year": current_year,
                        "building_age_years": building_age,
                        "threshold_years": 30,
                    },
                    next_action="No action required. Building is within the 30-year threshold.",
                )
            )
            return findings

        # Building age > 30 years!
        structural_doc = next(
            (d for d in uploaded_docs if d.document_type == "structural_stability_certificate"),
            None,
        )

        if not structural_doc:
            findings.append(
                FindingCreate(
                    rule_id=self.rule_id,
                    status="missing",
                    title="Mandatory Structural Stability Certificate Missing (> 30 Years)",
                    reason=(
                        f"Building was completed in {completion_year} ({building_age} years old, exceeding 30 years). "
                        f"Per APH 2024-2027 Annexure-2 §2.1(iv), a Structural Stability Certificate from a registered "
                        f"Structural Engineer is mandatory."
                    ),
                    evidence={
                        "completion_date": date_str,
                        "completion_year": completion_year,
                        "building_age_years": building_age,
                        "threshold_years": 30,
                        "rule_reference": "APH 2024-2027 Annexure-2 §2.1(iv)",
                    },
                    next_action="Engage an empanelled/registered Structural Engineer and submit a Structural Stability Certificate.",
                )
            )
            return findings

        # Structural doc is present, inspect extraction
        s_extraction = extractions_by_doc_id.get(structural_doc.id)
        if not s_extraction or s_extraction.processing_status != "processed":
            findings.append(
                FindingCreate(
                    rule_id=self.rule_id,
                    status="unresolved",
                    title="Structural Stability Certificate Extraction Incomplete",
                    reason="Structural Stability Certificate has been uploaded but OCR extraction is still in progress.",
                    document_id=structural_doc.id,
                    document_name=structural_doc.original_filename,
                    next_action="Wait for OCR processing to complete.",
                )
            )
            return findings

        s_fields = s_extraction.fields or {}
        cert_num_field = s_fields.get("certificate_number")
        license_field = s_fields.get("engineer_license_number")

        cert_num = cert_num_field.get("value") if cert_num_field else None
        license_num = license_field.get("value") if license_field else None

        if not cert_num or not license_num:
            findings.append(
                FindingCreate(
                    rule_id=self.rule_id,
                    status="flagged",
                    title="Structural Stability Certificate Missing Key License/Cert Info",
                    reason="Structural Stability Certificate is missing certificate number or registered engineer license number.",
                    document_id=structural_doc.id,
                    document_name=structural_doc.original_filename,
                    evidence={"certificate_number": cert_num, "engineer_license_number": license_num},
                    next_action="Ensure the submitted Structural Stability Certificate includes the registered engineer's official license/registration number.",
                )
            )
        else:
            findings.append(
                FindingCreate(
                    rule_id=self.rule_id,
                    status="pass",
                    title="Structural Stability Certificate Verified (> 30 Years)",
                    reason=(
                        f"Building age ({building_age} years) is supported by a valid Structural Stability Certificate "
                        f"(Ref: {cert_num}, Engineer Reg: {license_num}) complying with Annexure-2 §2.1(iv)."
                    ),
                    document_id=structural_doc.id,
                    document_name=structural_doc.original_filename,
                    evidence={
                        "completion_year": completion_year,
                        "building_age_years": building_age,
                        "certificate_number": cert_num,
                        "engineer_license_number": license_num,
                    },
                    next_action="No action required.",
                )
            )

        return findings
