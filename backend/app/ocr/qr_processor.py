"""QR Code Detection and Payload Extraction Module (Pillar 3).

Detects, decodes, and parses digital QR codes from PDF pages and images using OpenCV.
Extracts encoded certificate metadata (certificate numbers, validity dates, issuing authority, URLs).
"""

import io
import json
import logging
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


def parse_qr_payload(raw_text: str) -> Dict[str, Any]:
    """Parse decoded QR string into structured certificate attributes.
    
    Supports:
    1. JSON payloads: {"cert_no": "...", "institution": "...", "expiry_date": "..."}
    2. Verification URLs: https://eservices.gov.in/verify?cert_no=FS-2024-9812&inst=Delhi+Tech
    3. Key-Value formatted text: Cert No: FS-2024-9812 \n Valid Till: 2026-03-31
    4. Plain reference numbers: DEL/FS/2024/0091
    """
    clean_text = raw_text.strip()
    parsed: Dict[str, Any] = {
        "raw_payload": clean_text,
        "format": "text",
        "certificate_number": None,
        "institution_name": None,
        "issue_date": None,
        "expiry_date": None,
        "issuing_authority": None,
        "verification_url": None,
    }

    if not clean_text:
        return parsed

    # 1. Try parsing JSON
    if (clean_text.startswith("{") and clean_text.endswith("}")) or (clean_text.startswith("[") and clean_text.endswith("]")):
        try:
            data = json.loads(clean_text)
            if isinstance(data, dict):
                parsed["format"] = "json"
                for k, v in data.items():
                    k_lower = k.lower().replace("-", "_").replace(" ", "_")
                    if any(t in k_lower for t in ["expiry", "valid_till", "valid_to", "upto"]):
                        parsed["expiry_date"] = str(v).strip()
                    elif any(t in k_lower for t in ["cert", "doc_no", "reg_no", "license", "order_no"]):
                        parsed["certificate_number"] = str(v).strip()
                    elif any(t in k_lower for t in ["institution", "college", "school", "org"]):
                        parsed["institution_name"] = str(v).strip()
                    elif any(t in k_lower for t in ["issue", "issued", "dated"]):
                        parsed["issue_date"] = str(v).strip()
                    elif any(t in k_lower for t in ["authority", "dept", "issuer"]):
                        parsed["issuing_authority"] = str(v).strip()
                return parsed
        except Exception:
            pass

    # 2. Try parsing URL
    if clean_text.startswith("http://") or clean_text.startswith("https://"):
        parsed["format"] = "url"
        parsed["verification_url"] = clean_text
        try:
            url_parts = urllib.parse.urlparse(clean_text)
            query_params = urllib.parse.parse_qs(url_parts.query)
            for k, val_list in query_params.items():
                if not val_list:
                    continue
                v = val_list[0].strip()
                k_lower = k.lower().replace("-", "_")
                # Prioritize expiry and validity keys first to prevent 'id' in 'valid' false matching
                if any(t in k_lower for t in ["exp", "valid", "upto"]):
                    parsed["expiry_date"] = v
                elif any(t in k_lower for t in ["cert", "certificate", "doc_no", "reg_no", "license_no"]):
                    parsed["certificate_number"] = v
                elif any(t in k_lower for t in ["inst", "college", "org"]):
                    parsed["institution_name"] = v
                elif any(t in k_lower for t in ["issue", "issued"]):
                    parsed["issue_date"] = v
                elif k_lower in ("id", "doc_id", "ref"):
                    parsed["certificate_number"] = v
            # Set issuing authority domain
            if url_parts.netloc:
                parsed["issuing_authority"] = url_parts.netloc
            return parsed
        except Exception:
            pass

    # 3. Try parsing Key-Value lines
    lines = clean_text.splitlines()
    for line in lines:
        if ":" in line:
            parts = line.split(":", 1)
            k_lower = parts[0].strip().lower()
            v = parts[1].strip()
            if any(t in k_lower for t in ["valid", "expiry", "upto"]):
                parsed["expiry_date"] = v
            elif any(t in k_lower for t in ["cert", "license", "noc", "reg", "number", "ref"]):
                parsed["certificate_number"] = v
            elif any(t in k_lower for t in ["institution", "college", "name"]):
                parsed["institution_name"] = v
            elif any(t in k_lower for t in ["issue", "dated"]):
                parsed["issue_date"] = v
            elif any(t in k_lower for t in ["authority", "dept", "office"]):
                parsed["issuing_authority"] = v

    # 4. Check if plain string is a certificate/reference code
    if not parsed["certificate_number"]:
        match = re.search(r"\b([A-Z0-9]{2,8}[/-][A-Z0-9/-]{3,30})\b", clean_text)
        if match:
            parsed["certificate_number"] = match.group(1).strip()

    return parsed


def scan_image_for_qr(cv_image: np.ndarray) -> Optional[Dict[str, Any]]:
    """Scan a single OpenCV image (numpy array) for QR code using cv2.QRCodeDetector."""
    try:
        detector = cv2.QRCodeDetector()
        decoded_info, points, _ = detector.detectAndDecode(cv_image)
        if decoded_info and decoded_info.strip():
            bbox = None
            if points is not None and len(points) > 0:
                pts = points[0]
                min_x = float(np.min(pts[:, 0]))
                min_y = float(np.min(pts[:, 1]))
                max_x = float(np.max(pts[:, 0]))
                max_y = float(np.max(pts[:, 1]))
                bbox = [round(min_x, 2), round(min_y, 2), round(max_x, 2), round(max_y, 2)]

            parsed = parse_qr_payload(decoded_info)
            return {
                "detected": True,
                "raw_text": decoded_info,
                "parsed": parsed,
                "bbox": bbox,
            }
    except Exception as e:
        logger.debug("QR detection attempt failed: %s", e)
    return None


def extract_qr_from_document(file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
    """Inspect a document (PDF, PNG, JPG) and extract any embedded QR code.
    
    Returns structured dictionary with parsed fields, page number, and bounding box.
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return None

    ext = path.suffix.lower()

    try:
        if ext == ".pdf":
            import pymupdf as fitz
            doc = fitz.open(path)
            # Scan all pages (up to first 5)
            for page_idx in range(min(5, len(doc))):
                page = doc[page_idx]
                # Render at 150 DPI for crisp QR detection
                pix = page.get_pixmap(dpi=150)
                img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                cv_img = np.array(img)
                # Convert RGB to BGR for OpenCV
                cv_bgr = cv2.cvtColor(cv_img, cv2.COLOR_RGB2BGR)

                res = scan_image_for_qr(cv_bgr)
                if res:
                    doc.close()
                    res["page_number"] = page_idx + 1
                    if res.get("bbox"):
                        scale = 72.0 / 150.0
                        res["bbox"] = [
                            round(res["bbox"][0] * scale, 2),
                            round(res["bbox"][1] * scale, 2),
                            round(res["bbox"][2] * scale, 2),
                            round(res["bbox"][3] * scale, 2),
                        ]
                    return res

            doc.close()
            return None
        elif ext in {".png", ".jpg", ".jpeg"}:
            img = cv2.imread(str(path))
            if img is not None:
                res = scan_image_for_qr(img)
                if res:
                    res["page_number"] = 1
                    return res
    except Exception as e:
        logger.warning("QR extraction failed on %s: %s", path.name, e)

    return None
