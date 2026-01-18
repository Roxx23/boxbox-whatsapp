@echo off
echo ============================================
echo GitHub Setup and Push Script
echo ============================================
echo.

REM Check if git is initialized
if not exist .git (
    echo Initializing Git repository...
    git init
    echo.
)

echo Checking Git status...
git status
echo.

echo Adding all files...
git add .
echo.

echo Committing changes...
git commit -m "Ready for Render deployment with persistent storage"
echo.

echo ============================================
echo Next Steps:
echo ============================================
echo.
echo 1. Create a new repository on GitHub:
echo    https://github.com/new
echo.
echo 2. Copy the repository URL (e.g., https://github.com/username/whatsapp-dashboard.git)
echo.
echo 3. Run these commands:
echo    git remote add origin YOUR_REPO_URL
echo    git branch -M main
echo    git push -u origin main
echo.
echo Or if remote already exists:
echo    git push
echo.
echo ============================================
pause
