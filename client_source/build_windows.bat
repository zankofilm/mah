@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set APP_VERSION=1.0.0
set APP_FOLDER=JavanroodCommitteeClient
set RELEASE_DIR=%CD%\release

echo ============================================================
echo   Javanrood Committee Client - Windows Build %APP_VERSION%
echo ============================================================

where py >nul 2>&1
if errorlevel 1 goto :error
if not exist .venv-build py -3.11 -m venv .venv-build
if errorlevel 1 goto :error
call .venv-build\Scripts\activate.bat
python -m pip install --upgrade pip wheel setuptools
if errorlevel 1 goto :error
python -m pip install -r requirements-build.txt
if errorlevel 1 goto :error
python windows_release_check.py
if errorlevel 1 goto :error
python -m compileall -q .
if errorlevel 1 goto :error
python -m unittest discover -s tests -p "test*.py"
if errorlevel 1 goto :error
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "%RELEASE_DIR%" rmdir /s /q "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%"
pyinstaller --noconfirm --clean client.spec
if errorlevel 1 goto :error
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\%APP_FOLDER%\*' -DestinationPath '%RELEASE_DIR%\JavanroodCommitteeClient_%APP_VERSION%_Windows_x64_Portable.zip' -Force"
if errorlevel 1 goto :error
powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-FileHash -Algorithm SHA256 '%RELEASE_DIR%\JavanroodCommitteeClient_%APP_VERSION%_Windows_x64_Portable.zip').Hash + '  JavanroodCommitteeClient_%APP_VERSION%_Windows_x64_Portable.zip' | Out-File -Encoding ascii '%RELEASE_DIR%\JavanroodCommitteeClient_%APP_VERSION%_Windows_x64_Portable.zip.sha256'"
echo BUILD COMPLETED: %RELEASE_DIR%
exit /b 0
:error
echo BUILD FAILED
pause
exit /b 1
