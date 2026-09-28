# Documentation

## `LegalEase.pdf`

The design specification this project was built against. It is the source of
truth for:

- the Streamlit UI layout and dark theme (including button order: Generate,
  Edit, TXT, DOCX, PDF),
- the generated document structure - title, effective date, party recitals,
  WITNESSETH clause, numbered clauses, and the signature block,
- the export footer and the closing `End of Document` marker,
- the `Image/` brand assets.

Use it when changing anything user-visible; the offline test suite in `_archive/`
asserts the document-level rules it specifies.
