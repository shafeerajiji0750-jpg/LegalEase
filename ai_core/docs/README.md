# ai_core

The LegalEase engine layer. Everything in this package is independent of the
web frameworks: it has no knowledge of FastAPI or Streamlit, which keeps the
document logic testable and reusable.

## Modules

| Module | Responsibility |
| --- | --- |
| `templates.py` | Composes the legal document from the four user inputs. Owns clause selection per contract profile, party recitals, and the signature block. |
| `generator.py` | Renders a composed document to HTML preview, DOCX, and PDF. |
| `gemini_generator.py` | Optional Gemini-backed composer. Falls back to the offline `templates.py` composer when the API key is missing or a placeholder. |
| `assets.py` | Generates the `Image/` brand logos (dark-ink and white-ink variants). |

## Generation flow

```
user input
   │
   ├─► gemini_generator.GeminiDocumentGenerator
   │        └─ key missing / call failed  ──►  templates.compose_document  (offline)
   │
   └─► markdown document string
            │
            └─► generator.format_html_preview / format_docx / format_pdf
```

The offline path is the default in development, so the app produces a complete,
spec-compliant document with no network access and no API key.

## Document contract

`compose_document` returns Markdown that follows the layout in the design
specification (`docs/LegalEase.pdf`):

1. Title heading (`##`)
2. "Agreement made this …" effective-date line
3. `**Between:**` / `**And:**` party recitals - individuals get a *residing at*
   recital, organisations get a *a corporation organized and existing under*
   recital
4. `**WITNESSETH:**` recital and `**NOW, THEREFORE,**` transition
5. Numbered clauses (`**1. **`, `**2. **` …), with the user's terms rendered as
   individual bullet points
6. `IN WITNESS WHEREOF`, then the signature block
7. `End of Document` marker in the DOCX and PDF exports

## Tests

`tests/` lives at the repository root and covers this package. Run the full
suite with:

```
python tests/run_all.py
```
