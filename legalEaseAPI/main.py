"""FastAPI application entry point for LegalEase."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from legalEaseAPI.routes import router

app = FastAPI(
    title="LegalEase - AI Legal Document Generator",
    description=(
        "Generate professional legal documents from parties, terms and an "
        "effective date, then export them as .txt, .docx or .pdf."
    ),
    version="1.0.0",
)

# The Streamlit frontend runs on a different origin, so allow cross-origin calls.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)


# Root endpoint
@app.get("/")
def home():
    return {"message": "Welcome to LegalEase AI Legal Document Generator API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)