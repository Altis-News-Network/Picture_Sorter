@echo off
echo Starting Picture Sorter...

:: Delete old log files if they exist
if exist text_image_sorter_gui.log del text_image_sorter_gui.log

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Run the application with warnings filtered
python -W ignore::DeprecationWarning app.py

:: Deactivate environment when done
call venv\Scripts\deactivate.bat
