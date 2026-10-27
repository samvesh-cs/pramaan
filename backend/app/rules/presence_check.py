from typing import Any
from app.checklist.eoa_checklist import EOA_DOCUMENT_CHECKLIST
from app.rules.base import BaseRule
from app.schemas.finding import FindingCreate

PRESENCE_RULE_MAP = {
    "fire_safety_certificate": ("PRESENCE_001", "Fire Safety Certificate Presence Check"),
    "building_completion_certificate": ("PRESENCE_002", "Building Completion / Occupancy Certificate Presence Check"),
    "affidavit_2": ("PRESENCE_003", "Affidavit-2 Presence Check"),
    "ter_payment_receipt": ("PRESENCE_004", "TER Payment Receipt Presence Check"),
}


class DocumentPresenceRule(BaseRule):
    rule_id = "PRESENCE_CHECK"
    title = "Mandatory Document Presence Verification"

    def evaluate(self, context: dict[str, Any]) -> list[FindingCreate]:
        findings: list[FindingCreate] = []
        uploaded_docs = context.get("documents", [])
        # Map by doc_type -> doc
        docs_by_type = {doc.document_type: doc for doc in uploaded_docs}

        for doc_type, info in EOA_DOCUMENT_CHECKLIST.items():
            # Skip conditional requirements from generic presence check; handled by dedicated conditional rules
            if info.get("applicability") == "required_if_applicable":
                continue

            rule_id, title = PRESENCE_RULE_MAP.get(doc_type, (f"PRESENCE_{doc_type.upper()}", f"{info['display_name']} Presence"))
            doc = docs_by_type.get(doc_type)

            if doc:
                findings.append(
                    FindingCreate(
                        rule_id=rule_id,
                        status="pass",
                        title=f"{info['display_name']} is present",
                        reason=f"Mandatory document '{info['display_name']}' is uploaded ({doc.original_filename}).",
                        document_id=doc.id,
                        document_name=doc.original_filename,
                        evidence={"document_type": doc_type, "original_filename": doc.original_filename},
                        next_action=None,
                    )
                )
            else:
                findings.append(
                    FindingCreate(
                        rule_id=rule_id,
                        status="missing",
                        title=f"{info['display_name']} is missing",
                        reason=f"Mandatory document '{info['display_name']}' is not uploaded. Sourced from {info['source']}.",
                        document_id=None,
                        document_name=None,
                        evidence={"missing_document_type": doc_type},
                        next_action=f"Upload a valid {info['display_name']} as required by AICTE regulations ({info['source']}).",
                    )
                )

        return findings
