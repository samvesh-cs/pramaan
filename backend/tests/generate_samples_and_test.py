"""Generate synthetic sample PDFs and run tests on backend/app/ocr/process_document."""

import sys
import os
from pathlib import Path

# Add project root and backend to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

import pymupdf as fitz
from app.ocr import process_document, ExtractionResult


def create_sample_pdf(file_path: Path, lines: list[str]):
    doc = fitz.open()
    page = doc.new_page()
    # Insert text lines
    y = 72  # 1 inch from top
    for line in lines:
        page.insert_text((72, y), line, fontsize=12)
        y += 24
    file_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(file_path)
    doc.close()


def main():
    samples_dir = PROJECT_ROOT / "backend" / "tests" / "test_samples"
    samples_dir.mkdir(parents=True, exist_ok=True)

    # 1. Fire Safety Certificate
    fire_pdf = samples_dir / "sample_fire_safety.pdf"
    create_sample_pdf(
        fire_pdf,
        [
            "GOVERNMENT FIRE SERVICE DEPARTMENT",
            "FIRE SAFETY COMPLIANCE CERTIFICATE",
            "",
            "Institution: Synthetic ABC Engineering College",
            "Certificate No: FS-2026-104",
            "Date of Issue: 15/01/2026",
            "Valid Until: 31/12/2026",
            "",
            "This certificate is issued after thorough inspection of fire fighting equipment."
        ]
    )

    # 2. Structural Stability Certificate
    struct_pdf = samples_dir / "sample_structural_stability.pdf"
    create_sample_pdf(
        struct_pdf,
        [
            "CHARTERED STRUCTURAL ENGINEERS ASSOCIATION",
            "BUILDING STRUCTURAL STABILITY CERTIFICATE",
            "",
            "Name of Institution: Synthetic ABC Engineering College",
            "Inspection No: SC-2026-88",
            "Structural Engineer Licence: STR-ENG-4412",
            "Date of Inspection: 10/02/2026",
            "Valid for period up to: 09/02/2027",
            "",
            "The institutional building has been inspected and found structurally sound."
        ]
    )

    # 3. Land Title Deed
    land_pdf = samples_dir / "sample_land_deed.pdf"
    create_sample_pdf(
        land_pdf,
        [
            "DEPARTMENT OF REVENUE & REGISTRATION",
            "REGISTERED LAND TITLE DEED",
            "",
            "This is to certify that: Synthetic ABC Engineering College",
            "Registration No: LD-2024-991",
            "Total Land Area: 5.5 Acres",
            "Date of Registration: 20/05/2024",
            "",
            "The land specified above is registered and designated for educational purposes."
        ]
    )

    # 4. Invalid text file
    invalid_file = samples_dir / "invalid_file.txt"
    invalid_file.write_text("Not a PDF or image file")

    print("\n--- TEST 1: Fire Safety Certificate ---")
    res1 = process_document(fire_pdf, document_type="fire_safety_certificate", document_id="doc_001")
    print(f"Status: {res1.processing_status}")
    print(f"Pages: {len(res1.pages)}")
    for k, v in res1.fields.items():
        print(f"  Field '{k}': value={v.value}, normalized={v.normalized_value}, raw='{v.raw_text}'")
    assert res1.processing_status == "processed"
    assert res1.fields["institution_name"].value == "Synthetic ABC Engineering College"
    assert res1.fields["document_number"].value == "FS-2026-104"
    assert res1.fields["expiry_date"].value == "2026-12-31"

    print("\n--- TEST 2: Structural Stability Certificate ---")
    res2 = process_document(struct_pdf, document_type="structural_stability_certificate", document_id="doc_002")
    print(f"Status: {res2.processing_status}")
    for k, v in res2.fields.items():
        print(f"  Field '{k}': value={v.value}, normalized={v.normalized_value}, raw='{v.raw_text}'")
    assert res2.processing_status == "processed"
    assert res2.fields["document_number"].value == "SC-2026-88"
    assert res2.fields["engineer_license_number"].value == "STR-ENG-4412"
    assert res2.fields["expiry_date"].value == "2027-02-09"

    print("\n--- TEST 3: Land Title Deed ---")
    res3 = process_document(land_pdf, document_type="land_title_deed", document_id="doc_003")
    print(f"Status: {res3.processing_status}")
    for k, v in res3.fields.items():
        print(f"  Field '{k}': value={v.value}, normalized={v.normalized_value}, raw='{v.raw_text}'")
    assert res3.processing_status == "processed"
    assert res3.fields["document_number"].value == "LD-2024-991"
    assert res3.fields["land_area"].value == "5.5 Acres"
    assert res3.fields["issue_date"].value == "2024-05-20"

    print("\n--- TEST 4: Graceful handling of invalid file ---")
    res4 = process_document(invalid_file, document_id="doc_004")
    print(f"Status: {res4.processing_status}, Error: {res4.error}")
    assert res4.processing_status == "processing_failed"
    assert "Unsupported file type" in res4.error

    print("\n--- TEST 5: Graceful handling of missing file ---")
    res5 = process_document("nonexistent_file.pdf", document_id="doc_005")
    print(f"Status: {res5.processing_status}, Error: {res5.error}")
    assert res5.processing_status == "processing_failed"
    assert "File not found" in res5.error

    print("\n[SUCCESS] ALL OCR & EXTRACTION TESTS PASSED!")


if __name__ == "__main__":
    main()
