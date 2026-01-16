@echo off
setlocal enabledelayedexpansion

echo ============================================
echo   AI-Dev-Workflow Setup Script
echo ============================================
echo.

:: Configuration
set "ZIP_PATH=C:\Users\david\Downloads\AI-Dev-Workflow.zip"
set "INSTALL_DIR=C:\Users\david\AI-Dev-Workflow"

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

echo Python found:
python --version
echo.

:: Ask about extraction
echo ============================================
echo   Installation Options
echo ============================================
echo.
echo   1. Full install (extract zip + setup)
echo   2. Setup only (skip extraction)
echo.
set /p CHOICE="Enter choice (1 or 2): "

if "%CHOICE%"=="2" (
    echo.
    echo Skipping extraction...
    goto :setup
)

:: Check if zip exists
if not exist "%ZIP_PATH%" (
    echo.
    echo ERROR: Zip file not found at %ZIP_PATH%
    echo Please download the zip file first, or choose option 2.
    pause
    exit /b 1
)

:: Remove existing installation if present
if exist "%INSTALL_DIR%" (
    echo.
    echo Removing existing installation...
    rmdir /s /q "%INSTALL_DIR%"
)

:: Extract zip
echo.
echo [1/5] Extracting zip file...
cd /d "C:\Users\david"
powershell -Command "Expand-Archive -Path '%ZIP_PATH%' -DestinationPath '.' -Force"
if errorlevel 1 (
    echo ERROR: Failed to extract zip file.
    pause
    exit /b 1
)
echo     Extracted to: %INSTALL_DIR%

:setup
:: Navigate to directory
cd /d "%INSTALL_DIR%"
if errorlevel 1 (
    echo ERROR: Could not find %INSTALL_DIR%
    echo Make sure the zip was extracted or run from the correct location.
    pause
    exit /b 1
)

:: Create virtual environment
echo.
echo [2/5] Creating virtual environment...
if exist "venv" (
    echo     Existing venv found, removing...
    rmdir /s /q venv
)
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    pause
    exit /b 1
)
echo     Created venv

:: Activate venv and install dependencies
echo.
echo [3/5] Installing dependencies (this may take a few minutes)...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)
echo     Dependencies installed

:: Create .env file
echo.
echo [4/5] Creating configuration file...
if not exist ".env" (
    copy .env.example .env >nul
    echo     Created .env from template
) else (
    echo     .env already exists
)

:: Check if API key is already set
findstr /c:"ANTHROPIC_API_KEY=sk-" .env >nul 2>&1
if errorlevel 1 (
    echo.
    echo ============================================
    echo   IMPORTANT: Add your Anthropic API Key
    echo ============================================
    echo.
    echo Notepad will open. Add your API key on this line:
    echo   ANTHROPIC_API_KEY=sk-ant-your-key-here
    echo.
    echo Save and close Notepad when done.
    echo.
    pause
    notepad .env
) else (
    echo     API key already configured
)

:: Verify installation
echo.
echo [5/5] Verifying installation...
python -c "import anthropic; print('    anthropic OK')" 2>nul || echo     WARNING: anthropic not found
python -c "import typer; print('    typer OK')" 2>nul || echo     WARNING: typer not found
python -c "import rich; print('    rich OK')" 2>nul || echo     WARNING: rich not found

:: Test CLI
echo.
echo Testing CLI...
python cli.py --help >nul 2>&1
if errorlevel 1 (
    echo     WARNING: CLI test failed. Check for errors above.
) else (
    echo     CLI OK
)

:: Create quick-start batch file
echo @echo off > "%INSTALL_DIR%\start-ai-dev-workflow.bat"
echo cd /d "%INSTALL_DIR%" >> "%INSTALL_DIR%\start-ai-dev-workflow.bat"
echo call venv\Scripts\activate.bat >> "%INSTALL_DIR%\start-ai-dev-workflow.bat"
echo echo. >> "%INSTALL_DIR%\start-ai-dev-workflow.bat"
echo echo AI-Dev-Workflow Ready >> "%INSTALL_DIR%\start-ai-dev-workflow.bat"
echo echo Type: python cli.py --help >> "%INSTALL_DIR%\start-ai-dev-workflow.bat"
echo echo. >> "%INSTALL_DIR%\start-ai-dev-workflow.bat"
echo cmd /k >> "%INSTALL_DIR%\start-ai-dev-workflow.bat"

:: Done
echo.
echo ============================================
echo   Setup Complete!
echo ============================================
echo.
echo To use AI-Dev-Workflow:
echo.
echo   1. Open PowerShell
echo   2. cd %INSTALL_DIR%
echo   3. .\venv\Scripts\Activate
echo   4. python cli.py --help
echo.
echo Or double-click: start-ai-dev-workflow.bat
echo.
pause
