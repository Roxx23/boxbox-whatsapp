@echo off
echo.
echo ============================================================
echo   Installing Authentication Dependencies
echo ============================================================
echo.

echo Installing flask-login...
pip install flask-login --quiet

echo Installing bcrypt...
pip install bcrypt --quiet

echo.
echo ============================================================
echo   Installation Complete!
echo ============================================================
echo.
echo Authentication system is ready to use.
echo.
echo Next steps:
echo   1. Run: python app.py
echo   2. Open: http://127.0.0.1:5000
echo   3. Click "Sign up here" to create your first account
echo.
pause
