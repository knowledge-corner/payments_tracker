@echo off
REM Deletes ALL data (database volume) and restarts with an empty app.
setlocal
title Payments Tracker - Reset data
cd /d "%~dp0"
echo.
echo  WARNING: this permanently deletes ALL cases, payments, hospitals and users
echo  stored in the local database, then starts the app again (empty, with the starter hospital list).
echo.
set /p CONFIRM=Type YES to continue: 
if /i not "%CONFIRM%"=="YES" (
  echo Cancelled.
  pause
  exit /b 0
)
docker compose down -v
call "%~dp0start_app.bat"
