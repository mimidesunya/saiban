@echo off
cd /d "%~dp0"
cd ..

set "TARGET_FILE=%~1"

if "%TARGET_FILE%"=="" (
    echo -------------------------------------------------------
    echo  PDFファイルまたはフォルダをこのファイルにドロップしてください。
    echo -------------------------------------------------------
    pause
    exit /b
)

REM .venvが存在するか確認し、あれば使用する。なければグローバルなpythonを使用する
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "src\ocr_doc.py" "%TARGET_FILE%"
) else (
    python "src\ocr_doc.py" "%TARGET_FILE%"
)

pause
