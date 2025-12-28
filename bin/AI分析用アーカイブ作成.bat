@echo off
cd /d "%~dp0"
cd ..

node src\archive_for_ai.js %*

if %errorlevel% neq 0 pause
pause
