@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul
if errorlevel 1 (
    python run_baysim.py
) else (
    start "" pythonw run_baysim.py
)
