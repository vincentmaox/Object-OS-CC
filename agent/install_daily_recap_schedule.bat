@echo off
chcp 65001 >nul
setlocal EnableExtensions

set "TASKNAME=ProjectOS_DailyRecap_Evening"
set "PYEXE=D:\miniconda3\python.exe"
set "SCRIPT=D:\ClaudeCodeProjects\_ProjectOS\agent\daily_recap.py"

echo === Check existing task ===
schtasks /Query /TN "%TASKNAME%" >nul 2>nul
if not errorlevel 1 (
    echo Task exists, removing old one...
    schtasks /Delete /TN "%TASKNAME%" /F
)

echo === Register daily task: every day at 22:57 ===
schtasks /Create /TN "%TASKNAME%" /TR "\"%PYEXE%\" \"%SCRIPT%\"" /SC DAILY /ST 22:57 /RL LIMITED /F

if errorlevel 1 (
    echo FAILED to register task.
    pause
    exit /b 1
)

echo.
echo === Task info ===
schtasks /Query /TN "%TASKNAME%" /FO LIST

echo.
echo === Done ===
echo Task: %TASKNAME%
echo Schedule: Every day at 22:57
echo Manual dry-run: "%PYEXE%" "%SCRIPT%" --dry-run
echo Manual no-llm:  "%PYEXE%" "%SCRIPT%" --dry-run --no-llm
echo Manual run now: schtasks /Run /TN "%TASKNAME%"
echo Uninstall:      schtasks /Delete /TN "%TASKNAME%" /F
pause
