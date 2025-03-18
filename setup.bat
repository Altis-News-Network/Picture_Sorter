@echo off
setlocal EnableDelayedExpansion

echo Setting up Kana's Text Image Sorter...

:: Check if WinPython is already downloaded
if not exist "portable_python" (
    echo Portable Python nicht gefunden. Wird heruntergeladen...
    
    :: Create temp directory for downloads
    if not exist "temp" mkdir temp
    
    :: Download WinPython using PowerShell
    echo Downloading WinPython, please wait...
    powershell -Command "& {Invoke-WebRequest -Uri 'https://github.com/winpython/winpython/releases/download/4.3.20210620/Winpython64-3.9.5.0dot.exe' -OutFile 'temp\winpython.exe'}"
    
    :: Extract WinPython
    echo Extracting WinPython...
    temp\winpython.exe -y -o"." -d"portable_python"
    
    :: Rename extracted folder to portable_python if needed
    for /d %%i in (WPy64-*) do (
        if "%%i" NEQ "portable_python" (
            move "%%i" "portable_python"
        )
    )
    
    :: Clean up
    echo Cleaning up...
    rmdir /s /q temp
)

:: Set environment paths
set PYTHON_PATH=%~dp0portable_python\python-3.9.5.amd64
set PATH=%PYTHON_PATH%;%PYTHON_PATH%\Scripts;%PATH%

:: Install required packages
echo Installing required packages...
"%PYTHON_PATH%\python.exe" -m pip install --upgrade pip
"%PYTHON_PATH%\python.exe" -m pip install pillow pytesseract pyqt5

echo Setup complete!
echo.
echo To run the application, use 'run.bat'
pause
