"""
API Routes for EVEREST Event Registration System
Handles authentication, registration, and password reset
"""

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse

router = APIRouter()

# Dummy user accounts (in-memory storage)
DUMMY_USERS = {
    "student@everest.com": {
        "password": "student123",
        "full_name": "Juan Dela Cruz",
        "role": "Student",
        "gsuite": "student@everest.com",
        "department": "Computer Science"
    },
    "participant@everest.com": {
        "password": "participant123",
        "full_name": "Maria Santos",
        "role": "Participant",
        "email": "participant@everest.com",
        "contact_number": "09171234567"
    },
    "admin@everest.com": {
        "password": "admin123",
        "full_name": "Admin User",
        "role": "Administrator",
        "email": "admin@everest.com"
    }
}

# Dummy organizers storage
DUMMY_ORGANIZERS = []


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
    Validates credentials against dummy user accounts
    """
    # Check if user exists
    if email in DUMMY_USERS:
        user = DUMMY_USERS[email]
        
        # Verify password
        if user["password"] == password:
            # Map role to lowercase for frontend routing
            role_map = {
                "Student": "student",
                "Participant": "participant",
                "Administrator": "admin"
            }
            
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Login successful",
                    "token": f"dummy-token-{email}",
                    "role": role_map.get(user["role"], "user"),
                    "name": user["full_name"],
                    "email": email
                }
            )
    
    # Invalid credentials
    return JSONResponse(
        status_code=401,
        content={
            "success": False,
            "message": "Invalid email or password"
        }
    )


@router.post("/api/register")
async def register(
    full_name: str = Form(...),
    role: str = Form(...)
):
    """
    Initial registration endpoint (collects basic info)
    Stores data in memory temporarily
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
    Adds new student to dummy users (in-memory)
    """
    if all([full_name, role, gsuite, department, password]):
        # Add to dummy users
        DUMMY_USERS[gsuite] = {
            "password": password,
            "full_name": full_name,
            "role": role,
            "gsuite": gsuite,
            "department": department
        }
        
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
    Adds new participant to dummy users (in-memory)
    """
    if all([full_name, role, email, contact_number, password]):
        # Add to dummy users
        DUMMY_USERS[email] = {
            "password": password,
            "full_name": full_name,
            "role": role,
            "email": email,
            "contact_number": contact_number
        }
        
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
    Checks if email exists in dummy users
    """
    if email and email in DUMMY_USERS:
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Password reset link sent to your email"
            }
        )
    
    # Return success even if email doesn't exist (security best practice)
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "If an account exists, you will receive a password reset link"
        }
    )


@router.get("/api/users")
def get_users():
    """
    Get all dummy users (for testing purposes only)
    Returns list of users without passwords
    """
    users_list = []
    for email, data in DUMMY_USERS.items():
        user_data = data.copy()
        user_data.pop("password", None)  # Remove password
        user_data["email"] = email
        users_list.append(user_data)
    
    return {
        "success": True,
        "count": len(users_list),
        "users": users_list
    }




@router.post("/api/organizers")
async def create_organizer(
    employment_id: str = Form(...),
    full_name: str = Form(...),
    department: str = Form(...),
    email: str = Form(...),
    contact_number: str = Form(...)
):
    """
    Create a new organizer
    Adds organizer to in-memory storage
    """
    organizer = {
        "id": len(DUMMY_ORGANIZERS) + 1,
        "employment_id": employment_id,
        "full_name": full_name,
        "department": department,
        "email": email,
        "contact_number": contact_number
    }
    
    DUMMY_ORGANIZERS.append(organizer)
    
    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "message": "Organizer created successfully",
            "organizer": organizer
        }
    )


@router.get("/api/organizers")
def get_organizers():
    """
    Get all organizers
    Returns list of organizers from in-memory storage
    """
    return {
        "success": True,
        "count": len(DUMMY_ORGANIZERS),
        "organizers": DUMMY_ORGANIZERS
    }


@router.delete("/api/organizers/{organizer_id}")
def delete_organizer(organizer_id: int):
    """
    Delete an organizer by ID
    """
    global DUMMY_ORGANIZERS
    
    # Find and remove organizer
    DUMMY_ORGANIZERS = [org for org in DUMMY_ORGANIZERS if org["id"] != organizer_id]
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Organizer deleted successfully"
        }
    )
