"""Compatibility shim — the application lives at backend.core.main.

The Docker entrypoint (uvicorn backend.main:app) and Railway's start command
continue to work without any config changes. All routes and logic are in
backend.core.main (shared cases/documents surface) and
backend.apps.investigation.routes (investigation-specific endpoints).
"""
from backend.core.main import app

__all__ = ["app"]
