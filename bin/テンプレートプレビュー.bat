@echo off
chcp 65001 > nul
cd /d "%~dp0"
cd ..

echo テンプレートプレビューを実行します...

REM .venvが存在するか確認し、あれば使用する。なければグローバルなpythonを使用する
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "src\preview_template.py"
) else (
    python "src\preview_template.py"
)
