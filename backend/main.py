"""Backward-compatible entry point.

The API is assembled in `backend.core.main` (shared app + core routes) with each product's
routes mounted on top (currently investigation). This shim keeps the existing run command and
deployment config working unchanged:

    uvicorn backend.main:app --reload
"""
from backend.core.main import app  # noqa: F401
