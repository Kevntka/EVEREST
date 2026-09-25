"""
Database Setup Script
Run this to create database tables and add initial admin user
"""

from database.config import init_db, drop_db, SessionLocal
from models.user import User, UserRole

def create_admin_user():
    """Create default admin user"""
    db = SessionLocal()
    try:
        # Check if admin exists
        existing_admin = db.query(User).filter(
            User.email == "admin@everest.com"
        ).first()
        
        if existing_admin:
            print("⚠️  Admin user already exists")
            return
        
        # Create admin user
        admin = User(
            email="admin@everest.com",
            password="admin123",  # Change this in production!
            full_name="Administrator",
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin)
        db.commit()
        print("✅ Admin user created successfully")
        print("   Email: admin@everest.com")
        print("   Password: admin123")
        print("   ⚠️  Please change the password in production!")
        
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        db.rollback()
    finally:
        db.close()


def main():
    """Main setup function"""
    print("=" * 50)
    print("EVEREST Database Setup")
    print("=" * 50)
    
    # Ask for confirmation
    print("\n⚠️  This will create/recreate database tables")
    response = input("Do you want to continue? (yes/no): ")
    
    if response.lower() != 'yes':
        print("Setup cancelled")
        return
    
    # Initialize database
    print("\n1. Initializing database tables...")
    try:
        init_db()
        print("✅ Database tables created")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return
    
    # Create admin user
    print("\n2. Creating admin user...")
    create_admin_user()
    
    print("\n" + "=" * 50)
    print("✅ Database setup complete!")
    print("=" * 50)
    print("\nYou can now run the server:")
    print("  uvicorn main:app --reload")


if __name__ == "__main__":
    main()
