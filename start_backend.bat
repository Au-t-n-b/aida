@echo off
title AIDA Backend :7401
cd /d D:\aida
call agent\.venv\Scripts\activate.bat
echo Starting AIDA backend on http://127.0.0.1:7401 ...
python -m uvicorn agent.main:app --host 127.0.0.1 --port 7401 --reload
pause
