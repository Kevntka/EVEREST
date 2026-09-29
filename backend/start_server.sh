#!/bin/bash
echo "========================================"
echo "Starting EVEREST Backend Server"
echo "========================================"
echo ""
echo "Using virtual environment..."
echo ""

# Activate virtual environment and start server
source venv/Scripts/activate
python -m uvicorn main:app --reload
