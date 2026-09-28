"""
CSRF Protection Middleware and Utilities
Implements Double Submit Cookie pattern for CSRF protection
"""

import secrets
import hmac
import hashlib
from fastapi import Request, HTTPException, status
from fastapi.responses import Response
from typing import Optional

# CSRF Configuration
CSRF_TOKEN_LENGTH = 32
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_FORM_FIELD_NAME = "csrf_token"

# Methods that don't need CSRF protection (safe methods)
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def generate_csrf_token() -> str:
    """
    Generate a cryptographically secure CSRF token
    
    Returns:
        Random token string
    """
    return secrets.token_urlsafe(CSRF_TOKEN_LENGTH)


def get_csrf_token_from_request(request: Request) -> Optional[str]:
    """
    Extract CSRF token from request (header or form field)
    
    Args:
        request: FastAPI Request object
        
    Returns:
        CSRF token if found, None otherwise
    """
    # Try header first (for JSON/AJAX requests)
    token = request.headers.get(CSRF_HEADER_NAME)
    
    if token:
        return token
    
    # Try form field (for traditional form submissions)
    # Note: This requires the request body to be read, which is done in middleware
    return None  # Form field check handled separately per endpoint


def validate_csrf_token(request_token: str, cookie_token: str) -> bool:
    """
    Validate CSRF token using constant-time comparison
    
    Args:
        request_token: Token from request header or form
        cookie_token: Token from cookie
        
    Returns:
        True if tokens match, False otherwise
    """
    if not request_token or not cookie_token:
        return False
    
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(request_token, cookie_token)


def set_csrf_cookie(response: Response, token: str) -> None:
    """
    Set CSRF token cookie in response
    
    Args:
        response: FastAPI Response object
        token: CSRF token to set
    """
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,  # Must be accessible to JavaScript
        secure=False,  # Set to True in production with HTTPS
        samesite="strict",  # Strict for CSRF token
        max_age=86400,  # 24 hours
        path="/"
    )


def get_csrf_token_from_cookie(request: Request) -> Optional[str]:
    """
    Get CSRF token from cookie
    
    Args:
        request: FastAPI Request object
        
    Returns:
        CSRF token if found, None otherwise
    """
    return request.cookies.get(CSRF_COOKIE_NAME)


async def verify_csrf_protection(request: Request) -> None:
    """
    Verify CSRF token for state-changing requests
    
    Args:
        request: FastAPI Request object
        
    Raises:
        HTTPException: If CSRF validation fails
    """
    # Skip CSRF check for safe methods
    if request.method in SAFE_METHODS:
        return
    
    # Get token from cookie
    cookie_token = get_csrf_token_from_cookie(request)
    
    if not cookie_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing from cookie"
        )
    
    # Get token from request (header)
    request_token = get_csrf_token_from_request(request)
    
    # If not in header, try to get from form data
    if not request_token:
        # For form submissions, we need to check form data
        # This will be handled by individual endpoints
        content_type = request.headers.get("content-type", "")
        if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            # Form data - will be validated by endpoint
            pass
        else:
            # JSON/other - must be in header
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing from request"
            )
    
    # Validate token
    if request_token and not validate_csrf_token(request_token, cookie_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token validation failed"
        )


from fastapi import Depends, Form
from typing import Optional


async def validate_csrf_form(
    request: Request,
    csrf_token: Optional[str] = Form(None)
) -> None:
    """
    FastAPI dependency to validate CSRF token from form data
    Use in endpoints: csrf_check = Depends(validate_csrf_form)
    
    Args:
        request: FastAPI Request object
        csrf_token: CSRF token from form field
        
    Raises:
        HTTPException: If CSRF validation fails
    """
    # Skip for safe methods
    if request.method in SAFE_METHODS:
        return
    
    cookie_token = get_csrf_token_from_cookie(request)
    
    if not cookie_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing from cookie"
        )
    
    if not csrf_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing from form"
        )
    
    if not validate_csrf_token(csrf_token, cookie_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token validation failed"
        )


async def validate_csrf_header(request: Request) -> None:
    """
    FastAPI dependency to validate CSRF token from header
    Use in endpoints: csrf_check = Depends(validate_csrf_header)
    
    Args:
        request: FastAPI Request object
        
    Raises:
        HTTPException: If CSRF validation fails
    """
    # Skip for safe methods
    if request.method in SAFE_METHODS:
        return
    
    cookie_token = get_csrf_token_from_cookie(request)
    
    if not cookie_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing from cookie"
        )
    
    request_token = get_csrf_token_from_request(request)
    
    if not request_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing from request header"
        )
    
    if not validate_csrf_token(request_token, cookie_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token validation failed"
        )
