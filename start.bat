@echo off
chcp 65001 >nul 2>nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

:: ============================================================
:: Entry
:: ============================================================
if not exist "backend\requirements.txt" (
    echo [ERROR] Cannot find KnowAll_Studio project files.
    echo Current dir: %CD%
    echo Make sure start.bat is inside the KnowAll_Studio folder.
    goto END_ERROR
)

title KnowAll Studio
echo ============================================
echo   KnowAll Studio - One-Click Launcher
echo   %CD%
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Install from https://python.org
    goto END_ERROR
)

where node >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js not found. Install from https://nodejs.org
    goto END_ERROR
)

:: ============================================================
:: [1/2] Backend Python packages
:: ============================================================
echo [1/2] Backend :8000 ...
cd backend

if exist "data\deps_ok" goto BACKEND_DONE

:: Disk space check (needs ~3 GB for heavy ML packages)
python -c "import shutil,sys; sys.exit(0 if shutil.disk_usage('.').free // 1024**3 >= 3 else 1)"
if errorlevel 1 (
    echo [ERROR] Less than 3 GB disk space available. Need more room for ML packages.
    goto END_ERROR
)

if not exist "data" mkdir "data"
set "PIP_LOG=%~dp0data\pip_install.log"
set RETRY=1

:PIP_INSTALL
echo.
if !RETRY! EQU 1 (
    echo   [Attempt 1/3] Default PyPI ^(120s timeout^) ...
    pip install -r requirements.txt --default-timeout=300 --no-cache-dir --log="!PIP_LOG!" 2>&1
) else if !RETRY! EQU 2 (
    echo   [Attempt 2/3] Tsinghua mirror ...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --default-timeout=300 --no-cache-dir --log="!PIP_LOG!" 2>&1
) else (
    echo   [Attempt 3/3] Aliyun mirror ...
    pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple --default-timeout=300 --no-cache-dir --log="!PIP_LOG!" 2>&1
)

if not errorlevel 1 goto PIP_OK
set /a RETRY+=1
if !RETRY! LEQ 3 (
    echo   [WARN] Attempt failed. Retrying with a different source...
    ping -n 3 127.0.0.1 >nul
    goto PIP_INSTALL
)
goto PIP_FAILED

:PIP_FAILED
echo.
echo   [ERROR] All 3 pip install attempts failed.
echo   Full error log saved to: !PIP_LOG!
echo   Common fixes:
echo     1. Check your internet connection or proxy
echo     2. Open the log file above for details
echo     3. Try running manually: pip install -r requirements.txt
goto END_ERROR

:PIP_OK
echo ok > "data\deps_ok"
echo.
echo   Python packages installed successfully.

:BACKEND_DONE
cd /d "%~dp0"

:: ============================================================
:: [2/2] Frontend Node packages
:: ============================================================
echo.
echo [2/2] Frontend :5173 ...
cd frontend

if exist "node_modules" goto FRONTEND_DONE

echo   Installing Node packages - first run, please wait...
set NPM_RETRY=1

:NPM_INSTALL
echo.
echo   [Attempt !NPM_RETRY!/3]
call npm install --fetch-timeout=120000
if not errorlevel 1 goto NPM_OK
set /a NPM_RETRY+=1
if !NPM_RETRY! LEQ 3 (
    echo   [WARN] npm install failed, retrying...
    ping -n 3 127.0.0.1 >nul
    goto NPM_INSTALL
)
goto NPM_FAILED

:NPM_FAILED
echo   [ERROR] npm install failed after 3 attempts.
goto END_ERROR

:NPM_OK
echo.
echo   Node packages installed successfully.

:FRONTEND_DONE
cd /d "%~dp0"

:: ============================================================
:: Start services
:: ============================================================
echo.
echo Starting services...
echo   Backend  (hot-reload on) -> http://localhost:8000
echo   Frontend (HMR on)        -> http://localhost:5173
echo.
start "KnowAll-Backend" /D "%~dp0backend" cmd /k python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app
start "KnowAll-Frontend" /D "%~dp0frontend" cmd /k npm run dev

start "" /b powershell -NoProfile -WindowStyle Hidden -Command "$ok=$false; for ($i=0; $i -lt 60; $i++) { try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', 8000); $c.Close(); $ok=$true; break } catch { Start-Sleep 1 } }; if ($ok) { Start-Process 'http://localhost:5173' }"

echo.
echo   Backend  -> http://localhost:8000/docs
echo   Frontend -> http://localhost:5173
echo.
echo   Close CMD windows to stop all services.
echo   Browser opens automatically when ready.
echo.
pause
endlocal
exit /b 0

:: ============================================================
:: Error exit - always pause so the user can read the message
:: ============================================================
:END_ERROR
echo.
echo   Launcher aborted.
cd /d "%~dp0"
pause
endlocal
exit /b 1



