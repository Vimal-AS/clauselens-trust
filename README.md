# ClauseLens Trust (v2)
> Evidence-based contract risk review for freelancers and small vendors

ClauseLens Trust is a local web application that empowers freelancers, consultants, and small vendors to review incoming contracts against their own personal risk policies. It checks payment terms, auto-renewals, liability exposures, governing jurisdictions, termination rights, and custom keywords deterministically, verifying every finding against exact quotes from the contract.

---

## ⚡ Quickstart (Windows)

Clone or download the repository into your workspace, then execute:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Then open your browser to **[http://127.0.0.1:5000](http://127.0.0.1:5000)**.

---

## 🎯 Key Capabilities

- **Policy Management with Persistence:**
  - Set your contract terms for payment (e.g., max 30 days), renewal (disallow auto-renewal, set max term & cancellation notice), liability (require liability cap, disallow unlimited liability), termination (min notice days, flag one-sided termination for convenience), and preferred/accepted jurisdiction (India, Singapore, etc.).
  - Custom deterministic keyword policy engine (`must_contain`, `must_not_contain`, and `number_max` thresholds).
  - All policies persist in local SQLite and survive server restarts. Defaults can be restored at any time.

- **PDF & DOCX Extraction with Precise Locations:**
  - Extracts text from both PDF (using PyMuPDF) and Word documents (using `python-docx`).
  - Tracks 1-based page numbers and line indices on PDFs, and paragraph/table cell locations on DOCX.
  - Rejects scanned/empty documents (<50 characters), corrupt files, encrypted documents, and protects against DOCX zip bombs.

- **Verbatim Evidence Verification:**
  - Every finding stores an exact verbatim slice of extracted text.
  - Verifies presence against document text and marks as `verified`, `needs_manual_review`, or `unable_to_verify`.
  - Never fabricates findings, locations, or confidence numbers.

- **Interactive Results Dashboard:**
  - Real computed summary cards (High, Medium, Low, Conflicts, Matches, Uncertain, Not Found).
  - Multi-attribute combinable live filtering: Severity, Category, Result Type, Verification Status, Review Status, and real-time full-text search.
  - Side-by-side display of policy expected vs condition detected.
  - In-browser review tracking: mark findings as `Reviewed` or `Needs Attention` and save custom notes.
  - Highlighting preview: view original PDF pages with evidence highlighted directly in modal.

- **Comprehensive Exports:**
  - Export full findings or the currently filtered view.
  - Complete JSON export with contract metadata, policy definitions, finding details, and legal disclaimers.
  - Professional PDF reports generated via ReportLab with summary tables, categorized findings, wrapped verbatim quotes, and disclaimers.

- **Themes & Internationalization:**
  - Instant Light, Dark, and System theme switching with persistent local storage. Accessible contrast levels preserved.
  - Static pre-written explanations in Tamil (எளிய தமிழ் விளக்கங்கள், using templates, not machine translation).

---

## ⚙️ Architecture & Tech Stack

- **Backend:** Python 3.10+, Flask REST API
- **Document Processing:** PyMuPDF (`fitz`), `python-docx`
- **Validation & Schemas:** Pydantic, Werkzeug
- **Reporting:** ReportLab (Unicode font support)
- **Database:** Local SQLite (`clauselens.db`) with WAL mode
- **Frontend:** Vanilla HTML5, CSS3 with CSS custom properties, modular ES6 JavaScript, `fetch()` API (zero heavy frontend frameworks)

---

## 🧪 Testing

Run the automated test suite covering parsing, detection engines, severity rules, document extraction, quote verification, API endpoints, and fixture expectations:

```powershell
venv\Scripts\activate
pytest -v
```

### Included Test Fixtures (`tests/fixtures/`):
- `sample_freelance_contract.pdf` (Standard 4-conflict demo contract: Net 60, auto-renewal with 90 days notice, unlimited liability, Singapore courts)
- `ambiguous_payment_contract.pdf` ("within a reasonable time" -> produces `uncertain`, 0 conflicts)
- `clean_compliant_contract.pdf` (Fully compliant contract matching all policies)
- `vendor_agreement.docx` (Word document with payment, renewal, uncapped liability, and London courts)
- `consulting_contract.docx` (Word document with tables, milestone advance payment, and liability caps)
- `scanned_empty.pdf` (Scanned PDF with <50 characters extractable)
- `encrypted.pdf` (AES-256 password-protected PDF)
- `corrupt.pdf` (Corrupt byte stream)
- `invalid_contract.jpg` (Wrong file type)

---

## 🔒 Security & Privacy

- Single-user local app bound strictly to `127.0.0.1`.
- Magic byte validation (`%PDF`, `PK\x03\x04`) and compression ratio check against zip bombs.
- Uploaded files stored with UUID filenames in a dedicated, isolated directory.
- HTML escaping on all rendered text to prevent XSS.
- No contract content logging or transmission outside your machine.
- Configurable immediate deletion of uploaded documents following extraction.
- One-click "Delete All Data" control in Settings permanently wipes all database entries and temporary files.

---

## ⚠️ Known Limitations & Out of Scope

- **No OCR by default:** Scanned PDFs without embedded text layers require Tesseract OCR installed on the system; otherwise the app informs the user that OCR is needed.
- **DOCX Page Numbers:** Microsoft Word (.docx) files do not contain fixed page layout information until rendered by a word processor; therefore, DOCX findings reference paragraph numbers and table cell positions, never simulated page numbers.
- **Rule-based heuristics:** The detection engine uses deterministic pattern matching and number parsing. Unusual or highly convoluted phrasing may be classified as `uncertain` for manual review.
- **Informational Tool:** ClauseLens Trust provides informational contract risk reviews and priority indicators; it does **NOT** provide legal advice or legal opinions.

---

## 🚀 Deployment Guide

### Option A: Docker / Docker Compose (Recommended for Production)
The repository includes a production-ready `Dockerfile` and `docker-compose.yml` preconfigured with Gunicorn and persistent volume mounts for database, uploads, and reports.

```bash
# Build and run container
docker compose up -d --build

# View container logs
docker compose logs -f
```
The application will be accessible at `http://localhost:5000`.

### Option B: Cloud Deployment (Render / Railway / Fly.io)
1. **Render:**
   - Create a **Web Service** pointing to your repository.
   - Set Environment to **Python 3**.
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 app:app`
   - Attach a persistent disk for SQLite if desired, or mount `/app/database`.

2. **Railway / Fly.io:**
   - Deploy using the included `Dockerfile`.
   - Set environment variables (`SECRET_KEY`, `UPLOAD_MAX_SIZE_MB`).

### Option C: Windows Production Server (Waitress WSGI)
Run using the production-grade multi-threaded Waitress WSGI server:

```powershell
venv\Scripts\activate
waitress-serve --listen=127.0.0.1:5000 app:app
```

---

## 📄 License
MIT License. Built for freelancers and small vendors worldwide.
