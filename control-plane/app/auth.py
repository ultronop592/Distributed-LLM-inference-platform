import hashlib
import hmac
import os
import secrets

from fastapi import Header

from . import db


class ApiError(Exception):
    def __init__(self, status_code, message, error_type):
        self.status_code = status_code
        self.message = message
        self.error_type = error_type


def generate_key():
    return "csk_" + secrets.token_urlsafe(32)


def hash_key(raw_key):
    return hashlib.sha256(raw_key.encode()).hexdigest()


def extract_bearer(authorization):
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization[7:].strip() or None


def require_api_key(authorization: str | None = Header(default=None)):
    token = extract_bearer(authorization)
    if token is None:
        raise ApiError(401, "Missing API key", "authentication_error")
    row = db.get_active_by_hash(hash_key(token))
    if row is None:
        raise ApiError(401, "Invalid or revoked API key", "authentication_error")
    return {"id": row["id"], "name": row["name"]}


async def require_admin(authorization: str | None = Header(default=None)):
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise ApiError(503, "Admin access is not configured", "service_unavailable")
    token = extract_bearer(authorization)
    if token is None or not hmac.compare_digest(token, admin_token):
        raise ApiError(401, "Invalid admin token", "authentication_error")