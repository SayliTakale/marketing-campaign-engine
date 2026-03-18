@echo off
echo ========================================
echo Starting Marketing Analytics Dashboard
echo ========================================
echo.
echo Opening dashboard at http://localhost:8000
echo.
echo Press Ctrl+C to stop the server
echo.

cd /d "%~dp0"
start http://localhost:8000/dashboard-professional.html
python -m http.server 8000