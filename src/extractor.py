"""
extractor.py
============

Single responsibility: get structured requirements out of the document.

It does three things:
1. Split the pages into batches (page boundaries preserved).
2. Send each batch to Gemini through LangChain, asking for structured output.
3. Turn the answers into plain dictionaries with unique requirement IDs.

It does NOT validate business rules (that is `validator.py`), build the
hierarchy (`hierarchy.py`) or create reports.

Note on imports: LangChain and Pydantic are imported *inside* the functions that
need them. That way mock mode and the unit tests run even if those packages are
not installed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from config import Settings
from src.logging_config import get_logger
from src.pdf_reader import PdfDocument, PdfPage, build_batches, format_pages_for_prompt
from src.prompts import SYSTEM_PROMPT, build_user_prompt
from src.records import make_record

logger = get_logger(__name__)

ProgressCallback = Optional[Callable[[str], None]]


class ExtractionError(Exception):
    """Raised when extraction cannot produce any usable result at all."""


class MissingApiKeyError(ExtractionError):
    pass


@dataclass
class ExtractionResult:
    """Everything the UI needs to know about one extraction run."""

    records: List[Dict[str, Any]] = field(default_factory=list)
    batch_count: int = 0
    successful_batches: int = 0
    failed_batches: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    mode: str = "gemini"          # "gemini" or "mock"
    duration_seconds: float = 0.0

    @property
    def has_failures(self) -> bool:
        return len(self.failed_batches) > 0


def _notify(callback: ProgressCallback, message: str) -> None:
    """Send a friendly status message to the UI, if one is listening."""
    if callback is not None:
        callback(message)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def extract_requirements(
    document: PdfDocument,
    settings: Settings,
    progress: ProgressCallback = None,
) -> ExtractionResult:
    """Extract requirements from a PDF document (real Gemini or mock mode)."""
    started = time.time()

    if settings.use_mock_data:
        result = _extract_mock(document, progress)
    else:
        result = _extract_with_gemini(document, settings, progress)

    result.duration_seconds = round(time.time() - started, 2)
    logger.info(
        "Extraction finished | mode=%s | records=%s | batches=%s | failed=%s | %.1fs",
        result.mode,
        len(result.records),
        result.batch_count,
        len(result.failed_batches),
        result.duration_seconds,
    )
    return result


# ---------------------------------------------------------------------------
# Mock mode
# ---------------------------------------------------------------------------
def _extract_mock(document: PdfDocument, progress: ProgressCallback) -> ExtractionResult:
    """Return the sample dataset instead of calling the API."""
    from src.mock_data import get_mock_raw_requirements

    _notify(progress, "Mock mode is on - using sample requirements (no API call).")
    raws = get_mock_raw_requirements(page_count=document.page_count)
    records = [make_record(raw, _new_id(i)) for i, raw in enumerate(raws, start=1)]

    return ExtractionResult(
        records=records,
        batch_count=1,
        successful_batches=1,
        warnings=[
            "Mock mode is enabled. These requirements are sample data, not the "
            "contents of your PDF. Set USE_MOCK_DATA=false to use Gemini."
        ],
        mode="mock",
    )


# ---------------------------------------------------------------------------
# Real extraction
# ---------------------------------------------------------------------------
def _extract_with_gemini(
    document: PdfDocument, settings: Settings, progress: ProgressCallback
) -> ExtractionResult:
    if not settings.google_api_key:
        raise MissingApiKeyError(
            "No Gemini API key was found. Add GOOGLE_API_KEY to your .env file, "
            "or switch on mock mode (USE_MOCK_DATA=true) to try the application "
            "without an API key."
        )

    structured_llm = _build_llm(settings)

    batches = build_batches(document.pages, char_budget=settings.batch_char_budget)
    result = ExtractionResult(batch_count=len(batches), mode="gemini")
    logger.info("Document split into %s batch(es)", len(batches))

    next_index = 1
    for batch_number, batch in enumerate(batches, start=1):
        first_page = batch[0].page_number
        last_page = batch[-1].page_number
        _notify(
            progress,
            f"Sending pages {first_page}-{last_page} to Gemini "
            f"(batch {batch_number} of {len(batches)})...",
        )

        try:
            raw_items = _extract_one_batch(
                structured_llm=structured_llm,
                document=document,
                batch=batch,
                batch_number=batch_number,
                batch_count=len(batches),
                settings=settings,
            )
        except Exception as exc:
            # One failed batch must not lose the work already done.
            message = _friendly_api_error(exc)
            logger.error(
                "Batch %s (pages %s-%s) failed: %s",
                batch_number,
                first_page,
                last_page,
                exc,
                exc_info=True,
            )
            result.failed_batches.append(
                {
                    "batch_number": batch_number,
                    "pages": f"{first_page}-{last_page}",
                    "error": message,
                }
            )
            result.warnings.append(
                f"Pages {first_page}-{last_page} could not be analysed: {message}"
            )
            continue

        for raw in raw_items:
            result.records.append(make_record(raw, _new_id(next_index)))
            next_index += 1

        coverage_warning = _check_page_coverage(batch, raw_items)
        if coverage_warning:
            logger.warning(
                "Batch %s (pages %s-%s): %s",
                batch_number,
                first_page,
                last_page,
                coverage_warning,
            )
            result.warnings.append(
                f"Pages {first_page}-{last_page} (batch {batch_number}): {coverage_warning}"
            )

        result.successful_batches += 1
        _notify(
            progress,
            f"Batch {batch_number} of {len(batches)} done - "
            f"{len(raw_items)} requirement(s) found so far in these pages.",
        )

    if result.successful_batches == 0:
        raise ExtractionError(
            "Gemini could not analyse any part of the document. "
            + (result.failed_batches[0]["error"] if result.failed_batches else "")
        )

    return result


# ---------------------------------------------------------------------------
# Page-coverage check
# ---------------------------------------------------------------------------
# A batch can "succeed" (valid, parseable structured output) while still
# silently skipping a chunk of the pages it was given - the model just stops
# generating records for a stretch of pages without raising any error. This
# is not caught by exception handling because nothing is actually wrong with
# the JSON; it is simply incomplete. The only way to notice is to check, after
# the fact, whether every page in the batch is actually referenced by at
# least one returned record.
#
# A short run of untouched pages is often legitimate (a page of boilerplate,
# a blank page, a page that genuinely has no explicit requirements), so this
# only warns when there is a gap of MIN_GAP_PAGES or more consecutive pages
# inside the batch with zero coverage - large enough to catch a dropped
# section without nagging on every ordinary content-free page.
MIN_GAP_PAGES = 3


def _check_page_coverage(
    batch: Sequence[PdfPage], raw_items: Sequence[Dict[str, Any]]
) -> Optional[str]:
    """Return a warning message if a suspiciously large page gap is found."""
    batch_pages = [page.page_number for page in batch]
    if not batch_pages:
        return None

    covered: set[int] = set()
    for raw in raw_items:
        for page in raw.get("source_pages") or []:
            try:
                covered.add(int(page))
            except (TypeError, ValueError):
                continue

    gap_start: Optional[int] = None
    gaps: List[tuple[int, int]] = []
    for page in batch_pages:
        if page in covered:
            if gap_start is not None:
                gaps.append((gap_start, page - 1))
                gap_start = None
        else:
            if gap_start is None:
                gap_start = page
    if gap_start is not None:
        gaps.append((gap_start, batch_pages[-1]))

    big_gaps = [(start, end) for start, end in gaps if (end - start + 1) >= MIN_GAP_PAGES]
    if not big_gaps:
        return None

    pretty = ", ".join(
        f"{start}-{end}" if end > start else str(start) for start, end in big_gaps
    )
    return (
        f"no requirement referenced pages {pretty} - this may be genuine "
        "(no explicit requirements there) or the model may have skipped "
        "this content. Worth a manual check against the source PDF."
    )


def _build_llm(settings: Settings):
    """
    Create the LangChain chat model bound to our output schema.

    `with_structured_output` tells Gemini the exact JSON shape to answer in and
    hands us back validated Python objects - no manual JSON parsing.
    """
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError(
            "The package 'langchain-google-genai' is not installed. "
            "Run: pip install -r requirements.txt"
        ) from exc

    from src.models import ExtractionResponse

    llm = ChatGoogleGenerativeAI(
        model=settings.model_name,
        temperature=settings.temperature,
        google_api_key=settings.google_api_key,
        timeout=settings.request_timeout_seconds,
        max_retries=0,   # we do our own retry loop so we can log each attempt
    )
    return llm.with_structured_output(ExtractionResponse)


def _extract_one_batch(
    *,
    structured_llm,
    document: PdfDocument,
    batch: Sequence[PdfPage],
    batch_number: int,
    batch_count: int,
    settings: Settings,
) -> List[Dict[str, Any]]:
    """Call Gemini for one batch, retrying a few times on transient errors."""
    from langchain_core.messages import HumanMessage, SystemMessage

    user_prompt = build_user_prompt(
        file_name=document.file_name,
        content=format_pages_for_prompt(batch),
        first_page=batch[0].page_number,
        last_page=batch[-1].page_number,
        total_pages=document.page_count,
        batch_number=batch_number,
        batch_count=batch_count,
    )
    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]

    last_error: Optional[Exception] = None
    for attempt in range(1, settings.max_retries + 1):
        try:
            logger.info(
                "Sending batch %s/%s to Gemini (attempt %s)",
                batch_number,
                batch_count,
                attempt,
            )
            response = structured_llm.invoke(messages)
            logger.info("Gemini response received for batch %s", batch_number)

            if response is None:
                raise ExtractionError(
                    "Gemini returned an empty response (it may have been blocked "
                    "by a safety filter or hit the output size limit)."
                )

            items = getattr(response, "requirements", None)
            if items is None and isinstance(response, dict):
                items = response.get("requirements")
            if items is None:
                raise ExtractionError("Gemini response did not contain a requirements list.")

            # model_dump() gives us plain dicts, decoupling the rest of the app.
            return [
                item.model_dump() if hasattr(item, "model_dump") else dict(item)
                for item in items
            ]

        except Exception as exc:
            last_error = exc
            if attempt >= settings.max_retries:
                break
            wait = 2 ** attempt  # 2s, 4s, 8s - simple exponential backoff
            logger.warning(
                "Batch %s attempt %s failed (%s). Retrying in %ss.",
                batch_number,
                attempt,
                exc,
                wait,
            )
            time.sleep(wait)

    raise last_error if last_error else ExtractionError("Unknown extraction failure.")


def _new_id(index: int) -> str:
    """Requirement IDs look like REQ-0001, REQ-0002, ..."""
    return f"REQ-{index:04d}"


def _friendly_api_error(exc: Exception) -> str:
    """Translate a library exception into one sentence a normal user can act on."""
    text = str(exc).lower()
    if "api key" in text or "api_key" in text or "unauthenticated" in text or "401" in text:
        return "The Gemini API key is missing or invalid."
    if "permission" in text or "403" in text:
        return "The API key does not have permission to use this model."
    if "quota" in text or "rate" in text or "429" in text or "resource_exhausted" in text:
        return "The Gemini rate limit or quota was reached. Please wait and try again."
    if "timeout" in text or "deadline" in text:
        return "Gemini did not respond in time. Try a smaller BATCH_CHAR_BUDGET."
    if "not found" in text or "404" in text:
        return "The configured Gemini model name was not found. Check GEMINI_MODEL."
    if "safety" in text or "blocked" in text:
        return "Gemini blocked this content. The page range may need manual review."
    if "json" in text or "validation" in text or "parse" in text:
        return "Gemini returned a response that did not match the expected format."
    return "An unexpected error occurred while contacting Gemini."
