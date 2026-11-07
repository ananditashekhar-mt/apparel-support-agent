#!/bin/zsh
cd -- "${0:A:h}" || exit 1
open -a Ollama
./.venv/bin/python -m streamlit run app.py
