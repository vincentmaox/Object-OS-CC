@echo off
REM CC小助手 Bot 服务卸载脚本 - 必须右键"以管理员身份运行"
chcp 65001 > nul

set NSSM=D:\tools\nssm\nssm.exe
set SVCNAME=CCBotServer

net session >nul 2>&1
if errorlevel 1 (
    echo [错误] 必须以管理员身份运行
    pause
    exit /b 1
)

echo 停止服务...
%NSSM% stop %SVCNAME%
timeout /t 2 /nobreak > nul

echo 删除服务...
%NSSM% remove %SVCNAME% confirm

echo === 完成 ===
pause
