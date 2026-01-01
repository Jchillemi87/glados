@echo off
:: Ensure the script runs from the directory where this file is located
cd /d %~dp0

echo Starting Chainlit with PDM...
echo ------------------------------

:: Run the Chainlit app in watch mode
pdm run chainlit run src/app.py -w

:: Pause the window if the application stops (useful for seeing errors)
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with error code %ERRORLEVEL%.
    pause
)