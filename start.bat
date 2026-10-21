@echo off
cd /d "%~dp0"

REM 激活虚拟环境
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else (
    echo [ERROR] 未找到 .venv 虚拟环境
    pause
    exit /b 1
)

REM 每次都构建前端
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
