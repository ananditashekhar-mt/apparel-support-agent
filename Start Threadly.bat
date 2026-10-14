@echo off
setlocal
cd /d "%~dp0"
title Threadly

echo Threadly setup and launcher
echo ============================
echo.

where py >nul 2>nul
if errorlevel 1 goto python_missing

if not exist ".venv\Scripts\python.exe" (
  echo First-time setup: creating Threadly's private environment...
  py -m venv .venv
  if errorlevel 1 goto setup_failed
)

".venv\Scripts\python.exe" -c "import streamlit, langgraph, openai" >nul 2>nul
if errorlevel 1 (
  echo First-time setup: installing Threadly. This may take a few minutes...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto setup_failed
)

echo.
echo Starting Threadly...
echo Keep this window open while using the app.
echo To stop Threadly, close this window or press Control+C.
echo.
".venv\Scripts\python.exe" -m streamlit run app.py
goto end

:python_missing
echo Python is not installed yet.
echo Install it from https://www.python.org/downloads/
echo Select "Add Python to PATH" during installation.
echo Then double-click Start Threadly again.
start "" "https://www.python.org/downloads/"
pause
goto end

:setup_failed
echo.
echo Threadly setup did not complete. Please take a screenshot of this window
echo and send it to the person who shared the app with you.
pause

:end
endlocal
