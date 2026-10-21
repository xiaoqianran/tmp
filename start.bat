@echo off
cd /d "%~dp0"
if not exist "frontend\dist\index.html" (
    echo Building local frontend...
    pushd frontend
    call npm install
    if errorlevel 1 (popd & pause & exit /b 1)
    call npm run build
    if errorlevel 1 (popd & pause & exit /b 1)
    popd
)
echo Open http://127.0.0.1:8767
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
pause
