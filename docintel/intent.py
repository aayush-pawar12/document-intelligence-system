"""Intent detection -- which of the seven operations does the query want?

Intents: Summary, Search, Filter, Count, Aggregation, Sorting, Analytics.

Rather than hardcode "if 'summarize' in query", each intent owns a set of
signal words and regex patterns. We score every intent against the query and
pick the winner. The margin between the top two scores becomes a confidence
value, which lets the pipeline fall back gracefully when it is unsure.

Ordering note: some words overlap (e.g. "top 5 highest expenses" contains both a
sorting signal and an aggregation word). Patterns are weighted so the more
specific signal wins -- "top N" strongly implies Sorting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


SUMMARY = "Summary"
SEARCH = "Search"
FILTER = "Filter"
COUNT = "Count"
AGGREGATION = "Aggregation"
SORTING = "Sorting"
ANALYTICS = "Analytics"

INTENTS = [SUMMARY, SEARCH, FILTER, COUNT, AGGREGATION, SORTING, ANALYTICS]


@dataclass
class IntentGuess:
    intent: str
    confidence: float          # 0..1
    scores: dict               # per-intent raw scores, for transparency


# Each rule is (weight, compiled_regex). Higher weight = stronger signal.
def _rx(pattern: str):
    return re.compile(pattern, re.IGNORECASE)


_RULES: dict[str, list[tuple[int, re.Pattern]]] = {
    SUMMARY: [
        (3, _rx(r"\bsummar")), (3, _rx(r"\boverview\b")),
        (2, _rx(r"\bdescribe\b")), (2, _rx(r"\bwhat('?s| is) (this|the)\b")),
        (1, _rx(r"\btell me about\b")), (1, _rx(r"\bgist\b")),
    ],
    COUNT: [
        (3, _rx(r"\bhow many\b")), (3, _rx(r"\bcount\b")),
        (2, _rx(r"\bnumber of\b")), (1, _rx(r"\btotal (number|count)\b")),
    ],
    AGGREGATION: [
        (3, _rx(r"\b(sum|total) of\b")), (3, _rx(r"\baverage|avg|mean\b")),
        (2, _rx(r"\b(sum|total)\b")),
        (2, _rx(r"\b(maximum|minimum)\b")),
        (2, _rx(r"\bgroup(ed)? by\b")), (2, _rx(r"\b(by|per) \w+")),
        (1, _rx(r"\b(max|min)\b")),
    ],
    SORTING: [
        (4, _rx(r"\btop \d+")), (4, _rx(r"\bbottom \d+")),
        (3, _rx(r"\b(highest|lowest|largest|smallest)\b")),
        (2, _rx(r"\bsort(ed)?\b")), (2, _rx(r"\border by\b")),
        (2, _rx(r"\b(most|least) expensive\b")), (2, _rx(r"\bcheapest\b")),
        (1, _rx(r"\brank")),
    ],
    FILTER: [
        (4, _rx(r"\b(above|below|over|under|greater than|less than|more than)\b")),
        (3, _rx(r"\bwhere\b")),
        (2, _rx(r"\b(from|in|with|having)\b.+")),
        (2, _rx(r"[<>]=?\s*\d")),
        (2, _rx(r"\b(equal to|equals|is)\b")),
        (1, _rx(r"\bbetween\b.+\band\b")),
    ],
    SEARCH: [
        (3, _rx(r"\b(find|search)\b")), (2, _rx(r"\brelated to\b")),
        (2, _rx(r"\bcontaining|contains\b")), (2, _rx(r"\blook up\b")),
        (1, _rx(r"\b(show|list|get|give)\b")),
    ],
    ANALYTICS: [
        (3, _rx(r"\banalytics?\b")), (3, _rx(r"\binsights?\b")),
        (2, _rx(r"\bstatistics|stats\b")), (2, _rx(r"\bdistribution\b")),
        (2, _rx(r"\bbreakdown\b")), (1, _rx(r"\btrend")),
    ],
}


def detect(query: str) -> IntentGuess:
    scores = {name: 0 for name in INTENTS}
    for intent, rules in _RULES.items():
        for weight, rx in rules:
            if rx.search(query):
                scores[intent] += weight

    best = max(scores, key=scores.get)
    top = scores[best]

    # Nothing matched -> default to Search (most forgiving) with low confidence.
    if top == 0:
        return IntentGuess(SEARCH, 0.25, scores)

    # Confidence = how dominant the winner is over the runner-up, blended with
    # how strong the absolute signal was.
    ordered = sorted(scores.values(), reverse=True)
    runner_up = ordered[1] if len(ordered) > 1 else 0
    margin = (top - runner_up) / top
    strength = min(top / 5.0, 1.0)
    confidence = round(0.5 * margin + 0.5 * strength, 2)
    return IntentGuess(best, confidence, scores)
