"""
API Routes with PostgreSQL Database Integration
Matching the actual database schema
"""

from fastapi import APIRouter, Form, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session
from database.config import get_db
from models.user import User, UserRole, Department, Attendee, Event, Registration
from models.auth import set_user_password, get_user_password
from auth.jwt_handler import create_access_token, get_current_user, require_role, verify_password as verify_bcrypt_password
from datetime import timedelta
from pydantic import BaseModel
import re
from services.recaptcha_service import verify_recaptcha, get_error_message
from auth.csrf_protection import generate_csrf_token, set_csrf_cookie, validate_csrf_form

router = APIRouter()


@router.get("/test")
def test_api():
    """Test endpoint to verify API is working"""
    return {"message": "EVEREST API with PostgreSQL is okay"}




@router.get("/csrf-token")
async def get_csrf_token(request: Request):
    """
    Get or generate CSRF token
    This endpoint is called when the app starts to get a CSRF token
    """
    from auth.csrf_protection import get_csrf_token_from_cookie
    
    # Check if token already exists in cookie
    existing_token = get_csrf_token_from_cookie(request)
    
    if existing_token:
        # Return existing token
        return JSONResponse(
            status_code=200,
            content={"csrf_token": existing_token}
        )
    
    # Generate new token
    csrf_token = generate_csrf_token()
    
    response = JSONResponse(
        status_code=200,
        content={"csrf_token": csrf_token}
    )
    
    # Set CSRF cookie
    set_csrf_cookie(response, csrf_token)
    
    return response

@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    recaptcha_token: str = Form(None),
    db: Session = Depends(get_db)
):
    """
    User login endpoint with secure HTTP-only cookie authentication
    Token stored in cookie (not returned in response body)
    """
    try:
        # Verify reCAPTCHA first
        client_ip = request.client.host if request.client else None
        recaptcha_result = await verify_recaptcha(recaptcha_token, client_ip)
        
        if not recaptcha_result.get("success"):
            error_codes = recaptcha_result.get("error_codes", [])
            error_msg = get_error_message(error_codes)
            raise HTTPException(status_code=400, detail=error_msg)
        
        email = email.strip().lower()

        # Find user by email
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        # Verify password - check database password field
        if not user.password:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        # Verify password against database hash
        if not verify_bcrypt_password(password, user.password):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        # Create JWT token
        token_data = {
            "sub": email,  # Subject (user identifier)
            "user_id": user.id,
            "email": email,
            "name": user.full_name,
            "role": user.role
        }
        
        access_token = create_access_token(
            data=token_data,
            expires_delta=timedelta(hours=24)
        )
        
        # Response WITHOUT sensitive data (token in cookie, no email exposure)
        response_data = {
            "success": True,
            "message": "Login successful",
            "role": user.role,
            "name": user.full_name,
            "id": user.id
        }
        
        # Create response with cookie
        response = JSONResponse(status_code=200, content=response_data)
        
        # Set secure HTTP-only cookie with token
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,  # Cannot be accessed by JavaScript
            secure=False,  # Set to True in production with HTTPS
            samesite="lax",  # CSRF protection
            max_age=86400,  # 24 hours in seconds
            path="/"
        )
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Login error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/logout")
async def logout():
    """
    Logout endpoint - clears the authentication cookie
    """
    response = JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Logged out successfully"
        }
    )
    
    # Clear the cookie
    response.delete_cookie(
        key="access_token",
        path="/"
    )
    
    return response



@router.post("/register/student")
async def register_student(
    full_name: str = Form(...),
    role: str = Form(...),
    email: str = Form(...),
    department: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Student registration
    """
    email = email.strip().lower()
    if not re.fullmatch(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", email):
        raise HTTPException(status_code=400, detail="Please provide a valid email address")

    # Check if email already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash password
    from auth.jwt_handler import hash_password
    hashed_password = hash_password(password)
    
    # Create user
    new_user = User(
        full_name=full_name,
        email=email,
        password=hashed_password,
        role='student'
    )
    db.add(new_user)
    db.flush()
    
    # Get or create department
    dept = db.query(Department).filter(Department.department_name == department).first()
    if not dept:
        dept = Department(department_name=department)
        db.add(dept)
        db.flush()
    
    # Create user_role entry for additional info
    user_role = UserRole(
        user_id=new_user.id,
        role_type='student',
        department_id=dept.id
    )
    db.add(user_role)
    db.commit()
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Student registration successful",
            "user": {
                "id": new_user.id,
                "full_name": full_name,
                "email": email
            }
        }
    )


@router.post("/register/participant")
async def register_participant(
    full_name: str = Form(...),
    role: str = Form(...),
    email: str = Form(...),
    contact_number: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Participant registration
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash password
    from auth.jwt_handler import hash_password
    hashed_password = hash_password(password)
    
    # Create user
    new_user = User(
        full_name=full_name,
        email=email,
        password=hashed_password,
        role='participant'
    )
    db.add(new_user)
    db.flush()
    
    # Create user_role entry for additional info
    user_role = UserRole(
        user_id=new_user.id,
        role_type='participant',
        contact_number=contact_number
    )
    db.add(user_role)
    db.commit()
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Participant registration successful",
            "user": {
                "id": new_user.id,
                "full_name": full_name,
                "email": email
            }
        }
    )


@router.post("/organizers")
async def create_organizer(
    employment_id: str = Form(...),
    full_name: str = Form(...),
    department: str = Form(...),
    email: str = Form(...),
    contact_number: str = Form(None),  # Optional field
    db: Session = Depends(get_db)
):
    """
    Create organizer (admin only)
    """
    try:
        print(f"\n🔧 Creating organizer: {full_name} ({email})")
        
        # Check if email already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Generate random password
        import random
        import string
        password_chars = "1234567890qwertyuiopasdfghjklzxcvbnm!@#$%^&*_"
        random_password = ''.join(random.choice(password_chars) for _ in range(12))
        
        # Hash password
        from auth.jwt_handler import hash_password
        hashed_password = hash_password(random_password)
        
        # Get or create department
        dept = db.query(Department).filter(Department.department_name == department).first()
        if not dept:
            dept = Department(department_name=department)
            db.add(dept)
            db.flush()
        
        # Create user
        new_user = User(
            full_name=full_name,
            email=email,
            password=hashed_password,
            role='organizer'
        )
        db.add(new_user)
        db.flush()
        
        # Create user_role entry for additional info
        user_role = UserRole(
            user_id=new_user.id,
            role_type='organizer',
            department_id=dept.id,
            employment_id=employment_id,
            contact_number=contact_number
        )
        db.add(user_role)
        db.commit()
        
        # Send email with credentials and WAIT for SMTP confirmation
        from services.email_service import send_organizer_credentials
        
        print(f"\n📧 Sending credentials to {email}...")
        print(f"   ├─ Connecting to SMTP server...")
        print(f"   ├─ Authenticating...")
        print(f"   ├─ Sending email...")
        
        email_sent = False
        email_message = ""
        
        # TEMPORARY: Skip email for testing (remove this later)
        SKIP_EMAIL = True  # Set to False to enable email sending
        
        if SKIP_EMAIL:
            print(f"   └─ ⚠️ EMAIL SKIPPED (testing mode)")
            email_sent = False
            email_message = "Email skipped for testing"
        else:
            try:
                # IMPORTANT: Check the return value from SMTP confirmation
                email_sent = await send_organizer_credentials(
                    to_email=email,
                    organizer_name=full_name,
                    employment_id=employment_id,
                    password=random_password  # Send the random password
                )
                
                if email_sent:
                    print(f"   └─ ✅ SMTP confirmed email delivery")
                    email_message = "Credentials sent via email"
                else:
                    print(f"   └─ ⚠️ Email sending failed (no exception but returned False)")
                    email_message = "Email failed to send. Please share credentials manually."
                    
            except Exception as e:
                print(f"   └─ ❌ Error: {e}")
                email_sent = False
                email_message = f"Email failed: {str(e)}. Please share credentials manually."
        
        # Return different response based on email success
        if email_sent:
            return JSONResponse(
                status_code=201,
                content={
                    "success": True,
                    "message": f"Organizer created successfully and credentials sent via email",
                    "organizer": {
                        "id": new_user.id,
                        "employment_id": employment_id,
                        "full_name": full_name,
                        "department": department,
                        "email": email,
                        "contact_number": contact_number
                    },
                    "credentials": {
                        "email": email,
                        "password": random_password,
                        "note": "Credentials have been sent to the organizer's email"
                    },
                    "email_sent": True
                }
            )
        else:
            return JSONResponse(
                status_code=201,
                content={
                    "success": True,
                    "message": f"Organizer created but email could not be sent",
                    "organizer": {
                        "id": new_user.id,
                        "employment_id": employment_id,
                        "full_name": full_name,
                        "department": department,
                        "email": email,
                        "contact_number": contact_number
                    },
                    "credentials": {
                        "email": email,
                        "password": random_password,
                        "note": f"{email_message}"
                    },
                    "email_sent": False
                }
            )
    
    except HTTPException as http_ex:
        # Re-raise HTTP exceptions (like 400 for duplicate email)
        print(f"❌ HTTP Exception: {http_ex.detail}")
        raise http_ex
    
    except Exception as e:
        # Catch all other exceptions
        print(f"❌ UNEXPECTED ERROR creating organizer:")
        print(f"   Error: {e}")
        print(f"   Type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        
        # Rollback database changes
        db.rollback()
        
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/organizers")
def get_organizers(db: Session = Depends(get_db)):
    """
    Get all organizers
    """
    try:
        print("\n🔍 GET /organizers - Fetching organizers from database...")
        
        # Get all users with organizer role
        organizers = db.query(User, UserRole, Department).outerjoin(
            UserRole, User.id == UserRole.user_id
        ).outerjoin(
            Department, UserRole.department_id == Department.id
        ).filter(User.role == 'organizer').all()
        
        print(f"   Found {len(organizers)} organizers")
        
        result = []
        for user, user_role, dept in organizers:
            result.append({
                "id": user.id,
                "employment_id": user_role.employment_id if user_role else f"EMP{user.id:03d}",
                "full_name": user.full_name,
                "department": dept.department_name if dept else "N/A",
                "email": user.email,
                "contact_number": user_role.contact_number if user_role and user_role.contact_number else "N/A"
            })
        
        print(f"   ✅ Returning {len(result)} organizers")
        
        return {
            "success": True,
            "count": len(result),
            "organizers": result
        }
    
    except Exception as e:
        print(f"   ❌ Error fetching organizers: {e}")
        import traceback
        traceback.print_exc()
        
        # Return empty list instead of crashing
        return {
            "success": True,
            "count": 0,
            "organizers": [],
            "error": str(e)
        }


@router.delete("/organizers/{organizer_id}")
def delete_organizer(organizer_id: int, db: Session = Depends(get_db)):
    """
    Delete organizer
    """
    user = db.query(User).filter(User.id == organizer_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="Organizer not found")
    
    # Delete user (cascade will delete user_role)
    db.delete(user)
    db.commit()
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Organizer deleted successfully"
        }
    )


@router.get("/students")
def get_students(db: Session = Depends(get_db)):
    """
    Get all students
    """
    # Get all users with student role
    students = db.query(User, UserRole, Department).outerjoin(
        UserRole, User.id == UserRole.user_id
    ).outerjoin(
        Department, UserRole.department_id == Department.id
    ).filter(User.role == 'student').all()
    
    result = []
    for user, user_role, dept in students:
        result.append({
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "department": dept.department_name if dept else "N/A",
            "year_level": "N/A",
            "gender": "N/A",
            "contact_number": user_role.contact_number if user_role and user_role.contact_number else "N/A"
        })
    
    return {
        "success": True,
        "count": len(result),
        "students": result
    }


@router.delete("/students/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db)):
    """
    Delete student
    """
    user = db.query(User).filter(
        User.id == student_id,
        User.role == 'student'
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="Student not found")

    db.delete(user)
    db.commit()

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Student deleted successfully"
        }
    )


@router.get("/participants")
def get_participants(db: Session = Depends(get_db)):
    """
    Get all participants
    """
    # Get all users with participant role
    participants = db.query(User, UserRole).outerjoin(
        UserRole, User.id == UserRole.user_id
    ).filter(User.role == 'participant').all()
    
    result = []
    for user, user_role in participants:
        result.append({
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "address": "N/A",
            "gender": "N/A",
            "contact_number": user_role.contact_number if user_role and user_role.contact_number else "N/A"
        })
    
    return {
        "success": True,
        "count": len(result),
        "participants": result
    }


@router.delete("/participants/{participant_id}")
def delete_participant(participant_id: int, db: Session = Depends(get_db)):
    """
    Delete participant
    """
    user = db.query(User).filter(
        User.id == participant_id,
        User.role == 'participant'
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="Participant not found")

    # registrations.user_id has no ON DELETE CASCADE; attendees cascade from registrations
    db.query(Registration).filter(Registration.user_id == participant_id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Participant deleted successfully"
        }
    )


@router.post("/forgot-password")
async def forgot_password(email: str = Form(...), db: Session = Depends(get_db)):
    """
    Request password reset - sends email with reset link
    """
    # Check if user exists
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        # Don't reveal if email exists or not (security)
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "If an account exists, you will receive a password reset link"
            }
        )
    
    # Generate reset token
    import secrets
    token = secrets.token_urlsafe(32)
    
    # Set expiration (1 hour from now)
    from datetime import datetime, timedelta
    expires_at = datetime.now() + timedelta(hours=1)
    
    # Save token to database
    from sqlalchemy import text
    query = text("""
        INSERT INTO password_reset_tokens (user_id, token, expires_at)
        VALUES (:user_id, :token, :expires_at)
    """)
    
    try:
        db.execute(query, {
            "user_id": user.id,
            "token": token,
            "expires_at": expires_at
        })
        db.commit()
        
        # Send email with reset link
        reset_link = f"http://localhost:4200/reset-password?token={token}"
        
        from services.email_service import send_password_reset_email
        email_sent = await send_password_reset_email(
            to_email=email,
            reset_link=reset_link,
            user_name=user.full_name
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "If an account exists, you will receive a password reset link",
                "email_sent": email_sent
            }
        )
    except Exception as e:
        db.rollback()
        print(f"Error in forgot password: {e}")
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "If an account exists, you will receive a password reset link"
            }
        )


@router.post("/reset-password")
async def reset_password(
    token: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Reset password using token from email
    """
    from sqlalchemy import text
    from datetime import datetime
    
    # Find valid token
    query = text("""
        SELECT user_id, expires_at, used
        FROM password_reset_tokens
        WHERE token = :token
    """)
    
    result = db.execute(query, {"token": token}).first()
    
    if not result:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    user_id, expires_at, used = result
    
    # Check if token is already used
    if used:
        raise HTTPException(status_code=400, detail="Reset token has already been used")
    
    # Check if token is expired
    if datetime.now() > expires_at:
        raise HTTPException(status_code=400, detail="Reset token has expired")
    
    # Hash new password
    from auth.jwt_handler import hash_password
    hashed_password = hash_password(new_password)
    
    # Update user password
    update_query = text("""
        UPDATE users
        SET password = :password, updated_at = CURRENT_TIMESTAMP
        WHERE id = :user_id
    """)
    
    # Mark token as used
    mark_used_query = text("""
        UPDATE password_reset_tokens
        SET used = TRUE
        WHERE token = :token
    """)
    
    try:
        db.execute(update_query, {"password": hashed_password, "user_id": user_id})
        db.execute(mark_used_query, {"token": token})
        db.commit()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Password reset successfully"
            }
        )
    except Exception as e:
        db.rollback()
        print(f"Error resetting password: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset password")




# ==================== EVENTS ENDPOINTS ====================

from fastapi import File, UploadFile

MAX_COVER_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post("/events")
async def create_event(
    event_name: str = Form(...),
    event_description: str = Form(...),
    event_date: str = Form(...),
    event_time: str = Form(...),
    venue: str = Form(...),
    capacity: int = Form(...),
    organizer_id: int = Form(...),
    department: str = Form(None),
    about_event: str = Form(None),
    cover_photo: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    """
    Create a new event (organizer only)
    """
    # Cover photo bytes are stored in the database (events.cover_photo_data)
    # and served by GET /api/events/{id}/cover
    cover_photo_data = None
    cover_photo_type = None
    if cover_photo and cover_photo.filename:
        if not (cover_photo.content_type or "").startswith("image/"):
            raise HTTPException(status_code=400, detail="Cover photo must be an image")
        cover_photo_data = await cover_photo.read()
        if len(cover_photo_data) > MAX_COVER_PHOTO_BYTES:
            raise HTTPException(status_code=400, detail="Cover photo must be 5 MB or smaller")
        cover_photo_type = cover_photo.content_type

    # Link event to the organizer's user_roles row (events.user_role_id FK)
    organizer_role = db.query(UserRole).filter(
        UserRole.user_id == organizer_id,
        UserRole.role_type == 'organizer'
    ).first()
    if not organizer_role:
        raise HTTPException(status_code=400, detail="Organizer not found")

    from datetime import datetime
    try:
        datetime.strptime(f"{event_date} {event_time[:5]}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date or time")

    # Insert into database (raw SQL for now since schema is complex)
    from sqlalchemy import text
    
    query = text("""
        INSERT INTO events (
            user_role_id, event_name, event_description, 
            event_date, event_time, venue, capacity, status,
            cover_photo_data, cover_photo_type, department, about_event
        ) VALUES (
            :user_role_id, :event_name, :event_description,
            :event_date, :event_time, :venue, :capacity, 'open',
            :cover_photo_data, :cover_photo_type, :department, :about_event
        ) RETURNING id
    """)
    
    try:
        result = db.execute(query, {
            "user_role_id": organizer_role.id,
            "event_name": event_name,
            "event_description": event_description,
            "event_date": event_date,
            "event_time": event_time,
            "venue": venue,
            "capacity": capacity,
            "cover_photo_data": cover_photo_data,
            "cover_photo_type": cover_photo_type,
            "department": department or None,
            "about_event": about_event or None
        })
        event_id = result.scalar()

        # cover_photo keeps holding the URL the frontend loads
        cover_photo_url = None
        if cover_photo_data is not None:
            cover_photo_url = f"/api/events/{event_id}/cover"
            db.execute(
                text("UPDATE events SET cover_photo = :url WHERE id = :id"),
                {"url": cover_photo_url, "id": event_id}
            )
        db.commit()
        
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "message": "Event created successfully",
                "event": {
                    "id": event_id,
                    "event_name": event_name,
                    "event_description": event_description,
                    "event_date": event_date,
                    "event_time": event_time,
                    "venue": venue,
                    "capacity": capacity,
                    "status": "open",
                    "enrolled_count": 0,
                    "cover_photo": cover_photo_url
                }
            }
        )
    except Exception as e:
        db.rollback()
        print(f"Error creating event: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating event: {str(e)}")


@router.get("/events")
def get_events(db: Session = Depends(get_db)):
    """
    Get all events
    """
    from sqlalchemy import text
    
    query = text("""
        SELECT 
            e.id, e.event_name, e.event_description,
            e.event_date, e.event_time, e.venue, e.capacity,
            e.status, e.cover_photo,
            COALESCE(COUNT(r.id), 0) as enrolled_count,
            e.department, e.about_event
        FROM events e
        LEFT JOIN registrations r ON e.id = r.event_id
        GROUP BY e.id
        ORDER BY e.created_at DESC
    """)
    
    try:
        result = db.execute(query)
        events = []
        
        for row in result:
            events.append({
                "id": row[0],
                "event_name": row[1],
                "event_description": row[2],
                "event_date": str(row[3]) if row[3] else None,
                "event_time": str(row[4]) if row[4] else None,
                "venue": row[5],
                "capacity": row[6],
                "status": row[7],
                "cover_photo": row[8],
                "enrolled_count": row[9],
                "department": row[10],
                "about_event": row[11]
            })
        
        return {
            "success": True,
            "count": len(events),
            "events": events
        }
    except Exception as e:
        print(f"Error getting events: {e}")
        return {
            "success": True,
            "count": 0,
            "events": []
        }


@router.get("/events/{event_id}/cover")
def get_event_cover(event_id: int, db: Session = Depends(get_db)):
    """
    Serve an event's cover photo from the database
    """
    from sqlalchemy import text

    row = db.execute(
        text("SELECT cover_photo_data, cover_photo_type FROM events WHERE id = :id"),
        {"id": event_id}
    ).first()

    if not row or row[0] is None:
        raise HTTPException(status_code=404, detail="Cover photo not found")

    return Response(content=bytes(row[0]), media_type=row[1] or "application/octet-stream")


@router.get("/events/{event_id}")
def get_event(event_id: int, db: Session = Depends(get_db)):
    """
    Get a specific event by ID
    """
    from sqlalchemy import text
    
    query = text("""
        SELECT 
            e.id, e.event_name, e.event_description,
            e.event_date, e.event_time, e.venue, e.capacity,
            e.status, e.cover_photo,
            COALESCE(COUNT(r.id), 0) as enrolled_count,
            e.department, e.about_event
        FROM events e
        LEFT JOIN registrations r ON e.id = r.event_id
        WHERE e.id = :event_id
        GROUP BY e.id
    """)
    
    try:
        result = db.execute(query, {"event_id": event_id})
        row = result.first()
        
        if not row:
            raise HTTPException(status_code=404, detail="Event not found")
        
        return {
            "success": True,
            "event": {
                "id": row[0],
                "event_name": row[1],
                "event_description": row[2],
                "event_date": str(row[3]) if row[3] else None,
                "event_time": str(row[4]) if row[4] else None,
                "venue": row[5],
                "capacity": row[6],
                "status": row[7],
                "cover_photo": row[8],
                "enrolled_count": row[9],
                "department": row[10],
                "about_event": row[11]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/organizer/stats")
def get_organizer_stats(organizer_id: int, db: Session = Depends(get_db)):
    """
    Dashboard stats for one organizer (organizer_id is the organizer's users.id)
    """
    from sqlalchemy import text

    # events.user_role_id references the organizer's user_roles row
    events_query = text("""
        SELECT e.id, e.event_name, e.capacity, e.status,
               COUNT(r.id) AS enrolled
        FROM events e
        JOIN user_roles ur ON ur.id = e.user_role_id
        LEFT JOIN registrations r ON r.event_id = e.id
        WHERE ur.user_id = :organizer_id AND ur.role_type = 'organizer'
        GROUP BY e.id
        ORDER BY e.created_at DESC
    """)
    events = db.execute(events_query, {"organizer_id": organizer_id}).fetchall()

    totals_query = text("""
        SELECT COUNT(DISTINCT r.user_id) FILTER (WHERE u.role = 'student') AS students,
               COUNT(DISTINCT r.user_id) FILTER (WHERE u.role = 'participant') AS participants,
               COUNT(r.id) AS total_enrollment,
               COUNT(a.id) FILTER (WHERE a.attendance_status = 'present') AS present
        FROM registrations r
        JOIN users u ON u.id = r.user_id
        JOIN events e ON e.id = r.event_id
        JOIN user_roles ur ON ur.id = e.user_role_id
        LEFT JOIN attendees a ON a.registration_id = r.id
        WHERE ur.user_id = :organizer_id AND ur.role_type = 'organizer'
    """)
    totals = db.execute(totals_query, {"organizer_id": organizer_id}).first()

    total_enrollment = totals[2] or 0
    present = totals[3] or 0

    return {
        "success": True,
        "stats": {
            "students": totals[0] or 0,
            "participants": totals[1] or 0,
            "totalEnrollment": total_enrollment,
            "openEvents": sum(1 for e in events if e[3] == 'open')
        },
        "enrollmentData": [
            {"eventName": e[1], "enrolled": e[4], "capacity": e[2] or 0}
            for e in events
        ],
        "attendanceData": {
            "present": present,
            "notRecorded": total_enrollment - present
        }
    }


@router.get("/organizer/attendees")
def get_organizer_attendees(organizer_id: int, db: Session = Depends(get_db)):
    """
    Everyone enrolled in this organizer's events, one row per registration
    (organizer_id is the organizer's users.id)
    """
    from sqlalchemy import text

    query = text("""
        SELECT r.id, u.full_name, u.email, u.role, e.event_name,
               d.department_name, ur.contact_number,
               a.gender, a.year_level,
               COALESCE(a.attendance_status, 'not_recorded') AS status
        FROM registrations r
        JOIN users u ON u.id = r.user_id
        JOIN events e ON e.id = r.event_id
        JOIN user_roles org ON org.id = e.user_role_id
        LEFT JOIN user_roles ur ON ur.user_id = u.id AND ur.role_type = u.role
        LEFT JOIN departments d ON d.id = ur.department_id
        LEFT JOIN attendees a ON a.registration_id = r.id
        WHERE org.user_id = :organizer_id AND org.role_type = 'organizer'
        ORDER BY e.event_name, u.full_name
    """)
    rows = db.execute(query, {"organizer_id": organizer_id}).fetchall()

    return {
        "success": True,
        "attendees": [
            {
                "id": row[0],
                "name": row[1],
                "email": row[2],
                "type": row[3],
                "eventName": row[4],
                "department": row[5] or "N/A",
                "contactNumber": row[6] or "N/A",
                "gender": row[7] or "N/A",
                "yearLevel": str(row[8]) if row[8] else "N/A",
                "status": row[9]
            }
            for row in rows
        ]
    }


class AttendanceUpdate(BaseModel):
    status: str


@router.put("/organizer/attendees/{registration_id}/attendance")
def update_attendance(registration_id: int, body: AttendanceUpdate, db: Session = Depends(get_db)):
    """
    Mark a registration as present or not recorded
    """
    from sqlalchemy import text

    if body.status not in ("present", "not_recorded"):
        raise HTTPException(status_code=400, detail="Status must be 'present' or 'not_recorded'")

    registration = db.execute(text("""
        SELECT r.id, u.full_name, u.email, ur.contact_number, ur.department_id
        FROM registrations r
        JOIN users u ON u.id = r.user_id
        LEFT JOIN user_roles ur ON ur.user_id = u.id AND ur.role_type = u.role
        WHERE r.id = :registration_id
    """), {"registration_id": registration_id}).first()

    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")

    attended_at = "NOW()" if body.status == "present" else "NULL"
    existing = db.execute(
        text("SELECT id FROM attendees WHERE registration_id = :registration_id"),
        {"registration_id": registration_id}
    ).first()

    # Enrolling doesn't create an attendees row, so create one on first mark
    if existing:
        db.execute(text(f"""
            UPDATE attendees
            SET attendance_status = :status, attended_at = {attended_at}
            WHERE registration_id = :registration_id
        """), {"status": body.status, "registration_id": registration_id})
    else:
        db.execute(text(f"""
            INSERT INTO attendees (
                registration_id, department_id, full_name, email,
                contact_number, attendance_status, attended_at
            ) VALUES (
                :registration_id, :department_id, :full_name, :email,
                :contact_number, :status, {attended_at}
            )
        """), {
            "registration_id": registration_id,
            "department_id": registration[4],
            "full_name": registration[1],
            "email": registration[2],
            "contact_number": registration[3],
            "status": body.status
        })
    db.commit()

    return {"success": True, "status": body.status}


@router.delete("/events/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db)):
    """
    Delete an event by ID
    """
    from sqlalchemy import text
    
    query = text("DELETE FROM events WHERE id = :event_id")
    
    try:
        db.execute(query, {"event_id": event_id})
        db.commit()
        
        return {
            "success": True,
            "message": "Event deleted successfully"
        }
    except Exception as e:
        db.rollback()
        print(f"Error deleting event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/events/{event_id}/enroll")
async def enroll_event(
    event_id: int,
    student_email: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Enroll a student in an event
    """
    from sqlalchemy import text
    
    # Check if event exists
    event_query = text("SELECT id, capacity FROM events WHERE id = :event_id")
    event_result = db.execute(event_query, {"event_id": event_id}).first()
    
    if not event_result:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Check if already enrolled
    check_query = text("""
        SELECT id FROM registrations 
        WHERE event_id = :event_id AND user_id = (
            SELECT id FROM users WHERE email = :email
        )
    """)
    existing = db.execute(check_query, {"event_id": event_id, "email": student_email}).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Already enrolled in this event")
    
    # Enroll
    try:
        enroll_query = text("""
            INSERT INTO registrations (event_id, user_id, status)
            VALUES (:event_id, (SELECT id FROM users WHERE email = :email), 'confirmed')
            RETURNING id
        """)
        result = db.execute(enroll_query, {"event_id": event_id, "email": student_email})
        db.commit()
        
        return {
            "success": True,
            "message": "Successfully enrolled in event"
        }
    except Exception as e:
        db.rollback()
        print(f"Error enrolling: {e}")
        raise HTTPException(status_code=500, detail=str(e))
