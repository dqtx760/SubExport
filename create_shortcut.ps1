# 剪映SRT字幕导出 - 桌面快捷方式创建脚本
# 说明：本文件必须保存为 UTF-8 with BOM，否则 PowerShell 读取中文会乱码

$ErrorActionPreference = 'Stop'

$appDir    = $PSScriptRoot
$targetPyw = Join-Path $appDir 'app.pyw'
$icoPath   = Join-Path $appDir 'icon.ico'

# 查找 pythonw.exe（无控制台窗口）或 python.exe
$python = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source }

if (-not $python) {
    Write-Host ''
    Write-Host '  [!] 未检测到 Python 环境' -ForegroundColor Red
    Write-Host '      请先安装 Python 3.8 或更高版本：https://www.python.org/downloads/' -ForegroundColor Yellow
    Write-Host '      安装时务必勾选 Add python.exe to PATH' -ForegroundColor Yellow
    Write-Host ''
    Read-Host '按回车键退出'
    exit 1
}

$desktop      = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop '剪映SRT字幕导出.lnk'

$wsh = New-Object -ComObject WScript.Shell
$sc  = $wsh.CreateShortcut($shortcutPath)
$sc.TargetPath       = $python
$sc.Arguments        = '"' + $targetPyw + '"'
$sc.WorkingDirectory = $appDir
$sc.Description      = '剪映SRT字幕导出工具'
if (Test-Path $icoPath) { $sc.IconLocation = $icoPath + ',0' }
$sc.Save()

Write-Host ''
Write-Host '  桌面上已创建快捷方式：剪映SRT字幕导出' -ForegroundColor Green
Write-Host ('  图标来源：' + $icoPath) -ForegroundColor DarkGray
Write-Host ''
