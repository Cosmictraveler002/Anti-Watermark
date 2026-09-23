@echo off
cd /d "%~dp0"
echo ========================================================
echo   Pushing anti-watermark to GitHub
echo   Target: https://github.com/Cosmictraveler002/Anti-Watermark.git
echo ========================================================

echo [1/5] Initializing Git repository...
git init

echo [2/5] Setting default branch to main...
git branch -M main

echo [3/5] Configuring remote origin...
git remote remove origin 2>nul
git remote add origin https://github.com/Cosmictraveler002/Anti-Watermark.git

echo [4/5] Staging files...
git add .

echo [5/5] Committing changes...
git commit -m "feat: anti-watermark engine and brutalist B&W UI with project processing"

echo Pushing to origin main...
git push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo ========================================================
    echo   SUCCESS: Pushed successfully to GitHub!
    echo ========================================================
) else (
    echo ========================================================
    echo   Push failed or requires credentials/force push.
    echo   If the remote repository already has a README/commits,
    echo   run: git push -u origin main --force
    echo ========================================================
)

pause
