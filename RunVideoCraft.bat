@echo off
cd /d "%~dp0"

if not exist "myenv\Scripts\python.exe" (
    echo ERROR: virtualenv myenv not found.
    pause
    exit /b 1
)

myenv\Scripts\python.exe src\VideoCraftHub.py
