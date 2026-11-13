@echo off
cd /d "%~dp0.."
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  py -m app.server
) else (
  python -m app.server
)
pause
