"""PDF and Image processing service using PyMuPDF and PaddleOCR fallback."""

import logging
from pathlib import Path
from typing import List, Tuple
import pymupdf as fitz
from .models import PageResult, Region
from .ocr_service import run_ocr_on_image

logger = logging.getLogger(__name__)


def extract_selectable_text(page: fitz.Page) -> Tuple[str, List[Region]]:
    """Extract selectable text and line/word bounding boxes from a digital PDF page using PyMuPDF.

    Coordinates from PyMuPDF are in PDF points (72 DPI).
    Extracts block-level and line-level regions for pinpoint evidence highlighting.
    Confidence is set to None since PyMuPDF extracts exact digital text (not OCR).
    """
    blocks = page.get_text("blocks")
    lines: List[str] = []
    regions: List[Region] = []

    for block in blocks:
        # block tuple format: (x0, y0, x1, y1, text, block_no, block_type)
        # block_type 0 is text, 1 is image
        if len(block) >= 5 and block[6] == 0:
            text = block[4].strip()
            if text:
                lines.append(text)
                block_bbox = [round(block[0], 2), round(block[1], 2), round(block[2], 2), round(block[3], 2)]
                # Add block-level region
                regions.append(
                    Region(
                        text=text,
                        confidence=None,
                        bbox=block_bbox,
                    )
                )
                # Split multi-line blocks into lines for pinpoint line-level bounding box resolution
                block_lines = [l.strip() for l in text.splitlines() if l.strip()]
                if len(block_lines) > 1:
                    for bl in block_lines:
                        line_rects = page.search_for(bl)
                        if line_rects:
                            r = line_rects[0]
                            line_bbox = [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)]
                        else:
                            line_bbox = block_bbox
                        regions.append(
                            Region(
                                text=bl,
                                confidence=None,
                                bbox=line_bbox,
                            )
                        )

    full_text = "\n".join(lines)
    return full_text, regions


def render_page_to_pixmap(page: fitz.Page, dpi: int = 150) -> bytes:
    """Render a PDF page to PNG image bytes for OCR."""
    pix = page.get_pixmap(dpi=dpi)
    return pix.tobytes(output="png")


def process_pdf(file_path: Path) -> List[PageResult]:
    """Process a PDF file.

    For each page:
    1. Try extracting selectable text with PyMuPDF.
    2. If text is sparse (< 50 alphanumeric characters), treat as scanned and run PaddleOCR on rendered pixmap.
    """
    doc = fitz.open(file_path)
    pages: List[PageResult] = []

    for page_index in range(len(doc)):
        page_num = page_index + 1
        page = doc[page_index]
        
        # 1. Attempt digital extraction
        text, regions = extract_selectable_text(page)
        
        # Count alphanumeric characters to detect scanned page
        alnum_chars = sum(c.isalnum() for c in text)
        if alnum_chars < 50:
            logger.info("Page %d has sparse digital text (%d chars). Rendering page for OCR...", page_num, alnum_chars)
            try:
                img_bytes = render_page_to_pixmap(page, dpi=150)
                ocr_text, ocr_regions = run_ocr_on_image(img_bytes)
                if ocr_text:
                    text = ocr_text
                    regions = ocr_regions
            except Exception as e:
                logger.warning("OCR fallback on page %d encountered error: %s", page_num, e)

        pages.append(
            PageResult(
                page_number=page_num,
                text=text,
                regions=regions
            )
        )

    doc.close()
    return pages


def process_image_file(file_path: Path) -> List[PageResult]:
    """Process a single image file (JPG, PNG) using OCR."""
    text, regions = run_ocr_on_image(str(file_path))
    return [
        PageResult(
            page_number=1,
            text=text,
            regions=regions
        )
    ]
