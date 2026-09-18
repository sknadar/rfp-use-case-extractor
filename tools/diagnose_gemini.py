"""
diagnose_gemini.py
===================

Bypasses the whole Streamlit app and calls Gemini directly, once, with a tiny
prompt. It prints the EXACT error Google's server sends back, with nothing
simplified or hidden - useful for telling apart an auth problem, a rate limit,
a bad model name, or something else entirely.

Run it from the project root with the virtual environment activated:

    python tools/diagnose_gemini.py
"""

from __future__ import annotations

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import load_settings  # noqa: E402


def main() -> None:
    settings = load_settings()

    print("=" * 70)
    print("CONFIGURATION IN USE")
    print("=" * 70)
    print(f"Model:            {settings.model_name}")
    print(f"API key present:  {bool(settings.google_api_key)}")
    if settings.google_api_key:
        key = settings.google_api_key
        masked = key[:6] + "..." + key[-4:] if len(key) > 12 else "(too short?)"
        print(f"API key preview:  {masked}")
    print(f"Mock mode:        {settings.use_mock_data}")
    print()

    if not settings.google_api_key:
        print("No API key found in .env - nothing to test. Fix that first.")
        return

    print("=" * 70)
    print(f"SENDING ONE TEST REQUEST TO: {settings.model_name}")
    print("=" * 70)

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage

        llm = ChatGoogleGenerativeAI(
            model=settings.model_name,
            temperature=0,
            google_api_key=settings.google_api_key,
            timeout=60,
            max_retries=0,   # no retries - we want to see the raw failure once
        )
        response = llm.invoke([HumanMessage(content="Reply with exactly: OK")])
        print("SUCCESS. Gemini replied:")
        print(response.content)

    except Exception:
        print("FAILED. Full raw error below:")
        print("-" * 70)
        traceback.print_exc()
        print("-" * 70)
        print(
            "\nCopy everything between the two lines above and share it - "
            "that is the exact, unfiltered error from Google's server."
        )


if __name__ == "__main__":
    main()
