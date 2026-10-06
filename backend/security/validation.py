"""
Server-side input validation.

The Angular forms validate too, but anyone can call the API directly (curl, Postman),
so every value is checked again here before it reaches the database. Limits match the
column sizes in database/schema.sql.
"""

import re
from typing import Optional
from fastapi import HTTPException, UploadFile

EMAIL_PATTERN = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}")
# Control characters (except tab/newline in long text) are never valid form input
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
CONTROL_CHARS_SINGLE_LINE = re.compile(r"[\x00-\x1f\x7f]")

MAX_PASSWORD_LENGTH = 128  # bcrypt only uses the first 72 bytes; this stops huge inputs
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail=detail)


def text(value: Optional[str], label: str, max_length: int, required: bool = True,
         multiline: bool = False) -> Optional[str]:
    """Trimmed text with a length limit. Returns None for an empty optional field."""
    value = (value or "").strip()
    if not value:
        if required:
            raise bad_request(f"{label} is required")
        return None
    if len(value) > max_length:
        raise bad_request(f"{label} must be {max_length} characters or fewer")
    if (CONTROL_CHARS if multiline else CONTROL_CHARS_SINGLE_LINE).search(value):
        raise bad_request(f"{label} contains invalid characters")
    return value


def email(value: Optional[str]) -> str:
    """Lowercased, trimmed email address."""
    value = (value or "").strip().lower()
    if len(value) > 254 or not EMAIL_PATTERN.fullmatch(value):
        raise bad_request("Please provide a valid email address")
    return value


def password(value: Optional[str]) -> str:
    """
    Passwords only need to be non-empty (strength is rated on the frontend, not
    required: a product decision). The maximum length stops multi-megabyte inputs.
    """
    if not value or not value.strip():
        raise bad_request("Password is required.")
    if len(value) > MAX_PASSWORD_LENGTH:
        raise bad_request(f"Password must be {MAX_PASSWORD_LENGTH} characters or fewer")
    return value


def contact_number(value: Optional[str], required: bool = False) -> Optional[str]:
    """Phone number: digits with optional + - ( ) and spaces, 7 to 15 digits."""
    value = (value or "").strip()
    if not value:
        if required:
            raise bad_request("Contact number is required")
        return None
    digits = re.sub(r"\D", "", value)
    if not re.fullmatch(r"[0-9+\-() ]+", value) or not 7 <= len(digits) <= 15:
        raise bad_request("Please provide a valid contact number")
    return value


def whole_number(value: int, label: str, minimum: int, maximum: int) -> int:
    if value < minimum or value > maximum:
        raise bad_request(f"{label} must be between {minimum} and {maximum}")
    return value


def token(value: Optional[str]) -> str:
    """Tokens from emailed links (secrets.token_urlsafe output)."""
    value = (value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", value):
        raise bad_request("This link is invalid. Please request a new one.")
    return value


# Image types we accept, identified by the file's first bytes. The browser-supplied
# Content-Type is not trusted. SVG is deliberately not allowed: an SVG can contain
# JavaScript, and it would run when the image URL is opened (stored XSS).
_IMAGE_SIGNATURES = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def _detect_image_type(data: bytes) -> Optional[str]:
    for signature, mime in _IMAGE_SIGNATURES:
        if data.startswith(signature):
            return mime
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


async def image_upload(upload: UploadFile, label: str = "Image") -> tuple[bytes, str]:
    """Read an uploaded image. Returns (bytes, detected MIME type)."""
    data = await upload.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise bad_request(f"{label} must be 5 MB or smaller")
    mime = _detect_image_type(data)
    if not mime:
        raise bad_request(f"{label} must be a JPG, PNG, GIF or WebP image")
    return data, mime
