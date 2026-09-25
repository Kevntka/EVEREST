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
from services.recaptcha_service import verify_recaptcha, get_error_message

router = APIRouter()


@router.get("/test")
def test_api():
    """Test endpoint to verify API is working"""
    return {"message": "EVEREST API with PostgreSQL is okay"}


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
    gsuite: str = Form(...),  # G Suite email
    department: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Student registration
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == gsuite).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash password
    from auth.jwt_handler import hash_password
    hashed_password = hash_password(password)
    
    # Create user
    new_user = User(
        full_name=full_name,
        email=gsuite,
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
                "email": gsuite
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
    contact_number: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Create organizer (admin only)
    """
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
    
    # Send email with credentials
    from services.email_service import send_organizer_credentials
    email_sent = False
    try:
        await send_organizer_credentials(
            to_email=email,
            organizer_name=full_name,
            employment_id=employment_id,
            password=random_password  # Send the random password
        )
        email_sent = True
        email_message = "Email sent successfully with login credentials"
    except Exception as e:
        print(f"Failed to send email: {e}")
        email_message = f"Account created but email failed to send. Please provide credentials manually."
    
    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "message": f"Organizer created successfully. {email_message}",
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
                "note": "Random secure password generated. Email sent to organizer."
            },
            "email_sent": email_sent
        }
    )


@router.get("/organizers")
def get_organizers(db: Session = Depends(get_db)):
    """
    Get all organizers
    """
    # Get all users with organizer role
    organizers = db.query(User, UserRole, Department).outerjoin(
        UserRole, User.id == UserRole.user_id
    ).outerjoin(
        Department, UserRole.department_id == Department.id
    ).filter(User.role == 'organizer').all()
    
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
    
    return {
        "success": True,
        "count": len(result),
        "organizers": result
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
import os
import shutil
from pathlib import Path

# Create uploads directory
UPLOAD_DIR = Path("uploads/events")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/events")
async def create_event(
    event_name: str = Form(...),
    event_description: str = Form(...),
    event_date: str = Form(...),
    event_time: str = Form(...),
    venue: str = Form(...),
    capacity: int = Form(...),
    organizer_id: int = Form(...),
    cover_photo: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    """
    Create a new event (organizer only)
    """
    # Handle file upload
    cover_photo_url = None
    if cover_photo and cover_photo.filename:
        file_extension = os.path.splitext(cover_photo.filename)[1]
        unique_filename = f"event_{event_name.replace(' ', '_')}_{cover_photo.filename}"
        file_path = UPLOAD_DIR / unique_filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(cover_photo.file, buffer)
        
        cover_photo_url = f"/uploads/events/{unique_filename}"
    
    # For now, store in simplified format
    # TODO: Link to actual user_role_id from organizer
    from datetime import datetime
    event_datetime = datetime.strptime(f"{event_date} {event_time}", "%Y-%m-%d %H:%M")
    
    # Insert into database (raw SQL for now since schema is complex)
    from sqlalchemy import text
    
    query = text("""
        INSERT INTO events (
            user_role_id, event_name, event_description, 
            event_date, event_time, venue, capacity, status, cover_photo
        ) VALUES (
            1, :event_name, :event_description,
            :event_date, :event_time, :venue, :capacity, 'open', :cover_photo
        ) RETURNING id
    """)
    
    try:
        result = db.execute(query, {
            "event_name": event_name,
            "event_description": event_description,
            "event_date": event_date,
            "event_time": event_time,
            "venue": venue,
            "capacity": capacity,
            "cover_photo": cover_photo_url
        })
        db.commit()
        event_id = result.scalar()
        
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
            COALESCE(COUNT(r.id), 0) as enrolled_count
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
                "enrolled_count": row[9]
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
            COALESCE(COUNT(r.id), 0) as enrolled_count
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
                "enrolled_count": row[9]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
