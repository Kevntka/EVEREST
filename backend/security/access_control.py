"""
Access control: who is logged in, and are they allowed to call this endpoint?

The login cookie (access_token, HTTP-only) holds a signed JWT. These dependencies read
it, check the signature and expiry, and load the user from the database, so:
- a deleted account is logged out immediately (its row is gone),
- a role change takes effect immediately (the role comes from the database, not the token),
- changing or resetting the password logs out every old session (the token carries a
  fingerprint of the password hash, which no longer matches).

Usage in a route:
    user: User = Depends(require_roles("admin"))
    user: User = Depends(require_roles("organizer", "admin"))
    user: User = Depends(current_user)          # any logged-in role
"""

import hashlib
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database.config import get_db
from models.user import User
from auth.jwt_handler import decode_access_token

SESSION_EXPIRED = "Your session has expired. Please log in again."


def password_fingerprint(password_hash: str) -> str:
    """Short value stored in the JWT that changes whenever the password changes."""
    return hashlib.sha256((password_hash or "").encode()).hexdigest()[:16]


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    cookie = request.cookies.get("access_token")
    if not cookie:
        raise HTTPException(status_code=401, detail=SESSION_EXPIRED)
    try:
        payload = decode_access_token(cookie.removeprefix("Bearer "))
    except HTTPException:
        raise HTTPException(status_code=401, detail=SESSION_EXPIRED)

    user = db.query(User).filter(User.id == payload.get("user_id")).first()
    if (not user or user.is_active is False
            or payload.get("pwd") != password_fingerprint(user.password)):
        raise HTTPException(status_code=401, detail=SESSION_EXPIRED)
    return user


def require_roles(*roles: str):
    """Dependency: the logged-in user must have one of these roles (else 403)."""
    def checker(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="You don't have permission to do this.")
        return user
    return checker
