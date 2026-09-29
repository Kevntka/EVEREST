"""
Check actual database table structure
"""

from database.config import get_db
from sqlalchemy import text

def main():
    print("\n" + "="*80)
    print(" CHECKING DATABASE TABLE STRUCTURE ".center(80, "="))
    print("="*80 + "\n")
    
    db = next(get_db())
    
    # Check users table columns
    print("📋 USERS TABLE COLUMNS:")
    print("-" * 80)
    
    result = db.execute(text("""
        SELECT column_name, data_type, character_maximum_length
        FROM information_schema.columns
        WHERE table_name = 'users'
        ORDER BY ordinal_position
    """))
    
    for row in result:
        col_name = row[0]
        data_type = row[1]
        max_length = row[2] if row[2] else ""
        print(f"  {col_name:<20} {data_type:<20} {max_length}")
    
    # Check if role column exists
    print("\n" + "-" * 80)
    role_check = db.execute(text("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name = 'role'
        )
    """)).scalar()
    
    print(f"\n✓ 'role' column exists: {role_check}")
    
    # Try to query users with role
    print("\n📊 TESTING QUERY:")
    print("-" * 80)
    try:
        result = db.execute(text("SELECT id, full_name, email, role FROM users LIMIT 3"))
        print("\n✅ Query successful! Sample data:")
        for row in result:
            print(f"  ID {row[0]}: {row[1]} ({row[3]})")
    except Exception as e:
        print(f"\n❌ Query failed: {e}")
    
    print("\n" + "="*80)
    db.close()

if __name__ == "__main__":
    main()
