from datetime import datetime, timezone
import re
from typing import Any
from app.rules.base import BaseRule, OCR_CONFIDENCE_REVIEW_THRESHOLD
from app.rules.declarative_engine import default_clause_registry
from app.schemas.finding import FindingCreate


class BuildingAgeStructuralStabilityRule(BaseRule):
    rule_id = "STRUCTURAL_STABILITY_001"
    title = "Building Age & Structural Stability Check"

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

        # 2. Check >50-year exemption: requires age > 50 AND competent_authority_letter present (D-020)
        # Note: No institution-name matching. Letter content is not assessed (presence-only).
        competent_letter_doc = next(
            (d for d in uploaded_docs if d.document_type == "competent_authority_letter"),
            None,
        )

        if building_age > 50 and competent_letter_doc is not None:
            findings.append(
                FindingCreate(
                    rule_id=self.rule_id,
                    status="unresolved",
                    title="Competent Authority letter uploaded: reviewer to confirm it applies",
                    reason=(
                        "The preamble allows a letter from the Competent Authority for "
                        "government-constructed buildings older than 50 years where original documents "
                        "cannot be submitted; Pramaan does not read the letter and does not know whether "
                        "the building is government-constructed or whether the condition applies."
                    ),
                    document_id=competent_letter_doc.id,
                    document_name=competent_letter_doc.original_filename,
                    evidence={
                        "completion_certificate_issue_date": date_str,
                        "completion_year": completion_year,
                        "building_age_years": building_age,
                        "has_competent_authority_letter": True,
                        "letter_filename": competent_letter_doc.original_filename,
                        "rule_reference": "APH 2024-2027 Annexure-2 Section 2.1 (Preamble)",
                    },
                    clause_ref=default_clause_registry.get("APH_2024_27_ANNEX_2_CLAUSE_2_1_PREAMBLE"),
                    next_action="Reviewer to open the letter and confirm it applies.",
                )
            )
            return findings

        # 3. Check 30-year threshold from Completion Certificate ISSUE date per Clause 6.17(h) and Annexure-2 §2.1(iv)
        if building_age <= 30:
            findings.append(
                FindingCreate(
                    rule_id=self.rule_id,
                    status="not_applicable",
                    title="Structural Stability Certificate Not Applicable (<= 30 Years)",
                    reason=(
                        f"Completion Certificate issue date is {date_str} (building age {building_age} years <= 30 years). "
                        f"Per Clause 6.17(h) and Annexure-2 §2.1(iv), a Structural Stability Certificate is required only "
                        f"after expiry of thirty years from the issue of Completion Certificate."
                    ),
                    document_id=building_doc.id,
                    document_name=building_doc.original_filename,
                    evidence={
                        "completion_certificate_issue_date": date_str,
                        "completion_year": completion_year,
                        "current_year": current_year,
                        "building_age_years": building_age,
                        "threshold_years": 30,
                    },
                    next_action="No action required. Building is within the 30-year threshold from Completion Certificate issue date.",
                )
            )
            return findings

        # 4. Building age > 30 years: flag only if no Structural Stability Certificate is present
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
                        f"Completion Certificate issue date is {date_str} ({building_age} years old, exceeding 30-year threshold). "
                        f"Per APH Clause 6.17(h) and Annexure-2 §2.1(iv), a Structural Stability Certificate from a registered "
                        f"Structural Engineer is mandatory when the building is more than thirty years from the issue of Completion Certificate."
                    ),
                    evidence={
                        "completion_certificate_issue_date": date_str,
                        "completion_year": completion_year,
                        "building_age_years": building_age,
                        "threshold_years": 30,
                        "rule_reference": "APH 2024-2027 Clause 6.17(h) & Annexure-2 §2.1(iv)",
                    },
                    clause_ref=default_clause_registry.get("APH_2024_27_CLAUSE_6_17_H"),
                    next_action="Engage an empanelled/registered Structural Engineer and submit a Structural Stability Certificate.",
                )
            )
            return findings

        # 5. Structural doc is present, inspect extraction & enforce 5-year validity rule per Clause 6.17(h)
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
        s_issue_date_field = s_fields.get("issue_date") or s_fields.get("date_of_inspection") or s_fields.get("valid_until")

        cert_num = cert_num_field.get("value") if cert_num_field else None
        license_num = license_field.get("value") if license_field else None

        # Check 5-year validity rule: Clause 6.17(h)
        if s_issue_date_field and s_issue_date_field.get("value"):
            s_date_str = str(s_issue_date_field.get("value"))
            s_year_match = re.search(r"(\d{4})", s_date_str)
            if s_year_match:
                s_cert_year = int(s_year_match.group(1))
                s_cert_age = current_year - s_cert_year
                if s_cert_age > 5:
                    findings.append(
                        FindingCreate(
                            rule_id=self.rule_id,
                            status="flagged",
                            title="Structural Stability Certificate Expired (> 5 Years)",
                            reason=(
                                f"Structural Stability Certificate date is {s_date_str} (age {s_cert_age} years). "
                                f"Per APH Clause 6.17(h), a Structural Stability Certificate is valid for a period of "
                                f"FIVE years from the date of issue."
                            ),
                            document_id=structural_doc.id,
                            document_name=structural_doc.original_filename,
                            evidence={
                                "structural_certificate_date": s_date_str,
                                "certificate_age_years": s_cert_age,
                                "validity_limit_years": 5,
                                "clause_reference": "APH 2024-2027 Clause 6.17(h)",
                            },
                            next_action="Obtain renewed Structural Stability Certificate from a registered Structural Engineer.",
                        )
                    )
                    return findings

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
                    title="Structural Stability Certificate Provided (> 30 Years)",
                    reason=(
                        f"Building age ({building_age} years from Completion Certificate issue date) is supported by a "
                        f"Structural Stability Certificate (Ref: {cert_num}, Engineer Reg: {license_num}) consistent with "
                        f"Clause 6.17(h) (within 5-year validity period) and Annexure-2 §2.1(iv)."
                    ),
                    document_id=structural_doc.id,
                    document_name=structural_doc.original_filename,
                    evidence={
                        "completion_certificate_issue_date": date_str,
                        "completion_year": completion_year,
                        "building_age_years": building_age,
                        "certificate_number": cert_num,
                        "engineer_license_number": license_num,
                        "validity_years": 5,
                    },
                    next_action="No action required.",
                )
            )

        return findings
