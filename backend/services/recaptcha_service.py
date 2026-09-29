"""
Google reCAPTCHA Verification Service
Verifies reCAPTCHA tokens server-side
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")
RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


async def verify_recaptcha(token: str, remote_ip: str = None) -> dict:
    """
    Verify reCAPTCHA token with Google API
    
    Args:
        token: The reCAPTCHA response token from frontend
        remote_ip: Optional IP address of the user
    
    Returns:
        dict with success status and error codes
    """
    if not RECAPTCHA_SECRET_KEY or RECAPTCHA_SECRET_KEY == "your_secret_key_here":
        print("WARNING: reCAPTCHA not configured. Bypassing verification.")
        return {"success": True, "dev_mode": True}
    
    if not token:
        return {"success": False, "error_codes": ["missing-input-response"]}
    
    payload = {
        "secret": RECAPTCHA_SECRET_KEY,
        "response": token
    }
    
    if remote_ip:
        payload["remoteip"] = remote_ip
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(RECAPTCHA_VERIFY_URL, data=payload, timeout=10.0)
            
            if response.status_code != 200:
                return {"success": False, "error_codes": ["verification-failed"]}
            
            return response.json()
            
    except httpx.TimeoutException:
        return {"success": False, "error_codes": ["timeout-or-duplicate"]}
    except Exception as e:
        print(f"reCAPTCHA error: {e}")
        return {"success": False, "error_codes": ["unknown-error"]}


def get_error_message(error_codes: list) -> str:
    """Convert reCAPTCHA error codes to user-friendly messages"""
    error_map = {
        "missing-input-secret": "Server configuration error",
        "invalid-input-secret": "Server configuration error",
        "missing-input-response": "Please complete the reCAPTCHA",
        "invalid-input-response": "reCAPTCHA verification failed. Please try again.",
        "bad-request": "Invalid request",
        "timeout-or-duplicate": "reCAPTCHA expired. Please try again.",
        "verification-failed": "Could not verify reCAPTCHA. Please try again.",
        "unknown-error": "An error occurred. Please try again."
    }
    
    if not error_codes:
        return "reCAPTCHA verification failed"
    
    return error_map.get(error_codes[0], "reCAPTCHA verification failed")
