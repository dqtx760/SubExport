@echo off
chcp 65001 >nul
title 编译打包 剪映SRT字幕导出工具
echo ========================================================
echo        剪映SRT字幕导出工具 - 独立 EXE 编译打包程序
echo ========================================================
echo.

echo [1/3] 正在检查打包工具 PyInstaller...
python -m pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [提示] 检测到未安装 pyinstaller，正在自动安装...
    python -m pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple
    if %errorlevel% neq 0 (
        echo [错误] 安装 pyinstaller 失败，请检查网络或手动运行: pip install pyinstaller
        pause
        exit /b 1
    )
)

echo.
echo [2/3] 开始编译构建 (单文件、无控制台黑框、嵌入专属图标与解密引擎)...
pyinstaller -w -F -i icon.ico --add-binary "bin/jy-draftc.exe;bin" app.pyw -n "剪映SRT字幕导出"

if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo  编译打包成功！
    echo  生成文件路径: dist\剪映SRT字幕导出.exe
    echo ========================================================
) else (
    echo.
    echo [错误] 打包失败，请检查上方控制台报错。
)
pause
