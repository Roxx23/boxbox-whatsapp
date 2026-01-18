@echo off
echo Removing old virtual environment...
if exist venv rmdir /s /q venv

echo.
echo Creating virtual environment...
py -3-64 -m venv venv

echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Verifying Python architecture...
python -c "import sys; print(f'Python: {sys.version}'); print(f'Architecture: {64 if sys.maxsize > 2**32 else 32}-bit')"

echo.
echo Upgrading pip...
python -m pip install --upgrade pip

echo.
echo Installing packages one by one (using precompiled wheels)...
pip install --only-binary :all: numpy==2.0.2
pip install --only-binary :all: pandas==2.2.3
pip install apscheduler==3.11.1
pip install blinker==1.9.0
pip install certifi==2025.11.12
pip install charset-normalizer==3.4.4
pip install click==8.1.8
pip install colorama==0.4.6
pip install flask==3.1.2
pip install flask-login==0.6.3
pip install bcrypt==4.2.1
pip install idna==3.11
pip install importlib-metadata==8.7.0
pip install itsdangerous==2.2.0
pip install jinja2==3.1.6
pip install markupsafe==3.0.3
pip install python-dateutil==2.9.0.post0
pip install python-dotenv==1.2.1
pip install pytz==2025.2
pip install requests==2.32.5
pip install six==1.17.0
pip install tzdata==2025.2
pip install tzlocal==5.3.1
pip install urllib3==2.6.0
pip install werkzeug==3.1.4
pip install zipp==3.23.0

echo.
echo Virtual environment setup complete!
echo.
echo To activate in the future, run: venv\Scripts\activate
pause
