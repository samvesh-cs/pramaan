"""Perceptual hashing module for detecting visually duplicate or re-scanned documents.

Uses 64-bit difference hashing (dHash) on rendered document page layouts.
Invariant to minor compression artifacts, resolution changes, and scanner noise.
"""

import io
import logging
from pathlib import Path
from typing import Optional, Union
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


def compute_dhash_from_image(image: Image.Image, hash_size: int = 8) -> str:
    """Compute 64-bit difference hash (dHash) from a PIL Image.
    
    1. Converts image to grayscale.
    2. Resizes to (hash_size + 1, hash_size) -> (9, 8) for 64-bit hash.
    3. Compares adjacent horizontal pixels to capture structural gradient.
    4. Returns 16-character hexadecimal string.
    """
    try:
        # Convert to grayscale and resize
        resized = image.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
        pixels = np.array(resized)
        
        # Compare adjacent columns
        diff = pixels[:, 1:] > pixels[:, :-1]
        
        # Pack boolean array into 64-bit integer
        decimal_val = 0
        for bit in diff.flatten():
            decimal_val = (decimal_val << 1) | int(bit)
            
        return f"{decimal_val:016x}"
    except Exception as e:
        logger.warning("Error computing dHash from image: %s", e)
        return ""


def compute_perceptual_hash(file_path: Union[str, Path]) -> Optional[str]:
    """Compute 64-bit perceptual hash (dHash) for a PDF or image file.
    
    For PDFs, renders the first page at 100 DPI.
    For images (PNG/JPG), loads and hashes the image.
    Returns 16-char hex string, or None if computation failed.
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return None

    ext = path.suffix.lower()

    try:
        if ext == ".pdf":
            import pymupdf as fitz
            doc = fitz.open(path)
            if len(doc) == 0:
                doc.close()
                return None
            first_page = doc[0]
            # Render at 100 DPI
            pix = first_page.get_pixmap(dpi=100)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            phash = compute_dhash_from_image(img)
            doc.close()
            return phash
        elif ext in {".png", ".jpg", ".jpeg"}:
            with Image.open(path) as img:
                return compute_dhash_from_image(img)
    except Exception as e:
        logger.warning("Could not compute perceptual hash for %s: %s", path.name, e)
        return None

    return None


def hamming_distance(hash1: Optional[str], hash2: Optional[str]) -> int:
    """Calculate the Hamming distance (number of differing bits) between two 64-bit hex hashes.
    
    Returns:
        int: Number of differing bits between 0 and 64 (0 = identical layout).
             Returns 999 if either hash is missing or invalid.
    """
    if not hash1 or not hash2 or len(hash1) != len(hash2):
        return 999
    try:
        val1 = int(hash1, 16)
        val2 = int(hash2, 16)
        return bin(val1 ^ val2).count("1")
    except ValueError:
        return 999


def visual_similarity(hash1: Optional[str], hash2: Optional[str]) -> float:
    """Calculate visual similarity ratio between 0.0 and 1.0.
    
    A distance of 0 -> 1.0 (100% identical layout).
    A distance of 6 -> ~0.906 (90.6% visual match).
    """
    dist = hamming_distance(hash1, hash2)
    if dist >= 64:
        return 0.0
    return max(0.0, 1.0 - (dist / 64.0))

