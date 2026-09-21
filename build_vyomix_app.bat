@echo off
cd /d "%~dp0"

where npm >nul 2>nul
if errorlevel 1 (
    echo Node.js is not installed.
    echo Download it from: https://nodejs.org/
    pause
    exit /b 1
)

npm install
npx electron-builder

echo.
echo Windows installer created in the dist folder.
pause
