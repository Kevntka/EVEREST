@echo off
echo ========================================
echo Starting EVEREST Backend Server
echo ========================================
echo.
echo Using virtual environment...
echo.

REM Activate virtual environment and start server
call venv\Scripts\activate.bat
python -m uvicorn main:app --reload

pause
