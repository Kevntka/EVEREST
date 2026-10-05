"""
Create an admin account from the terminal (run from backend/, with the venv active):

    python create_admin.py

Asks for the name, email and password (the password isn't shown or saved anywhere
but the database, as a bcrypt hash). Uses DATABASE_URL from backend/.env. If the
email already has an account, offers to make it an admin with the new password.
"""

import getpass
import re
import sys

from database.config import SessionLocal, engine
from models.user import User
from auth.jwt_handler import hash_password

engine.echo = False  # no SQL logging in the terminal


def ask(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("  This is required.")


def ask_password() -> str:
    while True:
        password = getpass.getpass("Password (hidden): ")
        if not password:
            print("  Password is required.")
            continue
        if getpass.getpass("Confirm password: ") != password:
            print("  Passwords don't match. Try again.")
            continue
        return password


def main():
    print("=" * 50)
    print(f"Create admin account  (database: {engine.url.database})")
    print("=" * 50)

    full_name = ask("Full name: ")
    email = ask("Email: ").lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        sys.exit("Error: That doesn't look like an email address.")
    password = ask_password()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            answer = input(f"An account with {email} already exists (role: {user.role}). "
                           "Make it an admin with this password? [y/N]: ")
            if answer.strip().lower() != "y":
                sys.exit("Cancelled. Nothing was changed.")
            user.full_name = full_name
            user.role = "admin"
            user.is_active = True
            user.password = hash_password(password)
        else:
            db.add(User(full_name=full_name, email=email, role="admin",
                        is_active=True, password=hash_password(password)))
        db.commit()
    except Exception as e:
        db.rollback()
        sys.exit(f"Error: {e}")
    finally:
        db.close()

    print(f"Done: Admin ready. Log in with {email} and the password you entered.")


if __name__ == "__main__":
    main()
