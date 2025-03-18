@echo off
echo Starting Picture Sorter...

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Run the application
python app.py

:: Deactivate environment when done
call venv\Scripts\deactivate.bat
