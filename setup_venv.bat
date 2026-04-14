
@echo off
echo ================================================
echo   Self-RAG Streamlit App Setup (Windows)
echo ================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+ and add it to PATH.
    pause
    exit /b 1
)

echo [1/4] Checking Python version...
python --version

echo.
echo [2/4] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)

echo.
echo [3/4] Activating virtual environment...
call venv\Scripts\activate

echo.
echo [4/4] Upgrading pip and installing requirements...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install requirements.
    pause
    exit /b 1
)

echo.
echo ================================================
echo   Setup Complete!
echo ================================================
echo.
echo Next steps:
echo   1. Copy .env.example to .env and fill in your GROQ_API_KEY
echo   2. Run:  call venv\Scripts\activate
echo   3. Run:  streamlit run app.py
echo.
pause
