@echo off
REM ==========================================================================
REM  Payments Tracker - one-click start (Windows)
REM  Double-click this file. It:
REM    1. gets the latest code from GitHub (git pull)
REM    2. starts Docker Desktop if needed
REM    3. builds and starts the app + PostgreSQL
REM    4. applies database migrations
REM    5. opens your browser
REM ==========================================================================
setlocal EnableExtensions

REM "git pull" may update this very file while it runs, which confuses Windows.
REM So we run from a temporary copy and pass the project folder along.
if /i not "%~1"=="--run" (
  copy /y "%~f0" "%TEMP%\payments_tracker_start.bat" >nul
  "%TEMP%\payments_tracker_start.bat" --run "%~dp0."
)
title Payments Tracker - Start
cd /d "%~2"

echo.
echo  ==============================================
echo    Payments Tracker - starting up
echo  ==============================================
echo.

REM --- 0. Get the latest version of the code --------------------------------------
where git >nul 2>&1
if errorlevel 1 (
  echo  [!] Git is not installed - skipping the update check.
  goto :after_pull
)
if not exist ".git" (
  echo  [!] This folder was not cloned with Git - skipping the update check.
  goto :after_pull
)
echo  [..] Checking GitHub for updates...
git pull --ff-only
if errorlevel 1 (
  echo  [!] Could not update from GitHub - no internet, or files were changed locally.
  echo      Continuing with the version already on this computer.
) else (
  echo  [OK] Code is up to date.
)
for /f "delims=" %%V in ('git log -1 "--date=short" "--format=%%h  %%ad  %%s" 2^>nul') do echo       Version: %%V
:after_pull
echo.

REM --- 1. Is Docker installed? -------------------------------------------------
where docker >nul 2>&1
if errorlevel 1 (
  echo  [X] Docker Desktop is not installed.
  echo      Install it from https://www.docker.com/products/docker-desktop/
  echo      then run this file again.
  start "" https://www.docker.com/products/docker-desktop/
  goto :fail
)

REM --- 2. Is the Docker engine running? Start Docker Desktop if not. -----------
docker info >nul 2>&1
if not errorlevel 1 goto :docker_ready

echo  [..] Docker is not running - starting Docker Desktop...
if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
  start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
) else if exist "%LocalAppData%\Docker\Docker Desktop.exe" (
  start "" "%LocalAppData%\Docker\Docker Desktop.exe"
) else (
  echo  [!] Could not find Docker Desktop. Please start it manually.
)

set /a WAITED=0
:wait_docker
timeout /t 5 /nobreak >nul
set /a WAITED+=5
docker info >nul 2>&1
if not errorlevel 1 goto :docker_ready
if %WAITED% GEQ 180 (
  echo  [X] Docker did not start within 3 minutes. Open Docker Desktop, wait
  echo      until it says "Engine running", then run this file again.
  goto :fail
)
echo      still waiting for Docker... (%WAITED%s)
goto :wait_docker

:docker_ready
echo  [OK] Docker is running.

REM --- 3. Create .env on first run ---------------------------------------------
if not exist ".env" (
  copy /y ".env.example" ".env" >nul
  echo  [OK] Created .env from .env.example
)

set "PORT=8010"
for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
  if /i "%%A"=="APP_PORT" if not "%%B"=="" set "PORT=%%B"
)

REM --- 3b. Make sure no other program (e.g. another web app) owns the port --------
REM If our own container is already running, the port is ours - nothing to do.
set "OURS="
for /f %%I in ('docker compose ps -q --status running web 2^>nul') do set "OURS=1"
if defined OURS goto :port_ok

call :port_in_use %PORT%
if errorlevel 1 goto :port_ok

echo  [!] Port %PORT% is already used by another program on this computer.
set /a CANDIDATE=8010
:find_port
call :port_in_use %CANDIDATE%
if errorlevel 1 goto :found_port
set /a CANDIDATE+=1
if %CANDIDATE% GTR 8099 (
  echo  [X] Could not find a free port between 8010 and 8099.
  echo      Close the other program or set APP_PORT in .env, then try again.
  goto :fail
)
goto :find_port

:found_port
set "PORT=%CANDIDATE%"
findstr /b /c:"APP_PORT=" ".env" >nul 2>&1
if errorlevel 1 (
  >>".env" echo APP_PORT=%PORT%
) else (
  powershell -NoProfile -Command "(Get-Content '.env') -replace '^APP_PORT=.*','APP_PORT=%PORT%' | Set-Content '.env'"
)
echo  [OK] Using free port %PORT% instead (saved in .env).

:port_ok

REM --- 4. Build and start containers --------------------------------------------
echo  [..] Building and starting containers (first run can take a few minutes)...
docker compose up -d --build
if errorlevel 1 (
  echo  [X] docker compose failed. See the messages above.
  goto :fail
)

REM --- 5. Wait for the app to answer --------------------------------------------
echo  [..] Waiting for the app to be ready on http://localhost:%PORT% ...
set /a WAITED=0
:wait_app
timeout /t 3 /nobreak >nul
set /a WAITED+=3
curl -s "http://127.0.0.1:%PORT%/health/" 2>nul | findstr /c:"payments-tracker" >nul
if not errorlevel 1 goto :app_ready
if %WAITED% GEQ 180 (
  echo  [X] The app did not become ready. Showing the last log lines:
  docker compose logs --tail 40 web
  goto :fail
)
goto :wait_app

:app_ready
echo  [OK] App is running.

REM --- 6. Apply database migrations ----------------------------------------------
REM (The container also migrates on start-up; this makes sure and shows the result.)
echo  [..] Applying database migrations...
docker compose exec -T web python manage.py migrate --noinput
if errorlevel 1 (
  echo  [X] Database migration failed. Showing the last log lines:
  docker compose logs --tail 40 web
  goto :fail
)
echo  [OK] Database is up to date.
start "" "http://localhost:%PORT%/"

echo.
echo  ==============================================
echo    Payments Tracker is running
echo    Open:   http://localhost:%PORT%
echo.
echo    Demo logins (first run with SEED_DEMO_DATA=1):
echo      admin    / Admin@12345
echo      dr.mehta / Demo@12345
echo      dr.rao   / Demo@12345
echo.
echo    The app keeps running in the background.
echo    Use stop_app.bat to stop it.
echo  ==============================================
echo.
echo  You can close this window.
pause
exit /b 0

:fail
echo.
pause
exit /b 1

REM ---------------------------------------------------------------------------
REM :port_in_use <port>  -> errorlevel 0 if something is LISTENING on the port
:port_in_use
netstat -ano -p tcp | findstr /r /c:":%~1 .*LISTENING" >nul
exit /b %errorlevel%
