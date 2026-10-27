from typing import Any
from app.checklist.eoa_checklist import EOA_STATUTORY_TER_FEES
from app.rules.base import BaseRule, OCR_CONFIDENCE_REVIEW_THRESHOLD
from app.schemas.finding import FindingCreate


class TerPaymentRule(BaseRule):
    rule_id = "TER_PAYMENT_001"
    title = "TER Payment Statutory Fee & Validity Check"

    def evaluate(self, context: dict[str, Any]) -> list[FindingCreate]:
        findings: list[FindingCreate] = []
        uploaded_docs = context.get("documents", [])
        extractions_by_doc_id = context.get("extractions", {})
        application = context.get("application")

        # Find ter_payment_receipt document
        ter_doc = next((d for d in uploaded_docs if d.document_type == "ter_payment_receipt"), None)
        if not ter_doc:
            # Note: DocumentPresenceRule PRESENCE_004 handles missing document status.
            return findings

        extraction = extractions_by_doc_id.get(ter_doc.id)
        if not extraction or extraction.processing_status != "processed":
            findings.append(
                FindingCreate(
                    rule_id=self.rule_id,
                    status="unresolved",
                    title="TER Payment Receipt Extraction Incomplete",
                    reason=f"Payment fee could not be validated because '{ter_doc.original_filename}' has not finished OCR processing.",
                    document_id=ter_doc.id,
                    document_name=ter_doc.original_filename,
                    evidence={"processing_status": getattr(extraction, "processing_status", "not_processed")},
                    next_action="Wait for OCR processing to complete or re-upload if processing failed.",
                )
            )
            return findings

        fields = extraction.fields or {}
        amount_field = fields.get("amount_inr")
        receipt_num_field = fields.get("receipt_number")
        txn_date_field = fields.get("transaction_date")

        receipt_num = receipt_num_field.get("value") if receipt_num_field else None
        txn_date = txn_date_field.get("value") if txn_date_field else None

        # Check confidence
        if amount_field and (
            amount_field.get("status") == "uncertain"
            or (
                amount_field.get("confidence") is not None
                and amount_field.get("confidence") < OCR_CONFIDENCE_REVIEW_THRESHOLD
            )
        ):
            findings.append(
                FindingCreate(
                    rule_id=self.rule_id,
                    status="unresolved",
                    title="TER Payment Amount Low OCR Confidence",
                    reason=f"Extracted payment amount '{amount_field.get('raw_text')}' has low confidence ({amount_field.get('confidence', 0):.2f}). Manual scrutiny recommended.",
                    document_id=ter_doc.id,
                    document_name=ter_doc.original_filename,
                    evidence={
                        "raw_text": amount_field.get("raw_text"),
                        "confidence": amount_field.get("confidence"),
                        "page_number": amount_field.get("page_number"),
                        "bbox": amount_field.get("bbox"),
                    },
                    next_action="Auditor must manually verify the payment amount on the receipt voucher.",
                )
            )
            return findings

        if not amount_field or amount_field.get("value") is None:
            findings.append(
                FindingCreate(
                    rule_id=self.rule_id,
                    status="flagged",
                    title="TER Fee Amount Not Found in Receipt",
                    reason="Could not detect a valid numeric payment amount (INR) in the uploaded TER payment receipt.",
                    document_id=ter_doc.id,
                    document_name=ter_doc.original_filename,
                    evidence={"raw_text": getattr(amount_field, "raw_text", None)},
                    next_action="Upload an official AICTE online payment receipt displaying the transaction amount in INR.",
                )
            )
            return findings

        paid_amount = float(amount_field.get("value"))

        # Determine expected statutory minimum TER fee per Table 2.1
        # Default private unaided is ₹1,00,000; Govt/Aided is ₹50,000.
        inst_name = (application.institution_name if application else "").lower()
        if "government" in inst_name or "govt" in inst_name or "aided" in inst_name:
            expected_fee = float(EOA_STATUTORY_TER_FEES["government_aided"])
            category_desc = "Government / Govt-Aided Institution (₹50,000)"
        elif "minority" in inst_name:
            expected_fee = float(EOA_STATUTORY_TER_FEES["minority_unaided"])
            category_desc = "Minority Institution (₹75,000)"
        else:
            expected_fee = float(EOA_STATUTORY_TER_FEES["private_unaided"])
            category_desc = "Private Unaided Institution (₹1,00,000)"

        if paid_amount < expected_fee:
            findings.append(
                FindingCreate(
                    rule_id=self.rule_id,
                    status="flagged",
                    title="Statutory TER Fee Deficit Detected",
                    reason=(
                        f"Paid TER amount of ₹{paid_amount:,.2f} is less than the statutory requirement of "
                        f"₹{expected_fee:,.2f} applicable for {category_desc} under APH Table 2.1."
                    ),
                    document_id=ter_doc.id,
                    document_name=ter_doc.original_filename,
                    evidence={
                        "paid_amount": paid_amount,
                        "required_minimum_fee": expected_fee,
                        "category": category_desc,
                        "receipt_number": receipt_num,
                        "transaction_date": txn_date,
                        "bbox": amount_field.get("bbox"),
                        "page_number": amount_field.get("page_number"),
                    },
                    next_action="Remit deficit TER payment through AICTE portal and submit updated receipt.",
                )
            )
        else:
            findings.append(
                FindingCreate(
                    rule_id=self.rule_id,
                    status="pass",
                    title="Statutory TER Fee Payment Verified",
                    reason=(
                        f"TER payment of ₹{paid_amount:,.2f} satisfies statutory requirements "
                        f"(minimum required: ₹{expected_fee:,.2f} for {category_desc}) per Table 2.1."
                    ),
                    document_id=ter_doc.id,
                    document_name=ter_doc.original_filename,
                    evidence={
                        "paid_amount": paid_amount,
                        "required_minimum_fee": expected_fee,
                        "category": category_desc,
                        "receipt_number": receipt_num,
                        "transaction_date": txn_date,
                        "bbox": amount_field.get("bbox"),
                        "page_number": amount_field.get("page_number"),
                    },
                    next_action="No action required.",
                )
            )

        return findings
