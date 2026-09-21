@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python virtual environment for VYOMIX...
    py -3 -m venv .venv
    if errorlevel 1 (
        echo Failed to create .venv. Please install Python 3.10+ and ensure the "py" command is available.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"

start "VYOMIX AUTH" /min cmd /c "python -m uvicorn backend.main:app --reload --port 8000"
start "VYOMIX ML" /min cmd /c "python -m uvicorn backend.main2:app --reload --port 8003"

timeout /t 5 /nobreak >nul
start "" "%~dp0index.html"
