@echo off
chcp 65001 >nul
setlocal
cd /d %~dp0\..

if not exist ".venv" (
    echo [ERROR] 未找到 .venv 虚拟环境，请先执行部署脚本或创建虚拟环境。
    pause
    exit /b 1
)

call .venv\Scripts\activate
:: 使用 %* 将所有接收到的参数透传给 Python 脚本
python push_scheduler.py %*

if %ERRORLEVEL% neq 0 (
    if "%1"=="--service" (
        :: 后台模式静默记录
        echo [%DATE% %TIME%] Service exited with error %ERRORLEVEL% >> logs\run_dailybot_error.log
    ) else (
        echo [ERROR] 程序异常退出 (Error Code: %ERRORLEVEL%)
        pause
    )
)
