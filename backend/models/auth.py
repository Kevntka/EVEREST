"""
Authentication Helper - Password storage and verification
Uses JWT-based password hashing with bcrypt
"""

from auth.jwt_handler import hash_password, verify_password as verify_hash

# In-memory password storage (hashed passwords)
# In production, this should be in database
USER_PASSWORDS = {}

def set_user_password(email: str, password: str):
    """
    Store user password (hashed)
    
    Args:
        email: User email
        password: Plain text password (will be hashed)
    """
    hashed = hash_password(password)
    USER_PASSWORDS[email] = hashed
    print(f"✅ Password set for {email}")

def verify_password(email: str, password: str) -> bool:
    """
    Verify user password
    
    Args:
        email: User email
        password: Plain text password to verify
    
    Returns:
        True if password matches, False otherwise
    """
    stored_hash = USER_PASSWORDS.get(email)
    if not stored_hash:
        return False
    
    return verify_hash(password, stored_hash)

def get_user_password(email: str) -> str:
    """
    Get user password hash
    
    Args:
        email: User email
    
    Returns:
        Hashed password or None
    """
    return USER_PASSWORDS.get(email)

def password_exists(email: str) -> bool:
    """
    Check if password exists for user
    
    Args:
        email: User email
    
    Returns:
        True if password exists, False otherwise
    """
    return email in USER_PASSWORDS

