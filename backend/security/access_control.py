"""
Access control: who is logged in, and are they allowed to call this endpoint?

The login cookie (access_token, HTTP-only) holds a signed JWT. These dependencies read
it, check the signature and expiry, and load the user from the database, so:
- a deleted account is logged out immediately (its row is gone),
- a role change takes effect immediately (the role comes from the database, not the token),
- changing or resetting the password logs out every old session (the token carries a
  fingerprint of the password hash, which no longer matches),
- Sign Out ends that session on the server too: the token's id (jti) goes into the
  revoked_tokens table, so a copied token stops working (not just the browser's cookie).

Usage in a route:
    user: User = Depends(require_roles("admin"))
    user: User = Depends(require_roles("organizer", "admin"))
    user: User = Depends(current_user)          # any logged-in role
"""

import hashlib
from fastapi import Depends, HTTPException, Request
from sqlalchemy import text
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

    # Tokens without an id were issued before Sign Out could revoke them: log in again
    jti = payload.get("jti")
    if not jti or is_revoked(db, jti):
        raise HTTPException(status_code=401, detail=SESSION_EXPIRED)

    user = db.query(User).filter(User.id == payload.get("user_id")).first()
    if (not user or user.is_active is False
            or payload.get("pwd") != password_fingerprint(user.password)):
        raise HTTPException(status_code=401, detail=SESSION_EXPIRED)
    return user


def is_revoked(db: Session, jti: str) -> bool:
    return db.execute(text("SELECT 1 FROM revoked_tokens WHERE jti = :j"), {"j": jti}).first() is not None


def revoke_token(db: Session, cookie: str | None) -> None:
    """Sign Out: remember the token's id until it would have expired anyway."""
    if not cookie:
        return
    try:
        payload = decode_access_token(cookie.removeprefix("Bearer "))
    except HTTPException:
        return  # already invalid or expired
    if not payload.get("jti"):
        return
    db.execute(text("""
        INSERT INTO revoked_tokens (jti, expires_at) VALUES (:j, to_timestamp(:exp))
        ON CONFLICT (jti) DO NOTHING
    """), {"j": payload["jti"], "exp": payload["exp"]})
    # Expired tokens are rejected by their signature check anyway; keep the table small
    db.execute(text("DELETE FROM revoked_tokens WHERE expires_at < NOW()"))
    db.commit()


def require_roles(*roles: str):
    """Dependency: the logged-in user must have one of these roles (else 403)."""
    def checker(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="You don't have permission to do this.")
        return user
    return checker
