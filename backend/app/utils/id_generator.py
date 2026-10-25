import uuid


def generate_id(prefix: str) -> str:
    """Generate a clean unique identifier with a given prefix, e.g. 'app_a1b2c3d4'."""
    random_part = uuid.uuid4().hex[:8]
    return f"{prefix}_{random_part}"
