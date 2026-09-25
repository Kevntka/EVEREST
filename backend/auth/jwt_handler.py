"""
JWT Authentication Handler
Handles JWT token creation, validation, and password hashing
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
from dotenv import load_dotenv

load_dotenv()

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-here-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Bearer token security
security = HTTPBearer()


def hash_password(password: str) -> str:
    """Hash a password using bcrypt - direct implementation"""
    # Ensure password is within bcrypt's 72 byte limit
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    # Generate salt and hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash - direct implementation"""
    # Ensure password is within bcrypt's 72 byte limit
    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token
    
    Args:
        data: Dictionary containing user information (email, role, etc.)
        expires_delta: Optional expiration time delta
    
    Returns:
        JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT token
    
    Args:
        token: JWT token string
    
    Returns:
        Dictionary containing token payload
    
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Dependency to get current user from JWT token
    Use this in protected endpoints: current_user: dict = Depends(get_current_user)
    
    Args:
        credentials: HTTP Authorization credentials with Bearer token
    
    Returns:
        Dictionary containing user information from token
    
    Raises:
        HTTPException: If token is invalid or expired
    """
    token = credentials.credentials
    return decode_access_token(token)


def require_role(required_role: str):
    """
    Dependency factory to require specific role
    Usage: admin_user = Depends(require_role("admin"))
    
    Args:
        required_role: Role name required (admin, organizer, student, participant)
    
    Returns:
        Dependency function
    """
    def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role", "").lower()
        if user_role != required_role.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. {required_role.title()} role required."
            )
        return current_user
    
    return role_checker


# Example usage in routes:
# 
# @router.get("/api/admin/dashboard")
# def admin_dashboard(current_user: dict = Depends(require_role("admin"))):
#     return {"message": f"Welcome {current_user['name']}"}
# 
# @router.get("/api/profile")
# def get_profile(current_user: dict = Depends(get_current_user)):
#     return {"user": current_user}


def get_current_user_from_cookie(request: "Request") -> dict:
    """
    Dependency to get current user from cookie
    Use this in protected endpoints: current_user: dict = Depends(get_current_user_from_cookie)
    
    Args:
        request: FastAPI Request object
    
    Returns:
        Dictionary containing user information from token
    
    Raises:
        HTTPException: If cookie is missing or token is invalid
    """
    from fastapi import Request
    
    # Get cookie
    cookie_value = request.cookies.get("access_token")
    
    if not cookie_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated - cookie missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract token (remove "Bearer " prefix)
    token = cookie_value.replace("Bearer ", "") if cookie_value.startswith("Bearer ") else cookie_value
    
    return decode_access_token(token)


def require_role_from_cookie(required_role: str):
    """
    Dependency factory to require specific role from cookie
    Usage: admin_user = Depends(require_role_from_cookie("admin"))
    
    Args:
        required_role: Role name required (admin, organizer, student, participant)
    
    Returns:
        Dependency function
    """
    from fastapi import Request
    
    def role_checker(request: Request) -> dict:
        current_user = get_current_user_from_cookie(request)
        user_role = current_user.get("role", "").lower()
        if user_role != required_role.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. {required_role.title()} role required."
            )
        return current_user
    
    return role_checker


# Example usage with cookies:
# 
# @router.get("/api/admin/dashboard")
# def admin_dashboard(current_user: dict = Depends(require_role_from_cookie("admin"))):
#     return {"message": f"Welcome {current_user['name']}"}
# 
# @router.get("/api/profile")
# def get_profile(request: Request, current_user: dict = Depends(get_current_user_from_cookie)):
#     return {"user": current_user}
