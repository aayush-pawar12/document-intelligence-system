"""End-to-end and unit tests for the document intelligence system.

Run with:  pytest -q
The sample files are generated on the fly into a temp dir so the tests are
self-contained and don't depend on samples/ already existing.
"""

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docintel import corrector, intent, parsers
from docintel.executor import parse_condition, resolve_column
from docintel.pipeline import Pipeline


@pytest.fixture(scope="module")
def emp_csv(tmp_path_factory):
    d = tmp_path_factory.mktemp("data")
    df = pd.DataFrame({
        "EmpID": ["E1", "E2", "E3", "E4"],
        "Name": ["Aarti", "Rahul", "Priya", "Vikram"],
        "City": ["Mumbai", "Delhi", "Mumbai", "Pune"],
        "Department": ["Eng", "Sales", "Eng", "HR"],
        "Salary": [90000, 60000, 105000, 70000],
    })
    p = d / "emp.csv"
    df.to_csv(p, index=False)
    return str(p)


@pytest.fixture(scope="module")
def stock_xlsx(tmp_path_factory):
    d = tmp_path_factory.mktemp("data")
    df = pd.DataFrame({
        "Product": ["Mouse", "Keyboard", "Monitor"],
        "Price": [799, 3499, 18999],
        "Stock": [10, 0, 0],
    })
    p = d / "stock.xlsx"
    df.to_excel(p, index=False)
    return str(p)


# --- corrector -------------------------------------------------------------

def test_corrector_fixes_typos():
    vocab = corrector.build_vocabulary(["City", "Salary"])
    out = corrector.correct("summrize this docment", vocab)
    assert out.corrected.lower() == "summarize this document"
    assert out.changed


def test_corrector_leaves_known_words():
    out = corrector.correct("list all employees", corrector.build_vocabulary())
    assert "employees" in out.corrected.lower()


def test_corrector_preserves_numbers():
    out = corrector.correct("expenses above 5000", corrector.build_vocabulary())
    assert "5000" in out.corrected


# --- intent ----------------------------------------------------------------

@pytest.mark.parametrize("query,expected", [
    ("summarize this document", intent.SUMMARY),
    ("list all employees from Mumbai", intent.FILTER),
    ("find expenses above 5000", intent.FILTER),
    ("give me the top 5 highest expenses", intent.SORTING),
    ("how many products are out of stock", intent.COUNT),
    ("what is the average salary", intent.AGGREGATION),
    ("find all rows related to laptops", intent.SEARCH),
    ("show me analytics", intent.ANALYTICS),
])
def test_intent_detection(query, expected):
    assert intent.detect(query).intent == expected


# --- column / condition helpers -------------------------------------------

def test_resolve_column_fuzzy():
    assert resolve_column("salry", ["Name", "Salary", "City"]) == "Salary"


def test_parse_condition_numeric():
    df = pd.DataFrame({"Amount": [1, 2], "Item": ["a", "b"]})
    cond = parse_condition("amount above 5000", ["Amount", "Item"], df)
    assert cond.column == "Amount" and cond.op == "gt" and cond.value == 5000


def test_parse_condition_value_implies_column():
    df = pd.DataFrame({"City": ["Mumbai", "Delhi"], "N": [1, 2]})
    cond = parse_condition("employees from Mumbai", ["City", "N"], df)
    assert cond.column == "City" and cond.value == "Mumbai"


# --- parsers ---------------------------------------------------------------

def test_parse_csv(emp_csv):
    doc = parsers.parse(emp_csv)
    assert doc.kind == parsers.TABULAR
    assert "Salary" in doc.columns


def test_parse_rejects_unknown_ext(tmp_path):
    p = tmp_path / "x.zip"
    p.write_text("x")
    with pytest.raises(ValueError):
        parsers.parse(str(p))


# --- full pipeline ---------------------------------------------------------

def test_pipeline_filter(emp_csv):
    r = Pipeline(emp_csv).ask("list all employes from Mumbai")
    assert r.intent == intent.FILTER
    assert r.corrected_query.lower() == "list all employees from mumbai"
    assert len(r.answer_table) == 2          # two Mumbai rows


def test_pipeline_count_out_of_stock(stock_xlsx):
    r = Pipeline(stock_xlsx).ask("how many products are out of stock")
    assert r.intent == intent.COUNT
    assert r.meta["count"] == 2              # two zero-stock rows


def test_pipeline_aggregation(emp_csv):
    r = Pipeline(emp_csv).ask("what is the average salary")
    assert r.intent == intent.AGGREGATION
    assert r.meta["value"] == pytest.approx(81250.0)


def test_pipeline_sorting(emp_csv):
    r = Pipeline(emp_csv).ask("top 2 highest salary")
    assert r.intent == intent.SORTING
    assert list(r.answer_table["Salary"])[:2] == [105000, 90000]


def test_pipeline_structured_output_fields(emp_csv):
    r = Pipeline(emp_csv).ask("summarize this document")
    d = r.as_dict()
    for key in ("file_type", "original_query", "corrected_query",
                "intent", "result"):
        assert key in d
