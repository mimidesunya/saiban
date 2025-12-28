@echo off
cd /d "%~dp0"
cd ..

node "src\ocr_merge_pages.js" %*

if %errorlevel% neq 0 pause
pause
