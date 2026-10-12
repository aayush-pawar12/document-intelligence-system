"""Command-line interface.

Two ways to use it:

    # one-shot
    python -m docintel.cli samples/employees.csv "list all employees from Mumbai"

    # interactive REPL (keeps the file loaded, ask many questions)
    python -m docintel.cli samples/employees.csv
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from .pipeline import Pipeline, Result


def _render(result: Result) -> str:
    """Format a Result as the structured block the assignment specifies."""
    bar = "=" * 60
    lines = [
        bar,
        f"  File type       : {result.file_type}",
        f"  Original query  : {result.original_query}",
        f"  Corrected query : {result.corrected_query}",
        f"  Detected intent : {result.intent}  (confidence {result.confidence})",
        bar,
        "  Result:",
    ]
    for ln in result.answer_text.splitlines():
        lines.append(f"    {ln}")
    if result.answer_table is not None and len(result.answer_table):
        with pd.option_context("display.max_rows", 20,
                               "display.max_columns", 20,
                               "display.width", 120):
            rendered = result.answer_table.to_string(index=False)
        lines.append("")
        for ln in rendered.splitlines():
            lines.append(f"    {ln}")
    if result.meta.get("note"):
        lines.append("")
        lines.append(f"  Note: {result.meta['note']}")
    lines.append(bar)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="docintel",
        description="Ask plain-English questions about a PDF / Excel / CSV file.")
    ap.add_argument("file", help="path to the document")
    ap.add_argument("query", nargs="*", help="natural-language query")
    args = ap.parse_args(argv)

    try:
        pipe = Pipeline(args.file)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.query:
        print(_render(pipe.ask(" ".join(args.query))))
        return 0

    # interactive mode
    print(f"Loaded {pipe.doc.file_type} file. Type a query, or 'quit' to exit.")
    while True:
        try:
            q = input("\nquery> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if q.lower() in {"quit", "exit", "q"}:
            break
        if q:
            print(_render(pipe.ask(q)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
