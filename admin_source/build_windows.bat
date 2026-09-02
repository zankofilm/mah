@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set APP_VERSION=7.6.20
set APP_FOLDER=JavanroodNeighborhoodManagement
set RELEASE_DIR=%CD%\release
set PORTABLE_NAME=JavanroodNeighborhoodManagement_%APP_VERSION%_Windows_x64_Portable.zip
set SETUP_NAME=JavanroodNeighborhoodManagement_Setup_%APP_VERSION%_Windows_x64.exe

echo ============================================================
echo   Javanrood Neighborhood Management - Windows Build %APP_VERSION%
echo ============================================================

where py >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python Launcher ^(py.exe^) was not found.
  echo Install 64-bit Python 3.11 from python.org and enable the launcher.
  goto :error
)

for /f "usebackq delims=" %%V in (`py -3.11 -c "import struct; print(struct.calcsize('P') * 8)" 2^>nul`) do set PY_BITS=%%V
if not "!PY_BITS!"=="64" (
  echo [ERROR] 64-bit Python 3.11 was not found.
  echo Install Python 3.11.9 x64 and ensure the Python Launcher is enabled.
  goto :error
)

for /f "usebackq delims=" %%V in (`py -3.11 -c "import sys; print(sys.version_info[:2] == (3, 11))" 2^>nul`) do set PY311_OK=%%V
if /I not "!PY311_OK!"=="True" (
  echo [ERROR] Python 3.11 is required.
  goto :error
)

echo [1/8] Preparing isolated build environment...
if not exist .venv-build py -3.11 -m venv .venv-build
if errorlevel 1 goto :error
call .venv-build\Scripts\activate.bat
if errorlevel 1 goto :error

python -m pip install --upgrade pip wheel setuptools
if errorlevel 1 goto :error
python -m pip install -r requirements-build.txt
if errorlevel 1 goto :error

echo [2/8] Running Windows release validation...
python windows_release_check.py
if errorlevel 1 goto :error

echo [3/8] Compiling Python sources...
python -m compileall -q .
if errorlevel 1 goto :error

echo [4/8] Running automated tests...
set JAVANROOD_PORTABLE=1
python -m unittest discover -s tests -p "test*.py"
if errorlevel 1 goto :error
set JAVANROOD_PORTABLE=

echo [5/8] Cleaning old build outputs...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "%RELEASE_DIR%" rmdir /s /q "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%"

echo [6/8] Building Windows executable with PyInstaller...
pyinstaller --noconfirm --clean javanrood.spec
if errorlevel 1 goto :error
if not exist "dist\%APP_FOLDER%\%APP_FOLDER%.exe" (
  echo [ERROR] Expected executable was not created.
  goto :error
)

echo [7/8] Creating Windows portable package...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Compress-Archive -Path 'dist\%APP_FOLDER%\*' -DestinationPath '%RELEASE_DIR%\%PORTABLE_NAME%' -Force"
if errorlevel 1 goto :error

set ISCC=
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe

if defined ISCC (
  echo [8/8] Building Windows Setup with Inno Setup...
  "%ISCC%" /DMyAppVersion=%APP_VERSION% installer\JavanroodSetup.iss
  if errorlevel 1 goto :error
  if exist "installer\output\%SETUP_NAME%" copy /y "installer\output\%SETUP_NAME%" "%RELEASE_DIR%\%SETUP_NAME%" >nul
) else (
  echo [8/8] Inno Setup 6 was not found. Portable package was created.
  echo Install Inno Setup 6 and run build_windows.bat again to also create Setup.exe.
)

for %%F in ("%RELEASE_DIR%\*.zip" "%RELEASE_DIR%\*.exe") do (
  if exist "%%~fF" powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "(Get-FileHash -Algorithm SHA256 '%%~fF').Hash + '  ' + '%%~nxF' | Out-File -Encoding ascii '%%~fF.sha256'"
)

echo.
echo ============================================================
echo BUILD COMPLETED SUCCESSFULLY
echo Output: %RELEASE_DIR%
echo ============================================================
explorer "%RELEASE_DIR%"
exit /b 0

:error
echo.
echo ============================================================
echo BUILD FAILED - no existing user data was modified.
echo ============================================================
pause
exit /b 1
