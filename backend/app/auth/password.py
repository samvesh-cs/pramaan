import bcrypt

# Pre-computed dummy hash to mitigate user enumeration timing attacks
_DUMMY_SALT = bcrypt.gensalt(rounds=12)
_DUMMY_HASH = bcrypt.hashpw(b"timedummyunlikelypassword123!", _DUMMY_SALT)


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt (rounds=12, UTF-8 truncated to 72 bytes)."""
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False


def verify_dummy_password(plain_password: str) -> None:
    """Run password verification against dummy hash to prevent timing attacks."""
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        bcrypt.checkpw(pwd_bytes, _DUMMY_HASH)
    except Exception:
        pass
