@echo off
chcp 65001 >nul
title 剪映SRT字幕导出

:: 优先使用 pythonw 免黑框静默运行
where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pythonw "%~dp0app.pyw"
    exit
)

:: 备选使用 python
where python >nul 2>nul
if %errorlevel% equ 0 (
    start "" python "%~dp0app.pyw"
    exit
)

echo ========================================================
echo  【提示】未在当前电脑中检测到 Python 环境！
echo ========================================================
echo.
echo  本工具开箱即用，0 第三方依赖（无需执行 pip install）。
echo  但运行需要电脑安装了 Python 3.8 或更高版本。
echo.
echo  1. 请前往官网下载安装: https://www.python.org/downloads/
echo  2. 安装时请务必勾选底部的 [√] Add python.exe to PATH
echo.
echo ========================================================
pause
