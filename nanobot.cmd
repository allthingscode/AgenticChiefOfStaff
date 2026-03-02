@echo off
setlocal
set "PROJECT_ROOT=C:\Users\HayesChiefOfStaff\Documents\nanobot"
set "PYTHON_EXE=C:\Users\HayesChiefOfStaff\Documents\nanobot\nanoClaw\Scripts\python.exe"
set "LAUNCHER=C:\Users\HayesChiefOfStaff\Documents\nanobot\strategery\strategic_launcher.py"

"%PYTHON_EXE%" "%LAUNCHER%" %*
endlocal
