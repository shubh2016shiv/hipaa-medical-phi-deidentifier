#!/usr/bin/env python3
"""
PHI Identification Batch Evaluation CLI
========================================
Batch-evaluates PHI detection quality across all clinical note categories
using the existing annotation-free LLM evaluation pipeline (LM Studio).

For every .txt file found, the script:
  1. Runs all configured detectors via LLMEvaluator (hf, presidio, heuristics,
     pipeline, pipeline_filtered)
  2. Uses the LLM's expected-PHI list as a pseudo ground-truth reference
  3. Text-matches each detector's output against that reference to derive
     per-entity-type  TP / FP / FN / TN, precision, recall, F1, FNR, FPR
  4. Writes per-category Excel workbooks (one sheet per note + summary sheets)
  5. Writes an overall_summary.xlsx aggregating everything

Metrics naming matches the existing span_metrics.TypeMetrics fields:
  true_positives (TP), false_positives (FP), false_negatives (FN),
  true_negatives (TN), precision, recall, f1,
  false_negative_rate (FNR), false_positive_rate (FPR)

Usage
-----
    # Evaluate the entire data/ tree (all 7 categories, 21 notes)
    python hipaa_deidentifier/phi_detection/phi_identification_evaluation_cli.py \\
        --input-folder data/

    # Evaluate a single category
    python hipaa_deidentifier/phi_detection/phi_identification_evaluation_cli.py \\
        --input-folder "data/Long-term and Supportive Care/"

    # Count-only mode — no LM Studio required
    python hipaa_deidentifier/phi_detection/phi_identification_evaluation_cli.py \\
        --input-folder data/ --no-judge

    # Post-guardrail pipeline only
    python hipaa_deidentifier/phi_detection/phi_identification_evaluation_cli.py \\
        --input-folder data/ --detectors pipeline_filtered

Output
------
    phi_eval_results/
    ├── Administrative_and_Transitional_Care/
    │   └── evaluation.xlsx    (per-note sheets + CATEGORY_SUMMARY)
    ├── Diagnostic_and_Ancillary_Services/
    │   └── evaluation.xlsx
    ...   (one workbook per category)
    └── overall_summary.xlsx
        ├── All_Results          — every row from every note and detector
        ├── Summary_by_Note      — OVERALL rows only (one per note × detector)
        └── Aggregated_by_Cat    — summed TP/FP/FN/TN per category × entity_type
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# HIPAA Safe Harbor critical types — require ≥95% recall
_HIPAA_CRITICAL = frozenset(
    {
        "NAME",
        "MRN",
        "DATE",
        "AGE_OVER_89",
        "LOCATION",
        "ACCOUNT_NUMBER",
        "US_SSN",
    }
)
_RECALL_THRESHOLD = 0.95

# Complete set of HIPAA Safe Harbor identifiers — the only categories that belong
# in the expected-PHI set.  LLM judges sometimes label clinical content (MEDICATION,
# VITAL_SIGN, DIAGNOSIS, ALLERGY, LAB_RESULT, AGE, TIME, etc.) that is not PHI.
# Any expected entity whose category is not in this set is filtered before metrics.
_HIPAA_ALLOWED_CATEGORIES = frozenset(
    {
        "NAME",
        "DATE",
        "PHONE_NUMBER",
        "FAX_NUMBER",
        "EMAIL_ADDRESS",
        "US_SSN",
        "MRN",
        "ACCOUNT_NUMBER",
        "CERTIFICATE_NUMBER",
        "VIN",
        "DEVICE_ID",
        "URL",
        "IP_ADDRESS",
        "LOCATION",
        "AGE_OVER_89",
        "PROVIDER_NAME",
        "ORGANIZATION",
        "OTHER_ID",
        # Alias / variant labels the LLM sometimes uses for the above
        "HEALTH_PLAN_ID",
        "ENCOUNTER_ID",
        "LICENSE_NUMBER",
        "NPI",
    }
)

# Column order for all worksheets
_COLUMNS: List[str] = [
    "note_category",
    "note_file",
    "detector",
    "entity_type",
    "expected_count",
    "detected_count",
    "true_positives",
    "false_positives",
    "false_negatives",
    "true_negatives",
    "precision",
    "recall",
    "f1",
    "false_negative_rate",
    "false_positive_rate",
    "hipaa_critical",
    "hipaa_pass",
    "llm_coverage_score",
    "llm_overall_pass",
    "llm_status",
]

# Excel column header display names (same order as _COLUMNS)
_HEADERS: Dict[str, str] = {
    "note_category": "Note Category",
    "note_file": "Note File",
    "detector": "Detector",
    "entity_type": "Entity Type",
    "expected_count": "Expected",
    "detected_count": "Detected",
    "true_positives": "TP",
    "false_positives": "FP",
    "false_negatives": "FN",
    "true_negatives": "TN",
    "precision": "Precision",
    "recall": "Recall",
    "f1": "F1",
    "false_negative_rate": "FNR",
    "false_positive_rate": "FPR",
    "hipaa_critical": "HIPAA Critical",
    "hipaa_pass": "HIPAA Pass",
    "llm_coverage_score": "LLM Coverage",
    "llm_overall_pass": "LLM Pass",
    "llm_status": "LLM Status",
}

# ---------------------------------------------------------------------------
# Folder scanning
# ---------------------------------------------------------------------------


def scan_input_folder(root: Path) -> Dict[str, List[Path]]:
    """Return {category_name: [sorted .txt paths]}.

    If root contains subdirectories, each subdir is treated as a note category.
    .txt files directly in root are placed under root.name as a category.
    """
    categories: Dict[str, List[Path]] = {}

    subdirs = sorted(d for d in root.iterdir() if d.is_dir())
    direct_txts = sorted(root.glob("*.txt"))

    for subdir in subdirs:
        txts = sorted(subdir.glob("*.txt"))
        if txts:
            categories[subdir.name] = txts

    if direct_txts:
        categories.setdefault(root.name, []).extend(direct_txts)

    return categories


# ---------------------------------------------------------------------------
# Text-overlap matching (pseudo ground-truth comparison)
# ---------------------------------------------------------------------------


def _texts_overlap(a: str, b: str) -> bool:
    """Return True if one string contains the other (case-insensitive)."""
    a_c = a.strip().lower()
    b_c = b.strip().lower()
    return bool(a_c and b_c and (a_c in b_c or b_c in a_c))


# ---------------------------------------------------------------------------
# Per-detector metric computation
# ---------------------------------------------------------------------------


def compute_detector_metrics(
    detected: List[Dict[str, Any]],
    expected: List[Dict[str, Any]],
    text: str,
) -> Dict[str, Dict[str, Any]]:
    """Greedy text-overlap match of detected against expected per entity type.

    Uses the LLM's expected-PHI list as pseudo ground truth.  Matching is
    greedy (first overlap wins) to avoid double-counting.  TN is estimated
    from whitespace-token count minus TP+FP+FN.

    Args:
        detected: Serialised PHIEntity dicts from one detector
                  (keys: text, category, start, end, confidence, source).
        expected: LLM-identified expected entities
                  (keys: text, category, evidence, severity, rationale).
        text:     Original document text (used for TN estimation).

    Returns:
        Dict keyed by entity_type string (plus "OVERALL").
        Each value contains: expected_count, detected_count,
        true_positives, false_positives, false_negatives, true_negatives,
        precision, recall, f1, false_negative_rate, false_positive_rate,
        hipaa_critical, hipaa_pass.
    """
    # Detectors label all person names as NAME regardless of patient vs provider.
    # The LLM judge may split these into NAME and PROVIDER_NAME.  Merge both
    # expected pools when evaluating NAME detections so that a detected NAME
    # that matches a PROVIDER_NAME expected entity is counted as a TP, not a FP.
    _NAME_ALIASES: Dict[str, frozenset] = {
        "NAME": frozenset({"NAME", "PROVIDER_NAME"}),
        "PROVIDER_NAME": frozenset({"NAME", "PROVIDER_NAME"}),
    }
    # Similarly, detectors may emit ENCOUNTER_ID / HEALTH_PLAN_ID / ACCOUNT_NUMBER
    # for things the LLM calls OTHER_ID, and vice-versa.
    _ID_ALIASES: Dict[str, frozenset] = {
        "OTHER_ID": frozenset(
            {
                "OTHER_ID",
                "ENCOUNTER_ID",
                "HEALTH_PLAN_ID",
                "IDENTIFICATION_NUMBER",
                "CERTIFICATE_NUMBER",
                "FINANCE_ID",
                "FIN",
                "NPI",
            }
        ),
        "ENCOUNTER_ID": frozenset({"OTHER_ID", "ENCOUNTER_ID"}),
        "HEALTH_PLAN_ID": frozenset({"OTHER_ID", "HEALTH_PLAN_ID"}),
    }
    _ALIASES: Dict[str, frozenset] = {**_NAME_ALIASES, **_ID_ALIASES}

    all_types: set[str] = set()
    for e in expected:
        all_types.add(e.get("category", "UNKNOWN"))
    for e in detected:
        all_types.add(e.get("category", "UNKNOWN"))

    total_tokens = max(1, len(re.findall(r"\S+", text)))
    rows: Dict[str, Dict[str, Any]] = {}

    # Track which expected entities are already matched across alias groups
    # so a single expected entity cannot satisfy multiple detected types.
    globally_matched: set[tuple] = set()  # (category, index) pairs

    for etype in sorted(all_types):
        exp_t = [e for e in expected if e.get("category") == etype]
        # For detection-side matching, allow detected NAME to cover PROVIDER_NAME
        det_t = [e for e in detected if e.get("category") == etype]

        # Build the pool of expected entities this detector type can match against
        alias_cats = _ALIASES.get(etype, frozenset({etype}))
        exp_pool = [
            (cat, i, e)
            for cat in alias_cats
            for i, e in enumerate(e_ for e_ in expected if e_.get("category") == cat)
        ]

        matched_exp: set[int] = set()  # indices into exp_t (exact-type)
        tp = fp = 0
        for d in det_t:
            found = False
            # First try exact-type match
            for i, e in enumerate(exp_t):
                key = (etype, i)
                if key not in globally_matched and _texts_overlap(d["text"], e["text"]):
                    globally_matched.add(key)
                    matched_exp.add(i)
                    tp += 1
                    found = True
                    break
            if not found and alias_cats != frozenset({etype}):
                # Try alias match (e.g. NAME detected → PROVIDER_NAME expected)
                for cat, i, e in exp_pool:
                    key = (cat, i)
                    if key not in globally_matched and _texts_overlap(
                        d["text"], e["text"]
                    ):
                        globally_matched.add(key)
                        tp += 1
                        found = True
                        break
            if not found:
                fp += 1

        # Count FNs as expected entities not satisfied by either exact-type or alias-path matches.
        # matched_exp only tracks exact-type hits; globally_matched also captures alias hits
        # (e.g. NAME detector covering a PROVIDER_NAME expected entity), so use it here.
        fn = sum(1 for i in range(len(exp_t)) if (etype, i) not in globally_matched)
        tn = max(0, total_tokens - tp - fp - fn)

        prec = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if not det_t else 0.0)
        rec = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        f1_v = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        fnr = fn / (tp + fn) if (tp + fn) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

        is_crit = etype in _HIPAA_CRITICAL
        rows[etype] = {
            "expected_count": len(exp_t),
            "detected_count": len(det_t),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "true_negatives": tn,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1_v, 4),
            "false_negative_rate": round(fnr, 4),
            "false_positive_rate": round(fpr, 4),
            "hipaa_critical": is_crit,
            "hipaa_pass": (rec >= _RECALL_THRESHOLD) if is_crit else None,
        }

    # OVERALL aggregate row
    agg_tp = sum(r["true_positives"] for r in rows.values())
    agg_fp = sum(r["false_positives"] for r in rows.values())
    agg_fn = sum(r["false_negatives"] for r in rows.values())
    agg_exp = sum(r["expected_count"] for r in rows.values())
    agg_det = sum(r["detected_count"] for r in rows.values())
    agg_tn = max(0, total_tokens - agg_tp - agg_fp - agg_fn)

    p = agg_tp / (agg_tp + agg_fp) if (agg_tp + agg_fp) > 0 else 1.0
    r = agg_tp / (agg_tp + agg_fn) if (agg_tp + agg_fn) > 0 else 1.0
    f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    rows["OVERALL"] = {
        "expected_count": agg_exp,
        "detected_count": agg_det,
        "true_positives": agg_tp,
        "false_positives": agg_fp,
        "false_negatives": agg_fn,
        "true_negatives": agg_tn,
        "precision": round(p, 4),
        "recall": round(r, 4),
        "f1": round(f, 4),
        "false_negative_rate": round(
            agg_fn / (agg_tp + agg_fn) if (agg_tp + agg_fn) > 0 else 0.0, 4
        ),
        "false_positive_rate": round(
            agg_fp / (agg_fp + agg_tn) if (agg_fp + agg_tn) > 0 else 0.0, 4
        ),
        "hipaa_critical": None,
        "hipaa_pass": None,
    }

    return rows


def _count_only_metrics(detected: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Return count-only metric rows when no LLM reference is available."""
    all_types = sorted({e.get("category", "UNKNOWN") for e in detected})
    rows: Dict[str, Dict[str, Any]] = {}
    none_metrics: Dict[str, Any] = {
        "expected_count": None,
        "true_positives": None,
        "false_positives": None,
        "false_negatives": None,
        "true_negatives": None,
        "precision": None,
        "recall": None,
        "f1": None,
        "false_negative_rate": None,
        "false_positive_rate": None,
        "hipaa_pass": None,
    }
    for etype in all_types:
        count = sum(1 for e in detected if e.get("category") == etype)
        rows[etype] = {
            **none_metrics,
            "detected_count": count,
            "hipaa_critical": etype in _HIPAA_CRITICAL,
        }
    rows["OVERALL"] = {
        **none_metrics,
        "detected_count": len(detected),
        "hipaa_critical": None,
    }
    return rows


# ---------------------------------------------------------------------------
# LLM evaluation runner
# ---------------------------------------------------------------------------


def evaluate_document(
    txt_path: Path,
    detectors: str,
    use_judge: bool,
    eval_config: Any,
) -> Dict[str, Any]:
    """Run LLMEvaluator on one document and return its result dict."""
    from hipaa_deidentifier.phi_detection.evaluation.runners.llm_evaluator import (
        LLMEvaluator,
    )

    ev = LLMEvaluator(
        document_path=str(txt_path),
        detectors=detectors,
        config=eval_config,
        use_judge=use_judge,
    )
    return ev.run()


# ---------------------------------------------------------------------------
# LLMEvaluator result → flat metric rows
# ---------------------------------------------------------------------------


def build_rows(
    llm_result: Dict[str, Any],
    note_category: str,
    note_file: str,
) -> List[Dict[str, Any]]:
    """Flatten one LLMEvaluator result into a list of per-entity-type metric rows.

    Each row corresponds to one (detector, entity_type) combination and
    contains all metric fields defined in _COLUMNS.
    """
    _raw_expected = llm_result.get("llm_expected_entities") or []
    # Strip non-HIPAA categories the LLM judge sometimes labels (MEDICATION, VITAL_SIGN,
    # DIAGNOSIS, AGE, ALLERGY, LAB_RESULT, TIME, etc.) — these are clinical facts, not
    # Safe Harbor identifiers, and create phantom FNs that no detector should ever satisfy.
    expected = [
        e for e in _raw_expected if e.get("category") in _HIPAA_ALLOWED_CATEGORIES
    ]
    detector_results = llm_result.get("detector_entities") or {}
    judgment = llm_result.get("llm_judgment") or {}
    llm_coverage = judgment.get("coverage_score") if judgment else None
    llm_overall_pass = judgment.get("overall_pass") if judgment else None
    llm_status = llm_result.get("llm_status", "ok")

    doc_path = llm_result.get("document_path", "")
    text = ""
    if doc_path:
        try:
            text = Path(doc_path).read_text(encoding="utf-8")
        except OSError:
            pass

    has_expected = bool(expected)
    rows: List[Dict[str, Any]] = []

    for det_label, det_data in detector_results.items():
        base: Dict[str, Any] = {
            "note_category": note_category,
            "note_file": note_file,
            "detector": det_label,
            "llm_coverage_score": llm_coverage,
            "llm_overall_pass": llm_overall_pass,
            "llm_status": llm_status,
        }

        if det_data.get("status") != "ok":
            rows.append(
                {
                    **base,
                    "entity_type": "ERROR",
                    "expected_count": None,
                    "detected_count": None,
                    "true_positives": None,
                    "false_positives": None,
                    "false_negatives": None,
                    "true_negatives": None,
                    "precision": None,
                    "recall": None,
                    "f1": None,
                    "false_negative_rate": None,
                    "false_positive_rate": None,
                    "hipaa_critical": None,
                    "hipaa_pass": None,
                }
            )
            continue

        detected = det_data.get("entities") or []

        metrics = (
            compute_detector_metrics(detected, expected, text)
            if has_expected
            else _count_only_metrics(detected)
        )

        # Sort: HIPAA critical types first, then alphabetical, OVERALL last
        sorted_types = sorted(
            [t for t in metrics if t != "OVERALL"],
            key=lambda t: (0 if t in _HIPAA_CRITICAL else 1, t),
        ) + ["OVERALL"]

        for etype in sorted_types:
            rows.append({**base, "entity_type": etype, **metrics[etype]})

    return rows


# ---------------------------------------------------------------------------
# Excel output helpers
# ---------------------------------------------------------------------------


def _write_sheet(
    ws: Any,
    rows: List[Dict[str, Any]],
    columns: List[str],
) -> None:
    """Write rows to an openpyxl Worksheet with header styling and conditional fills."""
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    # Use display headers from _HEADERS map; fall back to column key
    header_row = [_HEADERS.get(c, c) for c in columns]

    # Header styling
    HEADER_FILL = PatternFill("solid", fgColor="4472C4")
    HEADER_FONT = Font(bold=True, color="FFFFFF")
    CENTER = Alignment(horizontal="center")

    for col_idx, header in enumerate(header_row, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER

    # Conditional fill colours
    GREEN = PatternFill("solid", fgColor="C6EFCE")
    RED = PatternFill("solid", fgColor="FFC7CE")
    ORANGE = PatternFill("solid", fgColor="FFEB9C")
    GREY = PatternFill("solid", fgColor="D9D9D9")

    for row_idx, row in enumerate(rows, 2):
        etype = row.get("entity_type", "")
        is_overall = etype == "OVERALL"
        is_error = etype == "ERROR"
        is_critical = row.get("hipaa_critical") is True

        for col_idx, col in enumerate(columns, 1):
            val = row.get(col)

            # Round floats for display
            if isinstance(val, float):
                val = round(val, 4)

            cell = ws.cell(row=row_idx, column=col_idx, value=val)

            if is_overall:
                cell.font = Font(bold=True)
                cell.fill = GREY
            elif is_error:
                cell.font = Font(bold=True, color="FF0000")

            # Colour hipaa_pass column
            if col == "hipaa_pass" and val is not None:
                cell.fill = GREEN if val else RED

            # Colour recall for HIPAA-critical entity types
            if col == "recall" and is_critical and isinstance(val, (int, float)):
                if val >= _RECALL_THRESHOLD:
                    cell.fill = GREEN
                elif val >= 0.80:
                    cell.fill = ORANGE
                else:
                    cell.fill = RED

            # Colour llm_overall_pass / llm_coverage_score
            if col == "llm_overall_pass" and val is not None:
                cell.fill = GREEN if val else RED
            if col == "llm_coverage_score" and isinstance(val, (int, float)):
                if val >= _RECALL_THRESHOLD:
                    cell.fill = GREEN
                elif val >= 0.80:
                    cell.fill = ORANGE
                else:
                    cell.fill = RED

    # Auto-width columns
    for col_idx, col in enumerate(columns, 1):
        lengths = [len(str(_HEADERS.get(col, col)))]
        lengths += [len(str(row.get(col) or "")) for row in rows]
        ws.column_dimensions[get_column_letter(col_idx)].width = min(
            max(lengths) + 2, 35
        )

    ws.freeze_panes = "A2"


def write_category_excel(
    category_name: str,
    note_rows: Dict[str, List[Dict[str, Any]]],
    output_dir: Path,
) -> Path:
    """Write one .xlsx per category: one sheet per note file + CATEGORY_SUMMARY sheet.

    Args:
        category_name: Human-readable category (used for folder name).
        note_rows:     {note_stem: [metric rows]} for every note in the category.
        output_dir:    Root output directory.

    Returns:
        Path to the written .xlsx file.
    """
    try:
        import openpyxl
    except ImportError as exc:
        raise ImportError("openpyxl is required. Run: pip install openpyxl") from exc

    safe_name = re.sub(r'[<>:"/\\|?*\s]', "_", category_name)
    cat_dir = output_dir / safe_name
    cat_dir.mkdir(parents=True, exist_ok=True)
    out_path = cat_dir / "evaluation.xlsx"

    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # remove default blank sheet

    # Columns for note-specific sheets: exclude note_category/note_file (same for all rows)
    note_cols = [c for c in _COLUMNS if c not in {"note_category", "note_file"}]
    summary_rows: List[Dict[str, Any]] = []

    for note_stem, rows in sorted(note_rows.items()):
        sheet_name = note_stem[:31]  # Excel sheet name limit
        ws = wb.create_sheet(title=sheet_name)
        _write_sheet(ws, rows, note_cols)
        summary_rows.extend(rows)

    # CATEGORY_SUMMARY sheet (index 0 = leftmost tab) with all note rows
    ws_summary = wb.create_sheet(title="CATEGORY_SUMMARY", index=0)
    summary_cols = [c for c in _COLUMNS if c != "note_category"]
    _write_sheet(ws_summary, summary_rows, summary_cols)

    wb.save(out_path)
    logger.info("Wrote category workbook: %s", out_path)
    return out_path


def write_overall_summary(
    all_rows: List[Dict[str, Any]],
    output_dir: Path,
) -> Path:
    """Write overall_summary.xlsx aggregating results across all categories.

    Sheets:
      All_Results         — every row from every note and detector
      Summary_by_Note     — OVERALL rows only (one per note × detector)
      Aggregated_by_Cat   — summed TP/FP/FN/TN per category × entity_type
                            with recomputed derived metrics
    """
    try:
        import openpyxl
    except ImportError as exc:
        raise ImportError("openpyxl is required. Run: pip install openpyxl") from exc

    out_path = output_dir / "overall_summary.xlsx"
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # Sheet 1: every single row
    ws_all = wb.create_sheet(title="All_Results")
    _write_sheet(ws_all, all_rows, _COLUMNS)

    # Sheet 2: OVERALL rows only
    overall_rows = [r for r in all_rows if r.get("entity_type") == "OVERALL"]
    ws_overall = wb.create_sheet(title="Summary_by_Note")
    _write_sheet(ws_overall, overall_rows, _COLUMNS)

    # Sheet 3: aggregate TP/FP/FN/TN by (category, detector, entity_type)
    agg: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for r in all_rows:
        if r.get("entity_type") in {"OVERALL", "ERROR"}:
            continue
        key: Tuple[str, str, str] = (
            r["note_category"],
            r["detector"],
            r["entity_type"],
        )
        if key not in agg:
            agg[key] = {
                "note_category": r["note_category"],
                "note_file": "(aggregated)",
                "detector": r["detector"],
                "entity_type": r["entity_type"],
                "expected_count": 0,
                "detected_count": 0,
                "true_positives": 0,
                "false_positives": 0,
                "false_negatives": 0,
                "true_negatives": 0,
                "hipaa_critical": r.get("hipaa_critical"),
                "llm_coverage_score": None,
                "llm_overall_pass": None,
                "llm_status": None,
            }
        entry = agg[key]
        for field in (
            "expected_count",
            "detected_count",
            "true_positives",
            "false_positives",
            "false_negatives",
            "true_negatives",
        ):
            if r.get(field) is not None:
                entry[field] = (entry[field] or 0) + r[field]

    # Recompute derived metrics from aggregated counts
    agg_rows: List[Dict[str, Any]] = []
    for entry in agg.values():
        tp = entry["true_positives"] or 0
        fp = entry["false_positives"] or 0
        fn = entry["false_negatives"] or 0
        tn = entry["true_negatives"] or 0

        prec = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        f_v = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        fnr = fn / (tp + fn) if (tp + fn) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        is_crit = entry.get("hipaa_critical")

        entry.update(
            {
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1": round(f_v, 4),
                "false_negative_rate": round(fnr, 4),
                "false_positive_rate": round(fpr, 4),
                "hipaa_pass": (rec >= _RECALL_THRESHOLD) if is_crit else None,
            }
        )
        agg_rows.append(entry)

    agg_rows.sort(key=lambda r: (r["note_category"], r["detector"], r["entity_type"]))

    ws_cat = wb.create_sheet(title="Aggregated_by_Cat")
    _write_sheet(ws_cat, agg_rows, _COLUMNS)

    wb.save(out_path)
    logger.info("Wrote overall summary: %s", out_path)
    return out_path


# ---------------------------------------------------------------------------
# Console progress summary
# ---------------------------------------------------------------------------


def print_console_summary(all_rows: List[Dict[str, Any]]) -> None:
    """Print a recall/F1/pass table to stdout after all evaluations complete."""
    overall_rows = [r for r in all_rows if r.get("entity_type") == "OVERALL"]
    if not overall_rows:
        return

    col_cat = 34
    col_note = 38
    col_det = 22
    col_num = 8
    col_flag = 6
    width = col_cat + col_note + col_det + col_num * 2 + col_flag + 4

    print("\n" + "=" * width)
    print("  PHI IDENTIFICATION EVALUATION — RESULTS SUMMARY")
    print("=" * width)
    header = (
        f"  {'Category':<{col_cat}} "
        f"{'Note':<{col_note}} "
        f"{'Detector':<{col_det}} "
        f"{'Recall':>{col_num}} "
        f"{'F1':>{col_num}} "
        f"{'Pass':>{col_flag}}"
    )
    print(header)
    print("-" * width)

    prev_cat = None
    for r in sorted(
        overall_rows,
        key=lambda x: (
            x.get("note_category", ""),
            x.get("note_file", ""),
            x.get("detector", ""),
        ),
    ):
        cat = r.get("note_category", "")
        if cat != prev_cat:
            if prev_cat is not None:
                print()
            prev_cat = cat

        recall = r.get("recall")
        f1 = r.get("f1")
        pass_flag = (
            "PASS"
            if recall is not None and recall >= _RECALL_THRESHOLD
            else ("FAIL" if recall is not None else "N/A")
        )
        recall_str = f"{recall:.2%}" if recall is not None else "N/A"
        f1_str = f"{f1:.2%}" if f1 is not None else "N/A"

        det_short = r.get("detector", "")[:col_det]
        cat_short = cat[:col_cat]
        note_short = r.get("note_file", "")[:col_note]

        print(
            f"  {cat_short:<{col_cat}} "
            f"{note_short:<{col_note}} "
            f"{det_short:<{col_det}} "
            f"{recall_str:>{col_num}} "
            f"{f1_str:>{col_num}} "
            f"{pass_flag:>{col_flag}}"
        )

    print("=" * width + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="phi_identification_evaluation_cli",
        description=(
            "Batch PHI identification evaluation across all clinical note categories.\n"
            "Requires LM Studio running locally (default http://localhost:1234) unless\n"
            "--no-judge is used (count-only mode, no TP/FP/FN metrics)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  Evaluate all notes in data/:\n"
            "    python phi_identification_evaluation_cli.py --input-folder data/\n\n"
            "  Evaluate one category:\n"
            "    python phi_identification_evaluation_cli.py \\\n"
            '        --input-folder "data/Long-term and Supportive Care/"\n\n'
            "  No LM Studio (count-only, no TP/FP/FN):\n"
            "    python phi_identification_evaluation_cli.py --input-folder data/ --no-judge\n\n"
            "  Post-guardrail pipeline only:\n"
            "    python phi_identification_evaluation_cli.py \\\n"
            "        --input-folder data/ --detectors pipeline_filtered"
        ),
    )
    parser.add_argument(
        "--input-folder",
        required=True,
        metavar="DIR",
        help=(
            "Root folder to scan.  Subfolders are treated as note categories; "
            ".txt files directly in root are evaluated as a single category."
        ),
    )
    parser.add_argument(
        "--output-folder",
        default="phi_eval_results",
        metavar="DIR",
        help="Directory for Excel reports.  Default: phi_eval_results/",
    )
    parser.add_argument(
        "--detectors",
        default="all",
        help=(
            "Comma-separated detector names: "
            "hf, presidio, heuristics, pipeline, pipeline_filtered, all.  "
            "pipeline_filtered applies the FP guardrail (production behaviour).  "
            "Default: all"
        ),
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        default=False,
        help=(
            "Skip LM Studio judge.  Outputs detected entity counts only; "
            "precision/recall/TP/FP/FN will be empty."
        ),
    )
    parser.add_argument(
        "--eval-config",
        default=None,
        metavar="PATH",
        help="Optional YAML override for evaluation settings (LM Studio URL, model, etc.).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Enable DEBUG-level logging.",
    )
    return parser.parse_args(argv)


def _load_dotenv() -> None:
    """Load .env from the project root into os.environ.

    Tries python-dotenv first; if not installed, parses the file manually
    so the CLI works without requiring an extra dependency.
    Only sets variables that are not already present in the environment.
    """
    import os

    # Walk up from this file's location to find the nearest .env
    search = Path(__file__).resolve().parent
    env_file: Optional[Path] = None
    for _ in range(6):
        candidate = search / ".env"
        if candidate.exists():
            env_file = candidate
            break
        search = search.parent

    if env_file is None:
        return

    try:
        from dotenv import load_dotenv

        load_dotenv(env_file, override=False)
        return
    except ImportError:
        pass

    # Fallback: manual KEY=VALUE parser (no extra dependency needed)
    with env_file.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("transformers", "presidio_analyzer", "httpx", "deepeval"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    _configure_logging(args.verbose)

    # Load .env from the project root so OPENAI_API_KEY (and other secrets) are
    # available before the judge is constructed.  python-dotenv is optional —
    # if it's not installed we fall back to manually parsing the file.
    _load_dotenv()

    root = Path(args.input_folder)
    if not root.exists():
        print(f"\n[ERROR] Input folder not found: {root}", file=sys.stderr)
        return 1

    output_dir = Path(args.output_folder)
    output_dir.mkdir(parents=True, exist_ok=True)

    use_judge = not args.no_judge

    from hipaa_deidentifier.phi_detection.evaluation.evaluation_config import (
        load_evaluation_config,
    )

    eval_config = load_evaluation_config(args.eval_config)

    categories = scan_input_folder(root)
    if not categories:
        print(f"\n[ERROR] No .txt files found under {root}", file=sys.stderr)
        return 1

    total_files = sum(len(v) for v in categories.values())
    print("\n[EVAL] PHI Identification Batch Evaluation")
    print(f"   Input       : {root.resolve()}")
    print(f"   Categories  : {len(categories)}")
    print(f"   Total notes : {total_files}")
    print(f"   Detectors   : {args.detectors}")
    if use_judge:
        if eval_config.active_backend == "openai":
            _judge_label = f"enabled — OpenAI ({eval_config.openai_api.model})"
        else:
            _judge_label = f"enabled — LM Studio ({eval_config.lm_studio.model})"
    else:
        _judge_label = "disabled — count-only mode"
    print(f"   LLM judge   : {_judge_label}")
    print(f"   Output      : {output_dir.resolve()}\n")

    all_rows: List[Dict[str, Any]] = []
    completed = 0
    errors = 0

    for category_name, txt_paths in sorted(categories.items()):
        print(
            f"\n[CATEGORY] {category_name}  ({len(txt_paths)} note{'s' if len(txt_paths) != 1 else ''})"
        )
        note_rows: Dict[str, List[Dict[str, Any]]] = {}

        for txt_path in txt_paths:
            completed += 1
            print(
                f"   [{completed:>2}/{total_files}] {txt_path.name:<55}",
                end=" ",
                flush=True,
            )

            try:
                llm_result = evaluate_document(
                    txt_path=txt_path,
                    detectors=args.detectors,
                    use_judge=use_judge,
                    eval_config=eval_config,
                )
                rows = build_rows(
                    llm_result=llm_result,
                    note_category=category_name,
                    note_file=txt_path.stem,
                )
                note_rows[txt_path.stem] = rows
                all_rows.extend(rows)

                # Inline progress status
                judgment = llm_result.get("llm_judgment") or {}
                if judgment:
                    score = judgment.get("coverage_score")
                    score_str = (
                        f"{score:.2f}" if isinstance(score, float) else str(score)
                    )
                    # Pass/fail driven by computed recall against threshold, not LLM opinion
                    _overall_recall = None
                    for row in rows:
                        if row.get("entity_type") == "OVERALL":
                            _overall_recall = row.get("recall")
                            break
                    passed = (
                        "PASS"
                        if _overall_recall is not None
                        and _overall_recall >= _RECALL_THRESHOLD
                        else "FAIL"
                    )
                    print(f"coverage={score_str}  [{passed}]")
                else:
                    det_ents = llm_result.get("detector_entities") or {}
                    total_det = sum(
                        len(d.get("entities", []))
                        for d in det_ents.values()
                        if d.get("status") == "ok"
                    )
                    llm_err = llm_result.get("llm_error_message") or ""
                    status = f"detected={total_det}"
                    if llm_err:
                        status += f"  [LLM: {llm_err[:40]}]"
                    print(status)

            except Exception as exc:
                errors += 1
                print(f"ERROR: {exc}")
                logger.exception("Failed to evaluate %s", txt_path)

        if note_rows:
            try:
                out_path = write_category_excel(category_name, note_rows, output_dir)
                print(f"   -> Wrote: {out_path}")
            except Exception as exc:
                logger.error("Failed to write Excel for '%s': %s", category_name, exc)
                errors += 1

    # Overall summary workbook
    if all_rows:
        try:
            out_path = write_overall_summary(all_rows, output_dir)
            print(f"\n[SUMMARY] overall_summary.xlsx -> {out_path}")
        except Exception as exc:
            logger.error("Failed to write overall summary: %s", exc)
            errors += 1

    print_console_summary(all_rows)

    status_str = (
        f"{errors} error{'s' if errors != 1 else ''}" if errors else "no errors"
    )
    print(
        f"[DONE]  {completed} note{'s' if completed != 1 else ''} evaluated, {status_str}"
    )
    print(f"        Results: {output_dir.resolve()}\n")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
