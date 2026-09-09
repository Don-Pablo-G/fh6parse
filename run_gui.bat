@echo off
cd /d "%~dp0"
python -m fh6parse --gui
if errorlevel 1 pause
