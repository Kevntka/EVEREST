"""
Delete student by email
"""

from database.config import get_db
from sqlalchemy import text

def delete_student(email):
    db = next(get_db())
    
    query = text("DELETE FROM users WHERE email = :email")
    
    try:
        result = db.execute(query, {"email": email})
        db.commit()
        print(f"✅ Deleted user with email: {email}")
        print(f"Rows affected: {result.rowcount}")
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # Delete juan dela crus
    delete_student("23-12312")
