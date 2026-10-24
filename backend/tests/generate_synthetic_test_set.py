"""Generate synthetic test set in backend/tests/samples with 8 documents and backend/tests/ground_truth.json."""

import os
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import pymupdf as fitz

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(BASE_DIR, "samples")
os.makedirs(SAMPLES_DIR, exist_ok=True)

# 1. Clean PDF: fire_safety_certificate
def create_clean_pdf(output_path):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842) # A4
    text = (
        "GOVERNMENT FIRE & RESCUE SERVICES DEPARTMENT\n"
        "FIRE SAFETY COMPLIANCE CERTIFICATE\n\n"
        "Institution Name: Synthetic ABC Institute of Technology\n"
        "Certificate No: FS-2026-881\n"
        "Date of Issue: 10/02/2026\n"
        "Valid Until: 09/02/2027\n\n"
        "This is to certify that the premises of Synthetic ABC Institute of Technology have been inspected "
        "and found to comply with the National Building Code fire protection norms."
    )
    page.insert_text((50, 80), text, fontsize=12)
    doc.save(output_path)
    doc.close()

# 2. Scanned-style image: structural_stability_certificate
def create_scanned_image(output_path):
    img = Image.new("RGB", (1240, 1754), color=(248, 248, 246))
    draw = ImageDraw.Draw(img)
    lines = [
        ("OFFICE OF ACCREDITED STRUCTURAL ENGINEERS", 100, 120),
        ("STRUCTURAL STABILITY & SOUNDNESS CERTIFICATE", 90, 180),
        ("Institution Name: Synthetic ABC Institute of Technology", 80, 320),
        ("Certificate No: SSC-2026-402", 80, 400),
        ("Engineer License Number: STR-ENG-9821", 80, 480),
        ("Date of Inspection: 20/01/2026", 80, 560),
        ("Valid Until: 19/01/2031", 80, 640),
        ("This is to certify that all instructional buildings and structures are sound and safe.", 80, 750)
    ]
    for text, x, y in lines:
        draw.text((x, y), text, fill=(20, 20, 20))
    img.save(output_path, "PNG")

# 3. Low-quality image: land_title_deed (with noise, low-res and slight blur)
def create_low_quality_image(output_path):
    img = Image.new("RGB", (800, 1100), color=(235, 230, 220))
    draw = ImageDraw.Draw(img)
    lines = [
        ("REGISTRATION AND REVENUE DEPARTMENT", 50, 80),
        ("CERTIFIED COPY OF LAND TITLE DEED", 50, 130),
        ("Institution Name: Synthetic ABC Institute of Technology", 50, 220),
        ("Deed No: DEED-2026-5541", 50, 280),
        ("Total Land Area: 10.5 Acres", 50, 340),
        ("Date of Registration: 15/11/2025", 50, 400),
        ("Survey / Khasra No: 142/1, Village Ramnagar", 50, 460),
    ]
    for text, x, y in lines:
        draw.text((x, y), text, fill=(40, 40, 40))
    
    # Add noise
    np_img = np.array(img)
    noise = np.random.normal(0, 15, np_img.shape).astype(np.int16)
    noisy_img = np.clip(np_img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(noisy_img)
    img = img.filter(ImageFilter.GaussianBlur(radius=0.8))
    img.save(output_path, "PNG", quality=40)

# 4. Multi-page PDF: structural_stability_certificate (Page 1 + Page 2)
def create_multipage_pdf(output_path):
    doc = fitz.open()
    # Page 1
    p1 = doc.new_page(width=595, height=842)
    p1_text = (
        "CONSULTING STRUCTURAL ENGINEERS & ASSESSORS\n"
        "COMPREHENSIVE STRUCTURAL AUDIT REPORT\n\n"
        "Institution Name: Synthetic ABC Institute of Technology\n"
        "Campus Location: Sector 12, Knowledge Park\n\n"
        "Page 1 of 2: Preliminary Site Inspection Summary.\n"
        "Visual assessment and non-destructive rebound hammer tests conducted."
    )
    p1.insert_text((50, 80), p1_text, fontsize=12)

    # Page 2
    p2 = doc.new_page(width=595, height=842)
    p2_text = (
        "FINAL COMPLIANCE & CERTIFICATION DETAILS\n\n"
        "Certificate No: SSC-2026-905\n"
        "Engineer License Number: SE-LIC-4421\n"
        "Date of Inspection: 01/03/2026\n"
        "Valid Until: 28/02/2029\n\n"
        "The institutional superstructure satisfies seismic zone III design criteria."
    )
    p2.insert_text((50, 80), p2_text, fontsize=12)
    doc.save(output_path)
    doc.close()

# 5. Corrupt file: corrupt_doc.pdf
def create_corrupt_file(output_path):
    with open(output_path, "wb") as f:
        f.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\nThis is completely broken and corrupt content.\x00\xff\xfe\x00")

# 6. Empty file: empty_doc.pdf
def create_empty_file(output_path):
    with open(output_path, "wb") as f:
        pass

# 7. Unsupported type: unsupported_format.docx
def create_unsupported_file(output_path):
    with open(output_path, "wb") as f:
        f.write(b"PK\x03\x04Mock Docx unsupported archive content.")

# 8. Password-protected PDF: password_protected.pdf
def create_password_pdf(output_path):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 80), "Encrypted Confidential Document\nInstitution: Synthetic ABC Institute of Technology", fontsize=12)
    # Encrypt with owner/user password
    perm = fitz.PDF_PERM_ACCESSIBILITY
    encrypt_meth = fitz.PDF_ENCRYPT_AES_256
    doc.save(output_path, encryption=encrypt_meth, user_pw="secret123", owner_pw="adminpass", permissions=perm)
    doc.close()


def generate_all():
    files = {
        "clean_pdf": os.path.join(SAMPLES_DIR, "clean_fire_safety.pdf"),
        "scanned_image": os.path.join(SAMPLES_DIR, "scanned_structural_stability.png"),
        "low_quality_image": os.path.join(SAMPLES_DIR, "low_quality_land_deed.png"),
        "multipage_pdf": os.path.join(SAMPLES_DIR, "multipage_structural_stability.pdf"),
        "corrupt_file": os.path.join(SAMPLES_DIR, "corrupt_doc.pdf"),
        "empty_file": os.path.join(SAMPLES_DIR, "empty_doc.pdf"),
        "unsupported_type": os.path.join(SAMPLES_DIR, "unsupported_format.docx"),
        "password_protected_pdf": os.path.join(SAMPLES_DIR, "password_protected.pdf")
    }

    create_clean_pdf(files["clean_pdf"])
    create_scanned_image(files["scanned_image"])
    create_low_quality_image(files["low_quality_image"])
    create_multipage_pdf(files["multipage_pdf"])
    create_corrupt_file(files["corrupt_file"])
    create_empty_file(files["empty_file"])
    create_unsupported_file(files["unsupported_type"])
    create_password_pdf(files["password_protected_pdf"])

    ground_truth = {
        "clean_fire_safety.pdf": {
            "category": "clean PDF",
            "document_type": "fire_safety_certificate",
            "expected_processing_status": "processed",
            "expected_fields": {
                "institution_name": "Synthetic ABC Institute of Technology",
                "document_number": "FS-2026-881",
                "issue_date": "2026-02-10",
                "expiry_date": "2027-02-09"
            }
        },
        "scanned_structural_stability.png": {
            "category": "scanned-style image",
            "document_type": "structural_stability_certificate",
            "expected_processing_status": "processed",
            "expected_fields": {
                "institution_name": "Synthetic ABC Institute of Technology",
                "document_number": "SSC-2026-402",
                "engineer_license_number": "STR-ENG-9821",
                "issue_date": "2026-01-20",
                "expiry_date": "2031-01-19"
            }
        },
        "low_quality_land_deed.png": {
            "category": "low-quality image",
            "document_type": "land_title_deed",
            "expected_processing_status": "processed",
            "expected_fields": {
                "institution_name": "Synthetic ABC Institute of Technology",
                "document_number": "DEED-2026-5541",
                "land_area": "10.5 Acres",
                "issue_date": "2025-11-15"
            }
        },
        "multipage_structural_stability.pdf": {
            "category": "multi-page PDF",
            "document_type": "structural_stability_certificate",
            "expected_processing_status": "processed",
            "expected_fields": {
                "institution_name": "Synthetic ABC Institute of Technology",
                "document_number": "SSC-2026-905",
                "engineer_license_number": "SE-LIC-4421",
                "issue_date": "2026-03-01",
                "expiry_date": "2029-02-28"
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
            "document_type": "structural_stability_certificate",
            "expected_processing_status": "processing_failed",
            "expected_fields": {}
        }
    }

    gt_path = os.path.join(BASE_DIR, "ground_truth.json")
    with open(gt_path, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2)

    print(f"Generated 8 synthetic documents in: {SAMPLES_DIR}")
    print(f"Generated ground truth file in: {gt_path}")


if __name__ == "__main__":
    generate_all()
