@echo off
REM Local dev needs mock DC (:9000) + manager (:8081) + agent (:7401).
REM Use start_local.bat for the full stack; this file only starts the agent.
title AIDA Agent :7401
cd /d "%~dp0"
call agent\.venv\Scripts\activate.bat
echo Starting AIDA agent on http://127.0.0.1:7401 ...
echo Tip: also run start_local.bat if landing page shows "Failed to fetch".
python -m uvicorn agent.main:app --host 127.0.0.1 --port 7401 --reload
pause
