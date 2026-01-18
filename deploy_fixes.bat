@echo off
echo ============================================
echo Committing and Pushing All Fixes
echo ============================================
echo.

echo Adding all changes...
git add .

echo.
echo Committing changes...
git commit -m "Fix pandas import error and Shopify JSON parsing"

echo.
echo Pushing to GitHub...
git push

echo.
echo ============================================
echo Done! Render will auto-deploy in 2-5 minutes
echo ============================================
echo.
echo Check deployment at: https://dashboard.render.com
pause
