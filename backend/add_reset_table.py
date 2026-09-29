"""
Add password_reset_tokens table to database
"""

from database.config import get_db
from sqlalchemy import text

def add_reset_table():
    db = next(get_db())
    
    query = text("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token VARCHAR(255) UNIQUE NOT NULL,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            used BOOLEAN DEFAULT FALSE
        );
    """)
    
    try:
        db.execute(query)
        db.commit()
        print("✅ password_reset_tokens table created successfully!")
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    add_reset_table()
