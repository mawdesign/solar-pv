@echo off
echo ===================================================
echo Setting up Solar PV App environment on Windows...
echo ===================================================

echo.
echo Creating virtual environment (.venv)...
python -m venv .venv

echo.
echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo.
echo Upgrading pip...
python -m pip install --upgrade pip

echo.
echo Installing requirements...
pip install -r requirements.txt

echo.
echo ===================================================
echo Setup complete! 
echo To run the app or scripts, always activate the environment first by running:
echo .venv\Scripts\activate
echo ===================================================
pause
