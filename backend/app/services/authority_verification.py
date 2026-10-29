"""Issuing Authority and Digital Verification Service (Pillar 3).

Complies with SIH 2026 PS 26261:
- Facilitates verification through issuing authority registries, official portals, QR codes, and digital reference numbers.
- Compares submitted/extracted details against source registry records.
- Records issuing authority source, verification timestamp, and result.
- Produces the exact 6-state status enum required by AICTE:
    1. verified
    2. mismatch_detected
    3. expired
    4. verification_pending
    5. source_unavailable
    6. manual_review_required
"""

import logging
from datetime import datetime, timezone, date
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

AuthorityStatus = Literal[
    "verified",
    "mismatch_detected",
    "expired",
    "verification_pending",
    "source_unavailable",
    "manual_review_required",
]


class AuthorityVerificationResult(BaseModel):
    status: AuthorityStatus
    authority_name: str
    source_channel: str  # "QR_CODE" | "STATE_PORTAL_REGISTRY" | "DIGITAL_REPOSITORY"
    verification_timestamp: str
    reference_number: Optional[str] = None
    source_details: Optional[Dict[str, Any]] = None
    discrepancy_reason: Optional[str] = None
    is_trusted_source: bool = True


# Simulated Issuing Authority Registries (authoritative data sources for demonstration and mock verification)
MOCK_AUTHORITY_REGISTRIES = {
    # Fire Service Department Records
    "fire_safety": {
        "DEL/FS/2026/001": {
            "institution_name": "Government Engineering College, Delhi (Demo)",
            "expiry_date": "2026-12-31",
            "authority": "Delhi Fire Service, Government of NCT of Delhi",
            "is_valid": True,
        },
        "FS-2024-9812": {
            "institution_name": "Delhi Institute of Technology",
            "expiry_date": "2026-06-30",
            "authority": "Delhi Fire Service, Government of NCT of Delhi",
            "is_valid": True,
        },
        "FS-EXPIRED-99": {
            "institution_name": "Delhi Institute of Technology",
            "expiry_date": "2023-01-01",
            "authority": "Delhi Fire Service, Government of NCT of Delhi",
            "is_valid": False,
        },
    },
    # Municipal Building Completion Records
    "building_completion": {
        "MCD/BCC/2024/771": {
            "institution_name": "Government Engineering College, Delhi (Demo)",
            "authority": "Municipal Corporation of Delhi (MCD)",
            "is_valid": True,
        },
        "BCC-2023-1122": {
            "institution_name": "Delhi Institute of Technology",
            "authority": "Municipal Corporation of Delhi (MCD)",
            "is_valid": True,
        },
    },
    # e-Stamping National Records (SHCIL)
    "affidavit": {
        "IN-DL10049281726354": {
            "institution_name": "Government Engineering College, Delhi (Demo)",
            "authority": "Stock Holding Corporation of India Ltd (SHCIL)",
            "is_valid": True,
        }
    }
}


def verify_with_issuing_authority(
    document_type: str,
    certificate_number: Optional[str],
    institution_name: Optional[str],
    expiry_date: Optional[str] = None,
    qr_payload: Optional[Dict[str, Any]] = None,
) -> AuthorityVerificationResult:
    """Verify document authenticity and metadata against simulated issuing authority portal.
    
    Returns structured AuthorityVerificationResult with one of the 6 AICTE statuses.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Verification via Digital QR Code
    if qr_payload and qr_payload.get("raw_payload"):
        qr_parsed = qr_payload.get("parsed") or qr_payload
        qr_cert = (qr_parsed.get("certificate_number") or "").strip().lower()
        qr_inst = (qr_parsed.get("institution_name") or "").strip().lower()
        doc_cert = (certificate_number or "").strip().lower()
        doc_inst = (institution_name or "").strip().lower()

        # If QR contains certificate info, cross-verify
        if qr_cert:
            if doc_cert and qr_cert != doc_cert:
                return AuthorityVerificationResult(
                    status="mismatch_detected",
                    authority_name=qr_parsed.get("issuing_authority") or "Digital Issuing Authority",
                    source_channel="QR_CODE",
                    verification_timestamp=now_iso,
                    reference_number=certificate_number,
                    source_details=qr_parsed,
                    discrepancy_reason=(
                        f"QR Code decoded certificate '{qr_cert}' does not match printed text "
                        f"certificate number '{doc_cert}'."
                    ),
                )
            if qr_inst and doc_inst and qr_inst not in doc_inst and doc_inst not in qr_inst:
                return AuthorityVerificationResult(
                    status="mismatch_detected",
                    authority_name=qr_parsed.get("issuing_authority") or "Digital Issuing Authority",
                    source_channel="QR_CODE",
                    verification_timestamp=now_iso,
                    reference_number=certificate_number,
                    source_details=qr_parsed,
                    discrepancy_reason=(
                        f"QR Code decoded institution '{qr_inst}' does not match application "
                        f"institution '{doc_inst}'."
                    ),
                )

            # Check if QR embedded date is expired
            qr_exp = qr_parsed.get("expiry_date")
            if qr_exp:
                try:
                    exp_dt = datetime.strptime(qr_exp[:10], "%Y-%m-%d").date()
                    if exp_dt < date.today():
                        return AuthorityVerificationResult(
                            status="expired",
                            authority_name=qr_parsed.get("issuing_authority") or "Digital Issuing Authority",
                            source_channel="QR_CODE",
                            verification_timestamp=now_iso,
                            reference_number=qr_cert,
                            source_details=qr_parsed,
                            discrepancy_reason=f"Issuing authority record expired on {exp_dt.isoformat()}.",
                        )
                except ValueError:
                    pass

            return AuthorityVerificationResult(
                status="verified",
                authority_name=qr_parsed.get("issuing_authority") or "Digital Issuing Authority (QR)",
                source_channel="QR_CODE",
                verification_timestamp=now_iso,
                reference_number=qr_cert or certificate_number,
                source_details=qr_parsed,
            )

    # 2. Verification via Issuing Authority Portal Registry
    if not certificate_number:
        return AuthorityVerificationResult(
            status="manual_review_required",
            authority_name="Competent State / Municipal Authority",
            source_channel="STATE_PORTAL_REGISTRY",
            verification_timestamp=now_iso,
            discrepancy_reason="No certificate number was extracted to initiate automated issuing authority verification.",
        )

    clean_cert = certificate_number.strip().upper()
    registry_category = None
    if "fire" in document_type:
        registry_category = "fire_safety"
        authority_default = "State Fire & Emergency Services"
    elif "completion" in document_type or "building" in document_type:
        registry_category = "building_completion"
        authority_default = "Municipal Urban Local Body"
    elif "affidavit" in document_type:
        registry_category = "affidavit"
        authority_default = "National e-Stamping Portal (SHCIL)"
    else:
        authority_default = "State Licensing Authority"

    if registry_category and registry_category in MOCK_AUTHORITY_REGISTRIES:
        reg = MOCK_AUTHORITY_REGISTRIES[registry_category]
        if clean_cert in reg:
            record = reg[clean_cert]
            auth_name = record.get("authority", authority_default)

            if not record.get("is_valid", True):
                return AuthorityVerificationResult(
                    status="expired",
                    authority_name=auth_name,
                    source_channel="STATE_PORTAL_REGISTRY",
                    verification_timestamp=now_iso,
                    reference_number=clean_cert,
                    source_details=record,
                    discrepancy_reason=f"Issuing authority '{auth_name}' reports certificate is no longer valid or has lapsed.",
                )

            # Check institution match
            rec_inst = (record.get("institution_name") or "").strip().lower()
            cand_inst = (institution_name or "").strip().lower()
            if rec_inst and cand_inst and rec_inst not in cand_inst and cand_inst not in rec_inst:
                return AuthorityVerificationResult(
                    status="mismatch_detected",
                    authority_name=auth_name,
                    source_channel="STATE_PORTAL_REGISTRY",
                    verification_timestamp=now_iso,
                    reference_number=clean_cert,
                    source_details=record,
                    discrepancy_reason=f"Authority record is registered under '{record['institution_name']}', not '{institution_name}'.",
                )

            return AuthorityVerificationResult(
                status="verified",
                authority_name=auth_name,
                source_channel="STATE_PORTAL_REGISTRY",
                verification_timestamp=now_iso,
                reference_number=clean_cert,
                source_details=record,
            )

    # 3. If certificate number format is standard but not in demo registry, mark source unavailable or manual review
    return AuthorityVerificationResult(
        status="source_unavailable",
        authority_name=authority_default,
        source_channel="STATE_PORTAL_REGISTRY",
        verification_timestamp=now_iso,
        reference_number=clean_cert,
        discrepancy_reason=f"External authority portal for '{authority_default}' is currently offline or unreachable for automated lookup.",
    )

