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
SMTP_USER = os.getenv("SMTP_USER", "xcvinnn71@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "cxfd uohd wcqg jyhd")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)
FROM_NAME = os.getenv("FROM_NAME", "EVEREST Event System")


async def send_organizer_credentials(
    to_email: str,
    organizer_name: str,
    employment_id: str,
    password: str
):
    """
    Send email to new organizer with login credentials
    """
    
    # Create message
    message = MIMEMultipart("alternative")
    message["Subject"] = "Welcome to EVEREST - Your Organizer Account"
    message["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
    message["To"] = to_email
    
    # Email content
    text_content = f"""
Welcome to EVEREST Event Registration System!

Your organizer account has been created successfully.

Login Credentials:
-------------------
Email: {to_email}
Password: {password}
Employment ID: {employment_id}

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
              <p><strong>Employment ID:</strong> {employment_id}</p>
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
    
    # Attach both text and HTML versions
    part1 = MIMEText(text_content, "plain")
    part2 = MIMEText(html_content, "html")
    message.attach(part1)
    message.attach(part2)
    
    # Send email
    try:
        if SMTP_USE_SSL:
            # Use SSL (port 465)
            await aiosmtplib.send(
                message,
                hostname=SMTP_HOST,
                port=SMTP_PORT,
                use_tls=True,
                username=SMTP_USER,
                password=SMTP_PASSWORD,
            )
        else:
            # Use STARTTLS (port 587)
            await aiosmtplib.send(
                message,
                hostname=SMTP_HOST,
                port=SMTP_PORT,
                start_tls=True,
                username=SMTP_USER,
                password=SMTP_PASSWORD,
            )
        print(f"✅ Email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Failed to send email to {to_email}: {e}")
        # For development, we'll just log and continue
        # In production, you might want to handle this differently
        return False


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
    
    # Create message
    message = MIMEMultipart("alternative")
    message["Subject"] = "EVEREST - Password Reset Request"
    message["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
    message["To"] = to_email
    
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
    
    # Attach both text and HTML versions
    part1 = MIMEText(text_content, "plain")
    part2 = MIMEText(html_content, "html")
    message.attach(part1)
    message.attach(part2)
    
    # Send email
    try:
        if SMTP_USE_SSL:
            await aiosmtplib.send(
                message,
                hostname=SMTP_HOST,
                port=SMTP_PORT,
                use_tls=True,
                username=SMTP_USER,
                password=SMTP_PASSWORD,
            )
        else:
            await aiosmtplib.send(
                message,
                hostname=SMTP_HOST,
                port=SMTP_PORT,
                start_tls=True,
                username=SMTP_USER,
                password=SMTP_PASSWORD,
            )
        print(f"✅ Password reset email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Failed to send password reset email to {to_email}: {e}")
        return False
