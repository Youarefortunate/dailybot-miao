@REM 飞书授权认证
@echo off
title Feishu Auth Service
cd /d %~dp0\..
echo Starting Auth Server...
echo Please visit http://127.0.0.1:8001/auth in your browser.
echo.
call .venv\Scripts\activate
uvicorn feishu_oauth_fastapi:app --port 8001 --reload

pause
