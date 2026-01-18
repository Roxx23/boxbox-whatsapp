@echo off
echo Removing old virtual environment...
if exist venv rmdir /s /q venv

echo.
echo Creating new virtual environment...
python -m venv venv

echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Installing dependencies (32-bit compatible versions)...
pip install --upgrade pip
pip install -r requirements_32bit.txt

echo.
echo Virtual environment setup complete!
echo.
echo To activate in the future, run: venv\Scripts\activate
pause
