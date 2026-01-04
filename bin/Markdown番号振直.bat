@echo off
cd /d "%~dp0"
cd ..

node src\renumber_markdown.js %*

if %errorlevel% neq 0 pause
pause
