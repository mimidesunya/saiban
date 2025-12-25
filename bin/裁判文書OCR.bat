@echo off
chcp 65001 > nul
cd /d "%~dp0"
cd ..

set "TARGET_FILE=%*"
if defined TARGET_FILE set "TARGET_FILE=%TARGET_FILE:"=%"

echo Target File: "%TARGET_FILE%"

if "%TARGET_FILE%"=="" (
    echo -------------------------------------------------------
    echo  PDFファイルまたはフォルダをこのファイルにドロップしてください。
    echo -------------------------------------------------------
    pause
    exit /b
)

REM .venvが存在するか確認し、あれば使用する。なければグローバルなpythonを使用する
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "src\ocr_court_doc.py" "%TARGET_FILE%"
) else (
    python3 "src\ocr_court_doc.py" "%TARGET_FILE%"
)

pause
