@echo off
echo Removing old virtual environment...
if exist venv rmdir /s /q venv

echo.
echo Creating virtual environment with 64-bit Python...
python -m venv venv

echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Installing dependencies...
pip install --upgrade pip
pip install -r requirements_new.txt

echo.
echo Virtual environment setup complete!
echo.
echo To activate in the future, run: venv\Scripts\activate
pause
