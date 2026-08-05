@echo off
setlocal enabledelayedexpansion

echo 🚀 LinkedIn Ads Library MCP Server Installation
echo ===============================================
echo.

REM Check if Python is available
echo 📋 Checking Python version...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ Python not found. Please install Python 3.12+ first.
    echo    💡 Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo    Found Python %PYTHON_VERSION%
echo    ✅ Python found

REM Check if pip is available
echo.
echo 📦 Checking pip availability...
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo    ❌ pip not found. Please install pip first.
    pause
    exit /b 1
)
echo    ✅ pip found

REM Install dependencies
echo.
echo 📚 Installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo    ❌ Failed to install dependencies
    pause
    exit /b 1
)
echo    ✅ Dependencies installed successfully

REM Create .env file from template
echo.
echo 🔧 Setting up configuration...
if exist .env (
    echo    ⚠️  .env file already exists, skipping creation
    echo    💡 If you need to reset it, delete .env and run this script again
) else (
    if exist .env.template (
        copy .env.template .env >nul
        echo    ✅ Created .env file from template
        echo    📝 Please edit .env file and add your API keys
    ) else (
        echo    ❌ .env.template not found
        pause
        exit /b 1
    )
)

REM Get current directory for MCP configuration
set CURRENT_DIR=%cd%
set MCP_CONFIG_PATH=%CURRENT_DIR%\mcp_server.py

echo.
echo ⚙️  MCP Server Configuration
echo ============================
echo.
echo Add this configuration to your Claude Desktop or Cursor:
echo.
echo For Claude Desktop (%%APPDATA%%\Claude\claude_desktop_config.json):
echo.
echo {
echo   "mcpServers": {
echo     "linkedin_ads_library": {
echo       "command": "python",
echo       "args": [
echo         "%MCP_CONFIG_PATH%"
echo       ]
echo     }
echo   }
echo }
echo.
echo For Cursor (%%USERPROFILE%%\.cursor\mcp.json):
echo.
echo {
echo   "mcpServers": {
echo     "linkedin_ads_library": {
echo       "command": "python",
echo       "args": [
echo         "%MCP_CONFIG_PATH%"
echo       ]
echo     }
echo   }
echo }

echo.
echo 📋 Next Steps:
echo ==============
echo 1. 📝 Edit the .env file and add your API keys:
echo    - SCRAPECREATORS_API_KEY (required) - Get at: https://scrapecreators.com/
echo    - GEMINI_API_KEY (optional for video analysis) - Get at: https://aistudio.google.com/app/apikey
echo.
echo 2. 📋 Copy the MCP configuration above to your Claude Desktop or Cursor config
echo.
echo 3. 🔄 Restart Claude Desktop or Cursor
echo.
echo 4. 🎉 You're ready to use the LinkedIn Ads Library MCP server!
echo.
echo 💡 Need help? Check the README.md file for troubleshooting tips.
echo.
echo ✅ Installation completed successfully!
echo.
pause