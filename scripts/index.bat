@REM 一键启动
@echo off
title Feishu Bot - Start All
cd /d %~dp0

echo ==========================================
echo       Feishu Bot All-in-One Start
echo ==========================================
echo.

echo [1/2] Starting Auth Service in new window...
start "Feishu Auth" cmd /c "auth.bat"

timeout /t 3 /nobreak >nul

echo [2/2] Starting Scheduler Service in new window...
start "Feishu Scheduler" cmd /c "scheduler.bat"

echo.
echo ==========================================
echo All services started!
echo.
echo Use test.bat for manual testing.
echo ==========================================
timeout /t 5
