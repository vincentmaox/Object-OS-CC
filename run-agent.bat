@echo off
chcp 65001 >nul
cd /d "D:\ClaudeCodeProjects\_ProjectOS\agent"
python project_agent.py %*
pause
