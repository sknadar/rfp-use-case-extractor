# RFP Use Case Extractor

AI-powered extraction of structured requirements from RFP PDF documents.

Upload a Request for Proposal, and the application extracts the requirements the
customer **explicitly stated**, organises them as
Section → Sub-Section → Feature → Requirement, keeps the **source page** for each
one, lets a human review and correct the results, and produces Excel and Word
reports.

---

## 1. What it does

```
Upload PDF → Read page by page → LangChain → Gemini 2.5 Flash
   → Structured extraction → Validation → Hierarchy
   → Human review → Excel + Word reports
```

Key behaviours:

- **Extraction, not summarisation.** The prompt forbids inventing requirements,
  SLAs, technologies, timings or roles that the document does not state.
- **Page traceability is mandatory.** Page numbers travel with the text from the
  first step, and any record without a valid page is flagged for review.
- **Flag, never silently delete.** Bad records are marked, not dropped.
- **Mock mode.** The whole app runs without an API key, for free.

---

## 2. Installation (Windows)

```bat
cd rfp-use-case-extractor

python -m venv .venv
.venv\Scripts\activate

python -m pip install --upgrade pip
pip install -r requirements.txt

copy .env.example .env
notepad .env
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Get a free Gemini API key at <https://aistudio.google.com/app/apikey> and put it
in `.env`:

```
GOOGLE_API_KEY=AIza...your_real_key...
USE_MOCK_DATA=false
```

To try the application with no key at all, set `USE_MOCK_DATA=true` instead.

---

## 3. Running

```bat
streamlit run app.py
```

Your browser opens at <http://localhost:8501>.

1. Upload a PDF (a demo file is provided — see below).
2. Click **Run Extraction**.
3. Open the **Review** tab, correct anything that looks wrong, then click
   *Save changes and re-validate*.
4. Open the **Reports** tab, click *Generate*, then download the `.xlsx` and
   `.docx`.

### A sample RFP to test with

```bat
python tools\make_sample_pdf.py
```

This writes `sample_data/sample_rfp.pdf`, a four-page mock RFP.

---

## 4. Testing

```bat
pytest -v
```

The tests never call Gemini and never need an API key. They cover the PDF
reader, the validator, the hierarchy builder and both report writers.

---

## 5. Project structure

```
rfp-use-case-extractor/
├── app.py                  Streamlit UI only
├── config.py               All configuration in one place
├── requirements.txt
├── .env.example            Configuration template (copy to .env)
├── .gitignore
├── README.md
│
├── src/
│   ├── pdf_reader.py       PDF → page-level text (page numbers preserved)
│   ├── prompts.py          The Gemini system + user prompts
│   ├── models.py           Pydantic schema for structured output
│   ├── records.py          Plain-dict record shape used downstream
│   ├── extractor.py        LangChain/Gemini calls, batching, retries, mock mode
│   ├── validator.py        Field checks, page checks, duplicate flagging
│   ├── hierarchy.py        Section → Sub-Section → Feature → Requirement
│   ├── excel_report.py     openpyxl report
│   ├── word_report.py      python-docx report
│   ├── mock_data.py        Sample requirements for mock mode
│   └── logging_config.py   Developer logging
│
├── tools/
│   ├── simple_pdf.py       Tiny PDF writer (tests + demo only)
│   └── make_sample_pdf.py  Builds sample_data/sample_rfp.pdf
│
├── outputs/                Generated reports (git-ignored)
├── sample_data/
└── tests/
```

---

## 6. Configuration reference

| Variable | Default | Meaning |
| --- | --- | --- |
| `GOOGLE_API_KEY` | – | Gemini API key. Required unless mock mode is on. |
| `USE_MOCK_DATA` | `false` | Run the pipeline with sample data, no API calls. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model used for extraction. |
| `GEMINI_TEMPERATURE` | `0.0` | Keep at 0 for repeatable extraction. |
| `GEMINI_TIMEOUT_SECONDS` | `180` | Per-request timeout. |
| `GEMINI_MAX_RETRIES` | `3` | Retries per batch on transient failures. |
| `BATCH_CHAR_BUDGET` | `45000` | Characters of RFP text per Gemini request. |
| `MIN_CHARS_PER_PAGE` | `25` | Below this a page counts as visually empty. |
| `MAX_UPLOAD_MB` | `50` | Upload size limit. |
| `LOG_LEVEL` | `INFO` | Developer log verbosity. |

On Streamlit Cloud, put the same keys in **Settings → Secrets** instead of
`.env`.

---

## 7. Known limitations (MVP)

- **Scanned PDFs are not supported.** If a PDF has no text layer the app says so
  clearly instead of guessing. OCR is a planned extension; `pdf_reader.py` is the
  only file that would change.
- Requirement quality depends on the RFP's own structure. When the document has
  no clear headings, hierarchy levels come back as `Unclassified` and are flagged
  for review, by design.
- Duplicate detection compares wording, not meaning. It flags; it never deletes.
- Reviewer edits live in the browser session. Closing the tab loses them — export
  the reports to keep a record.
