"""Vercel Python Serverless entrypoint exposing Vallet's FastAPI ASGI application."""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = str(Path(__file__).resolve().parents[1] / "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.core.vercel_env import configure_vercel_env  # noqa: E402
from app.main import create_app  # noqa: E402

configure_vercel_env(os.environ)

app = create_app(strip_prefix="/api")
