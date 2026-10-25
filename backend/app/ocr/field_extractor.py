"""Field extraction engine for supported institutional document types.

Follows docs/API_CONTRACT.md section 5 and AICTE_RULEBOOK_REFERENCE - Copy.md (Section 3).
Targets:
  1. fire_safety_certificate:
       institution_name, document_number, issue_date, expiry_date, issuing_authority
  2. building_completion_certificate:
       institution_name, document_number, issue_date, issuing_authority
  3. affidavit_2:
       institution_name, notary_date, signatory_name
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from .models import ExtractedField, PageResult, Region

logger = logging.getLogger(__name__)

UNCERTAIN_CONFIDENCE_THRESHOLD = 0.70

MONTH_NAME_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12
}


def normalize_date(date_str: str) -> Optional[str]:
    """Parse various date formats and return standard ISO YYYY-MM-DD string.

    Supports:
      - 15/01/2026, 15-01-2026, 15.01.2026 (DD/MM/YYYY)
      - 2026-01-15, 2026/01/15, 2026.01.15 (YYYY-MM-DD)
      - 15 Jan 2026, 15 January 2026, 15th Jan 2026, 15th January 2026
      - 15-Jan-2026, 15-January-2026
      - January 15, 2026, Jan 15, 2026
      - "15th day of January, 2026" / "this 15th day of January, 2026"
    Returns None if date cannot be parsed reliably.
    """
    if not date_str:
        return None

    clean = date_str.strip()
    # Remove leading phrases like 'this', 'on', 'dated', etc.
    clean = re.sub(r"^(?:this\s+|on\s+|dated\s+|date\s*:\s*)", "", clean, flags=re.IGNORECASE).strip()

    # Pattern A: "15th day of January, 2026" or "15th day of Jan 2026"
    match_legal = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+day\s+of\s+([A-Za-z]+)[,\s]+(\d{4})", clean, re.IGNORECASE)
    if match_legal:
        d_str, m_str, y_str = match_legal.groups()
        m_num = MONTH_NAME_MAP.get(m_str.lower()[:3])
        if m_num:
            try:
                dt = datetime(int(y_str), m_num, int(d_str))
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

    # Pattern B: "15 Jan 2026" / "15 January 2026" / "15th Jan 2026" / "15-Jan-2026"
    match_dmy_words = re.search(r"(\d{1,2})(?:st|nd|rd|th)?[\s\-\/\.]+([A-Za-z]+)[\s\-\/\.,]+(\d{4})", clean, re.IGNORECASE)
    if match_dmy_words:
        d_str, m_str, y_str = match_dmy_words.groups()
        m_num = MONTH_NAME_MAP.get(m_str.lower()[:3])
        if m_num:
            try:
                dt = datetime(int(y_str), m_num, int(d_str))
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

    # Pattern C: "January 15, 2026" / "Jan 15 2026" / "Jan. 15, 2026"
    match_mdy_words = re.search(r"([A-Za-z]+)[\s\.\-]+(\d{1,2})(?:st|nd|rd|th)?[,\s]+(\d{4})", clean, re.IGNORECASE)
    if match_mdy_words:
        m_str, d_str, y_str = match_mdy_words.groups()
        m_num = MONTH_NAME_MAP.get(m_str.lower()[:3])
        if m_num:
            try:
                dt = datetime(int(y_str), m_num, int(d_str))
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

    # Pattern D: ISO YYYY-MM-DD / YYYY/MM/DD / YYYY.MM.DD
    match_iso = re.search(r"(\d{4})[\/\-\.](\d{1,2})[\/\-\.](\d{1,2})", clean)
    if match_iso:
        y_str, m_str, d_str = match_iso.groups()
        try:
            dt = datetime(int(y_str), int(m_str), int(d_str))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Pattern E: Indian / UK DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
    match_dmy = re.search(r"(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})", clean)
    if match_dmy:
        d_str, m_str, y_str = match_dmy.groups()
        try:
            dt = datetime(int(y_str), int(m_str), int(d_str))
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


def clean_institution_name(name_raw: str) -> str:
    """Clean institution name by removing trailing punctuation, location suffixes, or noisy tokens."""
    name = re.sub(r"[\r\n]+", " ", name_raw).strip()
    # Strip any leading field labels that might have been matched
    name = re.sub(
        r"^(?:Name\s*of\s*(?:the\s*)?(?:Institution|College|Institute|Trust|Society)|Institution\s*Name|College\s*Name|Institute\s*Name)[:\s]*",
        "",
        name,
        flags=re.IGNORECASE
    )
    # Strip leading/trailing quotation marks, dashes, colons
    name = re.sub(r"^['\"\-\s:]+|['\"\-\s:]+$", "", name)
    # Strip trailing legal affirmations or location clauses
    name = re.split(
        r"(?:,\s*(?:situated|located|having|campus|village|district|at|near|post|taluk)\b|\s+do\s+hereby\b|\s+solemnly\b|\s+having\s+complied\b)",
        name,
        flags=re.IGNORECASE
    )[0]
    return name.strip()


def clean_signatory_name(name_raw: str) -> str:
    """Clean person signatory name by stripping titles and parentage clauses."""
    name = re.sub(r"[\r\n]+", " ", name_raw).strip()
    name = re.sub(r"^['\"\-\s:]+|['\"\-\s:]+$", "", name)
    # Strip trailing parentage or designation clauses
    name = re.split(r"(?:,\s*(?:son|daughter|wife|s\/o|d\/o|w\/o|aged|years|Chairman|Secretary|Trustee|President|deponent)\b)", name, flags=re.IGNORECASE)[0]
    # Remove leading honorifics if desired, or keep as recognized
    name = re.sub(r"^(?:Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.|Shri|Smt\.)\s*", "", name, flags=re.IGNORECASE)
    return name.strip()


def build_field(
    value: Optional[Any],
    normalized_value: Optional[Any],
    raw_text: Optional[str],
    confidence: Optional[float],
    page_number: Optional[int],
    bbox: Optional[List[float]],
) -> ExtractedField:
    """Construct ExtractedField with explicit status: extracted, missing, or uncertain."""
    if value is None:
        status = "missing"
    elif confidence is not None and confidence < UNCERTAIN_CONFIDENCE_THRESHOLD:
        status = "uncertain"
    else:
        status = "extracted"

    return ExtractedField(
        value=value,
        normalized_value=normalized_value,
        raw_text=raw_text,
        confidence=confidence,
        page_number=page_number,
        bbox=bbox,
        status=status,
    )


def build_missing_field() -> ExtractedField:
    """Construct an explicitly missing ExtractedField."""
    return ExtractedField(
        value=None,
        normalized_value=None,
        raw_text=None,
        confidence=None,
        page_number=None,
        bbox=None,
        status="missing",
    )


def extract_regex_field(
    pages: List[PageResult],
    full_text: str,
    patterns: List[str],
    is_date: bool = False,
    is_institution: bool = False,
    is_signatory: bool = False,
) -> ExtractedField:
    """Helper to extract a field using regex patterns against document text."""
    for pattern in patterns:
        match = re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE)
        if match:
            raw_val = match.group(1).strip()
            raw_snippet = match.group(0).strip()

            if is_institution:
                raw_val = clean_institution_name(raw_val)
            elif is_signatory:
                raw_val = clean_signatory_name(raw_val)

            page_num, conf, bbox = find_region_for_text(pages, raw_val)

            if is_date:
                norm_val = normalize_date(raw_val)
                val = norm_val  # API contract rule: dates represented as ISO YYYY-MM-DD
                if not norm_val:
                    # Could not parse date format reliably
                    return build_missing_field()
            else:
                val = raw_val
                norm_val = raw_val.lower().strip()

            return build_field(
                value=val,
                normalized_value=norm_val,
                raw_text=raw_snippet,
                confidence=conf,
                page_number=page_num,
                bbox=bbox,
            )

    return build_missing_field()


# ==============================================================================
# Document Type Extractors
# ==============================================================================

def extract_fire_safety_fields(pages: List[PageResult], full_text: str) -> Dict[str, ExtractedField]:
    """Extractor for fire_safety_certificate.

    Exact field matrix:
      - institution_name
      - document_number
      - issue_date
      - expiry_date
      - issuing_authority
    """
    fields: Dict[str, ExtractedField] = {}

    # 1. institution_name
    inst_patterns = [
        r"(?:Name\s*of\s*(?:the\s*)?(?:Institution|College|Institute|Establishment)|Institution\s*Name|College\s*Name|Institute\s*Name)[:\s]+([^\n\r]+)",
        r"(?:Premises\s*of(?:\s*M\/s)?|Issued\s+to|In\s+respect\s+of|Certified\s+that)[:\s]+([^\n\r]+)",
        r"(?:^|\n)\s*(?:Institution|Institute|College)[:\s]+([^\n\r]+)",
    ]
    fields["institution_name"] = extract_regex_field(pages, full_text, inst_patterns, is_institution=True)

    # 2. document_number
    doc_num_patterns = [
        r"(?:Certificate\s*(?:No|Number|\#)|Cert\.?\s*No\.?|NOC\s*(?:No|Number|\#)|Fire\s*NOC\s*(?:No|Number|\#)|Ref\.?\s*(?:No|Number|\#)|Reference\s*(?:No|Number|\#)|Registration\s*(?:No|Number|\#)|Reg\.?\s*No\.?|Order\s*(?:No|Number|\#)|File\s*No\.?)[:\s]+([A-Za-z0-9\-\/\.\_]+)",
        r"(?:NOC|Certificate|Ref)[:\s]+([A-Za-z0-9\-\/\.\_]+)",
    ]
    fields["document_number"] = extract_regex_field(pages, full_text, doc_num_patterns)

    # 3. issue_date
    issue_date_patterns = [
        r"(?:Date\s*of\s*Issue|Issue\s*Date|Issued\s*(?:on|Date)|Date\s*of\s*Inspection|Inspection\s*Date|Dated)[:\s]+([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}|[0-9]{4}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{1,2}|[0-9]{1,2}(?:st|nd|rd|th)?[\s\-\/\.]+[A-Za-z]+[\s\-\/\.,]+[0-9]{4}|[A-Za-z]+[\s\.\-]+[0-9]{1,2}(?:st|nd|rd|th)?[,\s]+[0-9]{4})",
    ]
    fields["issue_date"] = extract_regex_field(pages, full_text, issue_date_patterns, is_date=True)

    # 4. expiry_date
    expiry_date_patterns = [
        r"(?:Valid\s*(?:Until|Upto|Up\s*To|Till|Through)|Expiry\s*Date|Date\s*of\s*Expiry|Expires\s*(?:on)?|Validity(?:\s*period)?(?:\s*upto)?|Valid\s*for\s*period\s*up\s*to)[:\s]+([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}|[0-9]{4}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{1,2}|[0-9]{1,2}(?:st|nd|rd|th)?[\s\-\/\.]+[A-Za-z]+[\s\-\/\.,]+[0-9]{4}|[A-Za-z]+[\s\.\-]+[0-9]{1,2}(?:st|nd|rd|th)?[,\s]+[0-9]{4})",
    ]
    fields["expiry_date"] = extract_regex_field(pages, full_text, expiry_date_patterns, is_date=True)

    # 5. issuing_authority
    authority_patterns = [
        r"(?:Issuing\s*Authority|Name\s*of\s*(?:the\s*)?Authority|Competent\s*Authority|Issued\s*by|Office\s*of\s*(?:the)?|Directorate\s*of)[:\s]+([^\n\r]+)",
        r"(?:^|\n)\s*(Government\s*of\s*[^\n\r]+Fire\s*(?:Service|Services|Department|Emergency)[^\n\r]*)",
        r"(?:^|\n)\s*(Directorate\s*of\s*Fire\s*(?:and\s*Rescue\s*)?Services[^\n\r]*)",
        r"(?:^|\n)\s*(Fire\s*&\s*Rescue\s*Services(?:\s*Department)?)[^\n\r]*",
        r"(?:^|\n)\s*(Chief\s*Fire\s*Officer[^\n\r]*)",
        r"(?:^|\n)\s*([A-Za-z\s]+Municipal\s*Corporation\s*(?:Fire\s*Department|Fire\s*Services)?)",
    ]
    fields["issuing_authority"] = extract_regex_field(pages, full_text, authority_patterns)

    return fields


def extract_building_completion_fields(pages: List[PageResult], full_text: str) -> Dict[str, ExtractedField]:
    """Extractor for building_completion_certificate.

    Exact field matrix:
      - institution_name
      - document_number
      - issue_date
      - issuing_authority
    """
    fields: Dict[str, ExtractedField] = {}

    # 1. institution_name
    inst_patterns = [
        r"(?:Name\s*of\s*(?:the\s*)?(?:Institution|College|Institute|Building|Premises)|Institution\s*Name|College\s*Name|Institute\s*Name)[:\s]+([^\n\r]+)",
        r"(?:Issued\s+to|In\s+respect\s+of|Certified\s+that\s+the\s+building\s+of)[:\s]+([^\n\r]+)",
        r"(?:^|\n)\s*(?:Institution|Institute|College)[:\s]+([^\n\r]+)",
    ]
    fields["institution_name"] = extract_regex_field(pages, full_text, inst_patterns, is_institution=True)

    # 2. document_number
    doc_num_patterns = [
        r"(?:Certificate\s*(?:No|Number|\#)|Cert\.?\s*No\.?|Building\s*(?:Completion|Permit|License)\s*(?:No|Number|\#)|Occupancy\s*(?:Certificate\s*)?(?:No|Number|\#)|Form\s*D\s*(?:No|Number|\#)|Reg\.?\s*No\.?|Ref\.?\s*(?:No|Number|\#)|Order\s*(?:No|Number|\#)|File\s*No\.?)[:\s]+([A-Za-z0-9\-\/\.\_]+)",
        r"(?:Plan\s*Approval\s*(?:No|Number|\#)|License\s*(?:No|Number|\#))[:\s]+([A-Za-z0-9\-\/\.\_]+)",
    ]
    fields["document_number"] = extract_regex_field(pages, full_text, doc_num_patterns)

    # 3. issue_date
    issue_date_patterns = [
        r"(?:Date\s*of\s*(?:Issue|Completion|Inspection)|Issue\s*Date|Completion\s*Date|Date\s*of\s*Occupancy|Issued\s*(?:on)?|Dated)[:\s]+([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}|[0-9]{4}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{1,2}|[0-9]{1,2}(?:st|nd|rd|th)?[\s\-\/\.]+[A-Za-z]+[\s\-\/\.,]+[0-9]{4}|[A-Za-z]+[\s\.\-]+[0-9]{1,2}(?:st|nd|rd|th)?[,\s]+[0-9]{4})",
    ]
    fields["issue_date"] = extract_regex_field(pages, full_text, issue_date_patterns, is_date=True)

    # 4. issuing_authority
    authority_patterns = [
        r"(?:Issuing\s*Authority|Competent\s*Authority|Issued\s*by|Office\s*of\s*(?:the)?|Approved\s*by|Sanctioned\s*by)[:\s]+([^\n\r]+)",
        r"(?:^|\n)\s*([A-Za-z\s]+(?:Municipal\s*Corporation|Municipality|Town\s*(?:&|and)\s*Country\s*Planning|Urban\s*Development\s*Authority|Public\s*Works\s*Department|Gram\s*Panchayat|Development\s*Authority)[^\n\r]*)",
    ]
    fields["issuing_authority"] = extract_regex_field(pages, full_text, authority_patterns)

    return fields


def extract_affidavit_2_fields(pages: List[PageResult], full_text: str) -> Dict[str, ExtractedField]:
    """Extractor for affidavit_2.

    Exact field matrix:
      - institution_name
      - notary_date
      - signatory_name
    """
    fields: Dict[str, ExtractedField] = {}

    # 1. institution_name
    inst_patterns = [
        r"(?:Institution\s*Name|College\s*Name|Institute\s*Name|Name\s*of\s*(?:the\s*)?(?:Institution|College|Institute|Trust|Society))[:\s]+([^\n\r]+)",
        r"(?:on\s*behalf\s*of|in\s*respect\s*of|deponent\s*for)[:\s]+([^\n\r]+)",
        r"(?:^|\n)\s*I[,.]\s*[^,]+,\s*(?:Chairman|Secretary|President|Trustee|Deponent)[^,]*,\s*(?:of|for|on\s*behalf\s*of)\s*([^\n\r,\.]+)",
        r"(?:^|\n)\s*(?:Institution|Institute|College)[:\s]+([^\n\r]+)",
    ]
    fields["institution_name"] = extract_regex_field(pages, full_text, inst_patterns, is_institution=True)

    # 2. notary_date
    notary_date_patterns = [
        r"(?:Sworn\s*(?:and\s*subscribed\s*)?before\s*me\s*(?:on|this)?|Notarized\s*on|Date\s*of\s*Notarization|Notary\s*Date|Attested\s*on)[:\s]+([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}|[0-9]{4}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{1,2}|[0-9]{1,2}(?:st|nd|rd|th)?[\s\-\/\.]+[A-Za-z]+[\s\-\/\.,]+[0-9]{4}|[A-Za-z]+[\s\.\-]+[0-9]{1,2}(?:st|nd|rd|th)?[,\s]+[0-9]{4})",
        r"(?:this\s+)?(\d{1,2}(?:st|nd|rd|th)?\s+day\s+of\s+[A-Za-z]+,?\s+\d{4})",
        r"(?:Dated|Date)[:\s]+([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}|[0-9]{4}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{1,2}|[0-9]{1,2}(?:st|nd|rd|th)?[\s\-\/\.]+[A-Za-z]+[\s\-\/\.,]+[0-9]{4}|[A-Za-z]+[\s\.\-]+[0-9]{1,2}(?:st|nd|rd|th)?[,\s]+[0-9]{4})",
    ]
    fields["notary_date"] = extract_regex_field(pages, full_text, notary_date_patterns, is_date=True)

    # 3. signatory_name
    signatory_patterns = [
        r"(?:Deponent\s*Name|Name\s*of\s*(?:the\s*)?Deponent|Signatory\s*Name|Signatory|Chairman\s*\/\s*Secretary)[:\s]+([A-Za-z\.\s]+?)(?:\n|,|$)",
        r"(?:^|\n)\s*I[,.]\s*([A-Za-z\.\s]+?)(?:,\s*(?:son|daughter|wife|s\/o|d\/o|w\/o|aged|Chairman|Secretary|Trustee|President|deponent)|\s+son|\s+daughter|\s+aged|\s+do\s+hereby)",
        r"(?:Deponent)[:\s]*:[\s]+([A-Za-z\.\s]+?)(?:\n|,|$)",
        r"(?:Signature\s*of\s*(?:the\s*)?Deponent)[\s\n]+([A-Za-z\.\s]+)",
    ]
    fields["signatory_name"] = extract_regex_field(pages, full_text, signatory_patterns, is_signatory=True)

    return fields


def extract_fields(document_type: Optional[str], pages: List[PageResult]) -> Dict[str, ExtractedField]:
    """Extract required fields strictly based on document_type.

    Dispatches to the target extractor specified in AICTE_RULEBOOK_REFERENCE - Copy.md (Section 3).
    """
    full_text = "\n".join(p.text for p in pages)
    doc_type = (document_type or "").lower().strip()

    if doc_type == "fire_safety_certificate":
        return extract_fire_safety_fields(pages, full_text)
    elif doc_type == "building_completion_certificate":
        return extract_building_completion_fields(pages, full_text)
    elif doc_type == "affidavit_2":
        return extract_affidavit_2_fields(pages, full_text)
    else:
        # Fallback for generic or other document types
        logger.info("Extracting with generic fallback for document_type='%s'", doc_type)
        fields: Dict[str, ExtractedField] = {}
        inst_patterns = [
            r"(?:Name\s*of\s*(?:the\s*)?(?:Institution|College|Institute)|Institution\s*Name|College\s*Name)[:\s]+([^\n\r]+)",
            r"(?:Premises\s*of|Issued\s+to|In\s+respect\s+of)[:\s]+([^\n\r]+)",
        ]
        fields["institution_name"] = extract_regex_field(pages, full_text, inst_patterns, is_institution=True)
        fields["document_number"] = extract_regex_field(pages, full_text, [
            r"(?:Certificate|Registration|Ref|NOC)\s*(?:No|Number|\#)[:\s]+([A-Za-z0-9\-\/\.\_]+)"
        ])
        fields["issue_date"] = extract_regex_field(pages, full_text, [
            r"(?:Date\s*of\s*Issue|Issue\s*Date|Issued\s*on|Dated)[:\s]+([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}|[0-9]{4}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{1,2})"
        ], is_date=True)
        return fields
