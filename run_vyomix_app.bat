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

if not exist ".venv\Scripts\python.exe" (
    echo Python virtual environment is still missing.
    pause
    exit /b 1
)

taskkill /FI "WINDOWTITLE eq VYOMIX AUTH*" /T /F >nul 2>nul
taskkill /FI "WINDOWTITLE eq VYOMIX ML*" /T /F >nul 2>nul

start "VYOMIX AUTH" /D "%~dp0" cmd /k ".venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000"
start "VYOMIX ML" /D "%~dp0" cmd /k ".venv\Scripts\python.exe -m uvicorn backend.main2:app --port 8003"

echo Waiting for VYOMIX services...
set /a attempts=0
:wait_for_services
set /a attempts+=1
powershell -NoProfile -ExecutionPolicy Bypass -Command "$auth=(try { (Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/ -TimeoutSec 1).StatusCode -eq 200 } catch { $false }); $ml=(try { (Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8003/ -TimeoutSec 1).StatusCode -eq 200 } catch { $false }); if ($auth -and $ml) { exit 0 } else { exit 1 }"
if not errorlevel 1 goto services_ready
if %attempts% GEQ 20 goto services_failed
timeout /t 1 /nobreak >nul
goto wait_for_services

:services_failed
echo VYOMIX services did not start. Check the AUTH and ML windows for errors.
pause
exit /b 1

:services_ready
echo Services are ready.

where npm >nul 2>nul
if errorlevel 1 (
    echo Node.js is not installed.
    echo Download it from: https://nodejs.org/
    pause
    exit /b 1
)

npm start
