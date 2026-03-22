"""Shared database URL helper for scripts.

Reads DATABASE_URL from the environment, falling back to the local dev default.
Set the DATABASE_URL environment variable to override in production or CI.
"""

import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://peru:peru2026@localhost:5434/peru_elecciones",
)
