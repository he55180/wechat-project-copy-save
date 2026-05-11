@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

title Project PureFocus - 行业情报抓取中 (Selenium)...
color 0A

echo ========================================================
echo       Project PureFocus ^| 极简行业情报聚合系统     
echo ========================================================
echo.

cd /d "%~dp0"

REM 检查是否有 venv，如果有则激活
if exist "venv\Scripts\activate.bat" (
    echo [INFO] 激活虚拟环境...
    call venv\Scripts\activate.bat
)

echo [1/3] 检查并安装依赖 (特别是 Selenium)...
pip install -r requirements.txt > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 依赖安装失败，正在重试并显示详细信息...
    pip install -r requirements.txt
) else (
    echo [OK] 依赖已就绪。
)

echo.
echo [2/3] 正在启动 Chrome 抓取 (daily_brief.py)...
echo       ⚠️  请注意：会自动打开一个 Chrome 窗口。
echo       ⚠️  如果有搜狗验证码，请手动处理，脚本会自动等待。
echo.

python daily_brief.py

echo.
echo [3/3] 任务结束。
echo ========================================================
echo.

REM 暂停供用户看结果
echo 本窗口将在 20 秒后自动关闭...
timeout /t 20
