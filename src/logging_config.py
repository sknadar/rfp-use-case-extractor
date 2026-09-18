"""
logging_config.py
=================

Developer-facing logging. Users see friendly messages in the Streamlit UI;
developers see these logs in the terminal.

Rule: never log the API key, never log full document text.
"""

from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger exactly once for the whole application."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        stream=sys.stdout,
    )
    # Third-party libraries are noisy; keep them quiet.
    for noisy in ("httpx", "urllib3", "google", "grpc"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, e.g. get_logger(__name__)."""
    return logging.getLogger(name)
