@echo off
rem Single-click entry point for the complete Windows EXE + Setup build.
call "%~dp0build_windows.bat"
exit /b %errorlevel%
