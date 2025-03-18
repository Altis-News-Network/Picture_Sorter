@echo off
setlocal EnableDelayedExpansion

echo Starting Kana's Text Image Sorter...

:: Delete old log files if they exist
if exist text_image_sorter_gui.log del text_image_sorter_gui.log

:: Check if portable Python exists
if not exist "portable_python\python-3.9.5.amd64\python.exe" (
    echo Portable Python nicht gefunden!
    echo Bitte führe zuerst setup.bat aus
    pause
    exit /b 1
)

:: Set environment paths
set PYTHON_PATH=%~dp0portable_python\python-3.9.5.amd64
set PATH=%PYTHON_PATH%;%PYTHON_PATH%\Scripts;%PATH%;%~dp0tesseract
set PYTHONPATH=%~dp0

:: Run the application
"%PYTHON_PATH%\python.exe" -W ignore::DeprecationWarning app.py

pause
