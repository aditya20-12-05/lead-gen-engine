"""Vercel entry point: serves the engine as one Python function."""

import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

# Vercel runs this file from api/; make the project root importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import create_app  # noqa: E402

engine_app = create_app()


def app(environ, start_response):
    """Restore the visitor's original path, which vercel.json passes as __path."""
    query = parse_qsl(environ.get("QUERY_STRING", ""), keep_blank_values=True)
    original = [value for key, value in query if key == "__path"]
    if original and environ.get("PATH_INFO", "/").startswith("/api/index"):
        environ["PATH_INFO"] = original[0] if original[0].startswith("/") else "/" + original[0]
    environ["QUERY_STRING"] = urlencode([(k, v) for k, v in query if k != "__path"])
    return engine_app(environ, start_response)
