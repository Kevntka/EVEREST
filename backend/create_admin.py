"""
Create Admin User
Run this after importing the schema
"""

from database.config import SessionLocal
from models.user import User, Role, UserRole
from models.auth import set_user_password

def create_admin():
    db = SessionLocal()
    try:
        # Check if admin exists
        existing_admin = db.query(User).filter(User.email == "kevndzon@gmail.com").first()
        if existing_admin:
            # Update password if admin exists
            set_user_password("kevndzon@gmail.com", "Kevin22melgar@")
            print("✅ Admin user already exists - password updated")
            print(f"   Email: kevndzon@gmail.com")
            print(f"   Password: Kevin22melgar@")
            return
        
        # Get Admin role
        admin_role = db.query(Role).filter(Role.role_name == 'Admin').first()
        if not admin_role:
            print("❌ Admin role not found in database")
            print("   Make sure you executed the schema.sql first!")
            return
        
        # Create admin user
        admin_user = User(
            full_name="Administrator",
            email="kevndzon@gmail.com"
        )
        db.add(admin_user)
        db.flush()
        
        # Create user_role
        admin_user_role = UserRole(
            user_id=admin_user.id,
            role_id=admin_role.id
        )
        db.add(admin_user_role)
        db.commit()
        
        # Store password
        set_user_password("kevndzon@gmail.com", "Kevin22melgar@")
        
        print("✅ Admin user created successfully!")
        print(f"   Email: kevndzon@gmail.com")
        print(f"   Password: Kevin22melgar@")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 50)
    print("Creating Admin User")
    print("=" * 50)
    create_admin()
