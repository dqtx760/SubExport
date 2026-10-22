@echo off
chcp 65001 >nul
title 创建桌面快捷方式

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$WshShell = New-Object -ComObject WScript.Shell;" ^
    "$desktop = [System.Environment]::GetFolderPath('Desktop');" ^
    "$shortcutPath = Join-Path $desktop '剪映SRT字幕导出.lnk';" ^
    "$targetPyw = Join-Path '%~dp0' 'app.pyw';" ^
    "$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source;" ^
    "if (-not $pythonw) { $pythonw = (Get-Command python.exe -ErrorAction SilentlyContinue).Source; };" ^
    "if (-not $pythonw) { Write-Host '未找到 Python，请先安装 Python！' -ForegroundColor Red; exit 1; };" ^
    "$shortcut = $WshShell.CreateShortcut($shortcutPath);" ^
    "$shortcut.TargetPath = $pythonw;" ^
    "$shortcut.Arguments = '\"' + $targetPyw + '\"';" ^
    "$shortcut.WorkingDirectory = '%~dp0';" ^
    "$shortcut.Description = '剪映SRT字幕导出工具';" ^
    "$icon = (Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'JianyingPro\Apps') -Filter 'JianyingPro.exe' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1).FullName;" ^
    "if ($icon) { $shortcut.IconLocation = $icon + ',0'; };" ^
    "$shortcut.Save();" ^
    "Write-Host '✅ 桌面快捷方式创建成功：剪映SRT字幕导出' -ForegroundColor Green;"

timeout /t 2 >nul
