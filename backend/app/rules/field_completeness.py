from typing import Any
from app.checklist.eoa_checklist import EOA_DOCUMENT_CHECKLIST
from app.rules.base import BaseRule
from app.schemas.finding import FindingCreate

FIELD_RULE_MAP = {
    "fire_safety_certificate": ("FIELD_001", "Fire Safety Certificate Field Completeness"),
    "building_completion_certificate": ("FIELD_002", "Building Certificate Field Completeness"),
    "affidavit_2": ("FIELD_003", "Affidavit-2 Field Completeness"),
}


class FieldCompletenessRule(BaseRule):
    rule_id = "FIELD_COMPLETENESS"
    title = "Mandatory Field Completeness Verification"

    def evaluate(self, context: dict[str, Any]) -> list[FindingCreate]:
        findings: list[FindingCreate] = []
        uploaded_docs = context.get("documents", [])
        extractions_by_doc_id = context.get("extractions", {})  # doc_id -> ExtractionRun

        for doc in uploaded_docs:
            doc_type = doc.document_type
            if doc_type not in EOA_DOCUMENT_CHECKLIST:
                continue

            rule_id, rule_title = FIELD_RULE_MAP.get(
                doc_type,
                (f"FIELD_{doc_type.upper()}", f"{doc_type} Fields"),
            )
            checklist_info = EOA_DOCUMENT_CHECKLIST[doc_type]
            required_fields = checklist_info.get("required_fields", [])

            extraction = extractions_by_doc_id.get(doc.id)
            if not extraction or extraction.processing_status != "processed":
                findings.append(
                    FindingCreate(
                        rule_id=rule_id,
                        status="unresolved",
                        title=f"{checklist_info['display_name']} extraction incomplete",
                        reason=f"Fields could not be validated because document '{doc.original_filename}' has not been successfully processed.",
                        document_id=doc.id,
                        document_name=doc.original_filename,
                        evidence={"processing_status": getattr(extraction, "processing_status", "not_processed")},
                        next_action="Wait for document OCR processing to complete or re-upload if processing failed.",
                    )
                )
                continue

            extracted_fields = extraction.fields or {}
            missing_fields: list[str] = []

            for field_name in required_fields:
                field_data = extracted_fields.get(field_name)
                if not field_data or field_data.get("value") is None:
                    missing_fields.append(field_name)

            if missing_fields:
                findings.append(
                    FindingCreate(
                        rule_id=rule_id,
                        status="missing",
                        title=f"Missing required fields in {checklist_info['display_name']}",
                        reason=f"The following required fields could not be extracted from '{doc.original_filename}': {', '.join(missing_fields)}.",
                        document_id=doc.id,
                        document_name=doc.original_filename,
                        evidence={"missing_fields": missing_fields},
                        next_action="Ensure the uploaded document contains clear text for all mandatory fields or manually review the file.",
                    )
                )
            else:
                findings.append(
                    FindingCreate(
                        rule_id=rule_id,
                        status="pass",
                        title=f"All required fields extracted for {checklist_info['display_name']}",
                        reason=f"All {len(required_fields)} required fields were successfully extracted from '{doc.original_filename}'.",
                        document_id=doc.id,
                        document_name=doc.original_filename,
                        evidence={"extracted_fields": list(extracted_fields.keys())},
                        next_action=None,
                    )
                )

        return findings
