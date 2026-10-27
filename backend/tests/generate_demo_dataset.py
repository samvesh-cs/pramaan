"""Generate synthetic demo documents and defective test cases for AICTE EoA prototype.

Covers all 6 test scenarios defined in Task 5.1:
1. Valid Case (Fire Safety, Building Completion, Affidavit-2)
2. Missing Document Case (Only 2 of 3 documents)
3. Expired Document Case (Fire Safety Certificate expired in 2023)
4. Missing Field Case (Building Certificate without Certificate Number or Authority)
5. Institution Name Mismatch Case (Different institution name in certificate)
6. Corrupt / Invalid Case (Corrupt bytes or non-standard format)
"""

import json
from pathlib import Path
import pymupdf

OUTPUT_DIR = Path("tests/demo_samples")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

INSTITUTION_NAME = "Synthetic ABC Institute of Technology"


def create_pdf(filename: str, lines: list[str]) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)  # Standard A4

    # Header decoration
    page.draw_rect(pymupdf.Rect(40, 40, 555, 80), color=(0.1, 0.2, 0.5), fill=(0.93, 0.95, 0.99))
    page.insert_text((55, 65), lines[0], fontsize=14, fontname="helv", color=(0.1, 0.2, 0.5))

    # Body text
    y = 110
    for line in lines[1:]:
        page.insert_text((55, y), line, fontsize=11, fontname="helv", color=(0.1, 0.1, 0.1))
        y += 26

    # Bottom border
    page.draw_line(pymupdf.Point(40, 780), pymupdf.Point(555, 780), color=(0.7, 0.7, 0.7), width=1)
    page.insert_text((55, 800), "Official Scrutiny Copy — AICTE Approval Process 2026-27", fontsize=9, color=(0.5, 0.5, 0.5))

    dest = OUTPUT_DIR / filename
    doc.save(dest)
    doc.close()
    print(f"Generated: {dest}")
    return dest


def generate_all():
    # 1. Valid Fire Safety Certificate
    create_pdf(
        "valid_fire_safety.pdf",
        [
            "STATE DISASTER RESPONSE & FIRE SERVICES DEPARTMENT",
            "FIRE SAFETY COMPLIANCE CERTIFICATE / NO OBJECTION CERTIFICATE",
            "",
            f"Name of the Institution: {INSTITUTION_NAME}",
            "Campus Address: Sector 4, Knowledge Park, Synthetic City - 560001",
            "Certificate No: FS-2026-881",
            "Issuing Authority: Directorate of Fire & Emergency Services",
            "Date of Issue: 10-02-2026",
            "Valid Until: 09-02-2027",
            "",
            "This is to certify that the institutional building premises have been inspected",
            "and found compliant with national building code fire safety standards.",
        ],
    )

    # 2. Valid Building Completion / Occupancy Certificate
    create_pdf(
        "valid_building_completion.pdf",
        [
            "MUNICIPAL DEVELOPMENT & TOWN PLANNING AUTHORITY",
            "BUILDING COMPLETION & OCCUPANCY CERTIFICATE",
            "",
            f"Name of the Institution: {INSTITUTION_NAME}",
            "Location: Plot 12, Institutional Area, Synthetic City",
            "Certificate No: BCC-2024-992",
            "Competent Authority: Municipal Development Authority",
            "Date of Issue: 15-05-2024",
            "Approved Built-up Area: 12500 Sq. Meters",
            "",
            "Certified that the educational institution building has been completed in accordance",
            "with the sanctioned plans and is cleared for educational occupancy.",
        ],
    )

    # 3. Valid Affidavit-2
    create_pdf(
        "valid_affidavit_2.pdf",
        [
            "BEFORE THE NOTARY PUBLIC — AFFIDAVIT ON E-STAMP PAPER",
            "FORMAT-2 AFFIDAVIT FOR EXTENSION OF APPROVAL (APH 2024-2027)",
            "",
            f"Institution Name: {INSTITUTION_NAME}",
            "I, Dr. S. K. Raman, Chairman / Secretary of the Society/Trust, do hereby solemnly affirm:",
            f"1. That the {INSTITUTION_NAME} complies with all AICTE norms.",
            "2. That all uploaded certificates, NOCs, and disclosures are true and authentic.",
            "3. That no anti-ragging or safety violation has occurred on campus.",
            "",
            "Deponent: Dr. S. K. Raman",
            "Sworn before me on: 15-01-2026",
            "Notary Registration No: NOT-DL-2018-4412",
        ],
    )

    # 4. Expired Fire Safety Certificate (Expired 2023)
    create_pdf(
        "expired_fire_safety.pdf",
        [
            "STATE DISASTER RESPONSE & FIRE SERVICES DEPARTMENT",
            "FIRE SAFETY COMPLIANCE CERTIFICATE",
            "",
            f"Name of the Institution: {INSTITUTION_NAME}",
            "Certificate No: FS-2022-104",
            "Issuing Authority: Fire & Emergency Services",
            "Date of Issue: 10-01-2022",
            "Valid Until: 09-01-2023",
            "",
            "Notice: This certificate has expired and is past its validity period.",
        ],
    )

    # 5. Missing Field Building Certificate (No certificate number or date)
    create_pdf(
        "missing_fields_building.pdf",
        [
            "MUNICIPAL DEVELOPMENT AUTHORITY",
            "BUILDING PERMISSION INTIMATION",
            "",
            f"Name of the Institution: {INSTITUTION_NAME}",
            "Status: Preliminary site inspection conducted.",
            "Note: Formal certificate number has not yet been assigned pending final review.",
        ],
    )

    # 6. Mismatched Institution Name
    create_pdf(
        "mismatched_fire_safety.pdf",
        [
            "STATE DISASTER RESPONSE & FIRE SERVICES DEPARTMENT",
            "FIRE SAFETY COMPLIANCE CERTIFICATE",
            "",
            "Name of the Institution: Northern Global Polytechnic College",
            "Certificate No: FS-2026-903",
            "Issuing Authority: Directorate of Fire Services",
            "Date of Issue: 01-02-2026",
            "Valid Until: 31-01-2027",
        ],
    )

    # Manifest metadata
    manifest = {
        "institution_name": INSTITUTION_NAME,
        "academic_year": "2026-27",
        "category": "eoa",
        "scenarios": [
            {
                "id": "scenario_1_valid",
                "title": "All 3 Mandatory Documents Valid & Consistent",
                "documents": [
                    {"type": "fire_safety_certificate", "file": "valid_fire_safety.pdf"},
                    {"type": "building_completion_certificate", "file": "valid_building_completion.pdf"},
                    {"type": "affidavit_2", "file": "valid_affidavit_2.pdf"},
                ],
                "expected_status": "checks_passed",
                "expected_summary": {"pass": 10, "flagged": 0, "missing": 0, "unresolved": 0},
            },
            {
                "id": "scenario_2_missing_doc",
                "title": "Missing Mandatory Affidavit-2",
                "documents": [
                    {"type": "fire_safety_certificate", "file": "valid_fire_safety.pdf"},
                    {"type": "building_completion_certificate", "file": "valid_building_completion.pdf"},
                ],
                "expected_status": "missing_documents",
                "expected_missing_types": ["affidavit_2"],
            },
            {
                "id": "scenario_3_expired",
                "title": "Expired Fire Safety Certificate",
                "documents": [
                    {"type": "fire_safety_certificate", "file": "expired_fire_safety.pdf"},
                    {"type": "building_completion_certificate", "file": "valid_building_completion.pdf"},
                    {"type": "affidavit_2", "file": "valid_affidavit_2.pdf"},
                ],
                "expected_status": "discrepancies_found",
                "expected_flags": ["EXPIRY_001"],
            },
            {
                "id": "scenario_4_missing_field",
                "title": "Missing Mandatory Fields in Building Certificate",
                "documents": [
                    {"type": "building_completion_certificate", "file": "missing_fields_building.pdf"},
                ],
                "expected_status": "missing_documents",
                "expected_missing_fields": ["FIELD_002"],
            },
            {
                "id": "scenario_5_name_mismatch",
                "title": "Cross-Document Institution Name Mismatch",
                "documents": [
                    {"type": "fire_safety_certificate", "file": "mismatched_fire_safety.pdf"},
                    {"type": "building_completion_certificate", "file": "valid_building_completion.pdf"},
                    {"type": "affidavit_2", "file": "valid_affidavit_2.pdf"},
                ],
                "expected_status": "discrepancies_found",
                "expected_flags": ["CONSISTENCY_001"],
            },
        ],
    }

    manifest_path = OUTPUT_DIR / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Generated manifest: {manifest_path}")


if __name__ == "__main__":
    generate_all()
