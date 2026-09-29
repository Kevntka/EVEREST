"""
Quick SQL Import - Simplified version
Just run: python quick_import.py
"""

import psycopg2

# Database connection settings
# CHANGE THESE if your PostgreSQL has different settings
DB_USER = "postgres"
DB_PASSWORD = "postgres"  # Change this to your PostgreSQL password
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "everest_db"

def import_schema():
    """Import schema.sql file"""
    
    print("=" * 60)
    print("EVEREST Database Quick Import")
    print("=" * 60)
    print(f"Database: {DB_NAME}")
    print(f"Host: {DB_HOST}")
    print("=" * 60)
    
    # Ask for password if needed
    password = input(f"\nEnter PostgreSQL password for user '{DB_USER}' (or press Enter for '{DB_PASSWORD}'): ")
    if not password:
        password = DB_PASSWORD
    
    try:
        # Connect
        print("\n📡 Connecting to database...")
        conn = psycopg2.connect(
            user=DB_USER,
            password=password,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME
        )
        conn.autocommit = True
        cursor = conn.cursor()
        print("✅ Connected successfully!")
        
        # Read SQL file
        print("\n📄 Reading schema.sql...")
        with open('database/schema.sql', 'r', encoding='utf-8') as f:
            sql = f.read()
        
        # Execute
        print("⚙️  Executing SQL...")
        cursor.execute(sql)
        print("✅ Database schema created successfully!")
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM users;")
        user_count = cursor.fetchone()[0]
        print(f"\n✅ Verification: {user_count} user(s) found (should have 1 admin)")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("✅ Import completed successfully!")
        print("=" * 60)
        print("\nDefault Admin Account:")
        print("  Email: admin@everest.com")
        print("  Password: admin123")
        print("\nYou can now run the server:")
        print("  uvicorn main:app --reload")
        print("=" * 60)
        
    except psycopg2.OperationalError as e:
        print(f"\n❌ Connection Error: {e}")
        print("\n💡 Tips:")
        print("  1. Make sure PostgreSQL is running")
        print("  2. Check if database 'everest_db' exists:")
        print("     - Open pgAdmin")
        print("     - Or run: CREATE DATABASE everest_db;")
        print("  3. Verify your PostgreSQL password")
        print("  4. Edit DB_PASSWORD in this file if needed")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    import_schema()
