"""
Email Service for sending notifications
"""

import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiosmtplib
from dotenv import load_dotenv

load_dotenv()

# Email configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "true").lower() == "true"
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)
FROM_NAME = os.getenv("FROM_NAME", "EVEREST Event System")

# Email mode - can disable for development
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "true").lower() == "true"

# Optional: send through Brevo's HTTPS API instead of SMTP. Use this on networks
# that block SMTP ports (587/465), e.g. campus Wi-Fi. FROM_EMAIL must be a
# verified sender in the Brevo account.
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


async def _send(to_email: str, subject: str, text_content: str, html_content: str) -> bool:
    """
    Deliver one email. Uses the Brevo HTTPS API when BREVO_API_KEY is set,
    otherwise SMTP. Returns True only when the provider accepted the message.
    """
    if BREVO_API_KEY:
        import httpx
        try:
            print(f"      ├─ Sending via Brevo API (HTTPS) as {FROM_EMAIL}")
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    BREVO_API_URL,
                    headers={"api-key": BREVO_API_KEY, "accept": "application/json"},
                    json={
                        "sender": {"name": FROM_NAME, "email": FROM_EMAIL},
                        "to": [{"email": to_email}],
                        "subject": subject,
                        "textContent": text_content,
                        "htmlContent": html_content,
                    },
                )
            if response.status_code in (200, 201, 202):
                print(f"      └─ ✅ Email accepted by Brevo for {to_email}")
                return True
            print(f"      └─ ❌ Brevo rejected the email ({response.status_code}): {response.text}")
            return False
        except Exception as e:
            print(f"      └─ ❌ Brevo error: {type(e).__name__}: {e}")
            return False

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
    message["To"] = to_email
    message.attach(MIMEText(text_content, "plain"))
    message.attach(MIMEText(html_content, "html"))

    try:
        print(f"      ├─ Connecting to {SMTP_HOST}:{SMTP_PORT} ({'SSL' if SMTP_USE_SSL else 'STARTTLS'}) as {SMTP_USER}")
        await aiosmtplib.send(
            message,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            use_tls=SMTP_USE_SSL,
            start_tls=not SMTP_USE_SSL,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
        )
        print(f"      └─ ✅ Email accepted by SMTP server for {to_email}")
        return True
    except Exception as e:
        print(f"      └─ ❌ SMTP Error: {type(e).__name__}: {e}")
        return False


async def send_organizer_credentials(
    to_email: str,
    organizer_name: str,
    employment_id: str,
    password: str
):
    """
    Send email to new organizer with login credentials
    """
    
    # Check if email is enabled
    if not EMAIL_ENABLED:
        print(f"      ├─ ⚠️  EMAIL DISABLED (development mode)")
        print(f"      └─ Skipping email to {to_email}")
        return False  # Return False to indicate email was not sent
    
    # Email content
    text_content = f"""
Welcome to EVEREST Event Registration System!

Your organizer account has been created successfully.

Login Credentials:
-------------------
Email: {to_email}
Password: {password}

You can now login at: http://localhost:4200/login

Please change your password after first login.

Best regards,
EVEREST Admin Team
    """
    
    html_content = f"""
    <html>
      <head>
        <style>
          body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
          .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
          .header {{ background: linear-gradient(135deg, #ff6b6b 0%, #ff8787 100%); 
                     color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
          .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
          .credentials {{ background: white; padding: 20px; border-left: 4px solid #ff6b6b; margin: 20px 0; }}
          .button {{ display: inline-block; padding: 12px 30px; background: #ff6b6b; 
                    color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
          .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h1>Welcome to EVEREST!</h1>
            <p>Event Registration System</p>
          </div>
          <div class="content">
            <p>Hello <strong>{organizer_name}</strong>,</p>
            <p>Your organizer account has been created successfully.</p>
            
            <div class="credentials">
              <h3>Login Credentials:</h3>
              <p><strong>Email:</strong> {to_email}</p>
              <p><strong>Password:</strong> {password}</p>
            </div>
            
            <p>You can now access your organizer dashboard:</p>
            <a href="http://localhost:4200/login" class="button">Login Now</a>
            
            <p><strong>Important:</strong> Please change your password after your first login for security.</p>
          </div>
          <div class="footer">
            <p>This is an automated email. Please do not reply.</p>
            <p>&copy; 2026 EVEREST Event Registration System</p>
          </div>
        </div>
      </body>
    </html>
    """
    
    return await _send(to_email, "Welcome to EVEREST - Your Organizer Account", text_content, html_content)


async def send_test_email():
    """
    Test function to verify email configuration
    """
    await send_organizer_credentials(
        to_email="test@example.com",
        organizer_name="Test Organizer",
        employment_id="TEST123",
        password="test123"
    )


async def send_password_reset_email(
    to_email: str,
    reset_link: str,
    user_name: str
):
    """
    Send password reset email with link
    """

    if not EMAIL_ENABLED:
        print(f"⚠️  EMAIL DISABLED (EMAIL_ENABLED=false) - skipping password reset email to {to_email}")
        return False

    # Email content
    text_content = f"""
Password Reset Request

Hello {user_name},

We received a request to reset your password for your EVEREST account.

Click the link below to reset your password:
{reset_link}

This link will expire in 1 hour.

If you did not request a password reset, please ignore this email.

Best regards,
EVEREST Admin Team
    """
    
    html_content = f"""
    <html>
      <head>
        <style>
          body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
          .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
          .header {{ background: linear-gradient(135deg, #ff6b6b 0%, #ff8787 100%); 
                     color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
          .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
          .button {{ display: inline-block; padding: 12px 30px; background: #ff6b6b; 
                    color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
          .warning {{ background: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0; }}
          .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h1>Password Reset</h1>
          </div>
          <div class="content">
            <p>Hello <strong>{user_name}</strong>,</p>
            <p>We received a request to reset your password for your EVEREST account.</p>
            
            <p>Click the button below to reset your password:</p>
            <a href="{reset_link}" class="button">Reset Password</a>
            
            <div class="warning">
              <p><strong>Important:</strong></p>
              <ul>
                <li>This link will expire in 1 hour</li>
                <li>If you did not request this reset, please ignore this email</li>
              </ul>
            </div>
            
            <p style="font-size: 12px; color: #666;">
              If the button doesn't work, copy and paste this link into your browser:<br>
              <a href="{reset_link}">{reset_link}</a>
            </p>
          </div>
          <div class="footer">
            <p>This is an automated email. Please do not reply.</p>
            <p>&copy; 2026 EVEREST Event Registration System</p>
          </div>
        </div>
      </body>
    </html>
    """
    
    return await _send(to_email, "EVEREST - Password Reset Request", text_content, html_content)


async def send_verification_code_email(to_email: str, user_name: str, code: str):
    """
    Send the 6-digit email verification code (same design as the organizer welcome email)
    """
    if not EMAIL_ENABLED:
        print(f"⚠️  EMAIL DISABLED (EMAIL_ENABLED=false) - skipping verification code to {to_email}")
        return False

    text_content = f"""
Verify your EVEREST account

Hello {user_name},

Your verification code is: {code}

Enter this code on the Verify Email page to activate your account.
The code expires in 15 minutes.

If you did not create an EVEREST account, you can ignore this email.

Best regards,
EVEREST Admin Team
    """

    html_content = f"""
    <html>
      <head>
        <style>
          body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
          .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
          .header {{ background: linear-gradient(135deg, #ff6b6b 0%, #ff8787 100%);
                     color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
          .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
          .code-box {{ background: white; padding: 20px; border-left: 4px solid #ff6b6b; margin: 20px 0; text-align: center; }}
          .code {{ font-size: 36px; font-weight: bold; letter-spacing: 10px; color: #dc3545; margin: 10px 0; }}
          .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h1>Verify Your Email</h1>
            <p>Event Registration System</p>
          </div>
          <div class="content">
            <p>Hello <strong>{user_name}</strong>,</p>
            <p>Thanks for registering. Enter this code on the Verify Email page to activate your account:</p>

            <div class="code-box">
              <h3>Your Verification Code:</h3>
              <p class="code">{code}</p>
            </div>

            <p><strong>Important:</strong> This code expires in 15 minutes. Never share it with anyone.</p>
            <p style="font-size: 12px; color: #666;">If you did not create an EVEREST account, you can ignore this email.</p>
          </div>
          <div class="footer">
            <p>This is an automated email. Please do not reply.</p>
            <p>&copy; 2026 EVEREST Event Registration System</p>
          </div>
        </div>
      </body>
    </html>
    """

    return await _send(to_email, f"EVEREST - Your verification code is {code}", text_content, html_content)
