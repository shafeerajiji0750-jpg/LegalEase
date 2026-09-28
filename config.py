"""Central configuration for the LegalEase stack.

Every path is resolved absolutely from this file's location so the app behaves
identically regardless of the working directory it is launched from.
"""

import os

from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
API_HOST = os.getenv("HOST", "0.0.0.0")
API_PORT = int(os.getenv("PORT", 8000))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "Image")

# Dark-ink logo: used on the white page of the DOCX/PDF exports.
LOGO_PATH = os.path.join(IMAGE_DIR, "Logo.png")
# White-ink logo: used on the dark Streamlit chrome.
INVERSE_LOGO_PATH = os.path.join(IMAGE_DIR, "inverseLogo.png")

# Base URL the Streamlit frontend uses to reach the FastAPI backend.
API_BASE_URL = os.getenv("API_BASE_URL", f"http://127.0.0.1:{API_PORT}")

# Shown in the footer of every exported page, per the specification.
FOOTER_TEXT = "LegalEase Inc. | contact@legalease.com | All Rights Reserved."

# Closing marker printed after the signature block of exported documents.
END_MARKER = "End of Document"

# Gemini model used for document generation.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")

# Allow an explicit opt-out of the offline fallback composer (useful in tests).
ALLOW_OFFLINE_FALLBACK = os.getenv("ALLOW_OFFLINE_FALLBACK", "1") not in ("0", "false", "False")
