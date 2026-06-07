@echo off
setlocal EnableExtensions

set "TASKNAME=ProjectOSDailyReport"
set "PYEXE=D:\miniconda3\python.exe"
set "SCRIPT=D:\ClaudeCodeProjects\_ProjectOS\agent\daily_projectos_report.py"
set "WORKDIR=D:\ClaudeCodeProjects\_ProjectOS\agent"

echo === Remove old task if exists ===
schtasks /Query /TN "%TASKNAME%" >nul 2>nul
if not errorlevel 1 schtasks /Delete /TN "%TASKNAME%" /F

echo === Create daily 09:07 task ===
schtasks /Create /TN "%TASKNAME%" /SC DAILY /ST 09:07 /TR "\"%PYEXE%\" -u \"%SCRIPT%\"" /F
if errorlevel 1 goto FAIL

echo === Task status ===
schtasks /Query /TN "%TASKNAME%" /V /FO LIST | findstr /C:"TaskName" /C:"Task To Run" /C:"Schedule Type" /C:"Start Time" /C:"Run As User"

echo.
echo Done. ProjectOS scan + Feishu base sync + morning report + blocker alert will run daily at 09:07.
pause
exit /b 0

:FAIL
echo ERROR: failed to create scheduled task.
pause
exit /b 1
