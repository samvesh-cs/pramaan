import logging
from typing import Any
from app.rules.base import BaseRule
from app.schemas.finding import FindingCreate

logger = logging.getLogger(__name__)


class DuplicateDocumentRule(BaseRule):
    """
    Identifies when the same document or certificate is uploaded more than once.
    
    Graded levels:
    1. Same file hash within the same application:
       - Note / low priority: "same file uploaded twice" (pass/info).
    2. Same file hash in the SAME institution's earlier application:
       - Note: "same document reused from previous application" (pass/info, legitimate reuse).
    3. Same file hash in ANOTHER institution's application:
       - Flagged finding: "possible duplicate, requires review".
         Status: 'flagged' (Manual review required) with evidence of both applications.
    4. Same certificate number extracted across different institutions:
       - Flagged finding: "possible duplicate certificate number, requires review".
         Status: 'flagged' (Manual review required) with evidence of certificate number and conflicting applications.
         
    Wording guardrail:
    Always uses "possible duplicate, requires review" — NEVER "fraud" or "forged".
    """
    rule_id = "DUPLICATE_DOC_001"
    title = "Duplicate Document & Certificate Detection Check"

    def evaluate(self, context: dict[str, Any]) -> list[FindingCreate]:
        findings: list[FindingCreate] = []
        application = context.get("application")
        if not application:
            return findings

        current_app_id = application.id
        current_institution = (application.institution_name or "").strip().lower()

        uploaded_docs = context.get("documents", [])
        extractions_by_doc_id = context.get("extractions", {})
        all_system_documents = context.get("all_system_documents", [])

        # Map to find duplicate hashes within current application
        current_app_hashes: dict[str, list[Any]] = {}
        for doc in uploaded_docs:
            if doc.file_hash:
                current_app_hashes.setdefault(doc.file_hash, []).append(doc)

        # 1. Check intra-application duplicates (same file uploaded twice in same application)
        for f_hash, docs in current_app_hashes.items():
            if len(docs) > 1:
                filenames = ", ".join(d.original_filename for d in docs)
                doc_types = ", ".join(d.document_type for d in docs)
                logger.info(
                    f"[DUPLICATE_CHECK] Intra-app duplicate detected in app {current_app_id}: "
                    f"hash={f_hash}, files=[{filenames}]"
                )
                findings.append(
                    FindingCreate(
                        rule_id=self.rule_id,
                        status="pass",
                        title=f"Same file uploaded multiple times ({docs[0].document_type})",
                        reason=(
                            f"The same document file ({filenames}) was uploaded more than once "
                            f"for {doc_types} in this application. Possible duplicate, requires review."
                        ),
                        document_id=docs[0].id,
                        document_name=docs[0].original_filename,
                        evidence={
                            "type": "intra_application_duplicate",
                            "file_hash": f_hash,
                            "duplicate_document_ids": [d.id for d in docs],
                            "filenames": [d.original_filename for d in docs],
                            "document_types": [d.document_type for d in docs],
                        },
                        next_action="Review uploaded documents to confirm if redundant file uploads were intended.",
                    )
                )

        # Map current docs' hashes and extracted cert numbers
        for doc in uploaded_docs:
            doc_hash = getattr(doc, "file_hash", None)
            extraction = extractions_by_doc_id.get(doc.id)
            fields = extraction.fields if extraction else {}

            # Extract certificate / approval numbers if available
            cert_no_entry = (
                fields.get("certificate_number")
                or fields.get("order_number")
                or fields.get("approval_number")
                or fields.get("transaction_id")
            )
            cert_val = (cert_no_entry.get("value") if cert_no_entry and cert_no_entry.get("value") else "").strip().lower()

            # Compare against other documents in the system
            for other_doc in all_system_documents:
                # Skip documents from the current application (handled above)
                if other_doc.application_id == current_app_id:
                    continue

                other_app = getattr(other_doc, "application", None)
                other_inst = (getattr(other_app, "institution_name", "") or "").strip().lower() if other_app else ""
                is_same_institution = (current_institution and other_inst and current_institution == other_inst)

                # Check Hash Duplication across applications
                if doc_hash and getattr(other_doc, "file_hash", None) == doc_hash:
                    if is_same_institution:
                        # Legitimate reuse from previous application of the same institution
                        logger.info(
                            f"[DUPLICATE_CHECK] Same-institution cross-application file reuse: "
                            f"app_id={current_app_id}, prev_app_id={other_doc.application_id}, hash={doc_hash}"
                        )
                        findings.append(
                            FindingCreate(
                                rule_id=self.rule_id,
                                status="pass",
                                title=f"Document reused from earlier submission ({doc.document_type})",
                                reason=(
                                    f"File '{doc.original_filename}' has an identical file hash as document "
                                    f"in previous application '{other_doc.application_id}' from the same institution. "
                                    f"Possible duplicate, legitimate renewal reuse."
                                ),
                                document_id=doc.id,
                                document_name=doc.original_filename,
                                evidence={
                                    "type": "same_institution_reuse",
                                    "file_hash": doc_hash,
                                    "current_application_id": current_app_id,
                                    "matched_application_id": other_doc.application_id,
                                    "matched_document_id": other_doc.id,
                                    "matched_filename": other_doc.original_filename,
                                },
                                next_action="Verify validity period against current academic year submission.",
                            )
                        )
                    else:
                        # Conflicting institution submission with identical document hash
                        logger.warning(
                            f"[DUPLICATE_CHECK] CROSS-INSTITUTION DUPLICATE: doc={doc.id} (app {current_app_id}) "
                            f"matches doc={other_doc.id} (app {other_doc.application_id})"
                        )
                        findings.append(
                            FindingCreate(
                                rule_id=self.rule_id,
                                status="flagged",
                                title=f"Possible duplicate document detected ({doc.document_type})",
                                reason=(
                                    f"Document file '{doc.original_filename}' has an identical hash to a document "
                                    f"uploaded in another application ('{other_doc.application_id}'). "
                                    f"Possible duplicate, requires review."
                                ),
                                document_id=doc.id,
                                document_name=doc.original_filename,
                                evidence={
                                    "type": "cross_institution_duplicate_file",
                                    "file_hash": doc_hash,
                                    "current_application_id": current_app_id,
                                    "matched_application_id": other_doc.application_id,
                                    "matched_document_id": other_doc.id,
                                    "document_type": doc.document_type,
                                },
                                next_action="Manual review required: Inspect original hard-copy certificates to verify issuance ownership.",
                            )
                        )

                # Check Extracted Certificate Number Duplication across different institutions
                if cert_val and len(cert_val) >= 4:
                    other_extractions = getattr(other_doc, "extractions", [])
                    other_ext = other_extractions[0] if other_extractions else None
                    if other_ext and hasattr(other_ext, "fields") and isinstance(other_ext.fields, dict):
                        other_fields = other_ext.fields
                        other_cert_entry = (
                            other_fields.get("certificate_number")
                            or other_fields.get("order_number")
                            or other_fields.get("approval_number")
                            or other_fields.get("transaction_id")
                        )
                        other_val = (other_cert_entry.get("value") if other_cert_entry and other_cert_entry.get("value") else "").strip().lower()

                        if other_val and other_val == cert_val and not is_same_institution:
                            logger.warning(
                                f"[DUPLICATE_CHECK] CROSS-INSTITUTION CERTIFICATE NUMBER MATCH: "
                                f"number='{cert_val}' in app {current_app_id} and app {other_doc.application_id}"
                            )
                            findings.append(
                                FindingCreate(
                                    rule_id=self.rule_id,
                                    status="flagged",
                                    title=f"Possible duplicate certificate number detected ({doc.document_type})",
                                    reason=(
                                        f"Certificate number '{cert_val}' in '{doc.original_filename}' matches the "
                                        f"certificate number in document from another application ('{other_doc.application_id}'). "
                                        f"Possible duplicate, requires review."
                                    ),
                                    document_id=doc.id,
                                    document_name=doc.original_filename,
                                    evidence={
                                        "type": "cross_institution_duplicate_certificate_number",
                                        "certificate_number": cert_val,
                                        "current_application_id": current_app_id,
                                        "matched_application_id": other_doc.application_id,
                                        "matched_document_id": other_doc.id,
                                        "document_type": doc.document_type,
                                    },
                                    next_action="Manual review required: Verify authority issuing ledger for certificate number assignment.",
                                )
                            )

        return findings
