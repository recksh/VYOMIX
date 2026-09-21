$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root '.venv\Scripts\python.exe'
$app = Join-Path $root 'dist\win-unpacked\VYOMIX.exe'

if (-not (Test-Path $python)) {
    Write-Host 'Creating missing Python virtual environment...'
    & py -3 -m venv (Join-Path $root '.venv')
    if (-not (Test-Path $python)) {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show('Python virtual environment could not be created. Please install Python 3.10+ and try again.', 'VYOMIX Startup Error')
        exit 1
    }
}

if (-not (Test-Path $app)) {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show('VYOMIX is not installed correctly. Please rebuild the desktop app.', 'VYOMIX')
    exit 1
}

$auth = Start-Process -FilePath $python -ArgumentList '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8000' -WorkingDirectory $root -WindowStyle Hidden -PassThru
$ml = Start-Process -FilePath $python -ArgumentList '-m', 'uvicorn', 'backend.main2:app', '--host', '127.0.0.1', '--port', '8003' -WorkingDirectory $root -WindowStyle Hidden -PassThru

try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $authResponse = Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/' -TimeoutSec 1
            $mlResponse = Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8003/' -TimeoutSec 1
            if ($authResponse.StatusCode -eq 200 -and $mlResponse.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }

    if (-not $ready) {
        throw 'The VYOMIX services did not start.'
    }

    $desktopApp = Start-Process -FilePath $app -WorkingDirectory (Split-Path $app) -PassThru
    Wait-Process -Id $desktopApp.Id
} catch {
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show($_.Exception.Message, 'VYOMIX Startup Error')
} finally {
    Stop-Process -Id $auth.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $ml.Id -Force -ErrorAction SilentlyContinue
}