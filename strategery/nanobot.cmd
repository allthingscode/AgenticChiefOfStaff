@echo off
setlocal
set "PROJECT_ROOT=%~dp0..\"
set "PYTHON_EXE=%PROJECT_ROOT%nanoClaw\Scripts\python.exe"
set "LAUNCHER=%PROJECT_ROOT%strategery\strategic_launcher.py"

"%PYTHON_EXE%" "%LAUNCHER%" %*
endlocal
