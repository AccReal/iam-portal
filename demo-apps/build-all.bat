@echo off
echo ========================================
echo   Building IAM Portal + Demo Applications
echo ========================================
echo.
echo This will build the IAM Portal shell and all 4 demo apps.
echo Each build may show some warnings - this is normal.
echo.
pause

echo.
echo [1/5] Building IAM Portal...
pushd ..\electron
call npm run build:win
popd

echo.
echo [2/5] Building CRM System...
cd crm-app
call npm run build:win
cd ..

echo.
echo [3/5] Building Corporate Mail...
cd mail-app
call npm run build:win
cd ..

echo.
echo [4/5] Building 1C Accounting...
cd 1c-app
call npm run build:win
cd ..

echo.
echo [5/5] Building Warehouse System...
cd warehouse-app
call npm run build:win
cd ..

echo.
echo ========================================
echo Build complete!
echo.
echo Executable files location:
echo   ..\electron\dist\win-unpacked\IAM System.exe
echo   crm-app\dist\win-unpacked\CRM Система.exe
echo   mail-app\dist\win-unpacked\Корпоративная почта.exe
echo   1c-app\dist\win-unpacked\1С Бухгалтерия.exe
echo   warehouse-app\dist\win-unpacked\Склад.exe
echo.
echo Next step: run create-all-shortcuts.ps1 to put icons on desktop.
echo ========================================
pause
