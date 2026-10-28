from typing import Any

# AICTE APH 2024-2027 Document Checklist for Extension of Approval (EoA)

EOA_DOCUMENT_CHECKLIST: dict[str, dict[str, Any]] = {
    "fire_safety_certificate": {
        "display_name": "Fire Safety Certificate",
        "applicability": "required",
        "source": "APH 2024-2027, Annexure-2, §2.1(v)",
        "has_expiry": True,
        "required_fields": [
            "institution_name",
            "certificate_number",
            "issue_date",
            "expiry_date",
            "issuing_authority",
        ],
        "description": "Valid Fire Safety Certificate / NOC issued by the Competent Authority",
    },
    "building_completion_certificate": {
        "display_name": "Occupancy/Completion Certificate/Building License/Form D",
        "applicability": "required",
        "source": "APH 2024-2027, Annexure-2, §2.1(iii), Clause 7.17",
        "has_expiry": False,
        "required_fields": [
            "institution_name",
            "certificate_number",
            "issue_date",
            "issuing_authority",
        ],
        "description": "Valid Occupancy/Completion Certificate/Building License/Form D issued by the Competent Authority",
    },
    "affidavit_2": {
        "display_name": "Affidavit-2",
        "applicability": "required",
        "source": "APH 2024-2027, Annexure-2, §2.1(i)",
        "has_expiry": False,
        "required_fields": [
            "institution_name",
            "affidavit_date",
            "deponent_name",
        ],
        "description": "Sworn Affidavit with digital signature of Chairman/Secretary on e-stamp paper",
    },
    "ter_payment_receipt": {
        "display_name": "TER Payment Receipt",
        "applicability": "required_if_applicable",
        "source": "APH 2024-2027, Annexure-2, §2.1(ii)",
        "has_expiry": False,
        "required_fields": [
            "institution_name",
            "receipt_number",
            "transaction_date",
            "amount_inr",
        ],
        "description": "Payment receipt of Technical Education Regulatory (TER) charges paid via AICTE portal",
    },
    "structural_stability_certificate": {
        "display_name": "Structural Stability Certificate",
        "applicability": "required_if_applicable",
        "source": "APH 2024-2027, Annexure-2, §2.1(iv)",
        "condition": "Mandatory only if Building is > 30 years old from date of Completion Certificate",
        "has_expiry": False,
        "required_fields": [
            "institution_name",
            "certificate_number",
            "engineer_license_number",
            "issue_date",
        ],
        "description": "Certificate from registered Structural Engineer regarding building stability (> 30 yrs)",
    },
}

# Supported document types for upload
EOA_MVP_DOCUMENT_TYPES = list(EOA_DOCUMENT_CHECKLIST.keys())

# Full EoA checklist reference for broader handbook roadmap
EOA_FULL_CHECKLIST: dict[str, dict[str, Any]] = {
    **EOA_DOCUMENT_CHECKLIST,
    "satellite_map": {
        "display_name": "Satellite Map with Lat/Long",
        "applicability": "required",
        "source": "APH 2024-2027, Annexure-2, §2.1(vi)",
    },
    "audited_accounts": {
        "display_name": "Audited Statement of Accounts",
        "applicability": "required",
        "source": "APH 2024-2027, Annexure-2, §2.1(vii)",
    },
}
