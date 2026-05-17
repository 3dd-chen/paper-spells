"""
Lightweight HS256 JWT implementation using Python stdlib only.
No external dependencies required.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import time
from fastapi import HTTPException


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    # Add padding back
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def create_token(admin_id: str, secret: str, expires_in: int = 86400) -> str:
    """Create a HS256 JWT token."""
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url_encode(json.dumps({
        "sub": admin_id,
        "exp": int(time.time()) + expires_in,
        "iat": int(time.time()),
    }).encode())

    signing_input = f"{header}.{payload}"
    signature = _b64url_encode(
        hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    )
    return f"{signing_input}.{signature}"


def verify_token(token: str, secret: str) -> dict:
    """Verify a HS256 JWT token. Raises HTTPException 401 if invalid."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid token format")

        header_b64, payload_b64, signature_b64 = parts

        # Verify signature
        signing_input = f"{header_b64}.{payload_b64}"
        expected_sig = _b64url_encode(
            hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(expected_sig, signature_b64):
            raise ValueError("Invalid signature")

        # Decode payload
        payload = json.loads(_b64url_decode(payload_b64))

        # Verify expiry
        if payload.get("exp", 0) < int(time.time()):
            raise ValueError("Token expired")

        return payload

    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Unauthorized: {e}")
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
