"""LegalEase - Streamlit frontend.

Mirrors the layout in the project specification: a centred logo, the
"AI Legal Document Generator" heading, four inputs, a Generate button, a dark
scrollable preview, an inline editor and three download buttons.
"""

import streamlit as st
import requests

import config
from ai_core.assets import ensure_assets
from ai_core.generator import (
    format_docx,
    format_html_preview,
    format_pdf,
    sanitize_text,
)

st.set_page_config(
    page_title="LegalEase",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Make sure the white-ink logo used on the dark chrome exists.
ensure_assets(config.IMAGE_DIR)
WEB_LOGO_PATH = config.INVERSE_LOGO_PATH

REQUEST_TIMEOUT = 180


def _slugify(text: str) -> str:
    """Build the download filename stem, e.g. 'Freelance Work Contract' -> 'freelance_work_contract'."""
    cleaned = sanitize_text(text or "").lower()
    out = []
    for ch in cleaned:
        if ch.isalnum():
            out.append(ch)
        elif ch in " -_/.":
            out.append("_")
    slug = "".join(out)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_") or "document"


def _render_header():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(WEB_LOGO_PATH, width="stretch")
    st.markdown(
        "<h2 style='text-align: center;'>AI Legal Document Generator</h2>",
        unsafe_allow_html=True,
    )


def _call_backend(document_type: str, parties: str, terms: str, dates: str):
    """POST to the FastAPI backend and return ``(document_text, error)``."""
    try:
        response = requests.post(
            f"{config.API_BASE_URL}/generate",
            json={
                "document_type": document_type,
                "parties": parties,
                "terms": terms,
                "dates": dates,
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.ConnectionError:
        return None, (
            "Backend is not running. Please start the FastAPI server first "
            "(uvicorn legalEaseAPI.main:app --port 8000)."
        )
    except requests.exceptions.Timeout:
        return None, "The backend took too long to respond. Please try again."

    if response.status_code == 200:
        try:
            return response.json()["document"], None
        except (ValueError, KeyError):
            return None, "The backend returned an unexpected response."
    if response.status_code == 422:
        return None, "Please fill in all the fields before generating a document."
    return None, f"Error generating document. Status code: {response.status_code}"



def _render_downloads(edited_text: str, document_type: str, terms: str):
    """Render the .TXT / .DOCX / .PDF download buttons."""
    stem = _slugify(document_type) or "document"
    st.download_button(
        "📄 Download as .TXT",
        data=edited_text,
        file_name=f"{stem}.txt",
        mime="text/plain",
    )
    st.download_button(
        "📝 Download as .DOCX",
        data=format_docx(edited_text, document_type, terms=terms),
        file_name=f"{stem}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    st.download_button(
        "📕 Download as .PDF",
        data=format_pdf(edited_text, document_type),
        file_name=f"{stem}.pdf",
        mime="application/pdf",
    )


def main():
    _render_header()

    document_type = st.text_input("Document Type", placeholder="Example: Agreement, Contract, NDA")
    parties = st.text_area("Parties Involved", placeholder="Enter the names of the parties")
    terms = st.text_area(
        "Terms & Conditions (Use semicolons for bullet points)",
        placeholder="Enter the terms separated by semicolons (;)",
    )
    dates = st.text_input("Effective Date", placeholder="Example: 27-09-2026")

    # A default (secondary) button, matching the specification's screenshots.
    generate = st.button("Generate Document")

    if not generate and "generated_text" not in st.session_state:
        st.info("ℹ️ Click 'Generate Document' to start")
        return

    if generate:
        if not all([document_type, parties, terms, dates]):
            st.warning("Please fill in all the fields.")
            return
        with st.spinner("Generating your document..."):
            document_text, error = _call_backend(document_type, parties, terms, dates)
        if error:
            st.error(error)
            return
        st.session_state.generated_text = sanitize_text(document_text)
        st.session_state.document_type = document_type
        st.session_state.terms = terms
        # A fresh document resets any in-progress edits.
        st.session_state.pop("editor", None)
        st.session_state.show_editor = False

    generated_text = st.session_state.get("generated_text", "")
    active_type = st.session_state.get("document_type", document_type)
    active_terms = st.session_state.get("terms", terms)

    st.success("✅ Document Generated Successfully!")
    st.markdown(format_html_preview(generated_text), unsafe_allow_html=True)

    if st.button("✏️ Click to Edit Document"):
        st.session_state.show_editor = not st.session_state.get("show_editor", False)

    edited_text = generated_text
    if st.session_state.get("show_editor", False):
        edited_text = st.text_area(
            "Edit Document Below:", generated_text, height=300, key="editor"
        )

    _render_downloads(edited_text, active_type, active_terms)


if __name__ == "__main__":
    main()
