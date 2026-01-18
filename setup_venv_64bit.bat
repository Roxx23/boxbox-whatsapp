@echo off
echo Checking Python architecture...
python -c "import sys; print(f'Python {sys.version}'); print(f'Architecture: {sys.maxsize > 2**32 and \"64-bit\" or \"32-bit\"}')"

echo.
echo Locating 64-bit Python...
py -3.13-64 --version 2>nul
if %errorlevel% equ 0 (
    set PYTHON_CMD=py -3.13-64
    goto :found
)

py -3.12-64 --version 2>nul
if %errorlevel% equ 0 (
    set PYTHON_CMD=py -3.12-64
    goto :found
)

py -3-64 --version 2>nul
if %errorlevel% equ 0 (
    set PYTHON_CMD=py -3-64
    goto :found
)

where /q python3
if %errorlevel% equ 0 (
    python3 -c "import sys; exit(0 if sys.maxsize > 2**32 else 1)"
    if %errorlevel% equ 0 (
        set PYTHON_CMD=python3
        goto :found
    )
)

where /q python
if %errorlevel% equ 0 (
    python -c "import sys; exit(0 if sys.maxsize > 2**32 else 1)"
    if %errorlevel% equ 0 (
        set PYTHON_CMD=python
        goto :found
    )
)

echo ERROR: Could not find 64-bit Python installation!
echo Please ensure 64-bit Python is installed and in PATH.
echo You can download it from: https://www.python.org/downloads/
pause
exit /b 1

:found
echo Found 64-bit Python: %PYTHON_CMD%
echo.

echo Removing old virtual environment...
if exist venv rmdir /s /q venv

echo.
echo Creating virtual environment with 64-bit Python...
%PYTHON_CMD% -m venv venv

echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Verifying virtual environment Python...
python -c "import sys; print(f'Venv Python: {sys.maxsize > 2**32 and \"64-bit\" or \"32-bit\"}')"

echo.
echo Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements_new.txt

echo.
echo Virtual environment setup complete!
echo.
echo To activate in the future, run: venv\Scripts\activate
pause
