REVIEW_REQUIRED_STATUSES = frozenset({"flagged", "missing", "unresolved"})
VALID_REVIEW_DECISIONS = frozenset(
    {"verified", "confirmed_discrepancy", "requested_resubmission", "escalated"}
)


def finding_requires_reviewer_decision(finding) -> bool:
    """Only findings that are open or adverse require an explicit reviewer action."""
    return finding.status in REVIEW_REQUIRED_STATUSES


def finding_has_recorded_decision(finding) -> bool:
    return (
        finding.reviewer_decision in VALID_REVIEW_DECISIONS
        and finding.reviewed_at is not None
    )
