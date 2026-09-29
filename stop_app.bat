@echo off
REM Stops the Payments Tracker containers. Your data is kept.
title Payments Tracker - Stop
cd /d "%~dp0"
echo Stopping Payments Tracker...
docker compose down
echo.
echo Stopped. Your data is kept - run start_app.bat to start again.
pause
