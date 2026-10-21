@echo off
cd /d "%~dp0"
echo Building Vue frontend...
pushd frontend
if not exist "node_modules\vite\bin\vite.js" (
    call npm install
    if errorlevel 1 (popd & pause & exit /b 1)
)
call npm run build
if errorlevel 1 (popd & pause & exit /b 1)
popd
echo Open http://127.0.0.1:8765
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
pause
