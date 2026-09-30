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
from typing import Optional
import re
from services.recaptcha_service import verify_recaptcha, get_error_message
from auth.csrf_protection import generate_csrf_token, set_csrf_cookie, validate_csrf_form

router = APIRouter()


PASSWORD_SYMBOLS = "!@#$%&*_"


def require_password(password: str) -> None:
    """
    Passwords only need to be non-empty. Strength is shown to the user as a
    rating (frontend strength bar) but not required.
    """
    if not password or not password.strip():
        raise HTTPException(status_code=400, detail="Password is required.")


def generate_strong_password(length: int = 12) -> str:
    """Random 12-character password with upper, lower, number and symbol (for new organizers)."""
    import secrets
    import string
    pools = [string.ascii_uppercase, string.ascii_lowercase, string.digits, PASSWORD_SYMBOLS]
    chars = [secrets.choice(pool) for pool in pools]
    everything = "".join(pools)
    chars += [secrets.choice(everything) for _ in range(length - len(chars))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def current_user_id(request: Request) -> int:
    """
    The logged-in user's id, read from the HTTP-only access_token cookie set by /login.
    The frontend must send the request with withCredentials: true.
    """
    from auth.jwt_handler import decode_access_token

    cookie = request.cookies.get("access_token")
    if not cookie:
        raise HTTPException(status_code=401, detail="Your session has expired. Please log in again.")
    payload = decode_access_token(cookie.removeprefix("Bearer "))
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Your session has expired. Please log in again.")
    return user_id


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
            # Registered but not verified yet? Send them to the Verify Email page.
            from sqlalchemy import text
            pending = db.execute(text("SELECT password_hash FROM pending_registrations WHERE email = :e"),
                                 {"e": email}).first()
            if pending and verify_bcrypt_password(password, pending.password_hash):
                return _unverified_response(email, "Please verify your email before logging in.")
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



# --- Email verification (6-digit code) for students and participants ---
# Registrations wait in pending_registrations until the code is verified; only then
# is the account created in users/user_roles. Unverified sign-ups never appear in
# admin lists, counts or login.
VERIFICATION_CODE_TTL_MINUTES = 15
VERIFICATION_MAX_ATTEMPTS = 5
VERIFICATION_RESEND_SECONDS = 60
PENDING_REGISTRATION_TTL_HOURS = 24
SELF_REGISTERED_ROLES = ("student", "participant")


def _hash_code(code: str) -> str:
    import hashlib
    return hashlib.sha256(code.encode()).hexdigest()


def _new_code() -> str:
    import secrets
    return f"{secrets.randbelow(1_000_000):06d}"


def _unverified_response(email: str, message: str, status_code: int = 403) -> JSONResponse:
    """Tells the frontend to send the user to the Verify Email page."""
    return JSONResponse(
        status_code=status_code,
        content={"detail": message, "verification_required": True, "email": email}
    )


async def _start_pending_registration(
    db: Session, *, email: str, full_name: str, role: str, password: str,
    department: Optional[str] = None, contact_number: Optional[str] = None
) -> JSONResponse:
    """
    Save (or replace) a pending registration and email its 6-digit code.
    Nothing is written to users until /verify-email succeeds.
    """
    from sqlalchemy import text
    from auth.jwt_handler import hash_password
    from services.email_service import send_verification_code_email

    email = email.strip().lower()
    if not re.fullmatch(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", email):
        raise HTTPException(status_code=400, detail="Please provide a valid email address")
    require_password(password)

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Drop abandoned sign-ups
    db.execute(text(f"""
        DELETE FROM pending_registrations
        WHERE created_at < NOW() - INTERVAL '{PENDING_REGISTRATION_TTL_HOURS} hours'
    """))

    recent = db.execute(text("""
        SELECT EXTRACT(EPOCH FROM (NOW() - last_sent_at)) FROM pending_registrations WHERE email = :e
    """), {"e": email}).scalar()
    if recent is not None and recent < VERIFICATION_RESEND_SECONDS:
        db.commit()
        return _unverified_response(
            email,
            "We already sent a verification code to this email. Enter it on the next page, or request a new one.",
            status_code=409
        )

    code = _new_code()
    db.execute(text("DELETE FROM pending_registrations WHERE email = :e"), {"e": email})
    db.execute(text(f"""
        INSERT INTO pending_registrations (
            email, full_name, role, password_hash, department, contact_number,
            code_hash, expires_at, attempts, last_sent_at
        ) VALUES (
            :email, :full_name, :role, :password_hash, :department, :contact_number,
            :code_hash, NOW() + INTERVAL '{VERIFICATION_CODE_TTL_MINUTES} minutes', 0, NOW()
        )
    """), {
        "email": email,
        "full_name": full_name.strip(),
        "role": role,
        "password_hash": hash_password(password),
        "department": (department or "").strip() or None,
        "contact_number": (contact_number or "").strip() or None,
        "code_hash": _hash_code(code),
    })
    db.commit()

    email_sent = await send_verification_code_email(email, full_name.strip(), code)
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Enter the 6-digit code we sent to your email to finish creating your account",
            "verification_required": True,
            "email_sent": email_sent,
            "user": {"full_name": full_name.strip(), "email": email}
        }
    )


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
    Student registration (account is created only after email verification)
    """
    return await _start_pending_registration(
        db, email=email, full_name=full_name, role="student", password=password, department=department
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
    Participant registration (account is created only after email verification)
    """
    return await _start_pending_registration(
        db, email=email, full_name=full_name, role="participant", password=password,
        contact_number=contact_number
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
        random_password = generate_strong_password(12)
        
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
        
        # Sending is controlled by EMAIL_ENABLED in backend/.env
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
    from sqlalchemy import text

    user = db.query(User).filter(User.id == organizer_id, User.role == 'organizer').first()

    if not user:
        raise HTTPException(status_code=404, detail="Organizer not found")

    # events.user_role_id has no ON DELETE CASCADE, so remove the organizer's events first
    # (their registrations and attendance cascade from events)
    db.execute(text("""
        DELETE FROM events
        WHERE user_role_id IN (SELECT id FROM user_roles WHERE user_id = :user_id)
    """), {"user_id": organizer_id})
    db.query(Registration).filter(Registration.user_id == organizer_id).delete(synchronize_session=False)

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
            "year_level": (user_role.year_level if user_role else None) or "N/A",
            "gender": (user_role.gender if user_role else None) or "N/A",
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

    # registrations.user_id has no ON DELETE CASCADE; attendees cascade from registrations
    db.query(Registration).filter(Registration.user_id == student_id).delete(synchronize_session=False)
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
            "gender": (user_role.gender if user_role else None) or "N/A",
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
    # Users are stored with lowercased emails (see login/register)
    email = email.strip().lower()

    # Check if user exists
    user = db.query(User).filter(User.email == email).first()

    if not user:
        # Product decision: tell the user the email isn't registered (this does
        # reveal whether an email has an account)
        raise HTTPException(status_code=404, detail="No account is registered with this email.")
    
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
        
        if not email_sent:
            raise HTTPException(
                status_code=503,
                detail="We couldn't send the reset email right now. Please try again later."
            )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "A password reset link has been sent to your email",
                "email_sent": True
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error in forgot password: {e}")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")


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
    # expires_at comes back timezone-aware (TIMESTAMPTZ); compare with an aware "now"
    now = datetime.now(expires_at.tzinfo) if expires_at.tzinfo else datetime.now()
    if now > expires_at:
        raise HTTPException(status_code=400, detail="Reset token has expired")
    
    # Hash new password
    from auth.jwt_handler import hash_password
    require_password(new_password)
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
               COALESCE(a.gender, ur.gender), COALESCE(a.year_level::text, ur.year_level),
               COALESCE(a.attendance_status, 'not_recorded') AS status,
               a.address
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
                "status": row[9],
                "address": row[10] or "N/A"
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
        # registrations and attendees cascade from events
        result = db.execute(query, {"event_id": event_id})
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Event not found")
        db.commit()
        
        return {
            "success": True,
            "message": "Event deleted successfully"
        }
    except HTTPException:
        raise
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
    event_query = text("""
        SELECT e.id, e.capacity, e.status, COUNT(r.id) AS enrolled
        FROM events e
        LEFT JOIN registrations r ON r.event_id = e.id
        WHERE e.id = :event_id
        GROUP BY e.id
    """)
    event_result = db.execute(event_query, {"event_id": event_id}).first()

    if not event_result:
        raise HTTPException(status_code=404, detail="Event not found")
    if event_result[2] != 'open':
        raise HTTPException(status_code=400, detail="This event is not open for enrollment")
    if event_result[1] is not None and event_result[3] >= event_result[1]:
        raise HTTPException(status_code=400, detail="This event is already full")

    user = db.query(User).filter(User.email == student_email.strip().lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="Account not found. Please log in again.")

    # Check if already enrolled
    existing = db.query(Registration).filter(
        Registration.event_id == event_id,
        Registration.user_id == user.id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Already enrolled in this event")

    # Enroll
    try:
        enroll_query = text("""
            INSERT INTO registrations (event_id, user_id, status)
            VALUES (:event_id, :user_id, 'confirmed')
            RETURNING id
        """)
        result = db.execute(enroll_query, {"event_id": event_id, "user_id": user.id})
        db.commit()
        
        return {
            "success": True,
            "message": "Successfully enrolled in event"
        }
    except Exception as e:
        db.rollback()
        print(f"Error enrolling: {e}")
        raise HTTPException(status_code=500, detail=str(e))



def get_or_create_department(db: Session, name: str) -> Department:
    dept = db.query(Department).filter(Department.department_name == name).first()
    if not dept:
        dept = Department(department_name=name)
        db.add(dept)
        db.flush()
    return dept


@router.put("/organizers/{organizer_id}")
def update_organizer(
    organizer_id: int,
    employment_id: str = Form(...),
    full_name: str = Form(...),
    department: str = Form(...),
    email: str = Form(...),
    contact_number: str = Form(None),
    db: Session = Depends(get_db)
):
    """
    Update an organizer's details (admin). The password is not changed here.
    """
    user = db.query(User).filter(User.id == organizer_id, User.role == 'organizer').first()
    if not user:
        raise HTTPException(status_code=404, detail="Organizer not found")

    email = email.strip().lower()
    if not re.fullmatch(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", email):
        raise HTTPException(status_code=400, detail="Please provide a valid email address")
    if db.query(User).filter(User.email == email, User.id != organizer_id).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    employment_id = employment_id.strip()
    duplicate_id = db.query(UserRole).filter(
        UserRole.employment_id == employment_id, UserRole.user_id != organizer_id
    ).first()
    if duplicate_id:
        raise HTTPException(status_code=400, detail="Employment ID already exists")

    user_role = db.query(UserRole).filter(
        UserRole.user_id == organizer_id, UserRole.role_type == 'organizer'
    ).first()
    if not user_role:
        user_role = UserRole(user_id=organizer_id, role_type='organizer')
        db.add(user_role)

    user.full_name = full_name.strip()
    user.email = email
    user_role.employment_id = employment_id
    user_role.department_id = get_or_create_department(db, department.strip()).id
    user_role.contact_number = (contact_number or "").strip() or None
    db.commit()

    return {"success": True, "message": "Organizer updated successfully"}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/organizer/change-password")
@router.post("/student/change-password")
@router.post("/change-password")
def change_password(body: ChangePasswordRequest, request: Request, db: Session = Depends(get_db)):
    """
    Change the logged-in user's password (identified by the login cookie)
    """
    from auth.jwt_handler import hash_password

    user = db.query(User).filter(User.id == current_user_id(request)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Your session has expired. Please log in again.")
    if not verify_bcrypt_password(body.current_password, user.password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    require_password(body.new_password)

    user.password = hash_password(body.new_password)
    db.commit()
    return {"success": True, "message": "Password changed successfully"}


def _profile_response(user: User, user_role, dept) -> dict:
    return {
        "fullName": user.full_name,
        "srCode": (user_role.student_number if user_role else None) or "",
        "collegeDepartment": dept.department_name if dept else "",
        "program": (user_role.program if user_role else None) or "",
        "yearLevel": (user_role.year_level if user_role else None) or "",
        "gender": (user_role.gender if user_role else None) or "",
        "contactNumber": (user_role.contact_number if user_role else None) or "",
        "email": user.email,
        "role": user.role.capitalize(),
    }


def _role_row(db: Session, user: User):
    user_role = db.query(UserRole).filter(
        UserRole.user_id == user.id, UserRole.role_type == user.role
    ).first()
    dept = None
    if user_role and user_role.department_id:
        dept = db.query(Department).filter(Department.id == user_role.department_id).first()
    return user_role, dept


@router.get("/student/profile")
def get_student_profile(request: Request, db: Session = Depends(get_db)):
    """
    The logged-in student's (or participant's) profile
    """
    user = db.query(User).filter(User.id == current_user_id(request)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Your session has expired. Please log in again.")
    user_role, dept = _role_row(db, user)
    return {"success": True, "profile": _profile_response(user, user_role, dept)}


class ProfileUpdate(BaseModel):
    fullName: str
    srCode: Optional[str] = None
    collegeDepartment: Optional[str] = None
    program: Optional[str] = None
    yearLevel: Optional[str] = None
    gender: Optional[str] = None
    contactNumber: Optional[str] = None


@router.put("/student/profile")
def update_student_profile(body: ProfileUpdate, request: Request, db: Session = Depends(get_db)):
    """
    Update the logged-in student's (or participant's) profile.
    Email and role can't be changed here.
    """
    user = db.query(User).filter(User.id == current_user_id(request)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Your session has expired. Please log in again.")
    if not body.fullName.strip():
        raise HTTPException(status_code=400, detail="Full name is required")

    user_role, _ = _role_row(db, user)
    if not user_role:
        user_role = UserRole(user_id=user.id, role_type=user.role)
        db.add(user_role)

    def clean(value: Optional[str]) -> Optional[str]:
        """Profile text is stored in ALL CAPS."""
        return (value or "").strip().upper() or None

    def year_level(value: Optional[str]) -> Optional[str]:
        """'1st', '2', '3RD YEAR' -> '1ST YEAR' .. '4TH YEAR' (the profile dropdown values)."""
        match = re.search(r"[1-4]", value or "")
        return ["1ST YEAR", "2ND YEAR", "3RD YEAR", "4TH YEAR"][int(match.group()) - 1] if match else None

    def phone(value: Optional[str]) -> Optional[str]:
        """Digits only, formatted 0912-345-6789 when it's an 11-digit number."""
        digits = re.sub(r"\D", "", value or "")[:11]
        if len(digits) == 11:
            return f"{digits[:4]}-{digits[4:7]}-{digits[7:]}"
        return digits or None

    user.full_name = clean(body.fullName)
    user_role.student_number = clean(body.srCode)
    user_role.program = clean(body.program)
    user_role.year_level = year_level(body.yearLevel)
    user_role.gender = clean(body.gender)
    user_role.contact_number = phone(body.contactNumber)
    if clean(body.collegeDepartment):
        user_role.department_id = get_or_create_department(db, clean(body.collegeDepartment)).id
    db.commit()

    user_role, dept = _role_row(db, user)
    return {
        "success": True,
        "message": "Profile updated successfully",
        "profile": _profile_response(user, user_role, dept)
    }


@router.put("/events/{event_id}")
async def update_event(
    event_id: int,
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
    Update an event (only by the organizer who created it). The cover photo is
    replaced only when a new one is uploaded.
    """
    from sqlalchemy import text
    from datetime import datetime

    owner = db.execute(text("""
        SELECT e.id FROM events e
        JOIN user_roles ur ON ur.id = e.user_role_id
        WHERE e.id = :event_id AND ur.user_id = :organizer_id
    """), {"event_id": event_id, "organizer_id": organizer_id}).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Event not found")

    try:
        datetime.strptime(f"{event_date} {event_time[:5]}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date or time")
    if capacity < 1:
        raise HTTPException(status_code=400, detail="Capacity must be at least 1")

    enrolled = db.execute(
        text("SELECT COUNT(*) FROM registrations WHERE event_id = :id"), {"id": event_id}
    ).scalar()
    if capacity < enrolled:
        raise HTTPException(
            status_code=400,
            detail=f"Capacity can't be lower than the {enrolled} people already enrolled"
        )

    params = {
        "id": event_id,
        "event_name": event_name,
        "event_description": event_description,
        "event_date": event_date,
        "event_time": event_time,
        "venue": venue,
        "capacity": capacity,
        "department": department or None,
        "about_event": about_event or None,
    }
    cover_sql = ""
    if cover_photo and cover_photo.filename:
        if not (cover_photo.content_type or "").startswith("image/"):
            raise HTTPException(status_code=400, detail="Cover photo must be an image")
        data = await cover_photo.read()
        if len(data) > MAX_COVER_PHOTO_BYTES:
            raise HTTPException(status_code=400, detail="Cover photo must be 5 MB or smaller")
        params.update(
            cover_photo_data=data,
            cover_photo_type=cover_photo.content_type,
            cover_photo=f"/api/events/{event_id}/cover"
        )
        cover_sql = (", cover_photo_data = :cover_photo_data, "
                     "cover_photo_type = :cover_photo_type, cover_photo = :cover_photo")

    db.execute(text(f"""
        UPDATE events SET
            event_name = :event_name, event_description = :event_description,
            event_date = :event_date, event_time = :event_time, venue = :venue,
            capacity = :capacity, department = :department, about_event = :about_event,
            updated_at = NOW(){cover_sql}
        WHERE id = :id
    """), params)
    db.commit()

    return {"success": True, "message": "Event updated successfully"}



@router.post("/verify-email")
def verify_email(email: str = Form(...), code: str = Form(...), db: Session = Depends(get_db)):
    """
    Check the 6-digit code; if correct, create the student/participant account
    from the pending registration.
    """
    import hmac
    from sqlalchemy import text

    email = email.strip().lower()
    code = code.strip()

    pending = db.execute(text("""
        SELECT id, full_name, role, password_hash, department, contact_number,
               code_hash, attempts, expires_at > NOW() AS still_valid
        FROM pending_registrations WHERE email = :e
    """), {"e": email}).first()

    if not pending:
        if db.query(User).filter(User.email == email).first():
            return {"success": True, "message": "Your email is already verified. You can log in."}
        raise HTTPException(status_code=404, detail="No pending registration for this email. Please register again.")
    if not pending.still_valid:
        raise HTTPException(status_code=400, detail="This code has expired. Please request a new one.")
    if pending.attempts >= VERIFICATION_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many incorrect attempts. Please request a new code.")

    if not (code.isdigit() and len(code) == 6 and hmac.compare_digest(_hash_code(code), pending.code_hash)):
        db.execute(text("UPDATE pending_registrations SET attempts = attempts + 1 WHERE id = :id"), {"id": pending.id})
        db.commit()
        left = VERIFICATION_MAX_ATTEMPTS - pending.attempts - 1
        if left <= 0:
            raise HTTPException(status_code=429, detail="Too many incorrect attempts. Please request a new code.")
        raise HTTPException(status_code=400, detail=f"Incorrect code. {left} attempt{'s' if left != 1 else ''} left.")

    if db.query(User).filter(User.email == email).first():
        db.execute(text("DELETE FROM pending_registrations WHERE id = :id"), {"id": pending.id})
        db.commit()
        raise HTTPException(status_code=400, detail="Email already registered")

    # Code is correct: create the real account now
    new_user = User(
        full_name=pending.full_name,
        email=email,
        password=pending.password_hash,
        role=pending.role,
        is_active=True
    )
    db.add(new_user)
    db.flush()

    user_role = UserRole(user_id=new_user.id, role_type=pending.role, contact_number=pending.contact_number)
    if pending.department:
        user_role.department_id = get_or_create_department(db, pending.department).id
    db.add(user_role)
    db.execute(text("DELETE FROM pending_registrations WHERE id = :id"), {"id": pending.id})
    db.commit()

    return {"success": True, "message": "Your email has been verified and your account is created. You can now log in."}


@router.post("/resend-verification")
async def resend_verification(email: str = Form(...), db: Session = Depends(get_db)):
    """
    Send a new 6-digit code for a pending registration (at most once every VERIFICATION_RESEND_SECONDS)
    """
    from sqlalchemy import text
    from services.email_service import send_verification_code_email

    email = email.strip().lower()
    pending = db.execute(text("""
        SELECT id, full_name, EXTRACT(EPOCH FROM (NOW() - last_sent_at)) AS seconds_since
        FROM pending_registrations WHERE email = :e
    """), {"e": email}).first()

    if not pending:
        if db.query(User).filter(User.email == email).first():
            raise HTTPException(status_code=400, detail="This email is already verified. You can log in.")
        raise HTTPException(status_code=404, detail="No pending registration for this email. Please register again.")

    if pending.seconds_since is not None and pending.seconds_since < VERIFICATION_RESEND_SECONDS:
        wait = int(VERIFICATION_RESEND_SECONDS - pending.seconds_since) + 1
        return JSONResponse(
            status_code=429,
            content={"detail": f"Please wait {wait} seconds before requesting a new code.", "retry_after": wait}
        )

    code = _new_code()
    db.execute(text(f"""
        UPDATE pending_registrations
        SET code_hash = :h, attempts = 0, last_sent_at = NOW(),
            expires_at = NOW() + INTERVAL '{VERIFICATION_CODE_TTL_MINUTES} minutes'
        WHERE id = :id
    """), {"h": _hash_code(code), "id": pending.id})
    db.commit()

    if not await send_verification_code_email(email, pending.full_name, code):
        raise HTTPException(status_code=503, detail="We couldn't send the code right now. Please try again later.")
    return {"success": True, "message": f"A new code was sent to {email}.", "retry_after": VERIFICATION_RESEND_SECONDS}


@router.get("/student/my-events")
def get_my_events(request: Request, db: Session = Depends(get_db)):
    """
    Events the logged-in student/participant enrolled in, with their attendance
    ('present' or 'not_recorded'). Identified by the login cookie.
    """
    from sqlalchemy import text

    user_id = current_user_id(request)
    rows = db.execute(text("""
        SELECT e.id, e.event_name, e.event_date, e.event_time, e.venue, e.status,
               COALESCE(a.attendance_status, 'not_recorded') AS attendance,
               r.registration_date
        FROM registrations r
        JOIN events e ON e.id = r.event_id
        LEFT JOIN attendees a ON a.registration_id = r.id
        WHERE r.user_id = :u
        ORDER BY e.event_date DESC NULLS LAST, e.event_time DESC NULLS LAST
    """), {"u": user_id}).fetchall()

    return {
        "success": True,
        "events": [
            {
                "id": row.id,
                "event_name": row.event_name,
                "event_date": str(row.event_date) if row.event_date else None,
                "event_time": str(row.event_time) if row.event_time else None,
                "venue": row.venue,
                "status": row.status,
                "attendance": row.attendance,
            }
            for row in rows
        ]
    }
