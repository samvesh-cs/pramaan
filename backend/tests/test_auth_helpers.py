from datetime import timedelta
import pytest
from jose import jwt

from app.auth.audit import log_auth_event
from app.auth.jwt import create_access_token, decode_access_token
from app.auth.password import hash_password, verify_dummy_password, verify_password
from app.config import settings


def test_password_hash_and_verify():
    plain = "SecureP@ssw0rd2026!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert verify_password(plain, hashed) is True


def test_password_wrong_fails():
    plain = "MySecret123"
    hashed = hash_password(plain)
    assert verify_password("WrongSecret", hashed) is False


def test_verify_dummy_password():
    # Should not raise exception
    verify_dummy_password("random_attempt")


def test_create_and_decode_valid_token():
    payload = {"sub": "user-123", "email": "test@college.edu", "role": "INSTITUTION"}
    token = create_access_token(payload)
    assert isinstance(token, str)

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "user-123"
    assert decoded["email"] == "test@college.edu"
    assert decoded["role"] == "INSTITUTION"
    assert decoded["token_type"] == "access"
    assert "exp" in decoded
    assert "iat" in decoded


def test_expired_token_returns_none():
    payload = {"sub": "user-expired", "role": "INSTITUTION"}
    # Token expired 1 minute ago (outside 10s leeway)
    token = create_access_token(payload, expires_delta=timedelta(minutes=-2))
    assert decode_access_token(token) is None


def test_tampered_token_returns_none():
    payload = {"sub": "user-legit", "role": "INSTITUTION"}
    token = create_access_token(payload)
    tampered = token[:-5] + "aaaaa"
    assert decode_access_token(tampered) is None


def test_wrong_secret_token_returns_none():
    to_encode = {"sub": "user-spoofed", "token_type": "access"}
    fake_token = jwt.encode(to_encode, "different-secret-key-12345", algorithm=settings.JWT_ALGORITHM)
    assert decode_access_token(fake_token) is None


def test_token_type_mismatch_returns_none():
    to_encode = {"sub": "user-123", "token_type": "refresh"}
    fake_token = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    assert decode_access_token(fake_token) is None


def test_audit_event_logging():
    # Calling log_auth_event should succeed cleanly
    log_auth_event(
        event_type="test_event",
        user_id="u-1",
        email="test@inst.edu",
        role="INSTITUTION",
        status="success",
        details="Unit test audit log",
    )
