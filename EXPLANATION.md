# Document Intelligence System — Explanation

## 1. What I built and the problem it solves

Organisations sit on piles of documents — spreadsheets of records, PDF reports,
CSV exports — and getting a specific answer out of them usually means opening the
file and hunting manually. I built a **document intelligence system** that lets a
person hand over a file and simply *ask a question in plain English*. The system:

1. reads the file (PDF / Excel / CSV),
2. corrects spelling/grammar mistakes in the question,
3. figures out what kind of operation the question wants,
4. runs that operation against the file, and
5. returns a clean, structured answer.

The same question logic works whether the file is a spreadsheet or a PDF.

## 2. What the system does — main features

- **File parsing** for CSV, TSV, Excel (`.xlsx/.xls/.xlsm`) and PDF.
- **Spell & grammar correction** of the query before anything else runs
  (`summrize this docment` → `Summarize this document`).
- **Intent detection** across seven intents: Summary, Search, Filter, Count,
  Aggregation, Sorting, Analytics.
- **Query execution** that returns accurate results per intent, including
  value-aware filtering (`from Mumbai` knows "Mumbai" lives in the City column)
  and grouped aggregation (`total salary by department`).
- **Structured output** — every response shows file type, original query,
  corrected query, detected intent (with a confidence score) and the result.
- **Multi-document support** — one query pipeline, two backends (pandas for
  tables, text logic for PDFs).
- **Confidence + fallback** — low-confidence intents are flagged and default to
  the most forgiving operation (Search) rather than failing.

## 3. Tech stack, libraries, tools

| Area              | Choice                               | Why |
|-------------------|--------------------------------------|-----|
| Language          | Python 3.12                          | Strong data ecosystem |
| Tabular data      | **pandas**                           | Filtering, grouping, sorting out of the box |
| Excel             | **openpyxl** (via pandas)            | Reads modern Excel files |
| PDF               | **pypdf**                            | Pure-Python text extraction |
| Fuzzy matching    | **RapidFuzz**                        | Fast Levenshtein for spell-fix + column resolution |
| Sample PDF        | **reportlab**                        | Generates a demo report |
| Tests             | **pytest**                           | 21 unit + end-to-end tests |

No database is used — the file *is* the data source, loaded into memory per
session. No external APIs and **no LLM**; all NLP is rule-based and edit-distance
based, so it runs fully offline.

## 4. How to run it locally

```bash
pip install -r requirements.txt       # install deps
python samples/make_samples.py        # create sample documents
python -m docintel.cli samples/employees.csv "list all employees from Mumbai"
python -m docintel.cli samples/expenses.csv     # interactive mode
python -m pytest -q                   # run the tests
```

## 5. Sample inputs and outputs

**Filter (CSV, with a typo):**
```
Original query  : list all employes from Mumbai
Corrected query : List all employees from Mumbai
Detected intent : Filter  (confidence 0.45)
Result:
  3 row(s) where City == Mumbai.
  E001 Aarti Shah Mumbai Engineering  92000 29
  E003 Priya Nair Mumbai Engineering 105000 31
  E005 Sneha Iyer Mumbai     Finance  88000 38
```

**Count with a domain phrase (Excel):**
```
Query  : how many products are out of stock
Intent : Count
Result : 3 row(s) where Stock == 0.
```

**Sorting (CSV):**
```
Query  : give me the top 3 highest expenses
Intent : Sorting
Result : Top 3 rows by Amount (highest first)
         Laptops (x3)        210000
         Software Licenses    92000
         Conference Tickets   60000
```

**Grouped aggregation (CSV):**
```
Query  : total salary by department
Intent : Aggregation
Result : sum(Salary) grouped by Department
         Engineering 296000 | Finance 203000 | Marketing 74000 | Sales 129000
```

**Summary (PDF, extractive):**
```
Query  : summrize this docment
Intent : Summary
Result : Quarterly Operations Report. The engineering team shipped three major
         releases this quarter... Overall margins improved for the quarter.
         Customer satisfaction scores improved for the third quarter in a row.
```

## 6. Design decisions

- **Four-stage pipeline** (`parse → correct → detect → execute`). Each stage is a
  separate module with a narrow job, so each can be tested and swapped
  independently. `pipeline.py` is the only thing that knows the full sequence.
- **A normalised `Document`.** Parsers return the same shape regardless of file
  type — a DataFrame-backed table or a text blob. Everything downstream branches
  on `doc.kind`, not on file extension, which is what makes multi-document
  support fall out naturally.
- **Document-aware spell correction.** The correction vocabulary is seeded with
  the file's own column names, so real terms like `GPA` or `Mumbai` are never
  "corrected" into something wrong. A similarity threshold (82/100) stops it from
  making confident-but-wrong fixes.
- **Weighted intent rules instead of keyword matching.** Each intent owns a set
  of weighted regex signals; the winner is the highest total, and the margin over
  the runner-up becomes a confidence score. Specific phrases (`top 5`) outweigh
  generic ones (`find`), which is how overlapping queries route correctly.
- **Generalised condition parsing.** `parse_condition` extracts a
  `(column, operator, value)` triple from free text. It resolves columns fuzzily,
  infers a column from its *value* (`from Mumbai` → City), and falls back to the
  main numeric column when the user names a value but no column (`above 5000`).
- **Extensibility by design.** Add a file type = one parser function + one line in
  `EXTENSIONS`. Add an intent = one rule set + one handler. Add a domain phrase
  (like `out of stock`) = one line in `_PHRASES`.

## 7. Assumptions

- The first row of a spreadsheet is the header; the first sheet is the one to
  read (other sheet names are recorded in metadata).
- A column is "numeric" if ≥60% of its values parse as numbers — tolerant of a
  few stray text cells.
- When a numeric comparison names no column (`above 5000`), the first numeric
  column is assumed to be the target.
- PDFs are text-based; scanned/image-only PDFs would need OCR (not included).

## 8. Known limitations

- **One condition per query.** `salary above 90000 and city Mumbai` only applies
  the first condition. Multi-condition parsing is the obvious next step.
- **PDF tables** are read as flowing text, not reconstructed into a grid, so
  numeric aggregation over a PDF table isn't supported.
- **Summarisation is extractive** (it picks the most representative existing
  sentences), not abstractive.
- **The common-word dictionary is small**, so an unusual misspelling that is also
  far from any document term may be left uncorrected rather than mis-corrected —
  a deliberate safe-failure choice.

## 9. What I would improve next

1. Multi-condition filters (`A and B`, `A or B`) with a small expression parser.
2. Proper PDF table extraction (e.g. `pdfplumber`) to unlock aggregation on PDFs.
3. A thin web UI (Streamlit/Flask) with drag-and-drop upload over the same
   pipeline — the CLI and a web app would share 100% of the logic.
4. Optional semantic search using TF-IDF / embeddings (scikit-learn) for
   "find rows *related to* X" when exact keyword matching misses synonyms.
5. Date-aware filtering (`expenses in February`, `last 30 days`).
