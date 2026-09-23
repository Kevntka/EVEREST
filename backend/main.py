"""
EVEREST Event Registration System - Backend API
FastAPI application with CORS enabled for Angular frontend
"""

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
import os

# Initialize FastAPI app
app = FastAPI(
    title="EVEREST API",
    description="Event Registration System API",
    version="1.0.0"
)

# Configure CORS for Angular frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)

# Configure paths
FRONTEND_PATH = os.path.join(os.path.dirname(__file__), "..", "frontend")
ASSETS_PATH = os.path.join(FRONTEND_PATH, "assets")

# Mount static files
app.mount("/assets", StaticFiles(directory=ASSETS_PATH), name="assets")


@app.get("/")
def root():
    """Serve main login page"""
    login_file = os.path.join(FRONTEND_PATH, "login.html")
    return FileResponse(login_file)


@app.get("/login")
def login_page():
    """Serve login page"""
    login_file = os.path.join(FRONTEND_PATH, "login.html")
    return FileResponse(login_file)
