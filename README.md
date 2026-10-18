# Document Intelligence System

Upload a **PDF, Excel, or CSV** file, ask a question in **plain English**, and get
back a clean, structured answer. The system fixes typos in your query, works out
what you are trying to do (summarise, search, filter, count, aggregate, sort, or
analyse), runs it against the file, and shows the result.

No LLMs are used. Everything runs on tokenisation, edit-distance spell
correction, and rule-based intent routing — fast, offline, and explainable.

## Quick start

```bash
# 1. install dependencies
pip install -r requirements.txt

# 2. generate the sample files (employees.csv, expenses.csv, products.xlsx, report.pdf)
python samples/make_samples.py

# 3. ask a one-off question
python -m docintel.cli samples/employees.csv "list all employees from Mumbai"

# 4. or open an interactive session (file stays loaded)
python -m docintel.cli samples/expenses.csv
```

## Example queries

| File            | Query                                   | Intent      |
|-----------------|-----------------------------------------|-------------|
| report.pdf      | `summrize this docment`                 | Summary     |
| employees.csv   | `list all employes from Mumbai`         | Filter      |
| students.csv    | `show students with GPA above 8`        | Filter      |
| expenses.csv    | `find expences above 5000`              | Filter      |
| expenses.csv    | `give me the top 3 highest expenses`    | Sorting     |
| products.xlsx   | `how many products are out of stock`    | Count       |
| employees.csv   | `total salary by department`            | Aggregation |
| products.xlsx   | `find all rows related to laptops`      | Search      |
| employees.csv   | `give me analytics`                     | Analytics   |

## Output format

Every answer includes the five required fields:

```
============================================================
  File type       : CSV
  Original query  : list all employes from Mumbai
  Corrected query : List all employees from Mumbai
  Detected intent : Filter  (confidence 0.45)
============================================================
  Result:
    3 row(s) where City == Mumbai.

    EmpID       Name   City  Department  Salary  Age
     E001 Aarti Shah Mumbai Engineering   92000   29
     E003 Priya Nair Mumbai Engineering  105000   31
     E005 Sneha Iyer Mumbai     Finance   88000   38
============================================================
```

## Web interface (optional)

A small browser UI over the same engine — upload a file (or pick a sample), type
a question, and see the structured result with the corrected query and matches
highlighted:

```bash
python webapp.py        # -> http://127.0.0.1:5001
```

## Running the tests

```bash
python -m pytest -q
```

## Project layout

```
docintel/
  parsers.py     file -> normalised Document (CSV/Excel/PDF)
  corrector.py   spell/grammar correction via edit distance
  intent.py      weighted rule-based intent detection
  executor.py    runs each intent on tables (pandas) or text
  pipeline.py    orchestrates the four stages into one Result
  cli.py         command-line interface
samples/         demo documents + generator
tests/           pytest suite
```

See `EXPLANATION.md` for the full write-up: design decisions, architecture,
assumptions, and known limitations.
