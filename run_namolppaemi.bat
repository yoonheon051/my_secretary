@echo off
rem Namolppaemi launcher: finds a windowless Python (pythonw) on this PC and starts the mascot.
cd /d "%~dp0"

rem 1) Python installed with uv
set "UVPY=%APPDATA%\uv\python\cpython-3.14-windows-x86_64-none\pythonw.exe"
if exist "%UVPY%" (
    start "" "%UVPY%" "%~dp0namolppaemi.py" %*
    exit /b
)

rem 2) python.org installer: Python launcher
where pyw >nul 2>nul
if not errorlevel 1 (
    start "" pyw "%~dp0namolppaemi.py" %*
    exit /b
)

rem 3) pythonw on PATH
where pythonw >nul 2>nul
if not errorlevel 1 (
    start "" pythonw "%~dp0namolppaemi.py" %*
    exit /b
)

echo Python 3 was not found on this PC.
echo Install it from https://www.python.org/downloads/ and run this file again.
echo (Check "Add python.exe to PATH" during installation.)
pause
