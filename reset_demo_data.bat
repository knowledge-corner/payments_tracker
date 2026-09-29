@echo off
REM Deletes ALL data (database volume) and restarts with fresh demo data.
setlocal
title Payments Tracker - Reset data
cd /d "%~dp0"
echo.
echo  WARNING: this permanently deletes ALL cases, payments, hospitals and users
echo  stored in the local database, then reloads the demo data.
echo.
set /p CONFIRM=Type YES to continue: 
if /i not "%CONFIRM%"=="YES" (
  echo Cancelled.
  pause
  exit /b 0
)
docker compose down -v
call "%~dp0start_app.bat"
