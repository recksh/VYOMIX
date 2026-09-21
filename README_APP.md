# VYOMIX Desktop App

## 1) Install Node.js
Download and install Node.js from https://nodejs.org/

## 2) Install project dependencies
Open PowerShell in this folder and run:

```powershell
npm install
```

## 3) Run the desktop app during development
```powershell
npm start
```

The development launcher requires the backend virtual environment. For normal use, install the Windows installer from the `dist` folder; the installed desktop app starts both backend services automatically.

## 4) Build the Windows installer
```powershell
npx electron-builder
```

This creates an installer in the `dist` folder.

## 5) Backend services during development
The packaged desktop app starts these automatically. When running from source, they can be started manually:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
.\.venv\Scripts\python.exe -m uvicorn backend.main2:app --reload --port 8003
```
