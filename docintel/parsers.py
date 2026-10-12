"""File parsing layer.

Turns a raw file on disk into a `Document` -- a normalised container the rest of
the system understands. Two shapes of document exist:

* TABULAR  -> backed by a pandas DataFrame (CSV / Excel)
* TEXT     -> backed by a plain string (PDF)

Adding a new file type means writing one more `_parse_*` function and registering
its extension in `EXTENSIONS`. Nothing downstream needs to change.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import pandas as pd


TABULAR = "tabular"
TEXT = "text"


@dataclass
class Document:
    """Normalised view of a parsed file."""

    kind: str                       # TABULAR or TEXT
    file_type: str                  # friendly label: CSV, Excel, PDF
    path: str
    table: pd.DataFrame | None = None
    text: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def columns(self) -> list[str]:
        if self.table is not None:
            return list(self.table.columns)
        return []


def _parse_csv(path: str) -> Document:
    # sep=None + engine="python" lets pandas sniff commas vs. semicolons vs. tabs.
    df = pd.read_csv(path, sep=None, engine="python")
    df = _clean_frame(df)
    return Document(kind=TABULAR, file_type="CSV", path=path, table=df,
                    meta={"rows": len(df), "cols": len(df.columns)})


def _parse_excel(path: str) -> Document:
    # Read the first sheet only; keep its name in meta for transparency.
    xls = pd.ExcelFile(path)
    sheet = xls.sheet_names[0]
    df = xls.parse(sheet)
    df = _clean_frame(df)
    return Document(kind=TABULAR, file_type="Excel", path=path, table=df,
                    meta={"rows": len(df), "cols": len(df.columns),
                          "sheet": sheet, "all_sheets": xls.sheet_names})


def _parse_pdf(path: str) -> Document:
    from pypdf import PdfReader

    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(pages).strip()
    return Document(kind=TEXT, file_type="PDF", path=path, text=text,
                    meta={"pages": len(pages), "chars": len(text)})


def _clean_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Tidy a freshly loaded table so querying is predictable."""
    # Normalise column names: strip whitespace, collapse internal spaces.
    df.columns = [str(c).strip() for c in df.columns]
    # Drop fully-empty rows/cols that spreadsheets love to leave behind.
    df = df.dropna(how="all").dropna(axis=1, how="all")
    # Strip padding from string cells so "Mumbai " matches "Mumbai".
    for col in df.select_dtypes(include=["object", "str"]).columns:
        df[col] = df[col].map(lambda v: v.strip() if isinstance(v, str) else v)
    return df.reset_index(drop=True)


# extension -> parser function
EXTENSIONS = {
    ".csv": _parse_csv,
    ".tsv": _parse_csv,
    ".xlsx": _parse_excel,
    ".xls": _parse_excel,
    ".xlsm": _parse_excel,
    ".pdf": _parse_pdf,
}


def parse(path: str) -> Document:
    """Dispatch a file to the right parser based on its extension."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    ext = os.path.splitext(path)[1].lower()
    if ext not in EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Supported: {', '.join(sorted(EXTENSIONS))}"
        )
    return EXTENSIONS[ext](path)
