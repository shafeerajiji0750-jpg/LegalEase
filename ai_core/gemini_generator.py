"""Gemini-backed document generation with a deterministic offline fallback."""

from __future__ import annotations

import logging

import google.generativeai as genai

import config
from ai_core.templates import compose_document

logger = logging.getLogger(__name__)

# Keys that mean "no real credential was configured".
_PLACEHOLDERS = {"", "your_actual_gemini_api_key_here", "your_gemini_api_key", "none", "null"}


def has_usable_key() -> bool:
    """True when ``GEMINI_API_KEY`` holds something other than a placeholder."""
    return (config.GEMINI_API_KEY or "").strip().lower() not in _PLACEHOLDERS


class GeminiDocumentGenerator:
    """Generate legal documents with Gemini, falling back to the local composer.

    The specification ships a placeholder API key, so the remote model is
    frequently unavailable.  Rather than failing the request, this class
    degrades to :func:`ai_core.templates.compose_document`, which produces the
    same markdown structure.  ``last_engine`` records which path served a
    given request so the frontend can surface it.
    """

    def __init__(self, model_name: str = None, allow_fallback: bool = None):
        self.model_name = model_name or config.GEMINI_MODEL
        self.allow_fallback = (
            config.ALLOW_OFFLINE_FALLBACK if allow_fallback is None else allow_fallback
        )
        self.model = None
        self.last_engine = None
        self.model = self._init_model()

    def _init_model(self):
        if not has_usable_key():
            logger.warning(
                "GEMINI_API_KEY is missing or a placeholder; using the offline composer."
            )
            return None
        try:
            genai.configure(api_key=config.GEMINI_API_KEY)
            return genai.GenerativeModel(self.model_name)
        except Exception as exc:  # pragma: no cover - depends on remote SDK state
            logger.warning("Could not initialise Gemini (%s); using the offline composer.", exc)
            return None

    @property
    def is_live(self) -> bool:
        """True when a real Gemini model instance is available."""
        return self.model is not None

    def build_prompt(self, document_type: str, parties: str, terms: str, dates: str) -> str:
        """Build the prompt described in the project specification."""
        return (
            f"Generate a comprehensive and legally sound document titled '{document_type}'.\n\n"
            f"Involved Parties:\n{parties}\n\n"
            f"Effective Date:\n{dates}\n\n"
            f"Terms and Conditions / Specific Clauses:\n{terms}\n\n"
            "Instructions:\n"
            "1. Ensure a formal legal structure with standard professional clauses (e.g., "
            "WITNESSETH, Term & Termination, Payment, Intellectual Property, Confidentiality, "
            "Governing Law, Severability, Signatures).\n"
            "2. Incorporate all user-specified terms as detailed clauses or bulleted points.\n"
            "3. Use Markdown headings (## and ###) for section titles.\n"
            "4. Do not include introductory/outro conversational text; output ONLY the complete "
            "legal document."
        )

    def generate_document(self, document_type: str, parties: str, terms: str, dates: str) -> str:
        """Generate the document, preferring Gemini and degrading gracefully."""
        if self.model is not None:
            try:
                response = self.model.generate_content(
                    self.build_prompt(document_type, parties, terms, dates)
                )
                text = (response.text or "").strip()
                if text:
                    self.last_engine = "gemini"
                    return text
                logger.warning("Gemini returned an empty document; using the offline composer.")
            except Exception as exc:
                if not self.allow_fallback:
                    raise
                logger.warning("Gemini request failed (%s); using the offline composer.", exc)

        if not self.allow_fallback:
            raise RuntimeError(
                "Gemini is unavailable and the offline fallback is disabled."
            )
        self.last_engine = "offline"
        return compose_document(document_type, parties, terms, dates)
