"""Pain mentions in the lifter's note, and medical language in AI feedback."""
from __future__ import annotations

import re

MAX_NOTE_LENGTH = 300

_PAIN = re.compile(r"\b(hurts?|hurting|pains?|painful|injur(?:y|ies|ed)|aches?|ached|aching)\b", re.IGNORECASE)

_APOS = "['’]"
_MEDICAL = [re.compile(p, re.IGNORECASE) for p in (
    r"\byou have\b",
    rf"\byou(?:{_APOS}ll| will)(?: \w+)? (?:injure|hurt|tear|damage|get (?:hurt|injured))\w*",
    r"\bwill (?:cause|lead to) (?:an? )?injur\w*",
    r"\bherniat\w*",
    r"\btorn\b",
    r"\bdiagnos\w*",
    r"\b(?:tendinitis|tendonitis|bursitis|sciatica|impingement)\b",
)]


def mentions_pain(note: str | None) -> bool:
    """True if the note mentions pain or injury. Errs toward True ("no pain" still counts)."""
    return bool(note and _PAIN.search(note))


def find_medical_language(text: str | None) -> list[str]:
    """Diagnosis or injury-prediction phrases found in `text`."""
    if not text:
        return []
    return [m.group(0) for pattern in _MEDICAL for m in pattern.finditer(text)]
