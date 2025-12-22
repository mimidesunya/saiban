@echo off
chcp 65001 > nul
cd /d "%~dp0"
cd ..

set "TARGET_FILE=%*"
if defined TARGET_FILE set "TARGET_FILE=%TARGET_FILE:"=%"

if "%TARGET_FILE%"=="" (
    echo -------------------------------------------------------
    echo  Markdownファイルまたはフォルダをこのファイルにドロップしてください。
    echo  ページ区切りマーカーを除去した _clean.md ファイルを作成します。
    echo -------------------------------------------------------
    pause
    exit /b
)

REM .venvが存在するか確認し、あれば使用する。なければグローバルなpythonを使用する
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "src\remove_page_breaks.py" "%TARGET_FILE%"
) else (
    python3 "src\remove_page_breaks.py" "%TARGET_FILE%"
)

pause
