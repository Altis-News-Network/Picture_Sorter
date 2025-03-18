@echo off
echo Starting Picture Sorter...

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Run the application with warnings filtered
python -W ignore::DeprecationWarning app.py

:: Deactivate environment when done
call venv\Scripts\deactivate.bat
