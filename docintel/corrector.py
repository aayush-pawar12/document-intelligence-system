"""Query spell / grammar correction -- no LLM, pure edit-distance matching.

The idea: every word the user types is checked against a *vocabulary*. The
vocabulary is two things glued together:

1. A small built-in list of command words the system understands
   ("summarize", "filter", "above", "count", ...).
2. The actual column names and text pulled from the uploaded document, so a
   query like "GPA" or "Mumbai" is never "corrected" into something wrong.

For each word we find the closest vocabulary entry using RapidFuzz (Levenshtein
ratio). If it is close enough but not identical, we swap it in. Words that are
already correct, numbers, and very short tokens are left alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import process, fuzz


# Command vocabulary: the words that carry meaning for intent detection.
# Keeping these correct is what matters most, so they always seed the vocab.
_COMMAND_WORDS = {
    "summarize", "summary", "overview", "describe", "tell", "about",
    "search", "find", "show", "list", "get", "give", "lookup", "related",
    "filter", "where", "from", "with", "above", "below", "over", "under",
    "greater", "less", "than", "equal", "between", "contains", "matching",
    "count", "how", "many", "number", "total", "rows",
    "sum", "average", "avg", "mean", "max", "maximum", "min", "minimum",
    "aggregate", "aggregation",
    "sort", "sorted", "order", "top", "bottom", "highest", "lowest", "first",
    "last", "best", "worst", "cheapest", "expensive",
    "analytics", "analyse", "analyze", "analysis", "statistics", "stats",
    "distribution", "breakdown", "trend", "insights",
    "this", "that", "the", "all", "of", "in", "and", "or", "by", "for",
    "document", "file", "data", "records", "entries",
}

# A tiny set of common English words so ordinary typos still get fixed even when
# the document is small. Deliberately short -- we are not shipping a dictionary.
_COMMON_WORDS = {
    "employee", "employees", "student", "students", "product", "products",
    "expense", "expenses", "price", "cost", "amount", "salary", "quantity",
    "stock", "name", "city", "department", "category", "date", "year", "age",
    "score", "grade", "gpa", "rating", "status", "available", "outstanding",
}

# Minimum similarity (0-100) to accept a correction. Below this we keep the
# original word rather than risk a confident-but-wrong fix.
_THRESHOLD = 82
_MIN_LEN = 3  # don't try to correct 1-2 letter tokens


@dataclass
class Correction:
    original: str
    corrected: str
    changed: bool


def build_vocabulary(doc_terms: list[str] | None = None) -> set[str]:
    """Combine command words, common words, and document-specific terms."""
    vocab = set(_COMMAND_WORDS) | set(_COMMON_WORDS)
    for term in doc_terms or []:
        for piece in re.split(r"[\s_/\-]+", str(term).lower()):
            if piece.isalpha() and len(piece) >= 2:
                vocab.add(piece)
    return vocab


def _correct_token(token: str, vocab: set[str]) -> str:
    low = token.lower()
    if low in vocab:                      # already a known word
        return token
    if len(low) < _MIN_LEN or not low.isalpha():
        return token                      # numbers, short tokens: leave as-is
    match = process.extractOne(low, vocab, scorer=fuzz.ratio)
    if match and match[1] >= _THRESHOLD:
        best = match[0]
        # Preserve capitalisation of the original where it makes sense.
        return best.capitalize() if token[0].isupper() else best
    return token


def correct(query: str, vocab: set[str] | None = None) -> Correction:
    """Return the query with per-word spelling fixes applied."""
    vocab = vocab or build_vocabulary()
    # Split into words + the gaps between them so punctuation/spacing survive.
    parts = re.split(r"(\W+)", query)
    fixed = [
        _correct_token(p, vocab) if p.strip() and p.isalnum() else p
        for p in parts
    ]
    corrected = "".join(fixed)
    corrected = _tidy_grammar(corrected)
    return Correction(original=query, corrected=corrected,
                      changed=corrected.strip().lower() != query.strip().lower())


def _tidy_grammar(text: str) -> str:
    """Light cosmetic grammar clean-up (not a full grammar engine)."""
    text = re.sub(r"\s+", " ", text).strip()        # collapse whitespace
    text = re.sub(r"\s+([?.!,])", r"\1", text)       # no space before punctuation
    if text:
        text = text[0].upper() + text[1:]            # capitalise first letter
    return text
