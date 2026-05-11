@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

title Wechat Project Copy-Save - 正在归档.....
color 0F

cd /d "%~dp0"

REM 检查并激活虚拟环境
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM 自动检查并安装依赖 (特别是 pyperclip)
echo [INFO] 正在检查系统组件...
pip install -r requirements.txt > nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] 首次运行，正在安装必要组件...
    pip install -r requirements.txt
)

REM 运行脚本
python clip_save.py

REM 暂停 3 秒供查看结果，然后自动关闭
timeout /t 3
