import re
from typing import Any
from app.rules.base import BaseRule, OCR_CONFIDENCE_REVIEW_THRESHOLD
from app.schemas.finding import FindingCreate


def normalize_text(text: str) -> str:
    """Normalize text for cross-document consistency checks."""
    if not text:
        return ""
    # Lowercase, remove punctuation and extra whitespace
    t = text.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def text_similarity(str1: str, str2: str) -> float:
    """Compute basic token overlap similarity."""
    tokens1 = set(normalize_text(str1).split())
    tokens2 = set(normalize_text(str2).split())
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    return len(intersection) / len(union)


class InstitutionNameConsistencyRule(BaseRule):
    rule_id = "CONSISTENCY_001"
    title = "Institution Name Cross-Document Consistency Check"

    def evaluate(self, context: dict[str, Any]) -> list[FindingCreate]:
        findings: list[FindingCreate] = []
        application = context.get("application")
        if not application:
            return findings

        app_name = application.institution_name
        norm_app_name = normalize_text(app_name)

        uploaded_docs = context.get("documents", [])
        extractions_by_doc_id = context.get("extractions", {})

        for doc in uploaded_docs:
            extraction = extractions_by_doc_id.get(doc.id)
            if not extraction or extraction.processing_status != "processed":
                continue

            fields = extraction.fields or {}
            name_field = fields.get("institution_name")

            if not name_field or not name_field.get("value"):
                # Missing field is handled by FieldCompletenessRule
                continue

            confidence = name_field.get("confidence")
            if name_field.get("status") == "uncertain" or (
                confidence is not None and confidence < OCR_CONFIDENCE_REVIEW_THRESHOLD
            ):
                findings.append(
                    FindingCreate(
                        rule_id=self.rule_id,
                        status="unresolved",
                        title="Institution name consistency check needs review",
                        reason=(
                            f"OCR confidence for the institution name in '{doc.original_filename}' "
                            f"was {confidence:.0%}, below the {OCR_CONFIDENCE_REVIEW_THRESHOLD:.0%} review threshold."
                        ),
                        document_id=doc.id,
                        document_name=doc.original_filename,
                        evidence={
                            "page_number": name_field.get("page_number"),
                            "text": name_field.get("raw_text"),
                            "field": "institution_name",
                            "value": name_field.get("value"),
                            "bbox": name_field.get("bbox"),
                            "confidence": confidence,
                        },
                        next_action="Review the institution name on the source page before comparing it with the application record.",
                    )
                )
                continue

            doc_name_val = str(name_field["value"])
            norm_doc_name = normalize_text(doc_name_val)

            # Check exact match or similarity > 0.70
            similarity = text_similarity(norm_app_name, norm_doc_name)
            is_match = (norm_app_name == norm_doc_name) or (similarity >= 0.70)

            evidence = {
                "page_number": name_field.get("page_number", 1),
                "text": name_field.get("raw_text") or doc_name_val,
                "field": "institution_name",
                "value": doc_name_val,
                "bbox": name_field.get("bbox"),
                "similarity_score": round(similarity, 2),
            }

            if is_match:
                findings.append(
                    FindingCreate(
                        rule_id=self.rule_id,
                        status="pass",
                        title="Institution name matches application record",
                        reason=f"The extracted institution name in '{doc.original_filename}' matches '{app_name}'.",
                        document_id=doc.id,
                        document_name=doc.original_filename,
                        evidence=evidence,
                        next_action=None,
                    )
                )
            else:
                findings.append(
                    FindingCreate(
                        rule_id=self.rule_id,
                        status="flagged",
                        title="Potential institution name mismatch",
                        reason=(
                            f"The extracted institution name '{doc_name_val}' in '{doc.original_filename}' "
                            f"does not closely match the application name '{app_name}' (similarity: {similarity:.0%})."
                        ),
                        document_id=doc.id,
                        document_name=doc.original_filename,
                        evidence=evidence,
                        next_action="Review the document manually to verify name spelling, change of name approval, or campus variance.",
                    )
                )

        return findings
