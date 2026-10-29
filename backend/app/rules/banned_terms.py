"""
Canonical Banned-Terms Registry and Enforcement for Pramaan Rule Definitions.
Enforces honest language boundaries across all finding titles, reasons, and next-action text.
"""

from typing import Optional

BANNED_FINDING_TERMS = [
    "fraud",
    "genuine",
    "verified issuer",
    "valid signature",
    "contravention",
    "violation",
    "non-compliant",
    "tampered",
    "forged",
    "authentic",
    "complies",
    "complying",
]


def validate_rule_text_claims(text: Optional[str], context_label: str = "") -> None:
    """
    Validates text against the canonical banned-terms list.
    Raises ValueError immediately if an overreaching or legally speculative claim term is present.
    """
    if not text:
        return

    lower_text = text.lower()

    # 1. Check core forbidden terms
    for term in BANNED_FINDING_TERMS:
        if term in lower_text:
            raise ValueError(
                f"{context_label} contains forbidden claim term '{term}': {text}"
            )

    # 2. Check unqualified 'verified' (must be qualified as 'unverified', 'not verified', or 'cannot be verified')
    t_clean = (
        lower_text.replace("cannot be verified", "")
        .replace("not verified", "")
        .replace("unverified", "")
    )
    if "verified" in t_clean:
        raise ValueError(
            f"{context_label} contains unqualified claim 'verified': {text}"
        )
