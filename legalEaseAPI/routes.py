"""API routes for LegalEase document generation."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai_core.gemini_generator import GeminiDocumentGenerator

logger = logging.getLogger(__name__)

router = APIRouter()

try:
    gemini_generator = GeminiDocumentGenerator()
except Exception as exc:  # pragma: no cover - defensive
    logger.error("Failed to build the generator: %s", exc)
    gemini_generator = None


class DocumentRequest(BaseModel):
    """Payload accepted by ``POST /generate``."""

    document_type: str = Field(..., min_length=1, description="e.g. Agreement, Contract, NDA")
    parties: str = Field(..., min_length=1, description="Names and roles of the parties")
    terms: str = Field(..., min_length=1, description="Semicolon separated terms")
    dates: str = Field(..., min_length=1, description="Effective date of the agreement")


class DocumentResponse(BaseModel):
    """Successful response returned by ``POST /generate``."""

    document: str
    engine: str


@router.get("/health")
def health():
    """Report backend and generation-engine status."""
    import config

    if gemini_generator is None:
        engine = "unavailable"
        model = config.GEMINI_MODEL
    else:
        engine = "gemini" if gemini_generator.is_live else "offline"
        model = gemini_generator.model_name
    return {"status": "ok", "engine": engine, "model": model}


@router.post("/generate", response_model=DocumentResponse)
def generate_legal_document(request: DocumentRequest):
    """Generate a legal document from the four user-supplied fields."""
    if gemini_generator is None:
        raise HTTPException(
            status_code=500,
            detail="Gemini API Key missing or generator uninitialized.",
        )
    try:
        doc_text = gemini_generator.generate_document(
            document_type=request.document_type,
            parties=request.parties,
            terms=request.terms,
            dates=request.dates,
        )
    except Exception as exc:
        logger.exception("Document generation failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not doc_text:
        raise HTTPException(status_code=502, detail="The generator returned an empty document.")

    return {"document": doc_text, "engine": gemini_generator.last_engine or "gemini"}
