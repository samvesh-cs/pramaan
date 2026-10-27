"""Generate updated synthetic test set in backend/tests/samples with the 3 agreed document types:
  1. fire_safety_certificate
  2. building_completion_certificate
  3. affidavit_2

Includes variants:
  - clean PDF
  - scanned-style image
  - noisy image
  - tilted image
  - missing-field variant
  - expired variant
  - plus bad-input cases (corrupt, empty, unsupported, password-protected).

Generates backend/tests/ground_truth.json.
"""

import os
import shutil
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import pymupdf as fitz

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(BASE_DIR, "samples")

# Clean out old samples directory
if os.path.exists(SAMPLES_DIR):
    shutil.rmtree(SAMPLES_DIR)
os.makedirs(SAMPLES_DIR, exist_ok=True)


# 1. Clean PDF: fire_safety_certificate
def create_clean_fire_safety(path):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    text = (
        "GOVERNMENT OF NCT OF DELHI\n"
        "DELHI FIRE SERVICES DEPARTMENT\n"
        "FIRE SAFETY COMPLIANCE CERTIFICATE\n\n"
        "Issuing Authority: Delhi Fire Services Department\n"
        "Certificate No: FS-2026-881\n"
        "Date of Issue: 10/02/2026\n"
        "Valid Upto: 09/02/2027\n\n"
        "Name of the Institution: Synthetic ABC Institute of Technology\n\n"
        "Certified that the educational premises comprised of ground plus three upper floors "
        "have complied with fire safety directives under Rule 33 of Delhi Fire Service Rules."
    )
    page.insert_text((50, 80), text, fontsize=12)
    doc.save(path)
    doc.close()


# 2. Expired PDF variant: fire_safety_certificate
def create_expired_fire_safety(path):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    text = (
        "GOVERNMENT OF NCT OF DELHI\n"
        "DELHI FIRE SERVICES DEPARTMENT\n"
        "FIRE SAFETY COMPLIANCE CERTIFICATE\n\n"
        "Issuing Authority: Delhi Fire Services Department\n"
        "Certificate No: FS-2023-104\n"
        "Date of Issue: 15/01/2023\n"
        "Valid Until: 14/01/2024\n\n"
        "Institution Name: Synthetic ABC Institute of Technology\n\n"
        "Inspection completed for academic year 2023. Validity expired."
    )
    page.insert_text((50, 80), text, fontsize=12)
    doc.save(path)
    doc.close()


# 3. Missing-field PDF variant: fire_safety_certificate (expiry_date missing)
def create_missing_field_fire_safety(path):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    text = (
        "GOVERNMENT OF NCT OF DELHI\n"
        "DELHI FIRE SERVICES DEPARTMENT\n"
        "PROVISIONAL FIRE NOC\n\n"
        "Issuing Authority: Delhi Fire Services Department\n"
        "NOC No: FS-2026-550\n"
        "Date of Issue: 01/03/2026\n\n"
        "Premises of: Synthetic ABC Institute of Technology\n\n"
        "Provisional NOC issued pending installation of automatic sprinklers. Expiry date omitted."
    )
    page.insert_text((50, 80), text, fontsize=12)
    doc.save(path)
    doc.close()


# 4. Scanned-style image: building_completion_certificate
def create_scanned_building_completion(path):
    img = Image.new("RGB", (1240, 1754), color=(248, 248, 245))
    draw = ImageDraw.Draw(img)
    lines = [
        ("GREATER NOIDA INDUSTRIAL DEVELOPMENT AUTHORITY", 100, 120),
        ("BUILDING COMPLETION AND OCCUPANCY CERTIFICATE", 90, 180),
        ("Issuing Authority: Greater Noida Industrial Development Authority", 80, 280),
        ("Building Completion Certificate No: BCC-2025-901", 80, 360),
        ("Date of Issue: 20/08/2025", 80, 440),
        ("Institution Name: Synthetic ABC Institute of Technology", 80, 520),
        ("Certified that instructional building block A and B have been completed per approved plan.", 80, 620),
        ("Sanctioned under Building Regulations Clause 7.17 of AICTE Handbook.", 80, 700),
    ]
    for text, x, y in lines:
        draw.text((x, y), text, fill=(20, 20, 20))
    img.save(path, "PNG")


# 5. Noisy image variant: building_completion_certificate
def create_noisy_building_completion(path):
    img = Image.new("RGB", (1100, 1500), color=(238, 235, 228))
    draw = ImageDraw.Draw(img)
    lines = [
        ("MUNICIPAL CORPORATION OF GREATER MUMBAI", 80, 100),
        ("FORM D - OCCUPANCY / COMPLETION CERTIFICATE", 70, 160),
        ("Issuing Authority: Municipal Corporation of Greater Mumbai", 60, 260),
        ("Certificate No: BCC-2025-442", 60, 340),
        ("Date of Completion: 10/11/2025", 60, 420),
        ("Name of the Institution: Synthetic ABC Institute of Technology", 60, 500),
        ("The building complies with municipal building development controls.", 60, 600),
    ]
    for text, x, y in lines:
        draw.text((x, y), text, fill=(35, 35, 35))

    # Add noise & compression artifacts
    np_img = np.array(img)
    noise = np.random.normal(0, 12, np_img.shape).astype(np.int16)
    noisy_img = np.clip(np_img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    res_img = Image.fromarray(noisy_img)
    res_img = res_img.filter(ImageFilter.GaussianBlur(radius=0.5))
    res_img.save(path, "PNG")


# 6. Clean PDF: affidavit_2
def create_clean_affidavit_2(path):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    text = (
        "GOVERNMENT OF INDIA\n"
        "NON-JUDICIAL E-STAMP CERTIFICATE - RS. 100\n"
        "FORMAT OF AFFIDAVIT - 2 (Clause 2.1(i) of Annexure-2)\n\n"
        "I, Rajesh Kumar Sharma, Chairman of the Trust, on behalf of\n"
        "Synthetic ABC Institute of Technology do hereby solemnly affirm and state:\n\n"
        "1. That the information furnished in the AICTE application portal is true and correct.\n"
        "2. That the institution possesses required land, buildings and faculty per AICTE norms.\n"
        "3. That all uploaded certificates including Fire Safety and Completion are genuine.\n\n"
        "Deponent: Rajesh Kumar Sharma\n\n"
        "Sworn before me on: 15/01/2026\n"
        "Notary Public, New Delhi"
    )
    page.insert_text((50, 80), text, fontsize=12)
    doc.save(path)
    doc.close()


# 7. Tilted image variant: affidavit_2
def create_tilted_affidavit_2(path):
    img = Image.new("RGB", (1240, 1754), color=(250, 250, 248))
    draw = ImageDraw.Draw(img)
    lines = [
        ("GOVERNMENT OF INDIA E-STAMP", 120, 100),
        ("AFFIDAVIT - 2 (AICTE EOA SELF-DISCLOSURE)", 100, 170),
        ("I, Vikram Singh, Secretary, deponent for", 80, 280),
        ("Institution Name: Synthetic ABC Institute of Technology", 80, 360),
        ("solemnly declare that all statutory requirements are duly fulfilled.", 80, 460),
        ("Deponent Name: Vikram Singh", 80, 560),
        ("Sworn before me on: 18/02/2026", 80, 660),
        ("Advocate & Notary Public", 80, 740),
    ]
    for text, x, y in lines:
        draw.text((x, y), text, fill=(25, 25, 25))

    # Tilt by 1.8 degrees
    tilted = img.rotate(1.8, expand=True, fillcolor=(250, 250, 248))
    tilted.save(path, "PNG")


# 8. Corrupt file: corrupt_doc.pdf
def create_corrupt_file(path):
    with open(path, "wb") as f:
        f.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\nBroken invalid content\x00\xff\xfe")


# 9. Empty file: empty_doc.pdf
def create_empty_file(path):
    with open(path, "wb") as f:
        pass


# 10. Unsupported file: unsupported_format.docx
def create_unsupported_file(path):
    with open(path, "wb") as f:
        f.write(b"PK\x03\x04Unsupported MS Word format archive")


# 11. Password-protected PDF: password_protected.pdf
def create_password_pdf(path):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 80), "Encrypted Confidential Document\nInstitution: Synthetic ABC Institute of Technology", fontsize=12)
    perm = fitz.PDF_PERM_ACCESSIBILITY
    encrypt_meth = fitz.PDF_ENCRYPT_AES_256
    doc.save(path, encryption=encrypt_meth, user_pw="secret123", owner_pw="adminpass", permissions=perm)
    doc.close()


def generate_all():
    files = {
        "clean_fire_safety.pdf": os.path.join(SAMPLES_DIR, "clean_fire_safety.pdf"),
        "expired_fire_safety.pdf": os.path.join(SAMPLES_DIR, "expired_fire_safety.pdf"),
        "missing_field_fire_safety.pdf": os.path.join(SAMPLES_DIR, "missing_field_fire_safety.pdf"),
        "scanned_building_completion.png": os.path.join(SAMPLES_DIR, "scanned_building_completion.png"),
        "noisy_building_completion.png": os.path.join(SAMPLES_DIR, "noisy_building_completion.png"),
        "clean_affidavit_2.pdf": os.path.join(SAMPLES_DIR, "clean_affidavit_2.pdf"),
        "tilted_affidavit_2.png": os.path.join(SAMPLES_DIR, "tilted_affidavit_2.png"),
        "corrupt_doc.pdf": os.path.join(SAMPLES_DIR, "corrupt_doc.pdf"),
        "empty_doc.pdf": os.path.join(SAMPLES_DIR, "empty_doc.pdf"),
        "unsupported_format.docx": os.path.join(SAMPLES_DIR, "unsupported_format.docx"),
        "password_protected.pdf": os.path.join(SAMPLES_DIR, "password_protected.pdf"),
    }

    create_clean_fire_safety(files["clean_fire_safety.pdf"])
    create_expired_fire_safety(files["expired_fire_safety.pdf"])
    create_missing_field_fire_safety(files["missing_field_fire_safety.pdf"])
    create_scanned_building_completion(files["scanned_building_completion.png"])
    create_noisy_building_completion(files["noisy_building_completion.png"])
    create_clean_affidavit_2(files["clean_affidavit_2.pdf"])
    create_tilted_affidavit_2(files["tilted_affidavit_2.png"])
    create_corrupt_file(files["corrupt_doc.pdf"])
    create_empty_file(files["empty_doc.pdf"])
    create_unsupported_file(files["unsupported_format.docx"])
    create_password_pdf(files["password_protected.pdf"])

    ground_truth = {
        "clean_fire_safety.pdf": {
            "category": "clean PDF",
            "document_type": "fire_safety_certificate",
            "expected_processing_status": "processed",
            "expected_fields": {
                "institution_name": "Synthetic ABC Institute of Technology",
                "document_number": "FS-2026-881",
                "issue_date": "2026-02-10",
                "expiry_date": "2027-02-09",
                "issuing_authority": "Delhi Fire Services Department"
            }
        },
        "expired_fire_safety.pdf": {
            "category": "expired variant (PDF)",
            "document_type": "fire_safety_certificate",
            "expected_processing_status": "processed",
            "expected_fields": {
                "institution_name": "Synthetic ABC Institute of Technology",
                "document_number": "FS-2023-104",
                "issue_date": "2023-01-15",
                "expiry_date": "2024-01-14",
                "issuing_authority": "Delhi Fire Services Department"
            }
        },
        "missing_field_fire_safety.pdf": {
            "category": "missing-field variant (PDF)",
            "document_type": "fire_safety_certificate",
            "expected_processing_status": "processed",
            "expected_fields": {
                "institution_name": "Synthetic ABC Institute of Technology",
                "document_number": "FS-2026-550",
                "issue_date": "2026-03-01",
                "expiry_date": None,
                "issuing_authority": "Delhi Fire Services Department"
            }
        },
        "scanned_building_completion.png": {
            "category": "scanned-style image",
            "document_type": "building_completion_certificate",
            "expected_processing_status": "processed",
            "expected_fields": {
                "institution_name": "Synthetic ABC Institute of Technology",
                "document_number": "BCC-2025-901",
                "issue_date": "2025-08-20",
                "issuing_authority": "Greater Noida Industrial Development Authority"
            }
        },
        "noisy_building_completion.png": {
            "category": "noisy image variant",
            "document_type": "building_completion_certificate",
            "expected_processing_status": "processed",
            "expected_fields": {
                "institution_name": "Synthetic ABC Institute of Technology",
                "document_number": "BCC-2025-442",
                "issue_date": "2025-11-10",
                "issuing_authority": "Municipal Corporation of Greater Mumbai"
            }
        },
        "clean_affidavit_2.pdf": {
            "category": "clean PDF",
            "document_type": "affidavit_2",
            "expected_processing_status": "processed",
            "expected_fields": {
                "institution_name": "Synthetic ABC Institute of Technology",
                "notary_date": "2026-01-15",
                "signatory_name": "Rajesh Kumar Sharma"
            }
        },
        "tilted_affidavit_2.png": {
            "category": "tilted image variant",
            "document_type": "affidavit_2",
            "expected_processing_status": "processed",
            "expected_fields": {
                "institution_name": "Synthetic ABC Institute of Technology",
                "notary_date": "2026-02-18",
                "signatory_name": "Vikram Singh"
            }
        },
        "corrupt_doc.pdf": {
            "category": "bad input: corrupt file",
            "document_type": "fire_safety_certificate",
            "expected_processing_status": "processing_failed",
            "expected_fields": {}
        },
        "empty_doc.pdf": {
            "category": "bad input: empty file",
            "document_type": "fire_safety_certificate",
            "expected_processing_status": "processing_failed",
            "expected_fields": {}
        },
        "unsupported_format.docx": {
            "category": "bad input: unsupported type",
            "document_type": "fire_safety_certificate",
            "expected_processing_status": "processing_failed",
            "expected_fields": {}
        },
        "password_protected.pdf": {
            "category": "bad input: password-protected PDF",
            "document_type": "building_completion_certificate",
            "expected_processing_status": "processing_failed",
            "expected_fields": {}
        }
    }

    gt_path = os.path.join(BASE_DIR, "ground_truth.json")
    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2)

    print(f"Generated {len(files)} synthetic documents in: {SAMPLES_DIR}")
    print(f"Updated ground truth in: {gt_path}")


if __name__ == "__main__":
    generate_all()
