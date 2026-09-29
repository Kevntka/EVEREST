"""
Import SQL file into PostgreSQL database
Place your .sql file in backend/database/ folder
"""

import os
import sys
from dotenv import load_dotenv
import psycopg2

# Load environment variables
load_dotenv()

# Database connection settings
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/everest_db"
)

def parse_database_url(url):
    """Parse DATABASE_URL into connection parameters"""
    
    url = url.replace('postgresql://', '')
    
    if '@' in url:
        auth, location = url.split('@')
        user, password = auth.split(':')
        host_port, database = location.split('/')
        host, port = host_port.split(':') if ':' in host_port else (host_port, '5432')
    else:
        return None
    
    return {
        'user': user,
        'password': password,
        'host': host,
        'port': port,
        'database': database
    }


def import_sql_file(sql_file_path):
    """Import SQL file into database"""
    
    if not os.path.exists(sql_file_path):
        print(f"❌ SQL file not found: {sql_file_path}")
        return False
    
    # Parse connection parameters
    conn_params = parse_database_url(DATABASE_URL)
    if not conn_params:
        print("❌ Invalid DATABASE_URL format")
        return False
    
    print("=" * 50)
    print("SQL File Import")
    print("=" * 50)
    print(f"Database: {conn_params['database']}")
    print(f"Host: {conn_params['host']}")
    print(f"SQL File: {sql_file_path}")
    print("=" * 50)
    
    try:
        # Connect to database
        print("\n📡 Connecting to database...")
        conn = psycopg2.connect(
            user=conn_params['user'],
            password=conn_params['password'],
            host=conn_params['host'],
            port=conn_params['port'],
            database=conn_params['database']
        )
        conn.autocommit = True
        cursor = conn.cursor()
        print("✅ Connected successfully")
        
        # Read SQL file
        print(f"\n📄 Reading SQL file: {os.path.basename(sql_file_path)}")
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # Execute SQL
        print("⚙️  Executing SQL...")
        cursor.execute(sql_script)
        print("✅ SQL executed successfully")
        
        # Close connection
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 50)
        print("✅ Import completed successfully!")
        print("=" * 50)
        return True
        
    except psycopg2.Error as e:
        print(f"\n❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def main():
    """Main function"""
    
    # Default SQL file path
    sql_file = "backend/database/schema.sql"
    
    # Check if custom path provided
    if len(sys.argv) > 1:
        sql_file = sys.argv[1]
    
    # Check if file exists
    if not os.path.exists(sql_file):
        print("=" * 50)
        print("SQL File Not Found")
        print("=" * 50)
        print(f"Looking for: {sql_file}")
        print("\n💡 Usage:")
        print("   python import_sql.py backend/database/schema.sql")
        print("\nOr place your SQL file at:")
        print("   backend/database/schema.sql")
        print("And run:")
        print("   python import_sql.py")
        return
    
    # Import SQL file
    success = import_sql_file(sql_file)
    
    if success:
        print("\n🚀 You can now run the server:")
        print("   uvicorn main:app --reload")
    else:
        print("\n⚠️  Import failed. Please check the error messages above.")


if __name__ == "__main__":
    main()
