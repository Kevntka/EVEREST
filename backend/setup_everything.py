"""
Complete Setup Script for EVEREST
Creates database, tables, and admin user
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os

DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "everest_db"
DB_USER = "postgres"
DB_PASSWORD = "Kevin22melgar"

ADMIN_EMAIL = "kevndzon@gmail.com"
ADMIN_PASSWORD = "Kevin22melgar@"

def create_database():
    """Step 1: Create database"""
    print("=" * 60)
    print("STEP 1: Creating Database")
    print("=" * 60)
    
    try:
        # Connect to default postgres database
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database="postgres",
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
        exists = cursor.fetchone()
        
        if exists:
            print(f"✅ Database '{DB_NAME}' already exists!")
        else:
            cursor.execute(f"CREATE DATABASE {DB_NAME}")
            print(f"✅ Database '{DB_NAME}' created successfully!")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        return False

def create_tables():
    """Step 2: Create tables from schema.sql"""
    print("\n" + "=" * 60)
    print("STEP 2: Creating Tables")
    print("=" * 60)
    
    try:
        # Read schema.sql
        schema_path = os.path.join("database", "schema.sql")
        
        if not os.path.exists(schema_path):
            print(f"❌ Schema file not found: {schema_path}")
            return False
        
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        # Connect to everest_db
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        cursor = conn.cursor()
        
        # Execute schema
        cursor.execute(schema_sql)
        conn.commit()
        
        print("✅ Tables created successfully!")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return False

def create_admin():
    """Step 3: Create admin user"""
    print("\n" + "=" * 60)
    print("STEP 3: Creating Admin User")
    print("=" * 60)
    
    try:
        # Hash password first
        from auth.jwt_handler import hash_password
        hashed_password = hash_password(ADMIN_PASSWORD)
        
        # Also save to in-memory storage for compatibility
        from models.auth import set_user_password
        
        # Connect to database
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        cursor = conn.cursor()
        
        # Check if admin exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (ADMIN_EMAIL,))
        existing = cursor.fetchone()
        
        if existing:
            print(f"✅ Admin user already exists: {ADMIN_EMAIL}")
            # Update password
            cursor.execute("""
                UPDATE users 
                SET password = %s 
                WHERE email = %s
            """, (hashed_password, ADMIN_EMAIL))
            conn.commit()
            print(f"✅ Password updated!")
        else:
            # Create user with password
            cursor.execute("""
                INSERT INTO users (email, password, full_name, role) 
                VALUES (%s, %s, %s, %s) 
                RETURNING id
            """, (ADMIN_EMAIL, hashed_password, "Administrator", "admin"))
            
            user_id = cursor.fetchone()[0]
            conn.commit()
            
            print(f"✅ Admin user created successfully!")
        
        # Also set in models.auth for compatibility
        set_user_password(ADMIN_EMAIL, ADMIN_PASSWORD)
        
        print()
        print("=" * 60)
        print("ADMIN CREDENTIALS:")
        print("=" * 60)
        print(f"Email:    {ADMIN_EMAIL}")
        print(f"Password: {ADMIN_PASSWORD}")
        print("=" * 60)
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error creating admin: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run complete setup"""
    print("\n")
    print("🚀" * 30)
    print("EVEREST COMPLETE SETUP")
    print("🚀" * 30)
    print()
    
    # Step 1: Create database
    if not create_database():
        print("\n⚠️  Setup failed at Step 1")
        return
    
    # Step 2: Create tables
    if not create_tables():
        print("\n⚠️  Setup failed at Step 2")
        return
    
    # Step 3: Create admin
    if not create_admin():
        print("\n⚠️  Setup failed at Step 3")
        return
    
    print("\n")
    print("🎉" * 30)
    print("SETUP COMPLETE!")
    print("🎉" * 30)
    print()
    print("Next steps:")
    print("1. Start backend: python -m uvicorn main:app --reload")
    print("2. Start frontend: cd ../frontend/event-registration && ng serve")
    print("3. Login at: http://localhost:4200/login")
    print()

if __name__ == "__main__":
    main()
