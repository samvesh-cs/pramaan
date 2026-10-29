import pytest
from PIL import Image, ImageDraw
from app.ocr.perceptual_hash import (
    compute_dhash_from_image,
    hamming_distance,
    visual_similarity,
)
from app.rules.duplicate_check import DuplicateDocumentRule
from app.models.application import Application
from app.models.document import Document
from app.schemas.extraction import ExtractionResponse


def test_dhash_identical_images():
    img1 = Image.new("RGB", (200, 200), color="white")
    draw1 = ImageDraw.Draw(img1)
    draw1.rectangle([20, 20, 100, 100], fill="black")

    img2 = Image.new("RGB", (200, 200), color="white")
    draw2 = ImageDraw.Draw(img2)
    draw2.rectangle([20, 20, 100, 100], fill="black")

    hash1 = compute_dhash_from_image(img1)
    hash2 = compute_dhash_from_image(img2)

    assert hash1 == hash2
    assert hamming_distance(hash1, hash2) == 0
    assert visual_similarity(hash1, hash2) == 1.0


def test_dhash_rescaled_noisy_image_near_zero_hamming_distance():
    # Base certificate layout
    img1 = Image.new("RGB", (300, 400), color="white")
    draw1 = ImageDraw.Draw(img1)
    draw1.rectangle([30, 30, 270, 80], fill="black")  # header bar
    draw1.rectangle([50, 120, 250, 160], fill="gray")  # body
    draw1.rectangle([50, 250, 150, 270], fill="black")  # signature

    # Re-scanned slightly resized & noisy version (different byte content, identical layout)
    img2 = img1.resize((350, 460), Image.Resampling.BILINEAR)

    hash1 = compute_dhash_from_image(img1)
    hash2 = compute_dhash_from_image(img2)

    dist = hamming_distance(hash1, hash2)
    similarity = visual_similarity(hash1, hash2)

    # Invariant to resolution changes: Hamming distance should be <= 2
    assert dist <= 4
    assert similarity >= 0.90


def test_dhash_different_documents():
    img1 = Image.new("RGB", (200, 200), color="white")
    draw1 = ImageDraw.Draw(img1)
    draw1.rectangle([10, 10, 90, 90], fill="black")

    img2 = Image.new("RGB", (200, 200), color="white")
    draw2 = ImageDraw.Draw(img2)
    # Completely different layout on bottom right
    draw2.rectangle([110, 110, 190, 190], fill="black")

    hash1 = compute_dhash_from_image(img1)
    hash2 = compute_dhash_from_image(img2)

    dist = hamming_distance(hash1, hash2)
    assert dist > 8


def test_duplicate_document_rule_flags_perceptual_duplicate():
    rule = DuplicateDocumentRule()

    app_current = Application(
        id="app_curr_001",
        institution_name="Delhi Institute of Technology",
    )
    doc_current = Document(
        id="doc_curr_1",
        application_id="app_curr_001",
        document_type="fire_safety_certificate",
        original_filename="fire_scan_new.pdf",
        stored_filename="stored_new.pdf",
        mime_type="application/pdf",
        file_size_bytes=15000,
        file_hash="hash_alpha_111",  # Different byte hash!
        perceptual_hash="132f6c0600000019",
        processing_status="processed",
    )

    app_other = Application(
        id="app_other_999",
        institution_name="Mumbai Engineering Institute",  # Different college!
    )
    doc_other = Document(
        id="doc_other_1",
        application_id="app_other_999",
        document_type="fire_safety_certificate",
        original_filename="mumbai_fire_scan.pdf",
        stored_filename="stored_mumbai.pdf",
        mime_type="application/pdf",
        file_size_bytes=16200,
        file_hash="hash_beta_222",  # Different byte hash!
        perceptual_hash="132f6c0600000019",  # Visually identical dHash!
        processing_status="processed",
    )
    doc_other.application = app_other

    context = {
        "application": app_current,
        "documents": [doc_current],
        "all_system_documents": [doc_other],
        "extractions": {
            doc_current.id: ExtractionResponse(
                document_id=doc_current.id,
                document_type="fire_safety_certificate",
                processing_status="processed",
                fields={},
            )
        },
    }

    findings = rule.evaluate(context)
    # Should flag a visual perceptual duplicate
    flagged = [f for f in findings if f.evidence.get("type") == "visual_duplicate_cross_institution"]
    assert len(flagged) == 1
    assert flagged[0].status == "flagged"
    assert "visual duplicate" in flagged[0].title.lower()
    assert flagged[0].evidence["matched_application_id"] == "app_other_999"
    assert flagged[0].evidence["visual_similarity"] == 1.0

