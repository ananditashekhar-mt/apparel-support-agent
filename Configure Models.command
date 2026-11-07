#!/bin/zsh
cd -- "${0:A:h}" || exit 1
./.venv/bin/python scripts/configure_models.py
