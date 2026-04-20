@echo off
echo ========================================
echo Rebuilding all demo applications...
echo ========================================
echo.

cd crm-app
echo [1/4] Building CRM System...
call npm run build
cd ..

cd mail-app
echo [2/4] Building Mail App...
call npm run build
cd ..

cd 1c-app
echo [3/4] Building 1C App...
call npm run build
cd ..

cd warehouse-app
echo [4/4] Building Warehouse App...
call npm run build
cd ..

echo.
echo ========================================
echo All applications rebuilt successfully!
echo ========================================
echo.
echo Next steps:
echo 1. Run: powershell -ExecutionPolicy Bypass -File create-shortcuts-fixed.ps1
echo 2. Start Docker: docker-compose up -d
echo 3. Open IAM System from desktop
echo 4. Login and click on any app in dashboard
echo ========================================
pause
