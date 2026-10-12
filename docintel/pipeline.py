"""The orchestrator: file + query  ->  structured result.

This is the single entry point the CLI (or any UI) calls. It wires the four
stages together in order:

    parse  ->  correct  ->  detect intent  ->  execute

and packages everything into a `Result` that always carries the five fields the
assignment asks for: file type, original query, corrected query, detected
intent, and the result itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import parsers, corrector, intent as intent_mod, executor


@dataclass
class Result:
    file_type: str
    original_query: str
    corrected_query: str
    intent: str
    confidence: float
    answer_text: str
    answer_table: pd.DataFrame | None = None
    meta: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        d = {
            "file_type": self.file_type,
            "original_query": self.original_query,
            "corrected_query": self.corrected_query,
            "intent": self.intent,
            "confidence": self.confidence,
            "result": self.answer_text,
        }
        if self.answer_table is not None:
            d["table"] = self.answer_table.to_dict(orient="records")
        return d


class Pipeline:
    """Parse a file once, then answer many queries against it."""

    def __init__(self, path: str):
        self.doc = parsers.parse(path)
        # Seed the spell-correction vocabulary with the document's own terms
        # (column names for tables, or an empty list for PDFs).
        self.vocab = corrector.build_vocabulary(self.doc.columns)

    def ask(self, query: str) -> Result:
        corr = corrector.correct(query, self.vocab)
        guess = intent_mod.detect(corr.corrected)
        answer = executor.execute(self.doc, guess.intent, corr.corrected)

        meta = dict(answer.meta or {})
        meta["intent_scores"] = guess.scores
        # Flag low-confidence calls so the UI can warn the user.
        if guess.confidence < 0.35:
            meta["note"] = (
                "Low confidence in intent detection; defaulted to the best "
                "guess. Try rephrasing for a more precise answer."
            )
        return Result(
            file_type=self.doc.file_type,
            original_query=corr.original,
            corrected_query=corr.corrected,
            intent=guess.intent,
            confidence=guess.confidence,
            answer_text=answer.text,
            answer_table=answer.table,
            meta=meta,
        )
