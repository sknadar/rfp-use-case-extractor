"""
config.py
=========

One single place where ALL configuration lives.

Why a separate file?
--------------------
If configuration is scattered across the code, changing the model name or the
batch size means hunting through many files. Here, everything is in one place.

Where do the values come from?
------------------------------
1. A `.env` file in the project root (loaded by python-dotenv), or
2. Real operating-system environment variables, or
3. Streamlit secrets (`.streamlit/secrets.toml`) when running on Streamlit Cloud.

The API key is NEVER written in the source code.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Read the .env file (if it exists) into environment variables.
# override=False means a real environment variable always wins over the file.
load_dotenv(override=False)


def _get_secret(name: str, default: str = "") -> str:
    """
    Look up a configuration value.

    Order of preference: environment variable -> Streamlit secrets -> default.

    Streamlit is imported lazily and inside a try/except because:
    * the unit tests run without Streamlit installed, and
    * accessing st.secrets raises an exception when no secrets file exists.
    """
    value = os.getenv(name)
    if value:
        return value

    try:  # pragma: no cover - depends on the runtime environment
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass

    return default


def _get_bool(name: str, default: bool = False) -> bool:
    """Read a true/false setting. Accepts true/1/yes/on (case-insensitive)."""
    raw = _get_secret(name, "").strip().lower()
    if raw == "":
        return default
    return raw in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    """Read a whole-number setting, falling back to the default if unreadable."""
    raw = _get_secret(name, "").strip()
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """A read-only snapshot of the application configuration."""

    # --- Gemini / LangChain -------------------------------------------------
    google_api_key: str = ""
    model_name: str = "gemini-2.5-flash"
    temperature: float = 0.0          # 0.0 = as deterministic as the model allows
    request_timeout_seconds: int = 180
    max_retries: int = 3              # retries per batch on transient API failures

    # --- Document handling --------------------------------------------------
    # Roughly how many characters of RFP text we send to Gemini in one request.
    # Gemini 2.5 Flash has a very large context window, but smaller batches give
    # better extraction quality and more reliable page attribution.
    batch_char_budget: int = 45_000
    # A page shorter than this is treated as "visually empty" (possibly scanned).
    min_chars_per_page_for_text_pdf: int = 25
    max_upload_mb: int = 50

    # --- Behaviour ----------------------------------------------------------
    use_mock_data: bool = False       # run the whole app without calling Gemini
    output_dir: str = "outputs"
    log_level: str = "INFO"

    # --- Derived ------------------------------------------------------------
    is_configured: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        # dataclass is frozen, so we bypass the normal setter once, on purpose.
        object.__setattr__(
            self, "is_configured", bool(self.google_api_key) or self.use_mock_data
        )


def load_settings() -> Settings:
    """Build a Settings object from the environment. Call this once at startup."""
    return Settings(
        google_api_key=_get_secret("GOOGLE_API_KEY", ""),
        model_name=_get_secret("GEMINI_MODEL", "gemini-2.5-flash"),
        temperature=float(_get_secret("GEMINI_TEMPERATURE", "0.0") or 0.0),
        request_timeout_seconds=_get_int("GEMINI_TIMEOUT_SECONDS", 180),
        max_retries=_get_int("GEMINI_MAX_RETRIES", 3),
        batch_char_budget=_get_int("BATCH_CHAR_BUDGET", 45_000),
        min_chars_per_page_for_text_pdf=_get_int("MIN_CHARS_PER_PAGE", 25),
        max_upload_mb=_get_int("MAX_UPLOAD_MB", 50),
        use_mock_data=_get_bool("USE_MOCK_DATA", False),
        output_dir=_get_secret("OUTPUT_DIR", "outputs"),
        log_level=_get_secret("LOG_LEVEL", "INFO"),
    )


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str, fallback: str = "rfp_document") -> str:
    """
    Turn any user-supplied file name into something safe to write to disk.

    An uploaded file could be called "../../etc/passwd" or contain characters
    that are illegal on Windows. We strip the folder part and replace every
    character that is not a letter, digit, dot, underscore or hyphen.
    """
    name = os.path.basename(name or "")
    name = name.rsplit(".", 1)[0]          # drop the extension
    cleaned = _SAFE_NAME.sub("_", name).strip("._-")
    return cleaned[:80] or fallback
