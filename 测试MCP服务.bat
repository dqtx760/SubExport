@echo off
cd /d "%~dp0"
echo ========================================================
echo        JianYing Subtitle MCP Self-Test
echo ========================================================
echo.
python mcp_server.py --test
echo.
pause
