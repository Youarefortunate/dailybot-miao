@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d %~dp0\..

echo [DailyBot 一键打包] 准备中...

:: --- 1. 参数解析 ---
set "CLEAN_BUILD=0"
for %%a in (%*) do (
    if "%%a"=="--clean" set "CLEAN_BUILD=1"
)

:: --- 2. 环境激活 ---
if exist ".venv" (
    echo [1/3] 正在激活 .venv 环境...
    call .venv\Scripts\activate
) else (
    echo [提示] 未找到 .venv 虚拟环境，将尝试使用系统全局环境。
)

:: --- 3. 依赖自检 ---
where pyinstaller >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [2/3] 未检测到 PyInstaller，正在尝试通过 requirements.txt 安装依赖...
    pip install -r requirements.txt
    
    :: 再次验证
    where pyinstaller >nul 2>nul
    if %ERRORLEVEL% neq 0 (
        echo [错误] 依赖安装后仍未找到 pyinstaller，请手动执行: pip install pyinstaller
        pause
        exit /b 1
    )
) else (
    echo [2/3] PyInstaller 已就绪。
)

:: --- 4. 执行打包 ---
echo [3/3] 正在启动 PyInstaller 打包流程...
pyinstaller scripts\DailyBot.spec --clean --noconfirm

if %ERRORLEVEL% neq 0 (
    echo.
    echo [错误] 打包过程中出现异常 (错误码: %ERRORLEVEL%)
    pause
    exit /b %ERRORLEVEL%
)

:: --- 5. 清理逻辑 ---
if "!CLEAN_BUILD!"=="1" (
    echo [清理] 正在移除临时文件 (build 目录)...
    if exist "build" rd /s /q "build"
) else (
    echo [提示] 跳过清理步骤。如需自动清理，请添加参数: --clean
)

echo.
echo ==========================================
echo ✨ 打包成功！成品在 dist 目录下。
echo ==========================================
pause
