@echo off
setlocal
cd /d "%~dp0"
echo Installing Smart Organizer...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\Install-SmartOrganizer.ps1"
if errorlevel 1 (
  echo.
  echo Installation failed. See the message above.
  pause
  exit /b 1
)
echo.
echo Smart Organizer installed successfully.
pause
