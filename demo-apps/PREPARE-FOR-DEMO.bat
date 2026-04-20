@echo off
echo ========================================
echo   Prepare for Realistic Demo
echo ========================================
echo.
echo This will:
echo 1. Install dependencies
echo 2. Build all applications
echo 3. Create desktop shortcuts
echo 4. (Optional) Create simple icons
echo.
pause

echo.
echo [1/4] Installing dependencies...
call install-all.bat

echo.
echo [2/4] Building applications...
call build-all.bat

echo.
echo [3/4] Creating desktop shortcuts...
powershell -ExecutionPolicy Bypass -File create-all-shortcuts.ps1

echo.
echo [4/4] Do you want to create simple colored icons? (y/n)
set /p CREATE_ICONS="Create icons? (y/n): "

if /i "%CREATE_ICONS%"=="y" (
    echo.
    echo Creating icons...
    python create-simple-icons.py
    echo.
    echo Icons created! You may want to rebuild apps to use new icons:
    echo   cd crm-app ^&^& npm run build:win
    echo   cd mail-app ^&^& npm run build:win
    echo   cd 1c-app ^&^& npm run build:win
    echo   cd warehouse-app ^&^& npm run build:win
)

echo.
echo ========================================
echo Preparation complete!
echo.
echo On your desktop you should now see:
echo   - CRM Система
echo   - Корпоративная почта
echo   - 1С Бухгалтерия
echo   - Склад
echo.
echo Demo scenario:
echo 1. Double-click any application icon
echo 2. It will open IAM System login
echo 3. Login as admin@company.ru / Test123456!@
echo 4. Application opens automatically
echo 5. All other apps work without re-login!
echo.
echo See REALISTIC-DEMO-SCENARIO.md for full script
echo ========================================
pause
