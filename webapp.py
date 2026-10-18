"""Web interface for the Document Intelligence System.

A thin Flask layer over the existing `docintel` engine -- it does no analysis of
its own, it just lets a browser upload a file (or pick a bundled sample), send a
plain-English query, and see the same structured result the CLI produces.

    pip install flask
    python webapp.py          # -> http://127.0.0.1:5001

Two endpoints:
    POST /api/upload   multipart file  -> {token}
    POST /api/query    {source, query} -> structured result JSON
`source` is either "sample:<name>" or "upload:<token>", so one uploaded file can
answer many queries without re-sending it.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from docintel.pipeline import Pipeline

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(HERE, "samples")
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "docintel_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXT = {".csv", ".tsv", ".xlsx", ".xls", ".xlsm", ".pdf"}
MAX_BYTES = 10 * 1024 * 1024  # 10 MB upload cap

app = Flask(__name__, static_folder="web", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = MAX_BYTES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_files() -> list[dict]:
    if not os.path.isdir(SAMPLES_DIR):
        return []
    out = []
    for name in sorted(os.listdir(SAMPLES_DIR)):
        ext = os.path.splitext(name)[1].lower()
        if ext in ALLOWED_EXT:
            label = {".csv": "CSV", ".tsv": "CSV", ".pdf": "PDF"}.get(ext, "Excel")
            out.append({"name": name, "type": label})
    return out


def _resolve(source: str) -> str | None:
    """Turn a 'sample:x' / 'upload:token' source into a real, safe path."""
    if source.startswith("sample:"):
        name = secure_filename(source.split(":", 1)[1])
        path = os.path.join(SAMPLES_DIR, name)
        return path if os.path.isfile(path) else None
    if source.startswith("upload:"):
        token = secure_filename(source.split(":", 1)[1])
        path = os.path.join(UPLOAD_DIR, token)
        return path if os.path.isfile(path) else None
    return None


def _table_payload(df: pd.DataFrame | None) -> dict | None:
    """Serialise a result DataFrame safely (handles numpy types / NaN)."""
    if df is None or len(df) == 0:
        return None
    return {
        "columns": [str(c) for c in df.columns],
        "rows": json.loads(df.to_json(orient="records")),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/samples")
def samples():
    return jsonify({"samples": _sample_files()})


@app.post("/api/upload")
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "No file provided."}), 400
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify({"error": f"Unsupported file type '{ext}'. "
                        f"Use PDF, CSV, or Excel."}), 400
    token = f"{uuid.uuid4().hex}{ext}"
    f.save(os.path.join(UPLOAD_DIR, token))
    return jsonify({"token": token, "name": f.filename}), 201


@app.post("/api/query")
def query():
    data = request.get_json(silent=True) or {}
    source = (data.get("source") or "").strip()
    q = (data.get("query") or "").strip()
    if not source:
        return jsonify({"error": "Choose a file or sample first."}), 400
    if not q:
        return jsonify({"error": "Type a question to ask about the document."}), 400

    path = _resolve(source)
    if path is None:
        return jsonify({"error": "That file could not be found. Re-upload it."}), 404

    try:
        result = Pipeline(path).ask(q)
    except Exception as e:                       # malformed file, etc.
        return jsonify({"error": f"Could not process the file: {e}"}), 400

    return jsonify({
        "file_type": result.file_type,
        "original_query": result.original_query,
        "corrected_query": result.corrected_query,
        "corrected": result.corrected_query.strip().lower() != result.original_query.strip().lower(),
        "intent": result.intent,
        "confidence": result.confidence,
        "result": result.answer_text,
        "table": _table_payload(result.answer_table),
        "meta": {k: v for k, v in (result.meta or {}).items()
                 if k in ("term", "value", "column", "note", "count", "func")},
    })


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


def create_app():
    return app


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
