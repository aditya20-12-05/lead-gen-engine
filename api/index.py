"""Vercel entry point: serves the engine as one Python function."""

from engine import create_app

app = create_app()
