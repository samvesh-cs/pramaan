import logging
import sys
from datetime import datetime, timezone

audit_logger = logging.getLogger("pramaan.audit")
if not audit_logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[AUDIT] %(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    audit_logger.addHandler(handler)
    audit_logger.setLevel(logging.INFO)


def log_auth_event(
    event_type: str,
    user_id: str | None = None,
    email: str | None = None,
    role: str | None = None,
    ip_address: str | None = None,
    status: str = "success",
    details: str | None = None,
) -> None:
    """Log security-relevant audit event in structured form."""
    timestamp = datetime.now(timezone.utc).isoformat()
    msg = (
        f"event={event_type} status={status} user_id={user_id or 'anonymous'} "
        f"email={email or 'unknown'} role={role or 'none'} ip={ip_address or 'unknown'} "
        f"time={timestamp}"
    )
    if details:
        msg += f" details={details}"
    audit_logger.info(msg)
