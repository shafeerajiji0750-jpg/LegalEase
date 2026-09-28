"""Deterministic legal-document composer used as the offline fallback.

The shipped ``.env`` only carries a placeholder Gemini key, so the stack would
otherwise be unusable out of the box.  This module composes a complete,
well-formed agreement from the same four user inputs that the Gemini prompt
receives, reproducing the section structure shown in the project
specification (``WITNESSETH`` recital, numbered operative clauses, execution
block).  It is used by :mod:`ai_core.gemini_generator` whenever the remote
model is unavailable, which keeps the product demonstrably functional and makes
it end-to-end testable without network access.
"""

from __future__ import annotations

import re
from datetime import date, datetime

_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

_DEFAULT_ROLES = ("First Party", "Second Party")

# Clause blueprints keyed by a keyword that appears in the document type.
_PROFILES = (
    (
        ("nda", "non-disclosure", "non disclosure", "confidentiality", "confidential"),
        "Non-Disclosure Agreement",
        (
            "Definition of Confidential Information",
            "Obligations of the Receiving Party",
            "Exclusions from Confidentiality",
            "Return or Destruction of Materials",
            "Term and Survival",
            "Remedies for Breach",
            "Governing Law",
            "Entire Agreement",
            "Severability",
        ),
    ),
    (
        ("lease", "tenancy", "rental"),
        "Lease Agreement",
        (
            "Premises",
            "Term of Lease",
            "Rent and Security Deposit",
            "Utilities and Maintenance",
            "Use of Premises",
            "Termination and Default",
            "Governing Law",
            "Entire Agreement",
            "Severability",
        ),
    ),
    (
        ("employment", "employment", "hiring", "offer"),
        "Employment Contract",
        (
            "Position and Duties",
            "Compensation and Benefits",
            "Working Hours and Leave",
            "Confidentiality",
            "Intellectual Property Assignment",
            "Termination of Employment",
            "Governing Law",
            "Entire Agreement",
            "Severability",
        ),
    ),
    (
        ("contract", "agreement", "service", "consulting", "freelance"),
        "Agreement",
        (
            "Scope of Services",
            "Term and Termination",
            "Payment",
            "Intellectual Property Rights",
            "Confidentiality",
            "Independent Contractor Status",
            "Governing Law",
            "Entire Agreement",
            "Severability",
        ),
    ),
)

# Used when the document type matches none of the blueprints above.
_DEFAULT_CLAUSES = (
    "Scope and Obligations",
    "Term and Termination",
    "Compensation",
    "Confidentiality",
    "Intellectual Property",
    "Representations and Warranties",
    "Governing Law",
    "Entire Agreement",
    "Severability",
)


# --------------------------------------------------------------------------- #
# Input parsing helpers
# --------------------------------------------------------------------------- #

def split_terms(terms: str):
    """Split the semicolon separated 'Terms' input into a clean bullet list."""
    if not terms:
        return []
    parts = re.split(r"[;\n]+", terms)
    out = []
    for part in parts:
        cleaned = part.strip().lstrip("-*•").strip()
        cleaned = re.sub(r"^\d+[.)]\s*", "", cleaned)
        if cleaned:
            out.append(cleaned)
    return out


def _split_top_level(text: str, sep: str):
    """Split ``text`` on ``sep`` while ignoring separators inside parentheses."""
    parts, buf, depth = [], [], 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == sep and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return parts


#: Matches a trailing "(Role)" suffix on a party fragment.
_ROLE_RE = re.compile(r"^(.*?)\s*\(([^)]*)\)\s*$")


def split_parties(parties: str):
    """Split the 'Parties' input into ``(name, role)`` tuples.

    Accepts ``"Jane Doe (Service Provider), TechNova Inc. (Client)"`` and the
    bare ``"Jane Doe, TechNova Inc."`` form.  Missing roles fall back to the
    neutral 'First Party' / 'Second Party' labels.
    """
    if not parties:
        return []
    chunks = [c.strip() for c in _split_top_level(parties, ",") if c.strip()]

    # A comma only separates parties when the fragment that follows it does not
    # carry a "(role)" suffix, so "Smith, John (Attorney)" stays a single party.
    merged = []
    for chunk in chunks:
        if merged and not _ROLE_RE.match(merged[-1]) and _ROLE_RE.match(chunk):
            merged[-1] = merged[-1] + ", " + chunk
        else:
            merged.append(chunk)

    parsed = []
    for chunk in merged:
        match = _ROLE_RE.match(chunk)
        if match:
            name, role = match.group(1).strip(), match.group(2).strip()
        else:
            idx = len(parsed)
            role = _DEFAULT_ROLES[idx] if idx < len(_DEFAULT_ROLES) else f"Party {idx + 1}"
            name = chunk
        if name:
            parsed.append((name, role or "Party"))
    return parsed


_DATE_PATTERNS = (
    "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y", "%B %d %Y", "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d",
)


def parse_date(raw: str):
    """Best-effort parse of the 'Effective Date' input into a ``date``."""
    if not raw:
        return None
    text = raw.strip().rstrip(".")
    for fmt in _DATE_PATTERNS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    return None


def ordinal(day: int) -> str:
    if 11 <= day % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def format_effective_date(raw: str) -> str:
    """Render the effective date the way the specification's sample does."""
    parsed = parse_date(raw)
    if parsed is None:
        return (raw or "").strip()
    return f"{ordinal(parsed.day)} day of {_MONTHS[parsed.month - 1]}, {parsed.year}"


# --------------------------------------------------------------------------- #
# Document composition
# --------------------------------------------------------------------------- #

def select_clauses(document_type: str):
    """Pick the clause blueprint that best matches ``document_type``."""
    haystack = (document_type or "").lower()
    for keywords, _label, clauses in _PROFILES:
        if any(keyword in haystack for keyword in keywords):
            return list(clauses)
    return list(_DEFAULT_CLAUSES)


#: Name endings that indicate the party is a company rather than a person.
_CORPORATE_SUFFIXES = (
    "inc", "inc.", "llc", "l.l.c", "ltd", "ltd.", "limited", "corp", "corp.",
    "corporation", "company", "co", "co.", "plc", "gmbh", "s.a.", "s.a.s",
    "pvt", "pvt.", "partners", "holdings", "group",
)


def _is_corporate(name: str) -> bool:
    """True when ``name`` looks like a company rather than an individual."""
    cleaned = re.sub(r"[^\w.\s]", " ", (name or "").lower()).strip()
    tokens = [t for t in cleaned.replace(".", " ").split() if t]
    if not tokens:
        return False
    return tokens[-1].rstrip(".") in {s.rstrip(".") for s in _CORPORATE_SUFFIXES}


def _describe_party(name: str, role: str, index: int) -> str:
    """Build the recital sentence for a party, mirroring the sample output."""
    if index == 0:
        return (
            f'{name} (hereinafter referred to as the "{role}"), residing at '
            f"[{name}'s Address], [{name}'s City, State, Zip Code]"
        )
    if _is_corporate(name):
        return (
            f'{name} (hereinafter referred to as the "{role}"), a corporation organized '
            f"and existing under the laws of [State of Incorporation], with its "
            f"principal place of business at [{name}'s Address], "
            f"[{name}'s City, State, Zip Code]"
        )
    return (
        f'{name} (hereinafter referred to as the "{role}"), with its principal place '
        f"of business at [{name}'s Address], [{name}'s City, State, Zip Code]"
    )


def _generic_body(title: str, role_a: str, role_b: str) -> str:
    lowered = title.lower()
    if "governing law" in lowered:
        return (
            "This Agreement shall be governed by and construed in accordance with the "
            "laws of the State of [State]."
        )
    if "entire agreement" in lowered:
        return (
            "This Agreement constitutes the entire understanding and agreement of the "
            "parties with respect to the subject matter hereof and supersedes all prior "
            "or contemporaneous communications, representations, or agreements, whether "
            "oral or written."
        )
    if "severab" in lowered:
        return (
            "If any provision of this Agreement is held to be invalid or unenforceable, "
            "the remaining provisions shall remain in full force and effect."
        )
    if "confidential" in lowered:
        return (
            f"Each party acknowledges that during the performance of this Agreement it "
            f"may receive confidential information from the other party. The receiving "
            f"party shall maintain the confidentiality of all such information and shall "
            f"not disclose it to any third party without prior written consent. This "
            f"obligation shall survive the termination of this Agreement."
        )
    if "intellectual property" in lowered:
        return (
            f"All intellectual property rights in any work product created by the {role_a} "
            f'in connection with this Agreement (the "Work Product") shall be the sole '
            f"and exclusive property of the {role_b}. The {role_a} hereby assigns all "
            f"such rights to the {role_b}."
        )
    return (
        f"The parties agree to cooperate in good faith and to perform their respective "
        f"obligations under this Agreement with reasonable skill, care, and diligence."
    )


def _clause_body(title: str, role_a: str, role_b: str, term_bullets, index: int) -> str:
    """Produce the prose body for one operative clause."""
    lowered = title.lower()
    if index == 0:
        if term_bullets:
            # The specification asks for user terms as bulleted points, and the
            # input itself is semicolon separated, so keep them as a list.
            bullets = "\n".join(f"- {term}" for term in term_bullets)
            return (
                f"The {role_a} agrees to provide the following services to the {role_b} "
                f'(the "Services"):\n\n{bullets}'
            )
        return (
            f'The {role_a} agrees to provide the following services to the {role_b} '
            f'(the "Services"): Clearly and comprehensively describe the services to be '
            f"rendered, including specific tasks, deliverables, and any required milestones."
        )
    if "independent contractor" in lowered or "contractor status" in lowered:
        return (
            f"The {role_a} is an independent contractor and not an employee of the "
            f"{role_b}. The {role_a} shall be solely responsible for the payment of all "
            f"taxes and other contributions arising from the performance of the Services."
        )
    if "payment" in lowered or "compensation" in lowered or "rent" in lowered:
        return (
            f"The {role_b} agrees to pay the {role_a} the fees set out in the schedule "
            "attached hereto. Payment shall be made within seven (7) days of receipt of "
            "a valid invoice, detailing the work performed and the amount due."
        )
    if "term" in lowered or "survival" in lowered or "termination" in lowered:
        return (
            "This Agreement commences on the Effective Date and continues until the "
            "obligations herein are fully performed. Either party may terminate this "
            "Agreement upon fifteen (15) days written notice to the other party."
        )
    if "remedies" in lowered or "breach" in lowered:
        return (
            "Any breach of this Agreement by either party shall entitle the non-breaching "
            "party to seek equitable relief, including injunctive relief, in addition to "
            "any other remedies available at law or in equity."
        )
    if "exclusion" in lowered:
        return (
            "Confidential Information does not include information that is or becomes "
            "publicly available through no fault of the receiving party, that was already "
            "known prior to disclosure, or that is independently developed."
        )
    if "return or destruction" in lowered:
        return (
            f"Upon written request of the {role_b}, the {role_a} shall promptly return or "
            "irreversibly destroy all materials containing Confidential Information and "
            "certify such destruction in writing."
        )
    if "position" in lowered or "duties" in lowered:
        return (
            f"The {role_a} shall devote such time, attention, and skill as is reasonably "
            f"necessary to perform the duties assigned, and shall cooperate with the "
            f"{role_b} in the execution of those duties."
        )
    if "premises" in lowered:
        return (
            f"The {role_b} hereby leases to the {role_a} the premises described in the "
            "schedule attached hereto, together with the right to use the common areas "
            "reasonably necessary for the permitted use."
        )
    if "representations" in lowered:
        return (
            "Each party represents and warrants that it has full power and authority to "
            "enter into this Agreement and that its obligations hereunder are not in "
            "conflict with any other agreement to which it is a party."
        )
    if "definition of confidential" in lowered:
        return (
            '"Confidential Information" means any non-public information disclosed by '
            "either party to the other, whether orally, in writing, or by inspection of "
            "tangible objects, that is designated as confidential or that reasonably "
            "should be understood to be confidential."
        )
    return _generic_body(title, role_a, role_b)


def compose_document(document_type: str, parties: str, terms: str, dates: str) -> str:
    """Compose a complete agreement from the four user inputs.

    The returned text is markdown-flavoured, matching what the Gemini prompt
    requests: ``##`` for the title, ``**bold**`` for clause headings and plain
    paragraphs for the body.
    """
    doc_type = (document_type or "Agreement").strip() or "Agreement"
    parsed = split_parties(parties) or [("First Party", "First Party"), ("Second Party", "Second Party")]
    term_bullets = split_terms(terms)
    effective = format_effective_date(dates)
    clauses = select_clauses(doc_type)

    first = parsed[0]
    second = parsed[1] if len(parsed) > 1 else ("Second Party", "Second Party")
    role_a, role_b = first[1], second[1]

    out = [f"## {doc_type}", ""]
    out.append(f"Agreement made this {effective}" if effective else "Agreement made on the Effective Date")
    out += ["", "**Between:**", "", _describe_party(first[0], role_a, 0), ""]
    out += ["**And:**", "", _describe_party(second[0], role_b, 1), ""]
    out += [
        "**WITNESSETH:**",
        "",
        f"WHEREAS, the {role_b} desires to engage the {role_a} to perform the services described herein; and",
        "",
        f"WHEREAS, the {role_a} is willing to perform such services for the {role_b} on the terms and "
        "conditions set forth in this Agreement;",
        "",
        "**NOW, THEREFORE,** in consideration of the mutual covenants and promises contained herein, "
        "the parties agree as follows:",
    ]

    for idx, title in enumerate(clauses, start=1):
        out += ["", f"**{idx}. {title}:**", ""]
        out.append(_clause_body(title, role_a, role_b, term_bullets, idx - 1))

    out += ["", "IN WITNESS WHEREOF, the parties have executed this Agreement as of the Effective Date."]
    # Signature block: rule, party, then representative details under the first
    # party -- matching the layout in the specification.
    for pos, (name, role) in enumerate((first, second)):
        out += ["", "______________", "", f"{name} ({role})"]
        if pos == 0:
            out += ["", "[Authorized Representative Signature]", ""]
            out += ["[Authorized Representative Title]"]
    out.append("")
    return "\n".join(out)
