@echo off
echo Setting up Picture Sorter environment...

:: Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Upgrade pip first
echo Upgrading pip...
python -m pip install --upgrade pip

:: Install required packages without --user flag
echo Installing required packages...
pip install pillow
pip install pytesseract
pip install pyqt5

echo Setup complete!
echo.
echo To run the application, use 'run.bat'
pause
