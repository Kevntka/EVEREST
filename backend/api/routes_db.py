"""
API Routes with PostgreSQL Database Integration
Matching the actual database schema
"""

from fastapi import APIRouter, Form, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database.config import get_db
from models.user import User, UserRole, Department, Attendee, Event, Registration
from auth.jwt_handler import create_access_token, verify_password as verify_bcrypt_password
from datetime import date, timedelta
from pydantic import BaseModel
from typing import Literal, Optional
import re
from services.recaptcha_service import verify_recaptcha, get_error_message
from security import validation as validate
from security.access_control import current_user, require_roles, password_fingerprint
from security.csrf import csrf_token_response
from security.rate_limit import rate_limit, login_lockout
from security.settings import FRONTEND_URL, HTTPS_ONLY

router = APIRouter()

# Who may call what (checked on the server from the login cookie, see security/access_control.py)
admin_only = require_roles("admin")
organizer_only = require_roles("organizer")
attendee_only = require_roles("student", "participant")

PASSWORD_SYMBOLS = "!@#$%&*_"


def generate_strong_password(length: int = 8) -> str:
    """
    Random 8-character password for new organizers: always at least one uppercase letter
    (A-Z), one lowercase letter, one number and one symbol; the rest are random from all four.
    """
    import secrets
    import string
    pools = [string.ascii_uppercase, string.ascii_lowercase, string.digits, PASSWORD_SYMBOLS]
    chars = [secrets.choice(pool) for pool in pools]
    everything = "".join(pools)
    chars += [secrets.choice(everything) for _ in range(length - len(chars))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


@router.get("/test")
def test_api():
    """Test endpoint to verify API is working"""
    return {"message": "EVEREST API with PostgreSQL is okay"}


@router.get("/csrf-token")
def get_csrf_token(request: Request):
    """
    CSRF token for the X-CSRF-Token header (fetched by the Angular csrf interceptor
    before its first POST/PUT/DELETE). Also sets the matching csrf_token cookie.
    """
    return csrf_token_response(request)


@router.post("/login", dependencies=[Depends(rate_limit("login", 20, 60))])
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
        email = validate.email(email)
        password = validate.password(password)
        # 5 wrong passwords in 15 minutes lock this email for 15 minutes
        login_lockout.check(email)

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
            # Registered but not verified yet? Send them to the Verify Email page.
            from sqlalchemy import text
            pending = db.execute(text("SELECT password_hash FROM pending_registrations WHERE email = :e"),
                                 {"e": email}).first()
            if pending and verify_bcrypt_password(password, pending.password_hash):
                return _unverified_response(email, "Please verify your email before logging in.")
            if not pending:
                raise HTTPException(
                    status_code=404,
                    detail="This account is not registered yet. Please create an account first."
                )
            login_lockout.failed(email)
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Verify password against the bcrypt hash in the database
        if not user.password or not verify_bcrypt_password(password, user.password):
            login_lockout.failed(email)
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if user.is_active is False:
            raise HTTPException(status_code=403, detail="This account has been deactivated.")
        login_lockout.succeeded(email)

        # Create JWT token. "pwd" is a fingerprint of the password hash: changing the
        # password makes every older token invalid (security/access_control.py).
        token_data = {
            "sub": email,  # Subject (user identifier)
            "user_id": user.id,
            "email": email,
            "name": user.full_name,
            "role": user.role,
            "pwd": password_fingerprint(user.password)
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
            secure=HTTPS_ONLY,  # HTTPS_ONLY=true in .env: only sent over HTTPS
            samesite="lax",  # not sent on cross-site POSTs (CSRF defense, with security/csrf.py)
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
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")


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

    # Clear the cookie (same attributes as when it was set)
    response.delete_cookie(key="access_token", path="/", httponly=True, secure=HTTPS_ONLY, samesite="lax")

    return response



# --- Email verification (link) for students and participants ---
# Registrations wait in pending_registrations until the emailed "Verify Account" link
# is opened; only then is the account created in users/user_roles. Unverified sign-ups
# never appear in admin lists, counts or login. pending_registrations.code_hash holds
# the SHA-256 of the link's token.
VERIFICATION_LINK_TTL_HOURS = 24
VERIFICATION_RESEND_SECONDS = 60
PENDING_REGISTRATION_TTL_HOURS = 24
SELF_REGISTERED_ROLES = ("student", "participant")


def _hash_code(code: str) -> str:
    import hashlib
    return hashlib.sha256(code.encode()).hexdigest()


def _new_token() -> str:
    import secrets
    return secrets.token_urlsafe(32)


def _verification_link(token: str) -> str:
    return f"{FRONTEND_URL}/verify-email?token={token}"


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
    Save (or replace) a pending registration and email its verification link.
    Nothing is written to users until /verify-email succeeds.
    """
    from sqlalchemy import text
    from auth.jwt_handler import hash_password
    from services.email_service import send_verification_link_email

    email = validate.email(email)
    validate.password(password)
    full_name = validate.text(full_name, "Full name", 150)
    department = validate.text(department, "Department", 150, required=role == "student")
    contact_number = validate.contact_number(contact_number, required=role == "participant")

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
            "We already sent a verification link to this email. Open it to verify your account, or request a new one.",
            status_code=409
        )

    token = _new_token()
    db.execute(text("DELETE FROM pending_registrations WHERE email = :e"), {"e": email})
    db.execute(text(f"""
        INSERT INTO pending_registrations (
            email, full_name, role, password_hash, department, contact_number,
            code_hash, expires_at, attempts, last_sent_at
        ) VALUES (
            :email, :full_name, :role, :password_hash, :department, :contact_number,
            :code_hash, NOW() + INTERVAL '{VERIFICATION_LINK_TTL_HOURS} hours', 0, NOW()
        )
    """), {
        "email": email,
        "full_name": full_name,
        "role": role,
        "password_hash": hash_password(password),
        "department": department,
        "contact_number": contact_number,
        "code_hash": _hash_code(token),
    })
    db.commit()

    email_sent = await send_verification_link_email(email, full_name, _verification_link(token))
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Open the link we sent to your email to finish creating your account",
            "verification_required": True,
            "email_sent": email_sent,
            "user": {"full_name": full_name, "email": email}
        }
    )


# Sign-ups per IP address: 20 every 10 minutes
register_limit = rate_limit("register", 20, 600)


@router.post("/register/student", dependencies=[Depends(register_limit)])
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


@router.post("/register/participant", dependencies=[Depends(register_limit)])
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


@router.post("/organizers", dependencies=[Depends(admin_only)])
async def create_organizer(
    background_tasks: BackgroundTasks,
    employment_id: str = Form(...),
    full_name: str = Form(...),
    department: str = Form(...),
    email: str = Form(...),
    contact_number: str = Form(None),  # Optional field
    db: Session = Depends(get_db)
):
    """
    Create organizer (admin only). The credentials email is sent in the background
    after the response (SMTP takes ~10 s), so the admin doesn't wait for it.
    """
    try:
        email = validate.email(email)
        employment_id = validate.text(employment_id, "Employment ID", 50)
        full_name = validate.text(full_name, "Full name", 150)
        department = validate.text(department, "Department", 150)
        contact_number = validate.contact_number(contact_number)
        print(f"\n🔧 Creating organizer: {full_name} ({email})")

        # Check if email already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        if db.query(UserRole).filter(UserRole.employment_id == employment_id).first():
            raise HTTPException(status_code=400, detail="Employment ID already exists")

        # Generate random password
        random_password = generate_strong_password(8)
        
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
        
        organizer = {
            "id": new_user.id,
            "employment_id": employment_id,
            "full_name": full_name,
            "department": department,
            "email": email,
            "contact_number": contact_number
        }

        from services.email_service import EMAIL_ENABLED, send_organizer_credentials
        if not EMAIL_ENABLED:
            # No email will go out: show the admin the password to share themselves
            return JSONResponse(
                status_code=201,
                content={
                    "success": True,
                    "message": "Organizer created but email is disabled (EMAIL_ENABLED=false)",
                    "organizer": organizer,
                    "credentials": {"email": email, "password": random_password},
                    "email_sent": False
                }
            )

        # Sent after this response is returned. If delivery fails it is only logged
        # (the organizer can still use Forgot Password on the login page).
        background_tasks.add_task(
            send_organizer_credentials,
            to_email=email,
            organizer_name=full_name,
            employment_id=employment_id,
            password=random_password
        )
        print(f"📧 Credentials email to {email} queued (sent in the background)")

        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "message": "Organizer created; credentials are being emailed",
                "organizer": organizer,
                "credentials": {"email": email},
                "email_sent": True
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
        
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")


@router.get("/organizers", dependencies=[Depends(admin_only)])
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
            "organizers": []
        }


@router.delete("/organizers/{organizer_id}", dependencies=[Depends(admin_only)])
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


@router.get("/students", dependencies=[Depends(admin_only)])
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
            "sr_code": (user_role.student_number if user_role else None) or "N/A",
            "department": dept.department_name if dept else "N/A",
            "program": (user_role.program if user_role else None) or "N/A",
            "year_level": (user_role.year_level if user_role else None) or "N/A",
            "gender": (user_role.gender if user_role else None) or "N/A",
            "contact_number": user_role.contact_number if user_role and user_role.contact_number else "N/A",
            "avatar_url": _avatar_url(user.id, user_role)
        })
    
    return {
        "success": True,
        "count": len(result),
        "students": result
    }


@router.delete("/students/{student_id}", dependencies=[Depends(admin_only)])
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


@router.get("/participants", dependencies=[Depends(admin_only)])
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
            "address": (user_role.address if user_role else None) or "N/A",
            "birthday": user_role.birthday.isoformat() if user_role and user_role.birthday else "N/A",
            "age": (_age(user_role.birthday) if user_role else "") or "N/A",
            "gender": (user_role.gender if user_role else None) or "N/A",
            "contact_number": user_role.contact_number if user_role and user_role.contact_number else "N/A",
            "avatar_url": _avatar_url(user.id, user_role)
        })
    
    return {
        "success": True,
        "count": len(result),
        "participants": result
    }


@router.delete("/participants/{participant_id}", dependencies=[Depends(admin_only)])
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


# Each one sends an email: 5 per IP every 15 minutes
reset_email_limit = rate_limit("reset-email", 5, 900)


@router.post("/forgot-password", dependencies=[Depends(reset_email_limit)])
async def forgot_password(email: str = Form(...), db: Session = Depends(get_db)):
    """
    Request password reset - sends email with reset link
    """
    # Users are stored with lowercased emails (see login/register)
    email = validate.email(email)

    # Check if user exists
    user = db.query(User).filter(User.email == email).first()

    if not user:
        # Product decision: tell the user the email isn't registered (this does
        # reveal whether an email has an account)
        raise HTTPException(status_code=404, detail="No account is registered with this email.")
    
    return await _send_reset_link(db, user)


async def _send_reset_link(db: Session, user: User) -> JSONResponse:
    """
    Email the user a one-hour link to the Set New Password page (/reset-password).
    Used by Forgot Password and by Change Password for logged-in users.
    """
    import secrets
    from datetime import datetime, timedelta
    from sqlalchemy import text

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=1)

    try:
        # Only the SHA-256 of the token is stored: someone who can read the database
        # still can't use a reset link (same as the email verification tokens)
        db.execute(text("""
            INSERT INTO password_reset_tokens (user_id, token, expires_at)
            VALUES (:user_id, :token, :expires_at)
        """), {"user_id": user.id, "token": _hash_code(token), "expires_at": expires_at})
        db.commit()

        reset_link = f"{FRONTEND_URL}/reset-password?token={token}"

        from services.email_service import send_password_reset_email
        email_sent = await send_password_reset_email(
            to_email=user.email,
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
                "email": user.email,
                "email_sent": True
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error sending password reset link: {e}")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")


@router.post("/reset-password", dependencies=[Depends(rate_limit("reset-password", 10, 900))])
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
    from auth.jwt_handler import hash_password

    token_hash = _hash_code(validate.token(token))
    validate.password(new_password)

    result = db.execute(text("""
        SELECT t.user_id, t.expires_at, t.used, u.email
        FROM password_reset_tokens t JOIN users u ON u.id = t.user_id
        WHERE t.token = :token
    """), {"token": token_hash}).first()

    if not result:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    user_id, expires_at, used, email = result
    
    # Check if token is already used
    if used:
        raise HTTPException(status_code=400, detail="Reset token has already been used")
    
    # Check if token is expired
    # expires_at comes back timezone-aware (TIMESTAMPTZ); compare with an aware "now"
    now = datetime.now(expires_at.tzinfo) if expires_at.tzinfo else datetime.now()
    if now > expires_at:
        raise HTTPException(status_code=400, detail="Reset token has expired")

    try:
        # The new password changes the hash fingerprint in login tokens, so every
        # session logged in with the old password is signed out
        db.execute(text("""
            UPDATE users SET password = :password, updated_at = CURRENT_TIMESTAMP WHERE id = :user_id
        """), {"password": hash_password(new_password), "user_id": user_id})
        # This link and any other unused links for the account stop working
        db.execute(text("""
            UPDATE password_reset_tokens SET used = TRUE WHERE user_id = :user_id AND used IS NOT TRUE
        """), {"user_id": user_id})
        db.commit()
        login_lockout.succeeded(email)
        
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



def _close_finished_events(db: Session) -> None:
    """
    Close open events whose end time has passed (start time if there is no end
    time, end of day if there is no time at all). Runs before events are read or
    enrolled in, so the stored status is always current. "Now" is the server's
    local time, matching the local date/time the organizer entered.
    """
    from sqlalchemy import text
    from datetime import datetime

    result = db.execute(text("""
        UPDATE events SET status = 'closed', updated_at = NOW()
        WHERE status = 'open' AND event_date IS NOT NULL
          AND event_date + COALESCE(event_end_time, event_time, TIME '23:59:59') < :now
    """), {"now": datetime.now()})
    if result.rowcount:
        db.commit()


def _validate_event_times(event_date: str, event_time: str, event_end_time: Optional[str]):
    """Check the date/start time, and that the end time (if given) is after the start."""
    from datetime import datetime
    for value in (event_time, event_end_time):
        if value and not re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", value):
            raise HTTPException(status_code=400, detail="Invalid date or time")
    try:
        start = datetime.strptime(f"{event_date} {event_time[:5]}", "%Y-%m-%d %H:%M")
        end = datetime.strptime(f"{event_date} {event_end_time[:5]}", "%Y-%m-%d %H:%M") if event_end_time else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date or time")
    if end is not None and end <= start:
        raise HTTPException(status_code=400, detail="End time must be after the start time")
    return end or start


def _validate_registration_period(registration_start: Optional[str], registration_end: Optional[str], event_date: str):
    """
    Registration start/end dates (YYYY-MM-DD, each optional): start <= end <= event date.
    Returns (start, end) as dates or None.
    """
    def parse(value: Optional[str], label: str):
        if not (value or "").strip():
            return None
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid registration {label} date")

    start, end = parse(registration_start, "start"), parse(registration_end, "end")
    event_day = date.fromisoformat(event_date)
    if start and start > event_day:
        raise HTTPException(status_code=400, detail="Registration must start on or before the event date")
    if end and end > event_day:
        raise HTTPException(status_code=400, detail="Registration must end on or before the event date")
    if start and end and end < start:
        raise HTTPException(status_code=400, detail="Registration end can't be before the registration start")
    return start, end


def _time_str(value) -> Optional[str]:
    return str(value) if value else None


def _validate_event_text(event_name, event_description, venue, capacity, department, about_event) -> dict:
    """Event form text: required fields, column-sized limits, capacity range."""
    return {
        "event_name": validate.text(event_name, "Event name", 200),
        "event_description": validate.text(event_description, "Description", 5000, multiline=True),
        "venue": validate.text(venue, "Venue", 200),
        "capacity": validate.whole_number(capacity, "Capacity", 1, 100000),
        "department": validate.text(department, "Department", 150, required=False),
        "about_event": validate.text(about_event, "About the event", 10000, required=False, multiline=True),
    }


def _organizer_owns_event(db: Session, event_id: int, organizer_user_id: int) -> bool:
    from sqlalchemy import text
    return db.execute(text("""
        SELECT 1 FROM events e JOIN user_roles ur ON ur.id = e.user_role_id
        WHERE e.id = :event_id AND ur.user_id = :user_id
    """), {"event_id": event_id, "user_id": organizer_user_id}).first() is not None


@router.post("/events")
async def create_event(
    event_name: str = Form(...),
    event_description: str = Form(...),
    event_date: str = Form(...),
    event_time: str = Form(...),
    venue: str = Form(...),
    capacity: int = Form(...),
    organizer_id: Optional[int] = Form(None),  # ignored: the organizer is the logged-in user
    department: str = Form(None),
    about_event: str = Form(None),
    event_end_time: str = Form(None),
    registration_start: str = Form(None),
    registration_end: str = Form(None),
    cover_photo: UploadFile = File(None),
    organizer: User = Depends(organizer_only),
    db: Session = Depends(get_db)
):
    """
    Create a new event (organizer only). The event belongs to the organizer in the
    login cookie, never to an id sent by the browser.
    """
    fields = _validate_event_text(event_name, event_description, venue, capacity, department, about_event)
    event_name, event_description, venue = fields["event_name"], fields["event_description"], fields["venue"]
    department, about_event = fields["department"], fields["about_event"]

    # Cover photo bytes are stored in the database (events.cover_photo_data)
    # and served by GET /api/events/{id}/cover
    cover_photo_data = None
    cover_photo_type = None
    if cover_photo and cover_photo.filename:
        cover_photo_data, cover_photo_type = await validate.image_upload(cover_photo, "Cover photo")

    # Link event to the organizer's user_roles row (events.user_role_id FK)
    organizer_role = db.query(UserRole).filter(
        UserRole.user_id == organizer.id,
        UserRole.role_type == 'organizer'
    ).first()
    if not organizer_role:
        raise HTTPException(status_code=400, detail="Organizer not found")

    _validate_event_times(event_date, event_time, event_end_time)
    registration_start, registration_end = _validate_registration_period(registration_start, registration_end, event_date)

    # Insert into database (raw SQL for now since schema is complex)
    from sqlalchemy import text
    
    query = text("""
        INSERT INTO events (
            user_role_id, event_name, event_description, 
            event_date, event_time, event_end_time, venue, capacity, status,
            cover_photo_data, cover_photo_type, department, about_event, registration_start, registration_end
        ) VALUES (
            :user_role_id, :event_name, :event_description,
            :event_date, :event_time, :event_end_time, :venue, :capacity, 'open',
            :cover_photo_data, :cover_photo_type, :department, :about_event, :registration_start, :registration_end
        ) RETURNING id
    """)
    
    try:
        result = db.execute(query, {
            "user_role_id": organizer_role.id,
            "event_name": event_name,
            "event_description": event_description,
            "event_date": event_date,
            "event_time": event_time,
            "event_end_time": event_end_time or None,
            "venue": venue,
            "capacity": capacity,
            "cover_photo_data": cover_photo_data,
            "cover_photo_type": cover_photo_type,
            "department": department or None,
            "about_event": about_event or None,
            "registration_start": registration_start,
            "registration_end": registration_end
        })
        event_id = result.scalar()
        _close_finished_events(db)  # an event created for a time that already ended starts closed

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
                    "event_end_time": event_end_time or None,
                    "registration_start": registration_start.isoformat() if registration_start else None,
                    "registration_end": registration_end.isoformat() if registration_end else None,
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
        raise HTTPException(status_code=500, detail="Error creating event. Please try again.")


@router.get("/events", dependencies=[Depends(current_user)])
def get_events(db: Session = Depends(get_db)):
    """
    Get all events
    """
    from sqlalchemy import text
    _close_finished_events(db)
    
    query = text("""
        SELECT 
            e.id, e.event_name, e.event_description,
            e.event_date, e.event_time, e.venue, e.capacity,
            e.status, e.cover_photo,
            COALESCE(COUNT(r.id), 0) as enrolled_count,
            e.department, e.about_event, e.event_end_time, e.registration_start, e.registration_end
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
                "about_event": row[11],
                "event_end_time": _time_str(row[12]),
                "registration_start": str(row[13]) if row[13] else None,
                "registration_end": str(row[14]) if row[14] else None
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


@router.get("/events/{event_id}", dependencies=[Depends(current_user)])
def get_event(event_id: int, db: Session = Depends(get_db)):
    """
    Get a specific event by ID
    """
    from sqlalchemy import text
    _close_finished_events(db)
    
    query = text("""
        SELECT 
            e.id, e.event_name, e.event_description,
            e.event_date, e.event_time, e.venue, e.capacity,
            e.status, e.cover_photo,
            COALESCE(COUNT(r.id), 0) as enrolled_count,
            e.department, e.about_event, e.event_end_time, e.registration_start, e.registration_end
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
                "about_event": row[11],
                "event_end_time": _time_str(row[12]),
                "registration_start": str(row[13]) if row[13] else None,
                "registration_end": str(row[14]) if row[14] else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting event: {e}")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")


@router.get("/organizer/stats")
def get_organizer_stats(organizer: User = Depends(organizer_only), db: Session = Depends(get_db)):
    """
    Dashboard stats for the logged-in organizer (from the login cookie; an
    organizer_id query parameter is ignored, so one organizer can't read another's)
    """
    from sqlalchemy import text
    organizer_id = organizer.id
    _close_finished_events(db)

    # events.user_role_id references the organizer's user_roles row
    events_query = text("""
        SELECT e.id, e.event_name, e.capacity, e.status,
               COUNT(r.id) AS enrolled,
               -- open for enrolling now: not upcoming (registration started) and not past the registration end
               (e.status = 'open'
                AND COALESCE(e.registration_start, e.event_date, CURRENT_DATE) <= CURRENT_DATE
                AND (e.registration_end IS NULL OR e.registration_end >= CURRENT_DATE)) AS enrolling
        FROM events e
        JOIN user_roles ur ON ur.id = e.user_role_id
        LEFT JOIN registrations r ON r.event_id = e.id
        WHERE ur.user_id = :organizer_id AND ur.role_type = 'organizer'
        GROUP BY e.id
        ORDER BY e.created_at DESC
    """)
    events = db.execute(events_query, {"organizer_id": organizer_id}).fetchall()

    # Students/participants are every registered (verified) account, not only
    # those enrolled in this organizer's events
    accounts_query = text("""
        SELECT COUNT(*) FILTER (WHERE role = 'student') AS students,
               COUNT(*) FILTER (WHERE role = 'participant') AS participants
        FROM users
    """)
    accounts = db.execute(accounts_query).first()

    totals_query = text("""
        SELECT COUNT(r.id) AS total_enrollment,
               COUNT(a.id) FILTER (WHERE a.attendance_status = 'present') AS present
        FROM registrations r
        JOIN users u ON u.id = r.user_id
        JOIN events e ON e.id = r.event_id
        JOIN user_roles ur ON ur.id = e.user_role_id
        LEFT JOIN attendees a ON a.registration_id = r.id
        WHERE ur.user_id = :organizer_id AND ur.role_type = 'organizer'
    """)
    totals = db.execute(totals_query, {"organizer_id": organizer_id}).first()

    total_enrollment = totals[0] or 0
    present = totals[1] or 0

    return {
        "success": True,
        "stats": {
            "students": accounts[0] or 0,
            "participants": accounts[1] or 0,
            "totalEnrollment": total_enrollment,
            "openEvents": sum(1 for e in events if e[5])
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
def get_organizer_attendees(organizer: User = Depends(organizer_only), db: Session = Depends(get_db)):
    """
    Everyone enrolled in the logged-in organizer's events, one row per registration
    """
    from sqlalchemy import text
    organizer_id = organizer.id

    query = text("""
        SELECT r.id, u.full_name, u.email, u.role, e.event_name,
               d.department_name, ur.contact_number,
               COALESCE(a.gender, ur.gender), COALESCE(a.year_level::text, ur.year_level),
               COALESCE(a.attendance_status, 'pending') AS status,
               COALESCE(a.address, ur.address) AS address
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
    status: Literal["present", "not_recorded"]


@router.put("/organizer/attendees/{registration_id}/attendance")
def update_attendance(
    registration_id: int,
    body: AttendanceUpdate,
    organizer: User = Depends(organizer_only),
    db: Session = Depends(get_db)
):
    """
    Mark a registration as present or not recorded (the student sees it on My Events).
    Only for registrations in the logged-in organizer's own events.
    """
    from sqlalchemy import text

    registration = db.execute(text("""
        SELECT r.id, u.full_name, u.email, ur.contact_number, ur.department_id
        FROM registrations r
        JOIN users u ON u.id = r.user_id
        JOIN events e ON e.id = r.event_id
        JOIN user_roles org ON org.id = e.user_role_id
        LEFT JOIN user_roles ur ON ur.user_id = u.id AND ur.role_type = u.role
        WHERE r.id = :registration_id AND org.user_id = :organizer_id
    """), {"registration_id": registration_id, "organizer_id": organizer.id}).first()

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
def delete_event(
    event_id: int,
    user: User = Depends(require_roles("admin", "organizer")),
    db: Session = Depends(get_db)
):
    """
    Delete an event by ID. Admins can delete any event; organizers only their own.
    """
    from sqlalchemy import text

    if user.role == "organizer" and not _organizer_owns_event(db, event_id, user.id):
        raise HTTPException(status_code=403, detail="You can only delete your own events.")
    
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
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")


@router.get("/events/{event_id}/enrollment")
def get_enrollment(event_id: int, user: User = Depends(attendee_only), db: Session = Depends(get_db)):
    """
    Whether the logged-in student/participant is enrolled in this event
    """
    from sqlalchemy import text

    row = db.execute(text("""
        SELECT COALESCE(a.attendance_status, 'pending') AS attendance
        FROM registrations r
        LEFT JOIN attendees a ON a.registration_id = r.id
        WHERE r.event_id = :event_id AND r.user_id = :user_id
    """), {"event_id": event_id, "user_id": user.id}).first()
    return {
        "success": True,
        "enrolled": row is not None,
        # 'present', 'not_recorded', or 'pending' (the organizer hasn't marked it yet)
        "attendance": row.attendance if row else None,
    }


@router.delete("/events/{event_id}/enroll")
def cancel_enrollment(event_id: int, user: User = Depends(attendee_only), db: Session = Depends(get_db)):
    """
    Cancel the logged-in user's enrollment. Only allowed during the registration period
    (registration start, or the event date, through registration end). The registration row
    is deleted (its attendees row cascades), so the slot frees up and they can enroll again.
    """
    from sqlalchemy import text
    _close_finished_events(db)

    row = db.execute(text("""
        SELECT r.id, e.status, a.attendance_status,
               COALESCE(e.registration_start, e.event_date) AS opens_on, e.registration_end
        FROM registrations r
        JOIN events e ON e.id = r.event_id
        LEFT JOIN attendees a ON a.registration_id = r.id
        WHERE r.event_id = :event_id AND r.user_id = :user_id
    """), {"event_id": event_id, "user_id": user.id}).first()

    if not row:
        raise HTTPException(status_code=404, detail="You are not enrolled in this event")
    if row.status != 'open':
        raise HTTPException(status_code=400, detail="This event is already closed, so the enrollment can't be cancelled")
    if row.attendance_status == 'present':
        raise HTTPException(status_code=400, detail="Your attendance was already recorded for this event")
    today = date.today()
    if (row.opens_on and today < row.opens_on) or (row.registration_end and today > row.registration_end):
        raise HTTPException(status_code=400, detail="Enrollment can only be cancelled during the registration period")

    db.execute(text("DELETE FROM registrations WHERE id = :id"), {"id": row.id})
    db.commit()
    return {"success": True, "message": "Enrollment cancelled"}


@router.post("/events/{event_id}/enroll")
async def enroll_event(
    event_id: int,
    user: User = Depends(attendee_only),
    db: Session = Depends(get_db)
):
    """
    Enroll the logged-in student/participant (identified by the login cookie) in an event
    """
    from sqlalchemy import text
    _close_finished_events(db)
    
    # Check if event exists
    event_query = text("""
        SELECT e.id, e.capacity, e.status, COUNT(r.id) AS enrolled,
               COALESCE(e.registration_start, e.event_date) AS opens_on,
               e.registration_end
        FROM events e
        LEFT JOIN registrations r ON r.event_id = e.id
        WHERE e.id = :event_id
        GROUP BY e.id
    """)
    event_result = db.execute(event_query, {"event_id": event_id}).first()

    if not event_result:
        raise HTTPException(status_code=404, detail="Event not found")
    if event_result[2] != 'open':
        raise HTTPException(status_code=400, detail="This event is closed for enrollment")
    # Upcoming: registration hasn't started yet (no registration start set -> opens on the event date)
    if event_result[4] and date.today() < event_result[4]:
        raise HTTPException(
            status_code=400,
            detail=f"Registration for this event opens on {event_result[4].strftime('%B')} {event_result[4].day}, {event_result[4].year}"
        )
    if event_result[5] and date.today() > event_result[5]:
        raise HTTPException(
            status_code=400,
            detail=f"Registration for this event ended on {event_result[5].strftime('%B')} {event_result[5].day}, {event_result[5].year}"
        )
    if event_result[1] is not None and event_result[3] >= event_result[1]:
        raise HTTPException(status_code=400, detail="This event is already full")

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
    except IntegrityError:
        # UNIQUE(event_id, user_id): a second click got here at the same time
        db.rollback()
        raise HTTPException(status_code=400, detail="Already enrolled in this event")
    except Exception as e:
        db.rollback()
        print(f"Error enrolling: {e}")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")



def get_or_create_department(db: Session, name: str) -> Department:
    dept = db.query(Department).filter(Department.department_name == name).first()
    if not dept:
        dept = Department(department_name=name)
        db.add(dept)
        db.flush()
    return dept


@router.put("/organizers/{organizer_id}", dependencies=[Depends(admin_only)])
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

    email = validate.email(email)
    full_name = validate.text(full_name, "Full name", 150)
    department = validate.text(department, "Department", 150)
    contact_number = validate.contact_number(contact_number)
    if db.query(User).filter(User.email == email, User.id != organizer_id).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    employment_id = validate.text(employment_id, "Employment ID", 50)
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

    user.full_name = full_name
    user.email = email
    user_role.employment_id = employment_id
    user_role.department_id = get_or_create_department(db, department).id
    user_role.contact_number = contact_number
    db.commit()

    return {"success": True, "message": "Organizer updated successfully"}


@router.post("/change-password", dependencies=[Depends(reset_email_limit)])
async def request_change_password_link(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """
    Change Password for a logged-in user: email a Set New Password link to the
    email of the account in the login cookie (never an address sent by the client)
    """
    return await _send_reset_link(db, user)


def _avatar_url(user_id: int, user_role) -> str:
    """URL of the user's profile picture ('' when they haven't uploaded one)."""
    return f"/api/users/{user_id}/avatar" if user_role and user_role.avatar_type else ""


def _age(birthday) -> str:
    """Whole years since the birthday ('' when there's no birthday). Not stored: it changes every year."""
    if not birthday:
        return ""
    today = date.today()
    return str(today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day)))


def _profile_response(user: User, user_role, dept) -> dict:
    return {
        "fullName": user.full_name,
        "srCode": (user_role.student_number if user_role else None) or "",
        "collegeDepartment": dept.department_name if dept else "",
        "program": (user_role.program if user_role else None) or "",
        "yearLevel": (user_role.year_level if user_role else None) or "",
        "gender": (user_role.gender if user_role else None) or "",
        "contactNumber": (user_role.contact_number if user_role else None) or "",
        "address": (user_role.address if user_role else None) or "",
        "birthday": user_role.birthday.isoformat() if user_role and user_role.birthday else "",
        "age": _age(user_role.birthday) if user_role else "",
        "email": user.email,
        "role": user.role.capitalize(),
        "avatarUrl": _avatar_url(user.id, user_role),
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
def get_student_profile(user: User = Depends(attendee_only), db: Session = Depends(get_db)):
    """
    The logged-in student's (or participant's) profile
    """
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
    address: Optional[str] = None
    birthday: Optional[str] = None  # YYYY-MM-DD


@router.put("/student/profile")
def update_student_profile(body: ProfileUpdate, user: User = Depends(attendee_only), db: Session = Depends(get_db)):
    """
    Update the logged-in student's (or participant's) profile.
    Email and role can't be changed here.
    """
    # Length limits match the user_roles columns
    validate.text(body.fullName, "Full name", 150)
    for value, label, limit in ((body.collegeDepartment, "College / Department", 150),
                                (body.program, "Program", 150), (body.gender, "Gender", 30),
                                (body.address, "Address", 255), (body.yearLevel, "Year level", 20),
                                (body.srCode, "SR-Code", 50), (body.contactNumber, "Contact number", 30),
                                (body.birthday, "Birthday", 10)):
        validate.text(value, label, limit, required=False)

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

    def birthday(value: Optional[str]):
        if not (value or "").strip():
            return None
        try:
            parsed = date.fromisoformat(value.strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="Please enter a valid birthday")
        if parsed > date.today():
            raise HTTPException(status_code=400, detail="Birthday can't be in the future")
        return parsed

    def letters(value: Optional[str], label: str) -> Optional[str]:
        """Names, department and program: letters, spaces and . - ' only."""
        if not re.fullmatch(r"[A-Za-zÑñ .'-]*", value or ""):
            raise HTTPException(status_code=400, detail=f"{label} can only contain letters")
        return clean(value)

    if (body.srCode or "").strip() and not re.fullmatch(r"\d{2}-\d{5}", body.srCode.strip()):
        raise HTTPException(status_code=400, detail="SR-Code must look like 23-30046")
    if (body.contactNumber or "").strip() and len(re.sub(r"\D", "", body.contactNumber)) != 11:
        raise HTTPException(status_code=400, detail="Contact number must have 11 digits (0912-345-6789)")

    user.full_name = letters(body.fullName, "Full name")
    user_role.student_number = clean(body.srCode)
    user_role.program = letters(body.program, "Program")
    user_role.year_level = year_level(body.yearLevel)
    user_role.gender = clean(body.gender)
    user_role.contact_number = phone(body.contactNumber)
    user_role.address = clean(body.address)
    user_role.birthday = birthday(body.birthday)
    if letters(body.collegeDepartment, "College / Department"):
        user_role.department_id = get_or_create_department(db, clean(body.collegeDepartment)).id
    db.commit()

    user_role, dept = _role_row(db, user)
    return {
        "success": True,
        "message": "Profile updated successfully",
        "profile": _profile_response(user, user_role, dept)
    }


@router.post("/student/profile/avatar")
async def upload_profile_avatar(avatar: UploadFile = File(...), user: User = Depends(attendee_only),
                                db: Session = Depends(get_db)):
    """
    Save the logged-in user's profile picture (bytes stored in user_roles.avatar_data)
    """
    data, mime = await validate.image_upload(avatar, "Profile picture")

    user_role, _ = _role_row(db, user)
    if not user_role:
        user_role = UserRole(user_id=user.id, role_type=user.role)
        db.add(user_role)
    user_role.avatar_data = data
    user_role.avatar_type = mime
    db.commit()

    return {"success": True, "message": "Profile picture updated", "avatarUrl": f"/api/users/{user.id}/avatar"}


@router.get("/users/{user_id}/avatar", dependencies=[Depends(current_user)])
def get_user_avatar(user_id: int, db: Session = Depends(get_db)):
    """
    Serve a user's profile picture from the database
    """
    row = db.query(UserRole.avatar_data, UserRole.avatar_type).filter(
        UserRole.user_id == user_id, UserRole.avatar_data.isnot(None)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Profile picture not found")

    # no-cache: the URL stays the same when the picture is replaced
    return Response(content=bytes(row[0]), media_type=row[1] or "application/octet-stream",
                    headers={"Cache-Control": "no-cache"})


@router.put("/events/{event_id}")
async def update_event(
    event_id: int,
    event_name: str = Form(...),
    event_description: str = Form(...),
    event_date: str = Form(...),
    event_time: str = Form(...),
    venue: str = Form(...),
    capacity: int = Form(...),
    organizer_id: Optional[int] = Form(None),  # ignored: the organizer is the logged-in user
    department: str = Form(None),
    about_event: str = Form(None),
    event_end_time: str = Form(None),
    registration_start: str = Form(None),
    registration_end: str = Form(None),
    cover_photo: UploadFile = File(None),
    organizer: User = Depends(organizer_only),
    db: Session = Depends(get_db)
):
    """
    Update an event (only by the organizer who created it, from the login cookie).
    The cover photo is replaced only when a new one is uploaded.
    """
    from sqlalchemy import text
    from datetime import datetime

    if not _organizer_owns_event(db, event_id, organizer.id):
        raise HTTPException(status_code=404, detail="Event not found")

    fields = _validate_event_text(event_name, event_description, venue, capacity, department, about_event)
    ends_at = _validate_event_times(event_date, event_time, event_end_time)
    registration_start, registration_end = _validate_registration_period(registration_start, registration_end, event_date)

    enrolled = db.execute(
        text("SELECT COUNT(*) FROM registrations WHERE event_id = :id"), {"id": event_id}
    ).scalar()
    if capacity < enrolled:
        raise HTTPException(
            status_code=400,
            detail=f"Capacity can't be lower than the {enrolled} people already enrolled"
        )

    params = {
        **fields,
        "id": event_id,
        "event_date": event_date,
        "event_time": event_time,
        "event_end_time": event_end_time or None,
        # Moving the end time later reopens an auto-closed event; an earlier one closes it
        "status_open": ends_at > datetime.now(),
        "registration_start": registration_start,
        "registration_end": registration_end,
    }
    cover_sql = ""
    if cover_photo and cover_photo.filename:
        data, mime = await validate.image_upload(cover_photo, "Cover photo")
        params.update(
            cover_photo_data=data,
            cover_photo_type=mime,
            cover_photo=f"/api/events/{event_id}/cover"
        )
        cover_sql = (", cover_photo_data = :cover_photo_data, "
                     "cover_photo_type = :cover_photo_type, cover_photo = :cover_photo")

    db.execute(text(f"""
        UPDATE events SET
            event_name = :event_name, event_description = :event_description,
            event_date = :event_date, event_time = :event_time, event_end_time = :event_end_time,
            venue = :venue, capacity = :capacity, department = :department, about_event = :about_event,
            registration_start = :registration_start, registration_end = :registration_end,
            status = CASE WHEN status IN ('open', 'closed')
                          THEN CASE WHEN :status_open THEN 'open' ELSE 'closed' END
                          ELSE status END,
            updated_at = NOW(){cover_sql}
        WHERE id = :id
    """), params)
    db.commit()

    return {"success": True, "message": "Event updated successfully"}



@router.post("/verify-email", dependencies=[Depends(rate_limit("verify-email", 20, 600))])
def verify_email(token: str = Form(...), db: Session = Depends(get_db)):
    """
    Opened from the emailed "Verify Account" link; creates the student/participant
    account from the pending registration.
    """
    from sqlalchemy import text

    pending = db.execute(text("""
        SELECT id, email, full_name, role, password_hash, department, contact_number,
               expires_at > NOW() AS still_valid
        FROM pending_registrations WHERE code_hash = :h
    """), {"h": _hash_code(validate.token(token))}).first()

    if not pending:
        raise HTTPException(
            status_code=400,
            detail="This verification link is invalid or has already been used. Try logging in, or register again."
        )
    if not pending.still_valid:
        return _unverified_response(
            pending.email, "This verification link has expired. Please request a new one.", status_code=400
        )

    if db.query(User).filter(User.email == pending.email).first():
        db.execute(text("DELETE FROM pending_registrations WHERE id = :id"), {"id": pending.id})
        db.commit()
        return {"success": True, "message": "Your account is already verified. You can log in."}

    # Link is valid: create the real account now
    new_user = User(
        full_name=pending.full_name,
        email=pending.email,
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

    return {"success": True, "message": "Your account has been verified. You can now log in."}


@router.post("/resend-verification", dependencies=[Depends(reset_email_limit)])
async def resend_verification(email: str = Form(...), db: Session = Depends(get_db)):
    """
    Send a new verification link for a pending registration (at most once every VERIFICATION_RESEND_SECONDS)
    """
    from sqlalchemy import text
    from services.email_service import send_verification_link_email

    email = validate.email(email)
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
            content={"detail": f"Please wait {wait} seconds before requesting a new link.", "retry_after": wait}
        )

    # A new link replaces the old one; created_at restarts so the 24-hour purge doesn't drop it early
    token = _new_token()
    db.execute(text(f"""
        UPDATE pending_registrations
        SET code_hash = :h, last_sent_at = NOW(), created_at = NOW(),
            expires_at = NOW() + INTERVAL '{VERIFICATION_LINK_TTL_HOURS} hours'
        WHERE id = :id
    """), {"h": _hash_code(token), "id": pending.id})
    db.commit()

    if not await send_verification_link_email(email, pending.full_name, _verification_link(token)):
        raise HTTPException(status_code=503, detail="We couldn't send the link right now. Please try again later.")
    return {"success": True, "message": f"A new link was sent to {email}.", "retry_after": VERIFICATION_RESEND_SECONDS}


@router.get("/student/my-events")
def get_my_events(user: User = Depends(attendee_only), db: Session = Depends(get_db)):
    """
    Events the logged-in student/participant enrolled in, with their attendance
    ('present', 'not_recorded', or 'pending' when the organizer hasn't
    marked it yet). Identified by the login cookie.
    """
    from sqlalchemy import text

    user_id = user.id
    _close_finished_events(db)
    rows = db.execute(text("""
        SELECT e.id, e.event_name, e.event_date, e.event_time, e.event_end_time, e.venue, e.status,
               COALESCE(a.attendance_status, 'pending') AS attendance,
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
                "event_end_time": _time_str(row.event_end_time),
                "venue": row.venue,
                "status": row.status,
                "attendance": row.attendance,
            }
            for row in rows
        ]
    }
