#!/usr/bin/env python3
"""Atalho de desenvolvimento: instala dependências (se faltarem) e sobe o servidor."""
import os
import subprocess
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
try:
    import flask_sqlalchemy  # noqa: F401
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--quiet"])

subprocess.check_call([sys.executable, "-m", "flask", "--app", "planner", "db", "upgrade"])
subprocess.call([sys.executable, "-m", "flask", "--app", "planner", "run", "--debug"])
