from datetime import date, datetime
from typing import Any
from app.checklist.eoa_checklist import EOA_DOCUMENT_CHECKLIST
from app.rules.base import BaseRule, OCR_CONFIDENCE_REVIEW_THRESHOLD
from app.schemas.finding import FindingCreate


class ExpiryDateRule(BaseRule):
    rule_id = "EXPIRY_001"
    title = "Document Expiry Verification"

    def evaluate(self, context: dict[str, Any]) -> list[FindingCreate]:
        findings: list[FindingCreate] = []
        uploaded_docs = context.get("documents", [])
        extractions_by_doc_id = context.get("extractions", {})
        reference_date = context.get("reference_date") or date.today()

        for doc in uploaded_docs:
            doc_type = doc.document_type
            checklist_info = EOA_DOCUMENT_CHECKLIST.get(doc_type, {})
            if not checklist_info.get("has_expiry", False):
                continue

            extraction = extractions_by_doc_id.get(doc.id)
            if not extraction or extraction.processing_status != "processed":
                findings.append(
                    FindingCreate(
                        rule_id=self.rule_id,
                        status="unresolved",
                        title=f"{checklist_info['display_name']} expiry check unresolved",
                        reason=f"Document '{doc.original_filename}' has not been processed. Expiry date cannot be verified.",
                        document_id=doc.id,
                        document_name=doc.original_filename,
                        evidence=None,
                        next_action="Process document OCR before running expiry check.",
                    )
                )
                continue

            fields = extraction.fields or {}
            expiry_data = fields.get("expiry_date")

            if not expiry_data or not expiry_data.get("value"):
                findings.append(
                    FindingCreate(
                        rule_id=self.rule_id,
                        status="unresolved",
                        title=f"{checklist_info['display_name']} expiry date not found",
                        reason=f"No valid expiry date was extracted from '{doc.original_filename}'.",
                        document_id=doc.id,
                        document_name=doc.original_filename,
                        evidence={"raw_text": expiry_data.get("raw_text") if expiry_data else None},
                        next_action="Review the certificate manually to confirm if an expiry date is specified.",
                    )
                )
                continue

            confidence = expiry_data.get("confidence")
            if expiry_data.get("status") == "uncertain" or (
                confidence is not None and confidence < OCR_CONFIDENCE_REVIEW_THRESHOLD
            ):
                findings.append(
                    FindingCreate(
                        rule_id=self.rule_id,
                        status="unresolved",
                        title=f"{checklist_info['display_name']} expiry date needs review",
                        reason=(
                            f"OCR confidence for the extracted expiry date was {confidence:.0%}, "
                            f"below the {OCR_CONFIDENCE_REVIEW_THRESHOLD:.0%} review threshold."
                        ),
                        document_id=doc.id,
                        document_name=doc.original_filename,
                        evidence={
                            "page_number": expiry_data.get("page_number"),
                            "text": expiry_data.get("raw_text"),
                            "field": "expiry_date",
                            "value": expiry_data.get("value"),
                            "bbox": expiry_data.get("bbox"),
                            "confidence": confidence,
                        },
                        next_action="Review the certificate and confirm the expiry date before relying on this check.",
                    )
                )
                continue

            raw_val = expiry_data["value"]
            parsed_date: date | None = None

            # Parse ISO YYYY-MM-DD date strictly
            if isinstance(raw_val, str):
                try:
                    parsed_date = date.fromisoformat(raw_val.strip())
                except (ValueError, TypeError):
                    parsed_date = None
            elif isinstance(raw_val, date):
                parsed_date = raw_val

            if not parsed_date:
                findings.append(
                    FindingCreate(
                        rule_id=self.rule_id,
                        status="unresolved",
                        title=f"Unparseable expiry date in {checklist_info['display_name']}",
                        reason=f"Extracted expiry date '{raw_val}' could not be parsed into a standard date format.",
                        document_id=doc.id,
                        document_name=doc.original_filename,
                        evidence={"raw_value": str(raw_val)},
                        next_action="A reviewer must manually confirm the expiry date.",
                    )
                )
                continue

            evidence = {
                "page_number": expiry_data.get("page_number", 1),
                "text": expiry_data.get("raw_text") or f"Valid Until: {parsed_date.isoformat()}",
                "field": "expiry_date",
                "value": parsed_date.isoformat(),
                "bbox": expiry_data.get("bbox"),
            }

            if parsed_date < reference_date:
                findings.append(
                    FindingCreate(
                        rule_id=self.rule_id,
                        status="flagged",
                        title="Document appears expired",
                        reason=f"The extracted expiry date ({parsed_date.isoformat()}) is earlier than the reference date ({reference_date.isoformat()}).",
                        document_id=doc.id,
                        document_name=doc.original_filename,
                        evidence=evidence,
                        next_action="Request a current document or have a reviewer confirm the extracted date.",
                    )
                )
            else:
                findings.append(
                    FindingCreate(
                        rule_id=self.rule_id,
                        status="pass",
                        title=f"{checklist_info['display_name']} is currently valid",
                        reason=f"The extracted expiry date ({parsed_date.isoformat()}) is on or after the reference date ({reference_date.isoformat()}).",
                        document_id=doc.id,
                        document_name=doc.original_filename,
                        evidence=evidence,
                        next_action=None,
                    )
                )

        return findings
