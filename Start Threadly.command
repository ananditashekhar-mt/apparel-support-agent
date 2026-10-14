#!/bin/zsh
set -e

APP_DIR="${0:A:h}"
cd "$APP_DIR"

clear
echo "Threadly setup and launcher"
echo "============================"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python is not installed yet."
  echo "Opening the official Python download page..."
  open "https://www.python.org/downloads/"
  echo
  echo "Install Python, then double-click Start Threadly again."
  read "?Press Enter to close."
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "First-time setup: creating Threadly's private environment..."
  python3 -m venv .venv
fi

if ! .venv/bin/python -c "import streamlit, langgraph, openai" >/dev/null 2>&1; then
  echo "First-time setup: installing Threadly. This may take a few minutes..."
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
fi

echo
echo "Starting Threadly..."
echo "Keep this window open while using the app."
echo "To stop Threadly, close this window or press Control+C."
echo
.venv/bin/python -m streamlit run app.py
