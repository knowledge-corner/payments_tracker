@echo off
REM Shows live application logs. Press Ctrl+C to stop watching.
title Payments Tracker - Logs
cd /d "%~dp0"
docker compose logs -f --tail 100 web
pause
