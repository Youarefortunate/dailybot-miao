@echo off
title Feishu Bot - Manual Test
cd /d %~dp0\..
echo Running manual push test...
echo.
call .venv\Scripts\activate
python main.py
echo.
echo Test finished.
pause
