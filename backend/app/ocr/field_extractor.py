"""Field extraction engine for supported institutional document types.
Follows docs/API_CONTRACT.md section 5.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from .models import ExtractedField, PageResult, Region

logger = logging.getLogger(__name__)


def normalize_date(date_str: str) -> Optional[str]:
    """Parse various date formats and return standard ISO YYYY-MM-DD string.

    Returns None if date cannot be parsed reliably.
    """
    if not date_str:
        return None
    
    clean_date = re.sub(r"[,\.]", " ", date_str).strip()
    
    # Common formats: DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, DD Month YYYY
    date_formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d %m %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d %Y",
        "%b %d %Y",
        "%Y/%m/%d"
    ]
    
    for fmt in date_formats:
        try:
            dt = datetime.strptime(clean_date, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
            
    # Try regex fallback for DD/MM/YYYY or YYYY-MM-DD
    match_dmy = re.search(r"(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})", date_str)
    if match_dmy:
        d, m, y = match_dmy.groups()
        try:
            dt = datetime(int(y), int(m), int(d))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None


def find_region_for_text(pages: List[PageResult], target_snippet: str) -> Tuple[Optional[int], Optional[float], Optional[List[float]]]:
    """Find the best-matching region in pages for bounding box, confidence, and page number."""
    if not target_snippet:
        return None, None, None

    snippet_clean = target_snippet.lower().strip()

    for page in pages:
        for reg in page.regions:
            reg_clean = reg.text.lower().strip()
            if snippet_clean in reg_clean or reg_clean in snippet_clean:
                return page.page_number, reg.confidence, reg.bbox

    # Default fallback to page 1 if any region exists
    if pages and pages[0].regions:
        return pages[0].page_number, pages[0].regions[0].confidence, pages[0].regions[0].bbox

    return 1 if pages else None, None, None


def extract_regex_field(
    pages: List[PageResult],
    full_text: str,
    patterns: List[str],
    is_date: bool = False
) -> ExtractedField:
    """Helper to extract a field using regex patterns against document text."""
    for pattern in patterns:
        match = re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE)
        if match:
            raw_val = match.group(1).strip()
            raw_snippet = match.group(0).strip()
            page_num, conf, bbox = find_region_for_text(pages, raw_val)
            
            if is_date:
                norm_val = normalize_date(raw_val)
                val = norm_val
            else:
                val = raw_val
                norm_val = raw_val.lower().strip()

            return ExtractedField(
                value=val,
                normalized_value=norm_val,
                raw_text=raw_snippet,
                confidence=conf,
                page_number=page_num,
                bbox=bbox
            )

    return ExtractedField(
        value=None,
        normalized_value=None,
        raw_text=None,
        confidence=None,
        page_number=None,
        bbox=None
    )


def extract_fields(document_type: Optional[str], pages: List[PageResult]) -> Dict[str, ExtractedField]:
    """Extract required fields based on document type."""
    full_text = "\n".join(p.text for p in pages)
    fields: Dict[str, ExtractedField] = {}

    # Common field: institution_name
    inst_patterns = [
        r"(?:Name\s*of\s*(?:the\s*)?(?:Institution|College|Institute)|Institution\s*Name|College\s*Name)[:\s]+([^\n\r]+)",
        r"(?:This\s+is\s+to\s+certify\s+that(?:\s+Messrs)?|Issued\s+to|In\s+respect\s+of)[:\s]+([^\n\r]+)",
        r"(?:^|\n)\s*(?:Institution|Institute)[:\s]+([^\n\r]+)",
        r"(?:^|\n)\s*(?:College)[:\s]+([^\n\r]+)",
    ]
    fields["institution_name"] = extract_regex_field(pages, full_text, inst_patterns)

    # Document-specific fields
    doc_type = (document_type or "").lower().strip()

    if doc_type == "fire_safety_certificate":
        fields["document_number"] = extract_regex_field(pages, full_text, [
            r"(?:Certificate\s*(?:No|Number)|NOC\s*(?:No|Number)|Ref\s*(?:No|Number))[:\s]*([A-Za-z0-9\-\/]+)"
        ])
        fields["issue_date"] = extract_regex_field(pages, full_text, [
            r"(?:Date\s*of\s*Issue|Issued\s*(?:on|Date)|Date)[:\s]*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}|[0-9]{4}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{1,2}|[0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})"
        ], is_date=True)
        fields["expiry_date"] = extract_regex_field(pages, full_text, [
            r"(?:Valid\s*(?:Until|Up\s*To|Till)|Expiry\s*Date|Expires\s*on)[:\s]*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}|[0-9]{4}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{1,2}|[0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})"
        ], is_date=True)

    elif doc_type == "structural_stability_certificate":
        fields["document_number"] = extract_regex_field(pages, full_text, [
            r"(?:Certificate\s*(?:No|Number)|Inspection\s*(?:No|Number)|Ref\s*(?:No|Number))[:\s]*([A-Za-z0-9\-\/]+)"
        ])
        fields["engineer_license_number"] = extract_regex_field(pages, full_text, [
            r"(?:Engineer\s*(?:Reg|License|Registration)\s*(?:No|Number)|Structural\s*Engineer\s*Licence)[:\s]*([A-Za-z0-9\-\/]+)"
        ])
        fields["issue_date"] = extract_regex_field(pages, full_text, [
            r"(?:Date\s*of\s*Inspection|Inspection\s*Date|Issued\s*on|Date)[:\s]*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}|[0-9]{4}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{1,2})"
        ], is_date=True)
        fields["expiry_date"] = extract_regex_field(pages, full_text, [
            r"(?:Valid\s*(?:Until|Up\s*To|Till)|Expiry\s*Date|Valid\s*for\s*period\s*up\s*to)[:\s]*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}|[0-9]{4}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{1,2})"
        ], is_date=True)

    elif doc_type == "land_title_deed":
        fields["document_number"] = extract_regex_field(pages, full_text, [
            r"(?:Deed\s*(?:No|Number)|Registration\s*(?:No|Number)|Document\s*(?:No|Number)|Khasra\s*(?:No|Number))[:\s]*([A-Za-z0-9\-\/]+)"
        ])
        fields["land_area"] = extract_regex_field(pages, full_text, [
            r"(?:Total\s*Land\s*Area|Land\s*Area|Total\s*Area|Area)[:\s]*([0-9]+(?:\.[0-9]+)?\s*(?:Acres?|Hectares?|Sq\.?\s*Meters?|Square\s*Meters?))"
        ])
        fields["issue_date"] = extract_regex_field(pages, full_text, [
            r"(?:Date\s*of\s*Registration|Registered\s*on|Execution\s*Date|Date)[:\s]*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}|[0-9]{4}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{1,2})"
        ], is_date=True)

    else:
        # Generic fallback: document_number, issue_date, expiry_date
        fields["document_number"] = extract_regex_field(pages, full_text, [
            r"(?:Document|Certificate|Reg|Ref)\s*(?:No|Number)[:\s]*([A-Za-z0-9\-\/]+)"
        ])
        fields["issue_date"] = extract_regex_field(pages, full_text, [
            r"(?:Issue\s*Date|Issued\s*on|Date)[:\s]*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}|[0-9]{4}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{1,2})"
        ], is_date=True)
        fields["expiry_date"] = extract_regex_field(pages, full_text, [
            r"(?:Expiry\s*Date|Valid\s*(?:Until|Up\s*To|Till))[:\s]*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}|[0-9]{4}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{1,2})"
        ], is_date=True)

    return fields
