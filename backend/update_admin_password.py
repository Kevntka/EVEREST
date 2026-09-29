"""
Update Admin Password
Updates the admin user credentials directly in the database
"""

from models.auth import set_user_password
import psycopg2

def update_admin_password():
    """Update admin password to Kevin22melgar@"""
    
    # Database connection
    DB_HOST = "localhost"
    DB_PORT = "5432"
    DB_NAME = "everest_db"
    DB_USER = "postgres"
    DB_PASSWORD = "Kevin22melgar"
    
    ADMIN_EMAIL = "kevndzon@gmail.com"
    ADMIN_PASSWORD = "Kevin22melgar@"
    
    try:
        # Connect to database
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        cursor = conn.cursor()
        
        # Check if admin user exists
        cursor.execute(
            "SELECT id, full_name FROM users WHERE email = %s",
            (ADMIN_EMAIL,)
        )
        
        result = cursor.fetchone()
        
        if result:
            print(f"✅ Found admin user: {result[1]} ({ADMIN_EMAIL})")
            
            # Update password using auth module
            set_user_password(ADMIN_EMAIL, ADMIN_PASSWORD)
            
            print(f"✅ Password updated successfully!")
            print()
            print("=" * 50)
            print("ADMIN CREDENTIALS:")
            print("=" * 50)
            print(f"Email:    {ADMIN_EMAIL}")
            print(f"Password: {ADMIN_PASSWORD}")
            print("=" * 50)
            
        else:
            print(f"⚠️  Admin user not found with email: {ADMIN_EMAIL}")
            print()
            print("Creating new admin user...")
            
            # Create admin user
            cursor.execute(
                """
                INSERT INTO users (email, full_name) 
                VALUES (%s, %s) 
                RETURNING id
                """,
                (ADMIN_EMAIL, "Administrator")
            )
            
            user_id = cursor.fetchone()[0]
            
            # Get Admin role ID
            cursor.execute(
                "SELECT id FROM roles WHERE role_name = 'Admin'"
            )
            
            role_result = cursor.fetchone()
            if not role_result:
                print("❌ Admin role not found in database!")
                print("Please make sure schema.sql has been imported.")
                return False
            
            role_id = role_result[0]
            
            # Create user_role
            cursor.execute(
                """
                INSERT INTO user_roles (user_id, role_id) 
                VALUES (%s, %s)
                """,
                (user_id, role_id)
            )
            
            conn.commit()
            
            # Set password
            set_user_password(ADMIN_EMAIL, ADMIN_PASSWORD)
            
            print(f"✅ Admin user created successfully!")
            print()
            print("=" * 50)
            print("ADMIN CREDENTIALS:")
            print("=" * 50)
            print(f"Email:    {ADMIN_EMAIL}")
            print(f"Password: {ADMIN_PASSWORD}")
            print("=" * 50)
        
        cursor.close()
        conn.close()
        
        return True
        
    except psycopg2.OperationalError as e:
        print(f"❌ Database connection error: {e}")
        print()
        print("Please check:")
        print("1. PostgreSQL is running")
        print("2. Database 'everest_db' exists")
        print("3. Connection details are correct")
        return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("UPDATING ADMIN PASSWORD")
    print("=" * 50)
    print()
    
    if update_admin_password():
        print()
        print("🎉 Done! You can now login with the new credentials.")
    else:
        print()
        print("⚠️  Update failed. Please check the errors above.")
