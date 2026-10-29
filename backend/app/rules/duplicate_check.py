import logging
from typing import Any
from app.ocr.perceptual_hash import hamming_distance, visual_similarity
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
    4. Perceptual visual duplicate (re-scanned / re-compressed file):
       - Detected via 64-bit difference hashing (dHash) and Hamming distance <= 6.
       - Flagged finding if cross-institution, pass/info if same institution.
    5. Same certificate number extracted across different institutions:
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
            doc_phash = getattr(doc, "perceptual_hash", None)
            extraction = extractions_by_doc_id.get(doc.id)
            fields = getattr(extraction, "fields", None) if extraction else {}
            if not fields and isinstance(extraction, dict):
                fields = extraction.get("fields", {})

            # Extract certificate / approval numbers if available
            cert_no_entry = (
                fields.get("certificate_number")
                or fields.get("order_number")
                or fields.get("approval_number")
                or fields.get("transaction_id")
            ) if isinstance(fields, dict) else None

            cert_val = (
                cert_no_entry.get("value")
                if isinstance(cert_no_entry, dict) and cert_no_entry.get("value")
                else getattr(cert_no_entry, "value", "")
            )
            cert_val = str(cert_val or "").strip().lower()

            # Compare against other documents in the system
            for other_doc in all_system_documents:
                # Skip documents from the current application (handled above)
                if other_doc.application_id == current_app_id:
                    continue

                other_app = getattr(other_doc, "application", None)
                other_inst = (getattr(other_app, "institution_name", "") or "").strip().lower() if other_app else ""
                is_same_institution = (current_institution and other_inst and current_institution == other_inst)

                other_hash = getattr(other_doc, "file_hash", None)
                other_phash = getattr(other_doc, "perceptual_hash", None)

                # Check Exact Hash Duplication across applications
                if doc_hash and other_hash == doc_hash:
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
                                    "matched_filename": other_doc.original_filename,
                                    "matched_institution_name": other_inst,
                                },
                                next_action="Investigate why an identical file was submitted by different applicants.",
                            )
                        )

                # Check Visual Perceptual Duplicate (when exact hash differs, but visual appearance matches for same document type)
                elif doc_phash and other_phash and doc_hash != other_hash and doc.document_type == other_doc.document_type:
                    # If both documents have distinct extracted certificate numbers, they are distinct documents
                    cert_differs = False
                    if cert_val and len(str(cert_val).strip()) >= 4:
                        other_extractions = getattr(other_doc, "extractions", [])
                        other_ext = other_extractions[0] if other_extractions else extractions_by_doc_id.get(other_doc.id)
                        other_fields = getattr(other_ext, "fields", None) if other_ext else {}
                        if not other_fields and isinstance(other_ext, dict):
                            other_fields = other_ext.get("fields", {})
                        if other_fields and isinstance(other_fields, dict):
                            other_cert_entry = (
                                other_fields.get("certificate_number")
                                or other_fields.get("order_number")
                                or other_fields.get("approval_number")
                                or other_fields.get("transaction_id")
                            )
                            other_cert_val = (
                                (other_cert_entry.get("value") if isinstance(other_cert_entry, dict) else getattr(other_cert_entry, "value", None))
                                if other_cert_entry else None
                            )
                            if other_cert_val and str(other_cert_val).strip() != str(cert_val).strip():
                                cert_differs = True

                    if not cert_differs:
                        dist = hamming_distance(doc_phash, other_phash)
                        if dist <= 6:
                            sim = visual_similarity(doc_phash, other_phash)
                            if is_same_institution:
                                findings.append(
                                    FindingCreate(
                                        rule_id=self.rule_id,
                                        status="pass",
                                        title=f"Re-scanned document reused from earlier submission ({doc.document_type})",
                                        reason=(
                                            f"Document '{doc.original_filename}' is visually identical ({sim:.0%} match, Hamming distance {dist}/64) "
                                            f"to a document in previous application '{other_doc.application_id}' from the same institution. "
                                            f"Re-scanned document reuse detected."
                                        ),
                                        document_id=doc.id,
                                        document_name=doc.original_filename,
                                        evidence={
                                            "type": "visual_duplicate_same_institution",
                                            "perceptual_hash": doc_phash,
                                            "matched_perceptual_hash": other_phash,
                                            "visual_similarity": round(sim, 3),
                                            "hamming_distance": dist,
                                            "current_application_id": current_app_id,
                                            "matched_application_id": other_doc.application_id,
                                            "matched_document_id": other_doc.id,
                                            "matched_filename": other_doc.original_filename,
                                        },
                                        next_action="Verify validity period against current academic year submission.",
                                    )
                                )
                            else:
                                findings.append(
                                    FindingCreate(
                                        rule_id=self.rule_id,
                                        status="flagged",
                                        title=f"Possible visual duplicate document detected ({doc.document_type})",
                                        reason=(
                                            f"Document '{doc.original_filename}' visually matches ({sim:.0%} match, Hamming distance {dist}/64) "
                                            f"a document uploaded in another institution's application ('{other_doc.application_id}'). "
                                            f"Possible re-scanned duplicate, requires review."
                                        ),
                                        document_id=doc.id,
                                        document_name=doc.original_filename,
                                        evidence={
                                            "type": "visual_duplicate_cross_institution",
                                            "perceptual_hash": doc_phash,
                                            "matched_perceptual_hash": other_phash,
                                            "visual_similarity": round(sim, 3),
                                            "hamming_distance": dist,
                                            "current_application_id": current_app_id,
                                            "matched_application_id": other_doc.application_id,
                                            "matched_document_id": other_doc.id,
                                            "matched_filename": other_doc.original_filename,
                                            "matched_institution_name": other_inst,
                                        },
                                        next_action="Review documents side-by-side to verify if document was reused across different institutions.",
                                    )
                                )

                # Check Certificate Number Duplication across applications
                if cert_val and len(cert_val) >= 4:
                    other_extractions = getattr(other_doc, "extractions", [])
                    other_ext = other_extractions[0] if other_extractions else extractions_by_doc_id.get(other_doc.id)
                    other_fields = getattr(other_ext, "fields", None) if other_ext else {}
                    if not other_fields and isinstance(other_ext, dict):
                        other_fields = other_ext.get("fields", {})

                    if other_fields and isinstance(other_fields, dict):
                        other_cert_entry = (
                            other_fields.get("certificate_number")
                            or other_fields.get("order_number")
                            or other_fields.get("approval_number")
                            or other_fields.get("transaction_id")
                        )
                        other_cert_val = (
                            other_cert_entry.get("value")
                            if isinstance(other_cert_entry, dict) and other_cert_entry.get("value")
                            else getattr(other_cert_entry, "value", "")
                        )
                        other_cert_val = str(other_cert_val or "").strip().lower()

                        if other_cert_val and cert_val == other_cert_val and not is_same_institution:
                            logger.warning(
                                f"[DUPLICATE_CHECK] CROSS-INSTITUTION CERTIFICATE NUMBER COLLISION: cert='{cert_val}' "
                                f"in app {current_app_id} (doc {doc.id}) and app {other_doc.application_id} (doc {other_doc.id})"
                            )
                            findings.append(
                                FindingCreate(
                                    rule_id=self.rule_id,
                                    status="flagged",
                                    title=f"Possible duplicate certificate number detected ({doc.document_type})",
                                    reason=(
                                        f"The extracted certificate number '{cert_val}' in document '{doc.original_filename}' "
                                        f"was also found in another institution's application ('{other_doc.application_id}'). "
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
                                        "matched_filename": other_doc.original_filename,
                                        "matched_institution_name": other_inst,
                                    },
                                    next_action="Verify with the issuing authority which institution was legitimately issued this certificate.",
                                )
                            )

        return findings
