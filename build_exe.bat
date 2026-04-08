@echo off
REM ===================================================
REM  Build AutoMouseClick into a standalone .exe
REM  Run this script on Windows with Python installed.
REM ===================================================

echo [1/3] Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

echo [2/3] Building .exe with PyInstaller...
pyinstaller AutoMouseClick.spec --noconfirm

echo [3/3] Done!
echo.
echo The executable is located at:
echo   dist\AutoMouseClick.exe
echo.
pause
