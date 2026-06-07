@echo off
setlocal EnableExtensions

set "TASKNAME=CCBotServer"
set "PYEXE=D:\miniconda3\python.exe"
set "SCRIPT=D:\ClaudeCodeProjects\_ProjectOS\agent\cc_bot_server.py"
set "WORKDIR=D:\ClaudeCodeProjects\_ProjectOS\agent"
set "LOGDIR=D:\ClaudeCodeProjects\_ProjectOS\agent\logs"
set "TASKXML=%TEMP%\ccbotserver_task.xml"

echo === Prepare log directory ===
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

echo === Remove old scheduled task if exists ===
schtasks /Query /TN "%TASKNAME%" >nul 2>nul
if not errorlevel 1 schtasks /Delete /TN "%TASKNAME%" /F

echo === Write task XML ===
> "%TASKXML%" echo ^<?xml version="1.0" encoding="UTF-16"?^>
>> "%TASKXML%" echo ^<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"^>
>> "%TASKXML%" echo   ^<RegistrationInfo^>^<Description^>CCBotServer Feishu WebSocket Bot^</Description^>^</RegistrationInfo^>
>> "%TASKXML%" echo   ^<Triggers^>
>> "%TASKXML%" echo     ^<LogonTrigger^>^<Enabled^>true^</Enabled^>^</LogonTrigger^>
>> "%TASKXML%" echo   ^</Triggers^>
>> "%TASKXML%" echo   ^<Principals^>
>> "%TASKXML%" echo     ^<Principal id="Author"^>^<LogonType^>InteractiveToken^</LogonType^>^<RunLevel^>LeastPrivilege^</RunLevel^>^</Principal^>
>> "%TASKXML%" echo   ^</Principals^>
>> "%TASKXML%" echo   ^<Settings^>
>> "%TASKXML%" echo     ^<MultipleInstancesPolicy^>IgnoreNew^</MultipleInstancesPolicy^>
>> "%TASKXML%" echo     ^<DisallowStartIfOnBatteries^>false^</DisallowStartIfOnBatteries^>
>> "%TASKXML%" echo     ^<StopIfGoingOnBatteries^>false^</StopIfGoingOnBatteries^>
>> "%TASKXML%" echo     ^<AllowHardTerminate^>true^</AllowHardTerminate^>
>> "%TASKXML%" echo     ^<StartWhenAvailable^>true^</StartWhenAvailable^>
>> "%TASKXML%" echo     ^<RunOnlyIfNetworkAvailable^>true^</RunOnlyIfNetworkAvailable^>
>> "%TASKXML%" echo     ^<IdleSettings^>^<StopOnIdleEnd^>false^</StopOnIdleEnd^>^<RestartOnIdle^>false^</RestartOnIdle^>^</IdleSettings^>
>> "%TASKXML%" echo     ^<AllowStartOnDemand^>true^</AllowStartOnDemand^>
>> "%TASKXML%" echo     ^<Enabled^>true^</Enabled^>
>> "%TASKXML%" echo     ^<Hidden^>false^</Hidden^>
>> "%TASKXML%" echo     ^<RunOnlyIfIdle^>false^</RunOnlyIfIdle^>
>> "%TASKXML%" echo     ^<WakeToRun^>false^</WakeToRun^>
>> "%TASKXML%" echo     ^<ExecutionTimeLimit^>PT0S^</ExecutionTimeLimit^>
>> "%TASKXML%" echo     ^<RestartOnFailure^>^<Interval^>PT1M^</Interval^>^<Count^>3^</Count^>^</RestartOnFailure^>
>> "%TASKXML%" echo   ^</Settings^>
>> "%TASKXML%" echo   ^<Actions Context="Author"^>
>> "%TASKXML%" echo     ^<Exec^>^<Command^>%PYEXE%^</Command^>^<Arguments^>-u "%SCRIPT%"^</Arguments^>^<WorkingDirectory^>%WORKDIR%^</WorkingDirectory^>^</Exec^>
>> "%TASKXML%" echo   ^</Actions^>
>> "%TASKXML%" echo ^</Task^>

echo === Create scheduled task ===
schtasks /Create /TN "%TASKNAME%" /XML "%TASKXML%" /F
if errorlevel 1 goto FAIL

echo === Start scheduled task ===
schtasks /Run /TN "%TASKNAME%"
if errorlevel 1 goto FAIL

timeout /t 3 /nobreak >nul
echo === Task status ===
schtasks /Query /TN "%TASKNAME%" /V /FO LIST | findstr /C:"Status" /C:"Task To Run" /C:"Run As User"

echo.
echo === Done ===
echo Task: %TASKNAME%
echo Starts at user logon.
echo Logs: %LOGDIR%
pause
exit /b 0

:FAIL
echo ERROR: failed to create or run scheduled task.
pause
exit /b 1
