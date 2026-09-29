"""
Setup script to initialize PostgreSQL database for EVEREST
Adds missing columns to events table
"""

import psycopg2
from psycopg2 import sql
import os
from dotenv import load_dotenv

load_dotenv()

# Database connection parameters
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "everest_db"
DB_USER = "postgres"
DB_PASSWORD = "Kevin22melgar"

def setup_database():
    """Setup database with required columns"""
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("✅ Connected to PostgreSQL database")
        
        # Add event_time column if it doesn't exist
        cursor.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='events' AND column_name='event_time') THEN
                    ALTER TABLE events ADD COLUMN event_time TIME;
                    RAISE NOTICE 'Added event_time column';
                END IF;
            END $$;
        """)
        
        # Add cover_photo column if it doesn't exist
        cursor.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='events' AND column_name='cover_photo') THEN
                    ALTER TABLE events ADD COLUMN cover_photo TEXT;
                    RAISE NOTICE 'Added cover_photo column';
                END IF;
            END $$;
        """)
        
        # Rename columns if needed
        cursor.execute("""
            DO $$ 
            BEGIN
                -- Check if event_name exists
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='events' AND column_name='event_name') THEN
                    ALTER TABLE events RENAME COLUMN title TO event_name;
                    RAISE NOTICE 'Renamed title to event_name';
                END IF;
            EXCEPTION
                WHEN undefined_column THEN
                    RAISE NOTICE 'Column already has correct name';
            END $$;
        """)
        
        print("✅ Database schema updated successfully!")
        print("\n📋 Current events table columns:")
        
        # Show current columns
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'events'
            ORDER BY ordinal_position
        """)
        
        for row in cursor.fetchall():
            print(f"   - {row[0]}: {row[1]}")
        
        cursor.close()
        conn.close()
        
        print("\n✅ Database is ready for use!")
        
    except psycopg2.OperationalError as e:
        print(f"❌ Database connection error: {e}")
        print("\nPlease check:")
        print("1. PostgreSQL is running")
        print("2. Database 'everest_db' exists")
        print("3. Password is correct")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 Setting up EVEREST database...")
    print(f"📍 Database: {DB_NAME}")
    print(f"📍 Host: {DB_HOST}:{DB_PORT}")
    print()
    
    if setup_database():
        print("\n🎉 Setup complete! You can now start the backend server.")
    else:
        print("\n⚠️  Setup failed. Please fix the errors and try again.")
