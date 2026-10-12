"""Query execution.

Given a corrected query, a detected intent, and a parsed Document, produce the
actual answer. Tabular documents are handled with pandas; text (PDF) documents
fall back to keyword / frequency logic.

The two reusable helpers that make this generalise instead of hardcode:

* `resolve_column` -- fuzzy-match a word in the query to a real column name,
  so "gpa", "G.P.A", or "Gpa" all land on the "GPA" column.
* `parse_condition` -- pull a (column, operator, value) triple out of free text
  like "expenses above 5000" or "city is Mumbai".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd
from rapidfuzz import process, fuzz

from . import intent as intents
from .parsers import Document, TABULAR


@dataclass
class Answer:
    text: str                       # human-readable result
    table: pd.DataFrame | None = None   # tabular result, if any
    meta: dict = None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

_OPERATORS = [
    (r">=|greater than or equal|at least|no less than", "ge"),
    (r"<=|less than or equal|at most|no more than", "le"),
    (r">|above|over|greater than|more than|exceed(?:s|ing)?", "gt"),
    (r"<|below|under|less than|fewer than", "lt"),
    (r"==|=|equal to|equals|\bis\b|\bof\b|\bfrom\b|\bin\b|\bwith\b", "eq"),
]


def resolve_column(word: str, columns: list[str], cutoff: int = 70) -> str | None:
    """Map a free-text word to the closest real column name."""
    if not columns:
        return None
    match = process.extractOne(
        word.lower(), {c: c.lower() for c in columns}.values(),
        scorer=fuzz.WRatio
    )
    if match and match[1] >= cutoff:
        # match[2] is the key index into the lowercased dict values
        lowered = [c.lower() for c in columns]
        return columns[lowered.index(match[0])]
    return None


def find_columns_in_text(query: str, columns: list[str]) -> list[str]:
    """Return every column whose name appears (fuzzily) in the query."""
    hits = []
    words = re.findall(r"[A-Za-z][A-Za-z0-9_]+", query)
    for col in columns:
        col_key = col.lower()
        # direct substring hit
        if col_key in query.lower():
            hits.append(col)
            continue
        # fuzzy single-word hit
        for w in words:
            if fuzz.ratio(w.lower(), col_key) >= 85:
                hits.append(col)
                break
    return list(dict.fromkeys(hits))   # dedupe, keep order


def _extract_value(raw: str):
    """Turn the right-hand side of a condition into a number or clean string."""
    raw = raw.strip().strip("'\"")
    num = re.search(r"-?\d[\d,]*\.?\d*", raw)
    if num:
        return float(num.group().replace(",", ""))
    return raw


@dataclass
class Condition:
    column: str
    op: str
    value: object


def _column_holding_value(df: pd.DataFrame, value) -> str | None:
    """Find a text column whose cells contain `value` (for "from Mumbai")."""
    if df is None or not isinstance(value, str):
        return None
    needle = value.lower()
    for col in df.select_dtypes(include=["object", "str"]).columns:
        if df[col].astype(str).str.lower().str.contains(
                re.escape(needle), na=False).any():
            return col
    return None


def parse_condition(query: str, columns: list[str],
                    df: pd.DataFrame | None = None) -> Condition | None:
    """Extract one (column, operator, value) triple from the query."""
    q = query.strip()
    for pattern, op in _OPERATORS:
        m = re.search(pattern, q, re.IGNORECASE)
        if not m:
            continue
        left = q[:m.start()].strip()
        right = q[m.end():].strip()
        # Column is the last recognisable column mentioned on the left side,
        # else the first column mentioned anywhere.
        left_cols = find_columns_in_text(left, columns)
        col = left_cols[-1] if left_cols else None
        if col is None:
            any_cols = find_columns_in_text(q, columns)
            col = any_cols[0] if any_cols else None
        value = _extract_value(right)
        if value == "" or value is None:
            continue
        # The query may name only the value ("from Mumbai"); infer its column
        # by looking for which column actually contains that value.
        if col is None and isinstance(value, str):
            col = _column_holding_value(df, value)
        # A numeric comparison with no named column ("above 5000") -> fall back
        # to the table's main numeric column.
        if col is None and isinstance(value, (int, float)) and df is not None:
            nums = _numeric_columns(df)
            if nums:
                col = nums[0]
        if col is None:
            continue
        return Condition(column=col, op=op, value=value)
    return None


# Domain phrases that map to a concrete condition. Keeps "out of stock" from
# being parsed literally. Extendable without touching the core parser.
_PHRASES = [
    (re.compile(r"\bout of stock\b", re.I), ("stock|quantity|available|qty", "eq", 0)),
    (re.compile(r"\b(in stock|available)\b", re.I), ("stock|quantity|available|qty", "gt", 0)),
]


def special_condition(query: str, df: pd.DataFrame) -> Condition | None:
    """Recognise fixed domain phrases like 'out of stock'."""
    if df is None:
        return None
    for rx, (col_pat, op, val) in _PHRASES:
        if rx.search(query):
            for col in df.columns:
                if re.search(col_pat, col, re.I):
                    return Condition(column=col, op=op, value=val)
    return None


def _apply(series: pd.Series, op: str, value) -> pd.Series:
    """Boolean mask for a single condition, numeric or string aware."""
    numeric = pd.to_numeric(series, errors="coerce")
    if isinstance(value, (int, float)) and numeric.notna().any():
        ops = {
            "gt": numeric > value, "lt": numeric < value,
            "ge": numeric >= value, "le": numeric <= value,
            "eq": numeric == value,
        }
        return ops[op].fillna(False)
    # string comparison: eq -> contains (case-insensitive), others -> contains
    text = series.astype(str).str.lower()
    needle = str(value).lower()
    return text.str.contains(re.escape(needle), na=False)


def _first_number(query: str, default: int) -> int:
    m = re.search(r"\b(\d+)\b", query)
    if m:
        return int(m.group(1))
    for word, n in _NUM_WORDS.items():
        if re.search(rf"\b{word}\b", query, re.IGNORECASE):
            return n
    return default


def _numeric_columns(df: pd.DataFrame) -> list[str]:
    out = []
    for c in df.columns:
        if pd.to_numeric(df[c], errors="coerce").notna().mean() > 0.6:
            out.append(c)
    return out


# ---------------------------------------------------------------------------
# Tabular handlers (one per intent)
# ---------------------------------------------------------------------------

def _tab_summary(df: pd.DataFrame, query: str) -> Answer:
    lines = [
        f"The table has {len(df)} rows and {len(df.columns)} columns.",
        f"Columns: {', '.join(df.columns)}.",
    ]
    nums = _numeric_columns(df)
    if nums:
        desc = df[nums].apply(pd.to_numeric, errors="coerce").describe().round(2)
        desc = desc.reset_index().rename(columns={"index": "stat"})
        lines.append("Numeric overview:")
        return Answer("\n".join(lines), table=desc, meta={"numeric_cols": nums})
    return Answer("\n".join(lines))


def _tab_search(df: pd.DataFrame, query: str) -> Answer:
    # Strip command words, keep the meaningful search term(s).
    term = re.sub(
        r"\b(find|search|show|list|get|give me|all|rows|related to|about|the|"
        r"records?|entries|for|me)\b", " ", query, flags=re.IGNORECASE)
    term = term.strip(" .?")
    if not term:
        return Answer("No search term found in the query.", table=df.head(10))

    def _search(needle: str) -> pd.DataFrame:
        mask = df.apply(
            lambda row: row.astype(str).str.contains(
                re.escape(needle), case=False, na=False).any(), axis=1)
        return df[mask]

    hits = _search(term)
    used = term
    # Retry with a de-pluralised term so "laptops" finds "Laptop Stand".
    if len(hits) == 0 and len(term) > 3 and term.lower().endswith("s"):
        singular = term[:-1]
        retry = _search(singular)
        if len(retry):
            hits, used = retry, singular
    return Answer(
        f"Found {len(hits)} row(s) matching '{used}'.",
        table=hits if len(hits) else None,
        meta={"term": used, "matches": int(len(hits))})


def _tab_filter(df: pd.DataFrame, query: str) -> Answer:
    cond = special_condition(query, df) or parse_condition(query, list(df.columns), df)
    if cond is None:
        # No structured condition -> treat as a search instead.
        return _tab_search(df, query)
    mask = _apply(df[cond.column], cond.op, cond.value)
    result = df[mask]
    pretty = {"gt": ">", "lt": "<", "ge": ">=", "le": "<=", "eq": "=="}[cond.op]
    return Answer(
        f"{len(result)} row(s) where {cond.column} {pretty} {cond.value}.",
        table=result if len(result) else None,
        meta={"column": cond.column, "op": cond.op, "value": cond.value})


def _tab_count(df: pd.DataFrame, query: str) -> Answer:
    cond = special_condition(query, df) or parse_condition(query, list(df.columns), df)
    if cond is None:
        return Answer(f"The table contains {len(df)} rows.",
                      meta={"count": int(len(df))})
    mask = _apply(df[cond.column], cond.op, cond.value)
    n = int(mask.sum())
    pretty = {"gt": ">", "lt": "<", "ge": ">=", "le": "<=", "eq": "=="}[cond.op]
    return Answer(f"{n} row(s) where {cond.column} {pretty} {cond.value}.",
                  meta={"count": n})


def _tab_aggregation(df: pd.DataFrame, query: str) -> Answer:
    func = "sum"
    if re.search(r"average|avg|mean", query, re.I):
        func = "mean"
    elif re.search(r"\bmax|maximum|highest\b", query, re.I):
        func = "max"
    elif re.search(r"\bmin|minimum|lowest\b", query, re.I):
        func = "min"
    elif re.search(r"\bcount\b", query, re.I):
        func = "count"

    nums = _numeric_columns(df)
    target = None
    for col in find_columns_in_text(query, list(df.columns)):
        if col in nums:
            target = col
            break
    if target is None and nums:
        target = nums[0]
    if target is None:
        return Answer("No numeric column found to aggregate.")

    # Optional "group by <col>"
    grp = re.search(r"group(?:ed)? by (\w+)|by (\w+)|per (\w+)", query, re.I)
    series = pd.to_numeric(df[target], errors="coerce")
    if grp:
        gword = next(g for g in grp.groups() if g)
        gcol = resolve_column(gword, list(df.columns))
        if gcol and gcol != target:
            grouped = series.groupby(df[gcol]).agg(func).round(2)
            table = grouped.reset_index().rename(columns={target: f"{func}({target})"})
            return Answer(f"{func}({target}) grouped by {gcol}:",
                          table=table, meta={"func": func, "column": target,
                                             "group_by": gcol})
    value = round(float(getattr(series, func)()), 2)
    return Answer(f"{func}({target}) = {value}",
                  meta={"func": func, "column": target, "value": value})


def _tab_sorting(df: pd.DataFrame, query: str) -> Answer:
    ascending = bool(re.search(
        r"lowest|smallest|cheapest|bottom|least|ascending|worst", query, re.I))
    n = _first_number(query, default=5)

    nums = _numeric_columns(df)
    target = None
    for col in find_columns_in_text(query, list(df.columns)):
        if col in nums:
            target = col
            break
    if target is None and nums:
        target = nums[0]
    if target is None:
        return Answer("No numeric column found to sort by.")

    ordered = df.assign(_k=pd.to_numeric(df[target], errors="coerce")) \
                .sort_values("_k", ascending=ascending).drop(columns="_k")
    direction = "lowest" if ascending else "highest"
    return Answer(f"Top {n} rows by {target} ({direction} first):",
                  table=ordered.head(n),
                  meta={"column": target, "n": n, "ascending": ascending})


def _tab_analytics(df: pd.DataFrame, query: str) -> Answer:
    lines = [f"Dataset: {len(df)} rows x {len(df.columns)} columns."]
    nums = _numeric_columns(df)
    cats = [c for c in df.columns if c not in nums]

    if nums:
        stats = df[nums].apply(pd.to_numeric, errors="coerce").agg(
            ["mean", "min", "max", "std"]).round(2)
        stats = stats.reset_index().rename(columns={"index": "stat"})
        lines.append("Numeric columns summarised below.")
    else:
        stats = None

    # Category breakdown for the first useful low-cardinality text column.
    # Skip ID-like columns (all-unique, or names containing 'id').
    breakdown = None
    for c in cats:
        nun = df[c].nunique()
        if 1 < nun <= 20 and nun < len(df) and "id" not in c.lower():
            breakdown = df[c].value_counts().reset_index()
            breakdown.columns = [c, "count"]
            lines.append(f"Distribution of '{c}' included.")
            break

    table = stats if stats is not None else breakdown
    return Answer("\n".join(lines), table=table,
                  meta={"numeric_cols": nums, "category_cols": cats})


_TAB_HANDLERS = {
    intents.SUMMARY: _tab_summary,
    intents.SEARCH: _tab_search,
    intents.FILTER: _tab_filter,
    intents.COUNT: _tab_count,
    intents.AGGREGATION: _tab_aggregation,
    intents.SORTING: _tab_sorting,
    intents.ANALYTICS: _tab_analytics,
}


# ---------------------------------------------------------------------------
# Text (PDF) handlers
# ---------------------------------------------------------------------------

def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _txt_summary(text: str, query: str) -> Answer:
    """Extractive summary: score sentences by word frequency, keep the top few."""
    sents = _sentences(text)
    if not sents:
        return Answer("The document has no extractable text.")
    words = re.findall(r"[a-z]{4,}", text.lower())
    stop = {"this", "that", "with", "from", "have", "will", "they", "their",
            "which", "there", "been", "were", "also", "than", "then"}
    freq: dict[str, int] = {}
    for w in words:
        if w not in stop:
            freq[w] = freq.get(w, 0) + 1
    scored = []
    for i, s in enumerate(sents):
        score = sum(freq.get(w, 0) for w in re.findall(r"[a-z]{4,}", s.lower()))
        scored.append((score / (len(s.split()) + 1), i, s))
    top = sorted(scored, reverse=True)[:5]
    summary = " ".join(s for _, _, s in sorted(top, key=lambda t: t[1]))
    return Answer(summary, meta={"sentences": len(sents)})


def _txt_search(text: str, query: str) -> Answer:
    term = re.sub(r"\b(find|search|show|all|rows|related to|about|the|for|me)\b",
                  " ", query, flags=re.I).strip(" .?")
    if not term:
        return Answer("No search term found in the query.")
    hits = [s for s in _sentences(text) if term.lower() in s.lower()]
    if not hits:
        return Answer(f"No passages matching '{term}'.")
    body = "\n".join(f"- {h}" for h in hits[:10])
    return Answer(f"{len(hits)} passage(s) mention '{term}':\n{body}",
                  meta={"term": term, "matches": len(hits)})


def _txt_count(text: str, query: str) -> Answer:
    term = re.sub(r"\b(how many|count|number of|times|does|the|appear|occur)\b",
                  " ", query, flags=re.I).strip(" .?")
    if not term:
        words = re.findall(r"\w+", text)
        return Answer(f"The document has {len(words)} words and "
                      f"{len(_sentences(text))} sentences.")
    n = len(re.findall(re.escape(term), text, re.I))
    return Answer(f"'{term}' appears {n} time(s) in the document.",
                  meta={"term": term, "count": n})


def _txt_analytics(text: str, query: str) -> Answer:
    words = re.findall(r"[a-z]{4,}", text.lower())
    freq: dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    top = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:10]
    body = ", ".join(f"{w} ({c})" for w, c in top)
    return Answer(
        f"{len(_sentences(text))} sentences, {len(words)} long words. "
        f"Most frequent terms: {body}.", meta={"top_terms": top})


_TXT_HANDLERS = {
    intents.SUMMARY: _txt_summary,
    intents.SEARCH: _txt_search,
    intents.FILTER: _txt_search,       # filtering free text == searching it
    intents.COUNT: _txt_count,
    intents.AGGREGATION: _txt_count,   # closest meaningful op on prose
    intents.SORTING: _txt_summary,     # no natural sort on prose -> summarise
    intents.ANALYTICS: _txt_analytics,
}


def execute(doc: Document, intent_name: str, query: str) -> Answer:
    """Route to the correct handler based on document kind + intent."""
    if doc.kind == TABULAR:
        handler = _TAB_HANDLERS.get(intent_name, _tab_search)
        return handler(doc.table, query)
    handler = _TXT_HANDLERS.get(intent_name, _txt_search)
    return handler(doc.text, query)
