"""Vercel entry point: serves the engine as one Python function."""

import sys
from pathlib import Path

# Vercel runs this file from api/; make the project root importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import create_app  # noqa: E402

app = create_app()
