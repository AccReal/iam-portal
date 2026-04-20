@echo off
echo ========================================
echo   IAM System - Rebuild with Admin Rights
echo ========================================
echo.
echo This script will rebuild the Electron app
echo with administrator privileges to avoid
echo symbolic link errors.
echo.
pause

echo.
echo Deleting old build...
rmdir /s /q dist 2>nul

echo.
echo Building application...
call npm run build:win

echo.
echo ========================================
echo Build complete!
echo.
echo Application location:
echo dist\win-unpacked\IAM System.exe
echo.
echo Creating desktop shortcut...
powershell -ExecutionPolicy Bypass -File create-shortcut.ps1

echo.
echo Done! You can now run the application.
pause
