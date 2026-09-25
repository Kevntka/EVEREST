"""
API Routes for EVEREST Event Registration System
Handles authentication, registration, and password reset
"""

from fastapi import APIRouter, Form, File, UploadFile
from fastapi.responses import JSONResponse
from services.email_service import send_organizer_credentials
import os
import shutil
from pathlib import Path

router = APIRouter()

# Create uploads directory if it doesn't exist
UPLOAD_DIR = Path("uploads/events")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

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
                "Administrator": "admin",
                "Organizer": "organizer"
            }
            
            response_data = {
                "success": True,
                "message": "Login successful",
                "token": f"dummy-token-{email}",
                "role": role_map.get(user["role"], "user"),
                "name": user["full_name"],
                "email": email
            }
            
            # Add organizer-specific data if role is organizer
            if user["role"] == "Organizer":
                response_data["id"] = user.get("id")
                response_data["employment_id"] = user.get("employment_id")
                response_data["department"] = user.get("department")
            
            return JSONResponse(
                status_code=200,
                content=response_data
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
                "token": f"dummy-token-{gsuite}",
                "role": "student",
                "name": full_name,
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
    Adds organizer to in-memory storage and creates login credentials
    """
    # Check if email already exists
    if email in DUMMY_USERS:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Email already registered"
            }
        )
    
    # Check if employment_id already exists
    for org in DUMMY_ORGANIZERS:
        if org["employment_id"] == employment_id:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "Employment ID already exists"
                }
            )
    
    # Generate default password (employment_id)
    default_password = employment_id
    
    organizer = {
        "id": len(DUMMY_ORGANIZERS) + 1,
        "employment_id": employment_id,
        "full_name": full_name,
        "department": department,
        "email": email,
        "contact_number": contact_number
    }
    
    DUMMY_ORGANIZERS.append(organizer)
    
    # Add to DUMMY_USERS for login capability
    DUMMY_USERS[email] = {
        "password": default_password,
        "full_name": full_name,
        "role": "Organizer",
        "email": email,
        "employment_id": employment_id,
        "department": department,
        "contact_number": contact_number,
        "id": organizer["id"]
    }
    
    # Send email with credentials (async, don't wait for it)
    import asyncio
    try:
        asyncio.create_task(send_organizer_credentials(
            to_email=email,
            organizer_name=full_name,
            employment_id=employment_id,
            password=default_password
        ))
        email_sent = True
    except Exception as e:
        print(f"Email sending failed: {e}")
        email_sent = False
    
    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "message": "Organizer created successfully" + (" and email sent" if email_sent else ""),
            "organizer": organizer,
            "credentials": {
                "email": email,
                "password": default_password,
                "note": "Default password is the employment ID"
            }
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
    Also removes their login credentials
    """
    global DUMMY_ORGANIZERS
    
    # Find organizer to get their email
    organizer_to_delete = None
    for org in DUMMY_ORGANIZERS:
        if org["id"] == organizer_id:
            organizer_to_delete = org
            break
    
    # Remove from DUMMY_ORGANIZERS
    DUMMY_ORGANIZERS = [org for org in DUMMY_ORGANIZERS if org["id"] != organizer_id]
    
    # Remove from DUMMY_USERS if found
    if organizer_to_delete:
        email = organizer_to_delete.get("email")
        if email and email in DUMMY_USERS:
            del DUMMY_USERS[email]
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Organizer deleted successfully"
        }
    )



# Dummy events storage
DUMMY_EVENTS = []


@router.post("/api/events")
async def create_event(
    event_name: str = Form(...),
    event_description: str = Form(...),
    event_date: str = Form(...),
    event_time: str = Form(...),
    venue: str = Form(...),
    capacity: int = Form(...),
    organizer_id: int = Form(...),
    cover_photo: UploadFile = File(None)
):
    """
    Create a new event
    Organizers can create events that students can see
    Accepts optional cover photo upload
    """
    cover_photo_url = None
    
    # Handle file upload if provided
    if cover_photo and cover_photo.filename:
        # Generate unique filename
        file_extension = os.path.splitext(cover_photo.filename)[1]
        unique_filename = f"event_{len(DUMMY_EVENTS) + 1}_{cover_photo.filename}"
        file_path = UPLOAD_DIR / unique_filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(cover_photo.file, buffer)
        
        # Store relative URL
        cover_photo_url = f"/uploads/events/{unique_filename}"
    
    event = {
        "id": len(DUMMY_EVENTS) + 1,
        "organizer_id": organizer_id,
        "event_name": event_name,
        "event_description": event_description,
        "event_date": event_date,
        "event_time": event_time,
        "venue": venue,
        "capacity": capacity,
        "status": "open",
        "enrolled_count": 0,
        "cover_photo": cover_photo_url,
        "created_at": None  # Would be datetime in real DB
    }
    
    DUMMY_EVENTS.append(event)
    
    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "message": "Event created successfully",
            "event": event
        }
    )


@router.get("/api/events")
def get_events():
    """
    Get all events
    Returns list of events available for students
    """
    return {
        "success": True,
        "count": len(DUMMY_EVENTS),
        "events": DUMMY_EVENTS
    }


@router.get("/api/events/{event_id}")
def get_event(event_id: int):
    """
    Get a specific event by ID
    """
    for event in DUMMY_EVENTS:
        if event["id"] == event_id:
            return {
                "success": True,
                "event": event
            }
    
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "message": "Event not found"
        }
    )


@router.put("/api/events/{event_id}")
async def update_event(
    event_id: int,
    event_name: str = Form(...),
    event_description: str = Form(...),
    event_date: str = Form(...),
    event_time: str = Form(...),
    venue: str = Form(...),
    capacity: int = Form(...)
):
    """
    Update an existing event
    """
    for event in DUMMY_EVENTS:
        if event["id"] == event_id:
            event["event_name"] = event_name
            event["event_description"] = event_description
            event["event_date"] = event_date
            event["event_time"] = event_time
            event["venue"] = venue
            event["capacity"] = capacity
            
            return {
                "success": True,
                "message": "Event updated successfully",
                "event": event
            }
    
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "message": "Event not found"
        }
    )


@router.delete("/api/events/{event_id}")
def delete_event(event_id: int):
    """
    Delete an event by ID
    """
    global DUMMY_EVENTS
    
    initial_count = len(DUMMY_EVENTS)
    DUMMY_EVENTS = [event for event in DUMMY_EVENTS if event["id"] != event_id]
    
    if len(DUMMY_EVENTS) < initial_count:
        return {
            "success": True,
            "message": "Event deleted successfully"
        }
    
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "message": "Event not found"
        }
    )


# Dummy enrollments storage
DUMMY_ENROLLMENTS = []


@router.post("/api/events/{event_id}/enroll")
async def enroll_event(
    event_id: int,
    student_email: str = Form(...)
):
    """
    Enroll a student in an event
    """
    # Check if event exists
    event = None
    for evt in DUMMY_EVENTS:
        if evt["id"] == event_id:
            event = evt
            break
    
    if not event:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": "Event not found"
            }
        )
    
    # Check if already enrolled
    for enrollment in DUMMY_ENROLLMENTS:
        if enrollment["event_id"] == event_id and enrollment["student_email"] == student_email:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "Already enrolled in this event"
                }
            )
    
    # Check capacity
    if event["enrolled_count"] >= event["capacity"]:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Event is full"
            }
        )
    
    enrollment = {
        "id": len(DUMMY_ENROLLMENTS) + 1,
        "event_id": event_id,
        "student_email": student_email,
        "enrollment_date": None  # Would be datetime in real DB
    }
    
    DUMMY_ENROLLMENTS.append(enrollment)
    event["enrolled_count"] += 1
    
    return {
        "success": True,
        "message": "Successfully enrolled in event",
        "enrollment": enrollment
    }


@router.get("/api/students/{student_email}/enrollments")
def get_student_enrollments(student_email: str):
    """
    Get all events a student is enrolled in
    """
    student_enrollments = [e for e in DUMMY_ENROLLMENTS if e["student_email"] == student_email]
    
    # Get full event details
    enrolled_events = []
    for enrollment in student_enrollments:
        for event in DUMMY_EVENTS:
            if event["id"] == enrollment["event_id"]:
                enrolled_events.append(event)
                break
    
    return {
        "success": True,
        "count": len(enrolled_events),
        "events": enrolled_events
    }
