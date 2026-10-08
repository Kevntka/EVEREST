from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
# from api.routes import router as memory_router  # In-memory routes (not used anymore)
from api.routes_db import router as db_router  # Database routes (ACTIVE)
from pathlib import Path
from security.settings import ALLOWED_ORIGINS, ENABLE_API_DOCS
from security.csrf import CSRFMiddleware
from security.headers import SecurityHeadersMiddleware
from security.rate_limit import RateLimitMiddleware
from security.errors import ServerErrorMiddleware

app = FastAPI(
    title="EVEREST Event Registration API",
    description="Backend API for event registration system",
    version="2.0.0",
    docs_url="/docs" if ENABLE_API_DOCS else None,
    redoc_url="/redoc" if ENABLE_API_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_API_DOCS else None,
)

# Middleware runs from the last one added to the first. CORS is added last so it
# wraps everything: even a 403 (CSRF) or 429 (rate limit) carries the CORS headers
# the browser needs to show the error message. ServerErrorMiddleware is added first
# (innermost) so an unexpected error becomes a JSON 500 that still gets CORS headers.
app.add_middleware(ServerErrorMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)

@app.on_event("startup")
def add_missing_columns():
    """Columns added after schema.sql was first run (idempotent; keeps existing data)."""
    from sqlalchemy import text
    from database.config import engine
    with engine.begin() as conn:
        # Organizer self-registration stores the Employment ID until the email is verified
        conn.execute(text("ALTER TABLE pending_registrations ADD COLUMN IF NOT EXISTS employment_id VARCHAR(50)"))


# Include database routes (PostgreSQL) - MUST BE BEFORE MOUNTS
app.include_router(db_router, prefix="/api")

# Create uploads directory if it doesn't exist
Path("uploads/events").mkdir(parents=True, exist_ok=True)

# Mount static files for uploads
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "EVEREST Event Registration API",
        "version": "2.0.0",
        "mode": "PostgreSQL Database",
        "status": "running"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
