@echo off
echo ========================================
echo   Installing IAM Portal + Demo Apps
echo ========================================
echo.

echo [1/5] Installing IAM Portal (Electron shell)...
pushd ..\electron
call npm install
popd

echo.
echo [2/5] Installing CRM System...
cd crm-app
call npm install
cd ..

echo.
echo [3/5] Installing Corporate Mail...
cd mail-app
call npm install
cd ..

echo.
echo [4/5] Installing 1C Accounting...
cd 1c-app
call npm install
cd ..

echo.
echo [5/5] Installing Warehouse System...
cd warehouse-app
call npm install
cd ..

echo.
echo ========================================
echo Installation complete!
echo.
echo To build all applications, run:
echo   build-all.bat
echo.
echo To start individual apps (dev mode):
echo   cd ..\electron ^&^& npm start   (IAM Portal)
echo   cd crm-app      ^&^& npm start
echo   cd mail-app     ^&^& npm start
echo   cd 1c-app       ^&^& npm start
echo   cd warehouse-app ^&^& npm start
echo ========================================
pause
