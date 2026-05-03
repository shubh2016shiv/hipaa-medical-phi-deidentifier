#!/usr/bin/env python3
"""
PHI Evaluation Summary Report
==============================
Reads results/overall_summary.xlsx and prints a Markdown report covering:

  1. System-level headline metrics
  2. Per-entity-type breakdown (HIPAA-allowed categories only)
  3. HIPAA-critical compliance table
  4. Worst / best performing notes
  5. FP/FN hotspot tables
  6. Judge contamination audit (non-HIPAA categories still in expected set)

Run from the project root:
    python hipaa_deidentifier/phi_detection/summarize_evaluation.py
    python hipaa_deidentifier/phi_detection/summarize_evaluation.py --results results/overall_summary.xlsx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import openpyxl
except ImportError:
    sys.exit("openpyxl is required: pip install openpyxl")

try:
    from tabulate import tabulate
except ImportError:
    sys.exit("tabulate is required: pip install tabulate")

# ---------------------------------------------------------------------------
# Constants (mirror phi_identification_evaluation_cli.py)
# ---------------------------------------------------------------------------

_HIPAA_CRITICAL = frozenset(
    {"NAME", "MRN", "DATE", "AGE_OVER_89", "LOCATION", "ACCOUNT_NUMBER", "US_SSN"}
)
_RECALL_PASS = 0.95

_HIPAA_ALLOWED = frozenset(
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
        "HEALTH_PLAN_ID",
        "ENCOUNTER_ID",
        "LICENSE_NUMBER",
        "NPI",
    }
)

# Column order as written by phi_identification_evaluation_cli.py
_COL = [
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


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _row_to_dict(row: Tuple) -> Dict[str, Any]:
    return dict(zip(_COL, row))


def load_all_results(xlsx_path: Path) -> List[Dict[str, Any]]:
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    if "All_Results" not in wb.sheetnames:
        sys.exit(f"Sheet 'All_Results' not found in {xlsx_path}")
    ws = wb["All_Results"]
    rows = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue  # skip header
        d = _row_to_dict(row)
        if d["entity_type"] is None:
            continue
        rows.append(d)
    return rows


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def _safe_pct(num: Optional[float], den: Optional[float]) -> Optional[float]:
    if num is None or den is None or den == 0:
        return None
    return num / den


def aggregate_by_entity(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    agg: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        et = r["entity_type"]
        if et == "OVERALL":
            continue
        if r["true_positives"] is None:
            continue
        if et not in agg:
            agg[et] = dict(
                expected=0,
                detected=0,
                tp=0,
                fp=0,
                fn=0,
                hipaa_critical=bool(r["hipaa_critical"]),
                hipaa_allowed=(et in _HIPAA_ALLOWED),
            )
        agg[et]["expected"] += r["expected_count"] or 0
        agg[et]["detected"] += r["detected_count"] or 0
        agg[et]["tp"] += r["true_positives"] or 0
        agg[et]["fp"] += r["false_positives"] or 0
        agg[et]["fn"] += r["false_negatives"] or 0
    for et, d in agg.items():
        d["precision"] = _safe_pct(d["tp"], d["tp"] + d["fp"])
        d["recall"] = _safe_pct(d["tp"], d["tp"] + d["fn"])
        p, rec = d["precision"], d["recall"]
        d["f1"] = (2 * p * rec / (p + rec)) if p and rec else None
    return agg


def aggregate_by_note(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    overall_rows = [
        r
        for r in rows
        if r["entity_type"] == "OVERALL" and r["true_positives"] is not None
    ]
    return overall_rows


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _pct(v: Optional[float], decimals: int = 1) -> str:
    return f"{v * 100:.{decimals}f}%" if v is not None else "—"


def _pass_fail(recall: Optional[float], is_critical: bool) -> str:
    if not is_critical:
        return ""
    if recall is None:
        return "?"
    return "✓ PASS" if recall >= _RECALL_PASS else "✗ FAIL"


# ---------------------------------------------------------------------------
# Report sections
# ---------------------------------------------------------------------------


def section_headline(agg: Dict[str, Dict[str, Any]]) -> str:
    all_tp = sum(d["tp"] for d in agg.values())
    all_fp = sum(d["fp"] for d in agg.values())
    all_fn = sum(d["fn"] for d in agg.values())
    all_exp = sum(d["expected"] for d in agg.values())
    all_det = sum(d["detected"] for d in agg.values())
    prec = _safe_pct(all_tp, all_tp + all_fp)
    rec = _safe_pct(all_tp, all_tp + all_fn)
    f1 = (2 * prec * rec / (prec + rec)) if prec and rec else None
    lines = [
        "## System-Level Headline Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| PHI expected (HIPAA-allowed categories) | {all_exp} |",
        f"| PHI detected | {all_det} |",
        f"| True Positives | {all_tp} |",
        f"| False Positives | {all_fp} |",
        f"| False Negatives | {all_fn} |",
        f"| Overall Precision | {_pct(prec, 2)} |",
        f"| Overall Recall | {_pct(rec, 2)} |",
        f"| Overall F1 | {_pct(f1, 2)} |",
    ]
    return "\n".join(lines)


def section_entity_breakdown(agg: Dict[str, Dict[str, Any]]) -> str:
    allowed = {et: d for et, d in agg.items() if d["hipaa_allowed"]}

    # Sort: HIPAA-critical first (by recall desc), then others (by recall desc)
    def sort_key(item):
        et, d = item
        return (not d["hipaa_critical"], -(d["recall"] or 0))

    rows = []
    for et, d in sorted(allowed.items(), key=sort_key):
        crit = "★" if d["hipaa_critical"] else ""
        pass_str = _pass_fail(d["recall"], d["hipaa_critical"])
        rows.append(
            [
                f"{et}{crit}",
                d["expected"],
                d["detected"],
                d["tp"],
                d["fp"],
                d["fn"],
                _pct(d["recall"], 1),
                _pct(d["precision"], 1),
                _pct(d["f1"], 1),
                pass_str,
            ]
        )
    headers = [
        "Entity Type",
        "Expected",
        "Detected",
        "TP",
        "FP",
        "FN",
        "Recall",
        "Precision",
        "F1",
        "HIPAA",
    ]
    table = tabulate(
        rows,
        headers=headers,
        tablefmt="pipe",
        colalign=(
            "left",
            "right",
            "right",
            "right",
            "right",
            "right",
            "right",
            "right",
            "right",
            "center",
        ),
    )
    note = "_★ = HIPAA Safe Harbor critical type (≥95% recall required)_"
    return f"## Per-Entity Performance (HIPAA-Allowed Categories)\n\n{note}\n\n{table}"


def section_hipaa_compliance(agg: Dict[str, Dict[str, Any]]) -> str:
    rows = []
    for et in sorted(_HIPAA_CRITICAL):
        d = agg.get(et, {})
        rec = d.get("recall")
        prec = d.get("precision")
        f1 = d.get("f1")
        fn = d.get("fn", "—")
        status = _pass_fail(rec, True)
        rows.append(
            [
                et,
                d.get("expected", "—"),
                d.get("tp", "—"),
                fn,
                _pct(rec, 1),
                _pct(prec, 1),
                _pct(f1, 1),
                status,
            ]
        )
    headers = [
        "Category",
        "Expected",
        "TP",
        "FN",
        "Recall",
        "Precision",
        "F1",
        "Status",
    ]
    table = tabulate(
        rows,
        headers=headers,
        tablefmt="pipe",
        colalign=(
            "left",
            "right",
            "right",
            "right",
            "right",
            "right",
            "right",
            "center",
        ),
    )
    return f"## HIPAA-Critical Compliance\n\n{table}"


def section_note_performance(note_rows: List[Dict[str, Any]]) -> str:
    data = []
    for r in note_rows:
        data.append(
            (
                (r.get("note_category") or "")[:35],
                (r.get("note_file") or "")[:38],
                r.get("recall"),
                r.get("precision"),
                r.get("f1"),
                r.get("false_negatives") or 0,
                r.get("expected_count") or 0,
            )
        )
    # Sort by recall ascending
    data.sort(key=lambda x: (x[2] or 0))

    def fmt_note_row(row):
        cat, fname, rec, prec, f1, fn, exp = row
        return [cat, fname, _pct(rec, 1), _pct(prec, 1), _pct(f1, 1), fn, exp]

    headers = ["Category", "Note File", "Recall", "Precision", "F1", "FN", "Expected"]
    worst5 = tabulate(
        [fmt_note_row(r) for r in data[:5]],
        headers=headers,
        tablefmt="pipe",
        colalign=("left", "left", "right", "right", "right", "right", "right"),
    )
    best5 = tabulate(
        [fmt_note_row(r) for r in data[-5:]],
        headers=headers,
        tablefmt="pipe",
        colalign=("left", "left", "right", "right", "right", "right", "right"),
    )
    return (
        "## Note-Level Performance\n\n"
        "### Worst 5 Notes (Lowest Recall)\n\n" + worst5 + "\n\n"
        "### Best 5 Notes (Highest Recall)\n\n" + best5
    )


def section_fp_fn_hotspots(agg: Dict[str, Dict[str, Any]]) -> str:
    # Top FP sources
    fp_rows = sorted(
        [(et, d["fp"]) for et, d in agg.items() if d["fp"] > 0],
        key=lambda x: x[1],
        reverse=True,
    )[:12]
    fp_table = tabulate(
        fp_rows,
        headers=["Entity Type", "False Positives"],
        tablefmt="pipe",
        colalign=("left", "right"),
    )

    # Top FN sources (HIPAA-allowed only)
    fn_rows = sorted(
        [(et, d["fn"]) for et, d in agg.items() if d["fn"] > 0 and d["hipaa_allowed"]],
        key=lambda x: x[1],
        reverse=True,
    )[:12]
    fn_table = tabulate(
        fn_rows,
        headers=["Entity Type", "False Negatives (Missed)"],
        tablefmt="pipe",
        colalign=("left", "right"),
    )

    return (
        "## FP / FN Hotspots\n\n"
        "### Over-Detection (False Positives)\n\n" + fp_table + "\n\n"
        "### Under-Detection (False Negatives, HIPAA-allowed only)\n\n" + fn_table
    )


def section_judge_contamination(agg: Dict[str, Dict[str, Any]]) -> str:
    contaminated = {
        et: d for et, d in agg.items() if not d["hipaa_allowed"] and d["expected"] > 0
    }
    if not contaminated:
        return (
            "## LLM Judge Contamination Audit\n\n"
            "_No non-HIPAA categories detected in expected set — judge is clean._"
        )
    rows = sorted(
        [(et, d["expected"], d["fn"]) for et, d in contaminated.items()],
        key=lambda x: x[1],
        reverse=True,
    )
    table = tabulate(
        rows,
        headers=["Non-HIPAA Category", "LLM Expected", "Phantom FNs"],
        tablefmt="pipe",
        colalign=("left", "right", "right"),
    )
    phantom_total = sum(r[2] for r in rows)
    return (
        "## LLM Judge Contamination Audit\n\n"
        "The following categories are **not HIPAA Safe Harbor identifiers** but appear "
        "in the LLM's expected-PHI set. Each creates a phantom FN the detector can never "
        "satisfy, suppressing recall.\n\n"
        + table
        + f"\n\n**Total phantom FNs from judge contamination: {phantom_total}**"
    )


def section_interpretation() -> str:
    return """\
## Interpretation Guide

| Symbol | Meaning |
|--------|---------|
| ★ | HIPAA Safe Harbor critical identifier — must reach ≥ 95% recall |
| ✓ PASS | Recall ≥ 95% for this HIPAA-critical category |
| ✗ FAIL | Recall < 95% — compliance gap, requires investigation |
| — | Metric not applicable or no data |

**Reading the FP count:** A high FP count means the detector found entities the LLM
judge did not label as expected PHI. For DATE this is often a *judge quality* issue
(LLM misses embedded dates) rather than over-detection by the pipeline.

**Reading the FN count:** A high FN (miss) count may reflect (a) a genuine detector
gap, (b) phantom FNs from the judge contamination table above, or (c) the alias-matching
logic crediting a TP to a related category (e.g. PROVIDER_NAME TP credited to NAME).
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="PHI evaluation Markdown summary")
    parser.add_argument(
        "--results",
        default="results/overall_summary.xlsx",
        help="Path to overall_summary.xlsx (default: results/overall_summary.xlsx)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write output to this file instead of stdout",
    )
    args = parser.parse_args()

    xlsx_path = Path(args.results)
    if not xlsx_path.exists():
        sys.exit(
            f"Results file not found: {xlsx_path}\n"
            "Run the evaluation CLI first, or pass --results <path>."
        )

    rows = load_all_results(xlsx_path)
    if not rows:
        sys.exit("No data rows found in All_Results sheet.")

    agg = aggregate_by_entity(rows)
    notes = aggregate_by_note(rows)

    sections = [
        f"# PHI Identification Evaluation Report\n\n_Source: `{xlsx_path}`_\n",
        section_headline(agg),
        section_hipaa_compliance(agg),
        section_entity_breakdown(agg),
        section_note_performance(notes),
        section_fp_fn_hotspots(agg),
        section_judge_contamination(agg),
        section_interpretation(),
    ]

    report = "\n\n---\n\n".join(sections)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
