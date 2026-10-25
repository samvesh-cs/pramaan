"""PaddleOCR 3.x Service wrapper for image and scanned PDF OCR.

Tested against PaddleOCR 3.7.0 / PaddlePaddle 3.3.1 on Windows (CPU).

Key API changes from PaddleOCR 2.x:
  - Constructor: use_angle_cls / cls=True removed.
    Orientation is controlled by use_textline_orientation (bool).
    enable_mkldnn=False is required on Windows/CPU due to a PIR→oneDNN
    regression in PaddlePaddle 3.3.x (ConvertPirAttribute2RuntimeAttribute).
  - Inference: ocr() is deprecated. Use predict(), which is an iterator
    yielding OCRResult objects (dict-like, from paddlex).
  - OCRResult keys used here:
      rec_texts  : list[str]           – recognised text per line
      rec_scores : list[float]         – confidence per line (0.0–1.0)
      rec_polys  : list[ndarray(4,2)]  – 4-point polygon in pixel coords
"""

import logging
from typing import List, Tuple, Optional
from .models import Region

logger = logging.getLogger(__name__)

_paddle_ocr_instance = None


def get_ocr_engine():
    """Lazy-initialise the PaddleOCR 3.x engine (one instance per process)."""
    global _paddle_ocr_instance
    if _paddle_ocr_instance is None:
        try:
            from paddleocr import PaddleOCR
            logger.info("Initialising PaddleOCR 3.x engine...")
            _paddle_ocr_instance = PaddleOCR(
                lang="en",
                use_textline_orientation=False,      # replaces cls=True
                use_doc_orientation_classify=False,  # skip heavy doc-level rotation
                use_doc_unwarping=False,             # skip dewarping for prototype
                enable_mkldnn=False,                 # required: disables oneDNN to avoid
                                                     # PaddlePaddle 3.3.x Windows crash
            )
            logger.info("PaddleOCR engine ready.")
        except Exception as e:
            logger.error("Failed to initialise PaddleOCR: %s", e)
            raise
    return _paddle_ocr_instance


def poly_to_bbox(poly) -> List[float]:
    """Convert a (4, 2) polygon array [[x,y], ...] to [x1, y1, x2, y2].

    Takes the axis-aligned bounding box of the four corner points.
    """
    xs = [float(pt[0]) for pt in poly]
    ys = [float(pt[1]) for pt in poly]
    return [round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2)]


def run_ocr_on_image(image_input) -> Tuple[str, List[Region]]:
    """Run PaddleOCR on an image path (str) or raw PNG bytes.

    Returns:
        (full_page_text, list_of_Region)

    Output contract (unchanged from the old 2.x wrapper):
        Region.text        – recognised text for that line
        Region.confidence  – float 0.0-1.0 from OCR, or None if unavailable
        Region.bbox        – [x1, y1, x2, y2] in input-image pixel coordinates
    """
    ocr = get_ocr_engine()

    # PaddleOCR 3.x predict() only accepts str (filepath) or numpy.ndarray.
    # Convert raw bytes (e.g. from rendered PDF pixmap) to RGB numpy ndarray.
    if isinstance(image_input, (bytes, bytearray)):
        import io
        import numpy as np
        from PIL import Image
        img = Image.open(io.BytesIO(image_input)).convert("RGB")
        image_input = np.array(img)

    try:
        # predict() returns an iterator of OCRResult (dict-like) objects.
        # One result per input image.
        result_iter = ocr.predict(image_input)
        results = list(result_iter)
    except Exception as e:
        logger.error("PaddleOCR predict() failed: %s", e)
        raise RuntimeError(f"OCR execution failed: {e}")

    lines: List[str] = []
    regions: List[Region] = []

    if not results:
        return "", []

    # First (and only) OCRResult for a single image input
    ocr_result = results[0]

    rec_texts  = ocr_result.get("rec_texts",  []) or []
    rec_scores = ocr_result.get("rec_scores", []) or []
    rec_polys  = ocr_result.get("rec_polys",  []) or []

    for i, text in enumerate(rec_texts):
        text_val = text.strip() if text else ""
        if not text_val:
            continue

        conf_val = round(float(rec_scores[i]), 4) if i < len(rec_scores) else None
        bbox = poly_to_bbox(rec_polys[i]) if i < len(rec_polys) else None

        lines.append(text_val)
        regions.append(Region(text=text_val, confidence=conf_val, bbox=bbox))

    full_text = "\n".join(lines)
    return full_text, regions
