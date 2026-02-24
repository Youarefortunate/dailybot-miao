@echo off
chcp 65001 >nul
setlocal
cd /d %~dp0\..

echo ==========================================
echo   DailyBot 调度服务启动入口
echo ==========================================

if not exist ".venv" (
    echo [ERROR] 未找到 .venv 虚拟环境，请先执行部署脚本或创建虚拟环境。
    pause
    exit /b 1
)

echo [INFO] 正在启动 Python 调度程序...
call .venv\Scripts\activate
python push_scheduler.py

if %ERRORLEVEL% neq 0 (
    echo [ERROR] 程序异常退出 (Error Code: %ERRORLEVEL%)
)

echo [INFO] 调度服务已由 Python 控制。
