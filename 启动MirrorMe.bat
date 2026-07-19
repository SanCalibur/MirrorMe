@echo off
setlocal

cd /d "%~dp0"
set "PYTHON=%CD%\.venv\Scripts\python.exe"
set "URL=http://127.0.0.1:8765/capture"

if not exist "%PYTHON%" (
    echo MirrorMe virtual environment was not found.
    echo Expected: %PYTHON%
    echo Please run the project setup first.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue) { exit 0 }; Start-Process -FilePath '%PYTHON%' -ArgumentList '-m','mirrorme.cli','serve','--host','127.0.0.1','--port','8765' -WorkingDirectory '%CD%' -WindowStyle Hidden; Start-Sleep -Seconds 2; exit 1"
if errorlevel 1 (
    echo MirrorMe server started.
) else (
    echo MirrorMe server is already running.
)

start "" "%URL%"
endlocal
