"""
Synthetic Test Fixture Generator for Advanced Tamper, Authenticity & Verification Tests.
Generates deterministic test PDFs in tests/fixtures/advanced/ for:
1. unsigned_clean.pdf: Clean digital PDF with standard metadata and single %%EOF.
2. metadata_anomalous.pdf: PDF with Canva/Photoshop creator tag and ModDate older than CreationDate.
3. incremental_save_multiple_eof.pdf: PDF with multiple incremental revisions and multiple %%EOF records.
4. qr_bearing_valid_url.pdf: Certificate embedding valid QR with URL query parameters.
5. qr_bearing_valid_kv.pdf: Certificate embedding valid QR with KEY:VALUE pairs.
6. qr_bearing_valid_json.pdf: Certificate embedding valid QR with JSON payload.
7. qr_bearing_unparseable.pdf: Certificate embedding unstructured non-standard binary/text string.
8. digitally_signed_valid.pdf: PDF digitally signed with self-signed test X.509 cert.
9. tampered_after_signing.pdf: Signed PDF modified after the signature ByteRange.
"""

import io
import datetime
from pathlib import Path
import pymupdf as fitz
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False

try:
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import fields, signers
    PYHANKO_AVAILABLE = True
except ImportError:
    PYHANKO_AVAILABLE = False


ADVANCED_FIXTURES_DIR = Path(__file__).parent / "advanced"


def create_base_certificate_doc(
    cert_title: str = "FIRE SAFETY CERTIFICATE",
    cert_no: str = "FS-2026-100",
    institution_name: str = "Synthetic ABC Institute of Technology",
    issue_date: str = "2024-04-01",
    valid_until: str = "2029-03-31",
    issuing_authority: str = "Delhi Fire Service, Government of NCT of Delhi",
) -> fitz.Document:
    """Create a standard one-page certificate document using PyMuPDF."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4

    # Header / Border
    rect = fitz.Rect(30, 30, 565, 812)
    page.draw_rect(rect, color=(0.1, 0.2, 0.4), width=2)

    # Title
    page.insert_text(
        fitz.Point(60, 80),
        "GOVERNMENT OF NCT OF DELHI",
        fontsize=14,
        fontname="helv",
        color=(0.1, 0.1, 0.1),
    )
    page.insert_text(
        fitz.Point(60, 110),
        cert_title,
        fontsize=18,
        fontname="helv",
        color=(0.1, 0.2, 0.5),
    )
    page.insert_text(
        fitz.Point(60, 135),
        f"Issuing Authority: {issuing_authority}",
        fontsize=10,
        fontname="helv",
        color=(0.3, 0.3, 0.3),
    )

    # Body Content
    body_lines = [
        f"Certificate Number: {cert_no}",
        f"This is to certify that the premises of {institution_name}",
        "situated at Sector 12, Dwarka, New Delhi 110078, have been inspected by the",
        "officers of this department and complied with the statutory fire prevention",
        "and fire safety requirements in accordance with Rule 33 of Delhi Fire Service Rules.",
        "",
        f"Date of Issue: {issue_date}",
        f"Valid Up To: {valid_until}",
        "",
        "This certificate is issued under the authority of Chief Fire Officer.",
        "Authorized Signatory: Er. Rajesh Sharma, Divisional Officer",
    ]

    y = 180
    for line in body_lines:
        page.insert_text(
            fitz.Point(60, y),
            line,
            fontsize=11,
            fontname="helv",
            color=(0.0, 0.0, 0.0),
        )
        y += 24

    return doc


def generate_qr_image_bytes(payload: str) -> bytes:
    """Generate PNG bytes of a QR code containing the given payload."""
    if not QRCODE_AVAILABLE:
        # Fallback: create a 100x100 black dummy image
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100), False)
        pix.clear_with(0)
        return pix.tobytes("png")

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def embed_qr_in_doc(doc: fitz.Document, qr_bytes: bytes, rect: fitz.Rect = fitz.Rect(430, 650, 530, 750)):
    """Embeds given image bytes into the first page of doc."""
    page = doc[0]
    page.insert_image(rect, stream=qr_bytes)
    page.insert_text(fitz.Point(435, 765), "Scan to Verify", fontsize=8, fontname="helv", color=(0.4, 0.4, 0.4))


def generate_self_signed_cert_and_key():
    """Generates an in-memory RSA private key and self-signed X.509 certificate for testing."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Delhi"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AICTE Demonstration CA"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Pramaan Test Signing Officer"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    return cert, key


def sign_pdf_file(input_path: Path, output_path: Path):
    """Signs a PDF using PyHanko and a synthetic self-signed certificate."""
    if not PYHANKO_AVAILABLE:
        # Fallback if pyHanko not yet installed: write placeholder with digital signature annotation
        doc = fitz.open(input_path)
        page = doc[0]
        page.insert_text(fitz.Point(60, 750), "[Digitally Signed by Pramaan Test Signing Officer]", fontsize=10, color=(0, 0.5, 0))
        doc.save(output_path)
        doc.close()
        return

    cert, key = generate_self_signed_cert_and_key()
    signer = signers.SimpleSigner(
        signing_cert=cert,
        signing_key=key,
        cert_registry=None,
    )

    with open(input_path, "rb") as inf:
        w = IncrementalPdfFileWriter(inf)
        fields.append_signature_field(
            w,
            sig_field_spec=fields.SigFieldSpec(
                sig_field_name="Signature1",
                box=(60, 40, 260, 90),
            ),
        )
        out_buf = io.BytesIO()
        w.write(out_buf)
        out_buf.seek(0)

    signer_meta = signers.PdfSignatureMetadata(
        field_name="Signature1",
        reason="Verification of Approval Document",
        location="New Delhi",
    )
    pdf_signer = signers.PdfSigner(signer_meta, signer=signer)

    with open(output_path, "wb") as outf:
        pdf_signer.sign_pdf(IncrementalPdfFileWriter(out_buf), output=outf)


def generate_all_fixtures(output_dir: Path = ADVANCED_FIXTURES_DIR) -> dict[str, Path]:
    """Generate all 9 advanced deterministic test fixtures."""
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = {}

    # 1. unsigned_clean.pdf
    f1_path = output_dir / "unsigned_clean.pdf"
    doc1 = create_base_certificate_doc()
    doc1.set_metadata({
        "title": "Fire Safety Certificate",
        "author": "Delhi Fire Service",
        "creator": "Government Printing System",
        "producer": "PyMuPDF PDF Generator",
        "creationDate": "D:20240401100000Z",
        "modDate": "D:20240401100000Z",
    })
    doc1.save(f1_path, garbage=3, deflate=True)
    doc1.close()
    generated["unsigned_clean"] = f1_path

    # 2. metadata_anomalous.pdf (Canva creator, ModDate older than CreationDate)
    f2_path = output_dir / "metadata_anomalous.pdf"
    doc2 = create_base_certificate_doc()
    doc2.set_metadata({
        "title": "Fire Safety Certificate",
        "author": "Delhi Fire Service",
        "creator": "Canva Creative Suite 2024",
        "producer": "Adobe Photoshop CC 2024 (Windows)",
        "creationDate": "D:20240401100000Z",
        "modDate": "D:20230101100000Z",  # Anomaly: modDate earlier than creationDate
    })
    doc2.save(f2_path, garbage=3, deflate=True)
    doc2.close()
    generated["metadata_anomalous"] = f2_path

    # 3. incremental_save_multiple_eof.pdf (simulating multiple incremental saves / revisions)
    f3_path = output_dir / "incremental_save_multiple_eof.pdf"
    doc3 = create_base_certificate_doc()
    base_bytes = doc3.tobytes(garbage=3, deflate=True)
    doc3.close()

    # Append revision 1 and revision 2 incremental update blocks
    rev1 = (
        b"\n% Revision 1: Audit Note\n"
        b"10 0 obj\n<< /Type /Annot /Subtype /Text /Contents (Revision 1: Audit Note) >>\nendobj\n"
        b"xref\n0 1\n0000000000 65535 f \n"
        b"trailer\n<< /Size 11 >>\n"
        b"startxref\n100\n%%EOF\n"
    )
    rev2 = (
        b"\n% Revision 2: Clearance Stamp\n"
        b"11 0 obj\n<< /Type /Annot /Subtype /Text /Contents (Revision 2: Clearance Stamp) >>\nendobj\n"
        b"xref\n0 1\n0000000000 65535 f \n"
        b"trailer\n<< /Size 12 >>\n"
        b"startxref\n200\n%%EOF\n"
    )
    f3_path.write_bytes(base_bytes + rev1 + rev2)
    generated["incremental_save_multiple_eof"] = f3_path

    # 4. qr_bearing_valid_url.pdf
    f4_path = output_dir / "qr_bearing_valid_url.pdf"
    doc4 = create_base_certificate_doc()
    url_payload = "https://edistrict.delhi.gov.in/verify?cert_no=FS-2026-100&inst=Synthetic+ABC+Institute+of+Technology"
    embed_qr_in_doc(doc4, generate_qr_image_bytes(url_payload))
    doc4.save(f4_path, garbage=3, deflate=True)
    doc4.close()
    generated["qr_bearing_valid_url"] = f4_path

    # 5. qr_bearing_valid_kv.pdf
    f5_path = output_dir / "qr_bearing_valid_kv.pdf"
    doc5 = create_base_certificate_doc()
    kv_payload = "CERT_NO:FS-2026-100|DATE:2026-03-31|INST:Synthetic ABC Institute of Technology"
    embed_qr_in_doc(doc5, generate_qr_image_bytes(kv_payload))
    doc5.save(f5_path, garbage=3, deflate=True)
    doc5.close()
    generated["qr_bearing_valid_kv"] = f5_path

    # 6. qr_bearing_valid_json.pdf
    f6_path = output_dir / "qr_bearing_valid_json.pdf"
    doc6 = create_base_certificate_doc()
    json_payload = '{"cert_no": "FS-2026-100", "institution": "Synthetic ABC Institute of Technology", "valid_until": "2029-03-31"}'
    embed_qr_in_doc(doc6, generate_qr_image_bytes(json_payload))
    doc6.save(f6_path, garbage=3, deflate=True)
    doc6.close()
    generated["qr_bearing_valid_json"] = f6_path

    # 7. qr_bearing_unparseable.pdf
    f7_path = output_dir / "qr_bearing_unparseable.pdf"
    doc7 = create_base_certificate_doc()
    unparseable_payload = "@@@NON_STRUCTURED_DATA_2026_BINARY_STREAM_XYZ12345###"
    embed_qr_in_doc(doc7, generate_qr_image_bytes(unparseable_payload))
    doc7.save(f7_path, garbage=3, deflate=True)
    doc7.close()
    generated["qr_bearing_unparseable"] = f7_path

    # 8. digitally_signed_valid.pdf
    f8_path = output_dir / "digitally_signed_valid.pdf"
    sign_pdf_file(f1_path, f8_path)
    generated["digitally_signed_valid"] = f8_path

    # 9. tampered_after_signing.pdf (signed document with appended bytes corrupting byte-range integrity)
    f9_path = output_dir / "tampered_after_signing.pdf"
    with open(f8_path, "rb") as rf:
        signed_bytes = rf.read()
    # Tamper by appending an unauthorized revision block after the signed ByteRange
    tampered_bytes = signed_bytes + b"\n% TAMPER_BLOCK_APPENDED_AFTER_SIGNING\n1 0 obj\n<< /Tampered true >>\nendobj\n%%EOF\n"
    with open(f9_path, "wb") as wf:
        wf.write(tampered_bytes)
    generated["tampered_after_signing"] = f9_path

    return generated


if __name__ == "__main__":
    fixtures = generate_all_fixtures()
    print(f"Successfully generated {len(fixtures)} advanced fixtures in {ADVANCED_FIXTURES_DIR}:")
    for name, path in fixtures.items():
        print(f" - {name}: {path.name} ({path.stat().st_size} bytes)")
