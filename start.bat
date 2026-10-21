@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM Create Python environment on first launch
if not exist ".venv\Scripts\activate.bat" (
    echo [INFO] Creating Python environment...
    uv venv --seed
    if errorlevel 1 (pause & exit /b 1)
)

call ".venv\Scripts\activate.bat"

REM Synchronize dependencies after requirements.txt changes (uv skips installed packages)
echo [INFO] Checking Python dependencies...
uv pip install -r requirements.txt
if errorlevel 1 (pause & exit /b 1)

REM Build Vue frontend
echo Building frontend...
pushd frontend
if not exist "node_modules" (
    call npm install
    if errorlevel 1 (popd & pause & exit /b 1)
)
call npm run build
if errorlevel 1 (popd & pause & exit /b 1)
popd

echo Open http://127.0.0.1:8766
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8766
pause