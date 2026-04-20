@echo off
echo ========================================
echo   IAM System - Complete Demo Setup
echo ========================================
echo.
echo This script will:
echo 1. Start Docker containers
echo 2. Install demo apps dependencies
echo 3. Build all demo applications
echo.
echo Make sure Docker Desktop is running!
echo.
pause

echo.
echo [1/3] Starting Docker containers...
docker-compose up -d

echo.
echo Waiting for services to start (30 seconds)...
timeout /t 30 /nobreak

echo.
echo [2/3] Installing demo apps dependencies...
cd demo-apps
call install-all.bat

echo.
echo [3/3] Building demo applications...
call build-all.bat

cd ..

echo.
echo ========================================
echo Setup complete!
echo.
echo Applications ready:
echo   1. IAM System: electron\dist\win-unpacked\IAM System.exe
echo   2. CRM: demo-apps\crm-app\dist\win-unpacked\CRM Система.exe
echo   3. Mail: demo-apps\mail-app\dist\win-unpacked\Корпоративная почта.exe
echo   4. 1C: demo-apps\1c-app\dist\win-unpacked\1С Бухгалтерия.exe
echo   5. Warehouse: demo-apps\warehouse-app\dist\win-unpacked\Склад.exe
echo.
echo Web interfaces:
echo   Frontend: http://localhost:3000
echo   Backend API: http://localhost:8000/docs
echo.
echo Test users:
echo   admin@company.ru / Test123456!@
echo   marina@company.ru / Test123456!@
echo   petr@company.ru / Test123456!@
echo   olga@company.ru / Test123456!@
echo.
echo See DEMO_APPS_GUIDE.md for demo scenarios
echo ========================================
pause
