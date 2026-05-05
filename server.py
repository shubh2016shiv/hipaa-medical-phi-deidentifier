#!/usr/bin/env python3
"""
SecurePHI — Flask API Server

Serves the HTML/CSS/JS frontend and provides HIPAA de-identification
API endpoints. Drop-in replacement for the Dash-based dash_ui.py.

Usage:
    python server.py
    # → http://localhost:8050
"""

import os
import re
import sys
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config import config as global_config
from hipaa_deidentifier.pipeline_orchestrator import HIPAAPipelineOrchestrator

app = Flask(__name__, static_folder="static")

_orchestrator: HIPAAPipelineOrchestrator | None = None


def get_orchestrator() -> HIPAAPipelineOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        cfg = global_config.get_settings()
        models = cfg.get("models", {})
        _orchestrator = HIPAAPipelineOrchestrator(
            config_path="config/main.yaml",
            spacy_model=models.get("spacy"),
            hf_model=models.get("huggingface"),
            device=models.get("device", -1),
        )
    return _orchestrator


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------


@app.route("/api/status")
def api_status():
    return jsonify({"status": "online", "hipaa_compliant": True})


@app.route("/api/documents")
def api_documents():
    """Return the document library tree organised by category."""
    data_dir = Path("data")
    tree: dict = {}
    if not data_dir.exists():
        return jsonify(tree)

    for cat_dir in sorted(data_dir.iterdir()):
        if not cat_dir.is_dir():
            continue
        docs = []
        for f in sorted(cat_dir.glob("*.txt")):
            name = f.stem.replace("_", " ").title()
            name = re.sub(r"\s*Patient\s*\d+", "", name, flags=re.IGNORECASE)
            name = re.sub(r"\s*P\d+", "", name, flags=re.IGNORECASE)
            name = " ".join(name.split())
            docs.append({"name": name, "path": f.as_posix()})
        if docs:
            tree[cat_dir.name] = docs

    return jsonify(tree)


@app.route("/api/document")
def api_document():
    """Return the text content of a single document file."""
    path = request.args.get("path", "").strip()
    if not path:
        return jsonify({"error": "path parameter required"}), 400

    doc_path = Path(path)

    # Guard against directory traversal attacks
    try:
        doc_path.resolve().relative_to(Path("data").resolve())
    except ValueError:
        return jsonify({"error": "access denied"}), 403

    if not doc_path.exists():
        return jsonify({"error": "file not found"}), 404

    return jsonify({"content": doc_path.read_text(encoding="utf-8")})


@app.route("/api/deidentify", methods=["POST"])
def api_deidentify():
    """
    De-identify clinical text.

    Request body (JSON):
        {"text": "<clinical note>"}

    Response (JSON):
        {
            "deidentified_text": "<redacted>",
            "entities": [
                {"start": int, "end": int, "category": str, "confidence": float},
                ...
            ]
        }
    """
    body = request.get_json(force=True, silent=True) or {}
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text field required"}), 400

    try:
        result = get_orchestrator().deidentify(text)
        return jsonify(
            {
                "deidentified_text": result["text"],
                "entities": result.get("entities", []),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("  SecurePHI — HIPAA De-identification Interface")
    print("  Open your browser at:  http://localhost:8050")
    print("  Press Ctrl+C to stop.")
    print("=" * 60)
    # threaded=False: the ML pipeline is not thread-safe
    app.run(debug=False, host="0.0.0.0", port=8050, threaded=False)
