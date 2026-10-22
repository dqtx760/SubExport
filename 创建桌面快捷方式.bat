@echo off
chcp 65001 >nul
title 创建桌面快捷方式

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcut.ps1"

if errorlevel 1 (
    pause
    exit /b 1
)

timeout /t 3 >nul
