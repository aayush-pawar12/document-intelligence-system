"""Document Intelligence System.

A lightweight, rule-based system that reads PDF / Excel / CSV files and answers
plain-English queries about them. No LLMs involved -- everything runs on
tokenisation, edit-distance spell correction, and pattern-based intent routing.
"""

__version__ = "1.0.0"

from .pipeline import Pipeline, Result

__all__ = ["Pipeline", "Result"]
