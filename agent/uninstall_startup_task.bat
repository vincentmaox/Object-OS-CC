@echo off
schtasks /End /TN "CCBotServer" >nul 2>nul
schtasks /Delete /TN "CCBotServer" /F
pause
