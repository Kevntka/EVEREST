"""
Database Configuration for EVEREST Event Registration System
Using PostgreSQL with SQLAlchemy
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection settings
# Change 'postgres' password below to your actual PostgreSQL password
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:Kevin22melgar@localhost:5432/everest_db"  # Change 'admin' to your password
)

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    echo=True,  # Set to False in production
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


def get_db():
    """
    Dependency function to get database session
    Usage in FastAPI endpoints: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database - create all tables
    Call this on application startup
    """
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully")


def drop_db():
    """
    Drop all database tables
    WARNING: Use only in development!
    """
    Base.metadata.drop_all(bind=engine)
    print("⚠️ All database tables dropped")
