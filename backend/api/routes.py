"""
API Routes for EVEREST Event Registration System
Handles authentication, registration, and password reset
"""

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/test")
def test_api():
    """Test endpoint to verify API is working"""
    return {"message": "EVEREST API is okay"}


@router.post("/api/login")
async def login(
    email: str = Form(...),
    password: str = Form(...),
    captcha: str = Form(None)
):
    """
    User login endpoint
    TODO: Add authentication logic (verify credentials, generate tokens)
    """
    if email and password:
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Login successful",
                "user": {"email": email}
            }
        )
    
    return JSONResponse(
        status_code=401,
        content={
            "success": False,
            "message": "Invalid credentials"
        }
    )


@router.post("/api/register")
async def register(
    full_name: str = Form(...),
    role: str = Form(...)
):
    """
    Initial registration endpoint (collects basic info)
    TODO: Store user data in database
    """
    if full_name and role:
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Registration successful",
                "user": {
                    "full_name": full_name,
                    "role": role
                }
            }
        )
    
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "message": "Invalid data"
        }
    )


@router.post("/api/register/student")
async def register_student(
    full_name: str = Form(...),
    role: str = Form(...),
    gsuite: str = Form(...),
    department: str = Form(...),
    password: str = Form(...)
):
    """
    Student registration endpoint
    TODO: Hash password, save to database, send verification email
    """
    if all([full_name, role, gsuite, department, password]):
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Student registration successful",
                "user": {
                    "full_name": full_name,
                    "role": role,
                    "gsuite": gsuite,
                    "department": department
                }
            }
        )
    
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "message": "Invalid data"
        }
    )


@router.post("/api/register/participant")
async def register_participant(
    full_name: str = Form(...),
    role: str = Form(...),
    email: str = Form(...),
    contact_number: str = Form(...),
    password: str = Form(...)
):
    """
    Participant registration endpoint
    TODO: Hash password, save to database, send verification email
    """
    if all([full_name, role, email, contact_number, password]):
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Participant registration successful",
                "user": {
                    "full_name": full_name,
                    "role": role,
                    "email": email,
                    "contact_number": contact_number
                }
            }
        )
    
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "message": "Invalid data"
        }
    )


@router.post("/api/forgot-password")
async def forgot_password(email: str = Form(...)):
    """
    Forgot password endpoint
    TODO: Generate reset token, send email with reset link
    """
    if email:
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Password reset link sent to your email"
            }
        )
    
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "message": "Invalid email"
        }
    )
