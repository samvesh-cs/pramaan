from typing import Any
from app.rules.base import BaseRule
from app.schemas.finding import FindingCreate


class TerPaymentRule(BaseRule):
    rule_id = "TER_PAYMENT_001"
    title = "TER Payment Receipt Information Check"

    def evaluate(self, context: dict[str, Any]) -> list[FindingCreate]:
        findings: list[FindingCreate] = []
        uploaded_docs = context.get("documents", [])
        extractions_by_doc_id = context.get("extractions", {})

        # Find ter_payment_receipt document
        ter_doc = next((d for d in uploaded_docs if d.document_type == "ter_payment_receipt"), None)
        if not ter_doc:
            # D-019 (Option A): An absent TER receipt produces NO finding.
            # Annexure-2 §2.1(ii) specifies pay receipt "if any".
            return findings

        extraction = extractions_by_doc_id.get(ter_doc.id)
        if not extraction or extraction.processing_status != "processed":
            findings.append(
                FindingCreate(
                    rule_id=self.rule_id,
                    status="not_applicable",
                    title="Advisory: TER Payment Receipt Extraction Incomplete",
                    reason=(
                        f"Payment receipt '{ter_doc.original_filename}' has not finished OCR processing. "
                        f"(Advisory: TER receipt is optional 'if any' under APH 2024-27 Annexure-2 §2.1(ii))."
                    ),
                    document_id=ter_doc.id,
                    document_name=ter_doc.original_filename,
                    evidence={"processing_status": getattr(extraction, "processing_status", "not_processed")},
                    next_action=None,
                    severity="info",
                    clause_ref="APH_2024_27_ANNEX_2_CLAUSE_2_1_II",
                )
            )
            return findings

        fields = extraction.fields or {}
        amount_field = fields.get("amount_inr")
        receipt_num_field = fields.get("receipt_number")
        txn_date_field = fields.get("transaction_date")

        receipt_num = receipt_num_field.get("value") if receipt_num_field else None
        txn_date = txn_date_field.get("value") if txn_date_field else None
        amount_val = amount_field.get("value") if amount_field else None

        # D-019: Advisory/informational check. Fee amount is not validated against portal records.
        findings.append(
            FindingCreate(
                rule_id=self.rule_id,
                status="pass",
                title="TER Payment Receipt Provided",
                reason=(
                    f"Payment receipt '{ter_doc.original_filename}' provided per Annexure-2 §2.1(ii) ('if any'). "
                    "This check is advisory/informational; fee amounts are not validated against AICTE portal records."
                ),
                document_id=ter_doc.id,
                document_name=ter_doc.original_filename,
                evidence={
                    "receipt_number": receipt_num,
                    "transaction_date": txn_date,
                    "amount_inr": amount_val,
                    "page_number": amount_field.get("page_number") if amount_field else None,
                    "bbox": amount_field.get("bbox") if amount_field else None,
                },
                next_action=None,
                severity="info",
                clause_ref="APH_2024_27_ANNEX_2_CLAUSE_2_1_II",
            )
        )

        return findings
