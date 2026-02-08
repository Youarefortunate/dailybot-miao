@REM 定时任务
@echo off
title Feishu Bot - Scheduler
cd /d %~dp0\..
echo Starting Scheduler...
echo.
call .venv\Scripts\activate
python push_scheduler.py
pause
