@echo off
setlocal EnableExtensions

set "NSSM=D:\tools\nssm\nssm.exe"
set "SVCNAME=SDKBotServer"
set "PYEXE=D:\miniconda3\python.exe"
set "SCRIPT=D:\ClaudeCodeProjects\_ProjectOS\agent\sdk_bot_server.py"
set "WORKDIR=D:\ClaudeCodeProjects\_ProjectOS\agent"
set "LOGDIR=D:\ClaudeCodeProjects\_ProjectOS\agent\logs"

REM ===== Admin detection (no self-elevation to avoid UAC loop) =====
echo === Check admin permission ===
whoami /groups 2>nul | findstr /C:"S-1-16-12288" >nul
if errorlevel 1 goto NEED_ADMIN
echo OK: running as Administrator

echo === Check files ===
if not exist "%NSSM%" goto NO_NSSM
if not exist "%PYEXE%" goto NO_PYTHON
if not exist "%SCRIPT%" goto NO_SCRIPT

echo === Prepare log directory ===
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

echo === Remove old CC bot service if exists (conflict with same APP_ID) ===
sc query "CCBotServer" >nul 2>nul
if errorlevel 1 goto SKIP_OLD_CC
echo Found CCBotServer - stopping and removing to avoid WS conflict...
"%NSSM%" stop "CCBotServer" >nul 2>nul
"%NSSM%" remove "CCBotServer" confirm >nul 2>nul
timeout /t 2 /nobreak >nul

:SKIP_OLD_CC
echo === Remove old SDK service if exists ===
sc query "%SVCNAME%" >nul 2>nul
if errorlevel 1 goto INSTALL
"%NSSM%" stop "%SVCNAME%" >nul 2>nul
"%NSSM%" remove "%SVCNAME%" confirm >nul 2>nul
timeout /t 2 /nobreak >nul

:INSTALL
echo === Install %SVCNAME% service ===
"%NSSM%" install "%SVCNAME%" "%PYEXE%" "-u" "%SCRIPT%"
if errorlevel 1 goto INSTALL_FAIL

echo === Configure service ===
"%NSSM%" set "%SVCNAME%" AppDirectory "%WORKDIR%"
"%NSSM%" set "%SVCNAME%" DisplayName "SDKBotServer Feishu+ClaudeAgentSDK"
"%NSSM%" set "%SVCNAME%" Description "Feishu bot using claude-agent-sdk with can_use_tool permission cards"
"%NSSM%" set "%SVCNAME%" Start SERVICE_AUTO_START
"%NSSM%" set "%SVCNAME%" AppStdout "%LOGDIR%\sdk_bot.stdout.log"
"%NSSM%" set "%SVCNAME%" AppStderr "%LOGDIR%\sdk_bot.stderr.log"
"%NSSM%" set "%SVCNAME%" AppRotateFiles 1
"%NSSM%" set "%SVCNAME%" AppRotateOnline 1
"%NSSM%" set "%SVCNAME%" AppRotateBytes 10485760
"%NSSM%" set "%SVCNAME%" AppThrottle 5000
"%NSSM%" set "%SVCNAME%" AppExit Default Restart
"%NSSM%" set "%SVCNAME%" AppRestartDelay 3000

echo === Set service to run as current User (inherit User env + ~/.claude config) ===
echo Account: %USERDOMAIN%\%USERNAME%
echo You will be prompted for your Windows login password (NSSM stores it encrypted in service config).
set /p USERPWD=Password for %USERDOMAIN%\%USERNAME%:
"%NSSM%" set "%SVCNAME%" ObjectName "%USERDOMAIN%\%USERNAME%" "%USERPWD%"
if errorlevel 1 (
    echo WARNING: Failed to set ObjectName. Service will run as LocalSystem and likely fail.
    echo You can fix later: "%NSSM%" set %SVCNAME% ObjectName %USERDOMAIN%\%USERNAME% YourPassword
)
set "USERPWD="

echo === Grant 'Log on as a service' right ===
REM Without this right, the service will refuse to start with: "Logon failure"
powershell -NoProfile -Command ^
  "$tmp = [IO.Path]::GetTempFileName(); ^
   secedit /export /cfg $tmp /quiet; ^
   $cfg = Get-Content $tmp; ^
   $line = $cfg | Where-Object { $_ -match '^SeServiceLogonRight' }; ^
   if (-not $line) { $line = 'SeServiceLogonRight = ' }; ^
   $sid = (New-Object System.Security.Principal.NTAccount('%USERDOMAIN%\%USERNAME%')).Translate([System.Security.Principal.SecurityIdentifier]).Value; ^
   if ($line -notmatch [regex]::Escape($sid)) { ^
     $newLine = $line.TrimEnd() + ',*' + $sid; ^
     $cfg = $cfg -replace [regex]::Escape($line), $newLine; ^
     $cfg | Set-Content $tmp; ^
     secedit /configure /db secedit.sdb /cfg $tmp /quiet; ^
     Write-Host 'Granted Log-on-as-service right.' ^
   } else { Write-Host 'Log-on-as-service right already present.' }; ^
   Remove-Item $tmp -Force"

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
echo Stdout log: %LOGDIR%\sdk_bot.stdout.log
echo Stderr log: %LOGDIR%\sdk_bot.stderr.log
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
echo.
echo ERROR: This script needs Administrator privileges.
echo.
echo How to run as Admin:
echo   1) File Explorer: right-click this .bat - "Run as Administrator"
echo   2) Win+X - "Terminal (Admin)" - then run:
echo      "%~f0"
echo.
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
