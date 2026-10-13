@echo off
REM Stops the Team Anesthesia containers. Your data is kept.
title Team Anesthesia - Stop
cd /d "%~dp0"
echo Stopping Team Anesthesia...
docker compose down --remove-orphans
echo.
echo Stopped. Your data is kept - run start_app.bat to start again.
pause
