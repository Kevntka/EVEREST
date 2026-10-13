"""
Database Configuration for EVEREST Event Registration System
Using PostgreSQL with SQLAlchemy
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from security.settings import DATABASE_URL, SQL_ECHO

# Up to 50 connections (PostgreSQL allows 100 by default). At most MAX_DB_REQUESTS API
# requests use the database at once (database/concurrency.py): fewer than the connections
# and no more than FastAPI's 40 worker threads, so requests never wait for a connection
# inside a worker thread (that deadlocked the server under load).
POOL_SIZE = 20
MAX_OVERFLOW = 30
MAX_DB_REQUESTS = 40

# DATABASE_URL comes only from backend/.env (no password in the code)
engine = create_engine(
    DATABASE_URL,
    echo=SQL_ECHO,  # SQL_ECHO=true in .env prints every query (off: parameters include password hashes)
    pool_pre_ping=True,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


async def get_db():
    """
    Dependency function to get database session
    Usage in FastAPI endpoints: db: Session = Depends(get_db)

    It is async on purpose: FastAPI then runs the cleanup (db.close(), which returns the
    connection to the pool) on the event loop instead of in a worker thread. As a sync
    generator, under load every one of the 40 worker threads could be waiting for a
    connection while the connections were held by finished requests waiting for a thread
    to close them: a deadlock that ended in 30-second pool timeouts and HTTP 500s
    (found by the 250-user load test). The routes still use the session normally.
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
