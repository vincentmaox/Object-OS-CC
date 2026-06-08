@echo off
chcp 65001 >nul
setlocal EnableExtensions

set "TASKNAME=ProjectOS_ThoughtInspector_Weekly"
set "PYEXE=D:\miniconda3\python.exe"
set "SCRIPT=D:\ClaudeCodeProjects\_ProjectOS\agent\thought_inspector.py"

echo === Check existing task ===
schtasks /Query /TN "%TASKNAME%" >nul 2>nul
if not errorlevel 1 (
    echo Task exists, removing old one...
    schtasks /Delete /TN "%TASKNAME%" /F
)

echo === Register weekly task: every Monday 09:07 ===
schtasks /Create /TN "%TASKNAME%" /TR "\"%PYEXE%\" \"%SCRIPT%\"" /SC WEEKLY /D MON /ST 09:07 /RL LIMITED /F

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
echo Schedule: Every Monday 09:07
echo Manual dry-run: "%PYEXE%" "%SCRIPT%" --dry-run
echo Manual run now: schtasks /Run /TN "%TASKNAME%"
echo Uninstall:      schtasks /Delete /TN "%TASKNAME%" /F
pause
