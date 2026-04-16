@echo off
title League Tracker Engine

echo === STEP 1: Running Database Sync ===
echo This will take a few minutes to fetch all 11,000 PUUIDs...
C:\IT\venvs\venv_pc\Scripts\python.exe C:\IT\coding-space\vs-code\league-tracker\crawler\sync.py

echo.
echo === STEP 2: Starting the Crawler ===
echo Launching crawler.py in the background...

:: Using pythonw.exe instead of python.exe runs the script completely invisibly!
start "" C:\IT\venvs\venv_pc\Scripts\pythonw.exe C:\IT\coding-space\vs-code\league-tracker\crawler\crawler.py

echo.
echo [SUCCESS] The crawler is now looping silently in the background.
echo You can safely close this terminal window!
pause