from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
# from api.routes import router as memory_router  # In-memory routes (not used anymore)
from api.routes_db import router as db_router  # Database routes (ACTIVE)
from pathlib import Path

app = FastAPI(
    title="EVEREST Event Registration API",
    description="Backend API for event registration system",
    version="2.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://127.0.0.1:4200"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

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
