@echo off
setlocal EnableDelayedExpansion

REM ─────────────────────────────────────────────────────────────────
REM   FLASK APP SETUP & RUN UTILITY (No Colors)
REM ─────────────────────────────────────────────────────────────────

pushd "%~dp0"
echo.

echo ===============================================================
echo                 FLASK APP SETUP & RUN UTILITY                  
echo ===============================================================
echo.

REM 1) Check for Python
echo [INFO]  Checking for Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.7+ and retry.
    pause
    popd & exit /b 1
)
echo [OK]    Python is installed.
echo.

REM 2) Create virtual environment
echo [INFO]  Setting up virtual environment...
if not exist venv (
    python -m venv venv >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        popd & exit /b 1
    )
    echo [OK]    Virtual environment created.
) else (
    echo [WARN]  Virtual environment already exists.
)
echo.

REM 3) Activate venv
echo [INFO]  Activating virtual environment...
call "%~dp0venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    popd & exit /b 1
)
echo [OK]    Virtual environment activated.
echo.

REM 4) Upgrade pip & install dependencies
echo [INFO]  Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1
if errorlevel 1 (
    echo [WARN]  Could not upgrade pip, continuing...
) else (
    echo [OK]    Pip upgraded successfully.
)

echo [INFO]  Installing dependencies...
if not exist requirements.txt (
    echo [ERROR] requirements.txt not found.
    pause
    popd & exit /b 1
)
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    popd & exit /b 1
)
echo [OK]    Dependencies installed.
echo.

REM 5) Launch Flask server
if not exist app.py (
    echo [ERROR] app.py not found in %~dp0.
    pause
    popd & exit /b 1
)

echo [INFO]  Launching Flask server...
set "FLASK_APP=app.py"
set "FLASK_ENV=development"
start "Flask Server" cmd /c "python -m flask run --host=127.0.0.1 --port=5000"

REM 6) Wait for server to become available
echo [INFO]  Waiting for server on http://127.0.0.1:5000 ...

set /a COUNT=0
:WAIT_LOOP
    powershell -noprofile -command ^
        "try { Invoke-WebRequest 'http://127.0.0.1:5000' -UseBasicParsing -TimeoutSec 2 >$null; exit 0 } catch { exit 1 }"
    if errorlevel 1 (
        if %COUNT% GEQ 30 (
            echo [WARN]  Server not responding after 30s. Opening browser anyway.
            goto OPEN_BROWSER
        )
        set /a COUNT+=1
        timeout /t 1 >nul
        goto WAIT_LOOP
    )

:OPEN_BROWSER
echo [OK]    Server is up! Opening your default browser...
start "" "http://127.0.0.1:5000"

REM Cleanup & exit
popd
exit /b 0


