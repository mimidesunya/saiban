@echo off
cd /d "%~dp0"
cd ..

node src\convert_to_pdf.js %*

if %errorlevel% neq 0 pause
pause

