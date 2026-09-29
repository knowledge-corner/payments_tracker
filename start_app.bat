@echo off
REM ==========================================================================
REM  Payments Tracker - one-click start (Windows)
REM  Double-click this file. It starts Docker Desktop if needed, builds and
REM  starts the app + PostgreSQL, waits until it is ready, then opens your browser.
REM ==========================================================================
setlocal EnableExtensions
title Payments Tracker - Start
cd /d "%~dp0"

echo.
echo  ==============================================
echo    Payments Tracker - starting up
echo  ==============================================
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

set "PORT=8000"
for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
  if /i "%%A"=="APP_PORT" if not "%%B"=="" set "PORT=%%B"
)

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
curl -s -f -o nul "http://localhost:%PORT%/health/" >nul 2>&1
if not errorlevel 1 goto :app_ready
if %WAITED% GEQ 180 (
  echo  [X] The app did not become ready. Showing the last log lines:
  docker compose logs --tail 40 web
  goto :fail
)
goto :wait_app

:app_ready
echo  [OK] App is running.
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
