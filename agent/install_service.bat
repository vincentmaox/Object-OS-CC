@echo off
setlocal EnableExtensions

set "NSSM=D:\tools\nssm\nssm.exe"
set "SVCNAME=CCBotServer"
set "PYEXE=D:\miniconda3\python.exe"
set "SCRIPT=D:\ClaudeCodeProjects\_ProjectOS\agent\cc_bot_server.py"
set "WORKDIR=D:\ClaudeCodeProjects\_ProjectOS\agent"
set "LOGDIR=D:\ClaudeCodeProjects\_ProjectOS\agent\logs"

echo === Check admin permission ===
net session >nul 2>nul
if errorlevel 1 goto NEED_ADMIN

echo === Check files ===
if not exist "%NSSM%" goto NO_NSSM
if not exist "%PYEXE%" goto NO_PYTHON
if not exist "%SCRIPT%" goto NO_SCRIPT

echo === Prepare log directory ===
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

echo === Remove old service if exists ===
sc query "%SVCNAME%" >nul 2>nul
if errorlevel 1 goto INSTALL
echo Old service found, stopping and removing...
"%NSSM%" stop "%SVCNAME%" >nul 2>nul
"%NSSM%" remove "%SVCNAME%" confirm >nul 2>nul
timeout /t 2 /nobreak >nul

:INSTALL
echo === Install %SVCNAME% service ===
"%NSSM%" install "%SVCNAME%" "%PYEXE%" "-u" "%SCRIPT%"
if errorlevel 1 goto INSTALL_FAIL

echo === Configure service ===
"%NSSM%" set "%SVCNAME%" AppDirectory "%WORKDIR%"
"%NSSM%" set "%SVCNAME%" DisplayName "CCBotServer Feishu WebSocket Bot"
"%NSSM%" set "%SVCNAME%" Description "Feishu message to claude CLI and reply back via WebSocket"
"%NSSM%" set "%SVCNAME%" Start SERVICE_AUTO_START
"%NSSM%" set "%SVCNAME%" AppStdout "%LOGDIR%\cc_bot.stdout.log"
"%NSSM%" set "%SVCNAME%" AppStderr "%LOGDIR%\cc_bot.stderr.log"
"%NSSM%" set "%SVCNAME%" AppRotateFiles 1
"%NSSM%" set "%SVCNAME%" AppRotateOnline 1
"%NSSM%" set "%SVCNAME%" AppRotateBytes 10485760
"%NSSM%" set "%SVCNAME%" AppThrottle 5000
"%NSSM%" set "%SVCNAME%" AppExit Default Restart
"%NSSM%" set "%SVCNAME%" AppRestartDelay 3000

echo === Start service ===
"%NSSM%" start "%SVCNAME%"
if errorlevel 1 goto START_FAIL

timeout /t 3 /nobreak >nul
echo === Service status ===
sc query "%SVCNAME%" | findstr "STATE"
echo.
echo === Done ===
echo Service: %SVCNAME%
echo Auto start: SERVICE_AUTO_START
echo Stdout log: %LOGDIR%\cc_bot.stdout.log
echo Stderr log: %LOGDIR%\cc_bot.stderr.log
echo.
echo Commands:
echo   net start %SVCNAME%
echo   net stop  %SVCNAME%
echo   sc query  %SVCNAME%
echo   "%NSSM%" edit %SVCNAME%
echo   "%NSSM%" remove %SVCNAME% confirm
pause
exit /b 0

:NEED_ADMIN
echo ERROR: Please run this script as Administrator.
pause
exit /b 1

:NO_NSSM
echo ERROR: NSSM not found: %NSSM%
pause
exit /b 1

:NO_PYTHON
echo ERROR: Python not found: %PYEXE%
pause
exit /b 1

:NO_SCRIPT
echo ERROR: Bot script not found: %SCRIPT%
pause
exit /b 1

:INSTALL_FAIL
echo ERROR: nssm install failed.
pause
exit /b 1

:START_FAIL
echo ERROR: service start failed. Check logs: %LOGDIR%
pause
exit /b 1
