@echo off
title CloudMind AI — Local Server
cd /d "%~dp0"
echo Starting CloudMind AI on http://127.0.0.1:5000 ...
start "" http://127.0.0.1:5000
python app.py
pause
