# LegalEase

AI-powered legal document generator. Describe an agreement in plain language and
get back a complete, professionally formatted legal document that you can edit
and export as TXT, DOCX, or PDF.

LegalEase is a full-stack application built to a fixed design specification. The
specification PDF is checked in at [`docs/LegalEase.pdf`](docs/LegalEase.pdf) and
is the source of truth for the UI layout, the generated document structure, and
the export formatting.

## Features

- Four-field document input: document type, parties, terms, and effective date
- Automatic selection of standard legal clauses based on the contract profile
  (agreements, contracts, NDAs, leases, employment, and a generic fallback)
- Correct party recitals: individuals receive a "residing at" clause,
  organisations receive corporate wording
- Live HTML preview, an inline editor, and one-click TXT, DOCX, and PDF export
- Branded DOCX and PDF output with a repeating footer and a closing
  "End of Document" marker
- Works fully offline with no API key, using a deterministic built-in composer

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | Streamlit |
| Backend | FastAPI, Uvicorn |
| Generation | Google Gemini (with offline fallback) |
| Export | python-docx, fpdf2, Pillow |

## Quick start

Requires Python 3.10 or newer.

```bash
git clone https://github.com/shafeerajiji0750-jpg/LegalEase.git
cd LegalEase

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # Windows: copy .env.example .env
```

Then start both processes, in two terminals:

```bash
# Terminal 1 - backend
uvicorn legalEaseAPI.main:app --port 8000

# Terminal 2 - frontend
streamlit run frontend/app.py
```

Open http://localhost:8501.

On Linux and macOS you can start both with `./run.sh`.

## Configuration

Settings are read from a `.env` file in the repository root. Copy
[`.env.example`](.env.example) to get started.

| Variable | Default | Purpose |
| --- | --- | --- |
| `GEMINI_API_KEY` | _(empty)_ | Google AI Studio key. When missing or still the placeholder, LegalEase logs a warning and uses the offline composer. |
| `HOST` | `0.0.0.0` | Backend bind address. |
| `PORT` | `8000` | Backend port. |
| `API_BASE_URL` | `http://127.0.0.1:8000` | Backend URL used by the frontend. |
| `GEMINI_MODEL` | `gemini-1.5-pro` | Model id used for generation. |
| `ALLOW_OFFLINE_FALLBACK` | `1` | Set to `0` to fail hard instead of falling back. |

### Offline mode

The app is fully functional without an API key or network access. When Gemini
is unavailable, `ai_core/templates.py` composes the document directly, which is
also what makes the output deterministic and testable. `/health` reports which
engine is active:

```bash
curl http://127.0.0.1:8000/health
```

```json
{"status": "ok", "engine": "offline", "model": "gemini-1.5-pro"}
```

## Project structure

```
LegalEase/
├── ai_core/              Document engine (no web framework dependencies)
│   ├── templates.py        Clause selection, recitals, signature block
│   ├── generator.py        HTML preview, DOCX, and PDF rendering
│   ├── gemini_generator.py Gemini integration and offline fallback
│   ├── assets.py           Programmatic logo generation
│   └── docs/               Engine documentation
├── legalEaseAPI/         FastAPI backend
│   ├── main.py             App entry point and CORS setup
│   └── routes.py           POST /generate, GET /health
├── frontend/             Streamlit UI
│   └── app.py
├── Image/                Brand assets (Logo.png, inverseLogo.png)
├── docs/                 Design specification
├── config.py             Paths, footer text, and runtime settings
├── requirements.txt
└── run.sh
```

## API

### `POST /generate`

Generates a document from the four supplied fields.

```bash
curl -X POST http://127.0.0.1:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "document_type": "Freelance Work Contract",
    "parties": "Jane Doe (Service Provider), TechNova Inc. (Client)",
    "terms": "Deliver by May 15; Pay within 7 days;",
    "dates": "April 15, 2025"
  }'
```

| Field | Type | Description |
| --- | --- | --- |
| `document_type` | string | Contract type, for example `Agreement`, `Contract`, or `NDA`. |
| `parties` | string | Party names with optional roles in parentheses. |
| `terms` | string | Terms separated by semicolons; each becomes a bullet point. |
| `dates` | string | Effective date in any common format. |

Responds with the generated Markdown plus the engine that produced it:

```json
{"document": "## Freelance Work Contract\n\n...", "engine": "offline"}
```

Interactive API docs are available at http://127.0.0.1:8000/docs.

### `GET /health`

Reports backend status and the active generation engine.

## Generated document structure

Output follows the layout defined in the design specification:

1. Title heading
2. "Agreement made this ..." effective-date line
3. Party recitals under `Between:` and `And:`
4. `WITNESSETH:` recital and the `NOW, THEREFORE,` transition
5. Numbered clauses, with the supplied terms rendered as individual bullets
6. `IN WITNESS WHEREOF` followed by the signature block
7. The `End of Document` marker in DOCX and PDF exports

## Notes

- Generated documents are a starting point, not legal advice. Have a qualified
  attorney review anything you intend to sign or file.
- `Image/` logos are generated programmatically by `ai_core/assets.py` rather
  than being hand-designed, and are regenerated automatically if missing.
- Export formatting is driven by `fpdf2` and `python-docx`, both of which
  require the fonts bundled with those packages.

## License

All rights reserved.
