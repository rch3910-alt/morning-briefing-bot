@echo off
chcp 65001 > nul
cd /d "%~dp0.."
echo [%date% %time%] 아침 브리핑 시작 >> output\briefing.log 2>&1
py main.py >> output\briefing.log 2>&1
echo [%date% %time%] 아침 브리핑 종료 >> output\briefing.log 2>&1
