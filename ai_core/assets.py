"""Brand asset generation for LegalEase.

The repository ships an ``Image/`` folder that is referenced by every exporter
(DOCX front page, PDF header) and by the Streamlit header.  This module is the
single source of truth for those assets: it renders the ``scales of justice +
wordmark`` logo shown in the project specification and writes it out as both a
normal (dark ink) and an inverse (white ink) variant for dark backgrounds.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

# The filename casing is part of the public contract - config.py resolves these.
LOGO_NAME = "Logo.png"
INVERSE_LOGO_NAME = "inverseLogo.png"

DARK_INK = (26, 32, 44)
LIGHT_INK = (255, 255, 255)
TRANSPARENT = (255, 255, 255, 0)

CANVAS = (900, 300)
SUPERSAMPLE = 4

# Serif faces that ship with Windows, tried in order of preference.
_SERIF_CANDIDATES = (
    "georgiab.ttf",
    "times.ttf",
    "cambria.ttc",
    "constan.ttf",
    "pala.ttf",
    "seguisym.ttf",
)



def _font_dirs():
    dirs = [r"C:\Windows\Fonts"]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        dirs.append(os.path.join(local, "Microsoft", "Windows", "Fonts"))
    return dirs


def load_font(size: int):
    """Return a serif TrueType font of ``size`` px, or None if none is found."""
    for name in _SERIF_CANDIDATES:
        for directory in _font_dirs():
            path = os.path.join(directory, name)
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except OSError:
                    continue
    return None


def _draw_scales(draw, ox: int, oy: int, w: int, h: int, ink):
    """Draw a scales-of-justice glyph inside the box at (ox, oy, w, h)."""
    cx = ox + w // 2
    base_y = oy + h
    top_y = oy + int(h * 0.06)
    beam_y = oy + int(h * 0.22)
    post_w = max(3, w // 34)

    # Base: wide plinth with a small tapered foot.
    plinth_h = max(4, h // 30)
    draw.rectangle([ox + int(w * 0.14), base_y - plinth_h, ox + int(w * 0.86), base_y], fill=ink)
    foot_h = max(3, h // 40)
    draw.rectangle(
        [ox + int(w * 0.32), base_y - plinth_h - foot_h, ox + int(w * 0.68), base_y - plinth_h],
        fill=ink,
    )

    # Central post.
    draw.rectangle([cx - post_w // 2, top_y, cx + post_w // 2, base_y - plinth_h - foot_h], fill=ink)

    # Finial above the beam.
    r = max(4, w // 26)
    draw.ellipse([cx - r, top_y - r, cx + r, top_y + r], fill=ink)

    # Beam, with rounded finials at each tip.
    beam_h = max(3, h // 34)
    half = int(w * 0.33)
    draw.rectangle([cx - half, beam_y, cx + half, beam_y + beam_h], fill=ink)
    tip = max(3, w // 30)
    draw.ellipse([cx - half - tip, beam_y, cx - half + tip, beam_y + 2 * tip], fill=ink)
    draw.ellipse([cx + half - tip, beam_y, cx + half + tip, beam_y + 2 * tip], fill=ink)

    # Two hanging pans, drawn as shallow arcs suspended by cords.
    pan_w = int(w * 0.30)
    pan_h = max(5, h // 16)
    cord = max(2, w // 55)
    for sign in (-1, 1):
        anchor_x = cx + sign * half
        pan_cx = cx + sign * int(w * 0.27)
        pan_top = oy + int(h * 0.56)
        draw.line([(anchor_x, beam_y + beam_h), (pan_cx, pan_top)], fill=ink, width=cord)
        draw.line(
            [(anchor_x, beam_y + beam_h), (pan_cx - pan_w // 3, pan_top)], fill=ink, width=cord
        )
        draw.line(
            [(anchor_x, beam_y + beam_h), (pan_cx + pan_w // 3, pan_top)], fill=ink, width=cord
        )
        draw.chord(
            [pan_cx - pan_w // 2, pan_top - pan_h // 2, pan_cx + pan_w // 2, pan_top + pan_h],
            start=0,
            end=180,
            fill=ink,
        )
        draw.line(
            [(pan_cx - pan_w // 2, pan_top), (pan_cx + pan_w // 2, pan_top)],
            fill=ink,
            width=max(2, h // 60),
        )


def _fit_font(draw, text: str, max_width: int, target_size: int, min_size: int = 8):
    """Largest serif font <= ``target_size`` whose ``text`` fits ``max_width``."""
    size = target_size
    while size > min_size:
        font = load_font(size)
        if font is None:
            return None
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 2
    return load_font(min_size)


def render_logo(ink=DARK_INK, wordmark: str = "LegalEase") -> Image.Image:
    """Render the LegalEase lockup at ``SUPERSAMPLE`` resolution with alpha."""
    width, height = CANVAS
    img = Image.new("RGBA", (width * SUPERSAMPLE, height * SUPERSAMPLE), TRANSPARENT)
    draw = ImageDraw.Draw(img)

    s = SUPERSAMPLE
    icon_w = int(width * 0.28) * s
    _draw_scales(
        draw, int(width * 0.02) * s, int(height * 0.10) * s, icon_w, int(height * 0.80) * s, ink
    )

    text_x = int(width * 0.02) * s + icon_w + int(width * 0.05) * s
    avail = width * s - text_x - int(width * 0.02) * s
    font = _fit_font(draw, wordmark, avail, int(height * 0.44) * s)
    if font is not None:
        bbox = draw.textbbox((0, 0), wordmark, font=font)
        text_y = (height * s - (bbox[3] - bbox[1])) // 2 - bbox[1]
        draw.text((text_x, text_y), wordmark, font=font, fill=tuple(ink) + (255,))
    else:  # pragma: no cover - only on systems with no TrueType font at all
        draw.rectangle(
            [text_x, height * s // 3, text_x + int(avail * 0.9), height * s * 2 // 3],
            outline=tuple(ink) + (255,),
            width=3 * s,
        )
    return img.resize(CANVAS, Image.LANCZOS)


def write_logo(directory: str, ink=DARK_INK, name: str = LOGO_NAME) -> str:
    """Render and save one logo variant inside ``directory``; return its path."""
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, name)
    render_logo(ink=ink).save(path)
    return path


def is_usable_logo(path: str) -> bool:
    """True when ``path`` exists, is non-empty and decodes as an image."""
    if not path or not os.path.exists(path) or os.path.getsize(path) == 0:
        return False
    try:
        with Image.open(path) as probe:
            probe.verify()
    except Exception:
        return False
    return True


def ensure_assets(directory: str, force: bool = False) -> dict:
    """Create the logo assets if missing/corrupt and return their paths.

    A file counts as missing if it does not exist, is empty, or cannot be
    decoded by Pillow - the originally checked-in files are 0-byte stubs.
    """
    os.makedirs(directory, exist_ok=True)
    results = {}
    for name, ink in ((LOGO_NAME, DARK_INK), (INVERSE_LOGO_NAME, LIGHT_INK)):
        path = os.path.join(directory, name)
        if force or not is_usable_logo(path):
            write_logo(directory, ink=ink, name=name)
        results[name] = path
    return results


if __name__ == "__main__":  # pragma: no cover
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for key, value in ensure_assets(os.path.join(here, "Image"), force=True).items():
        print(f"wrote {key}: {value}")
