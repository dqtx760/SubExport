@echo off
chcp 65001 >nul
title 创建桌面快捷方式

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$WshShell = New-Object -ComObject WScript.Shell;" ^
    "$appDir = '%~dp0'.TrimEnd('\');" ^
    "$desktop = [System.Environment]::GetFolderPath('Desktop');" ^
    "$shortcutPath = Join-Path $desktop '剪映SRT字幕导出.lnk';" ^
    "$targetPyw = Join-Path $appDir 'app.pyw';" ^
    "$pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source;" ^
    "if (-not $pythonw) { $pythonw = (Get-Command python.exe -ErrorAction SilentlyContinue).Source; };" ^
    "if (-not $pythonw) { Write-Host '未找到 Python，请先安装 Python！' -ForegroundColor Red; pause; exit 1; };" ^
    "$shortcut = $WshShell.CreateShortcut($shortcutPath);" ^
    "$shortcut.TargetPath = $pythonw;" ^
    "$shortcut.Arguments = '\"' + $targetPyw + '\"';" ^
    "$shortcut.WorkingDirectory = $appDir;" ^
    "$shortcut.Description = '剪映SRT字幕导出工具';" ^
    "$ico = Join-Path $appDir 'icon.ico';" ^
    "if (Test-Path $ico) { $shortcut.IconLocation = $ico + ',0'; };" ^
    "$shortcut.Save();" ^
    "Write-Host '';" ^
    "Write-Host '  桌面快捷方式创建成功：剪映SRT字幕导出' -ForegroundColor Green;" ^
    "Write-Host '';"

timeout /t 3 >nul
