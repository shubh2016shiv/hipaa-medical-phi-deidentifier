"""
Report Generator — Console Table + JSON Output
================================================

Renders evaluation results as a rich console table (using tabulate, which
is already in requirements.txt) and optionally writes a JSON report file
for long-term tracking.

Architecture:
-------------
    report_generator.py  ←  used by:
      ├─ evaluation/__init__.py (run_evaluation)
      └─ evaluation/__main__.py (CLI entry point)

Dependencies:
    - tabulate (already in requirements.txt)
    - json (stdlib)
    - datetime (stdlib)

Author: HIPAA De-identification System
Last Updated: 2026-05-02
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from tabulate import tabulate

from ..metrics.span_metrics import DetectorMetrics

logger = logging.getLogger(__name__)

# Directory for JSON output files (relative to project root)
_DEFAULT_RESULTS_DIR: Path = Path(__file__).resolve().parent.parent / "results"

# Entity types to show in the per-type breakdown table (display order)
_DISPLAY_ENTITY_TYPES: list[str] = [
    "NAME",
    "MRN",
    "DATE",
    "AGE_OVER_89",
    "LOCATION",
    "ACCOUNT_NUMBER",
    "ORGANIZATION",
    "PHONE_NUMBER",
    "FAX_NUMBER",
    "EMAIL_ADDRESS",
    "US_SSN",
    "LICENSE_NUMBER",
]


class ReportGenerator:
    """Renders PHI detection evaluation results as a console table and JSON file.

    Example:
        >>> generator = ReportGenerator()
        >>> generator.render_console(results_dict)
        >>> generator.write_json(results_dict, document_name="home_health_assessment")
    """

    def render_console(
        self,
        results: Dict[str, DetectorMetrics],
        document_name: Optional[str] = None,
    ) -> None:
        """Print a formatted evaluation report to stdout.

        Args:
            results: Dict mapping detector label → DetectorMetrics.
            document_name: Optional document name shown in the header.

        Example:
            >>> generator.render_console(results, document_name="home_health_assessment_patient_01")
        """
        header = self._build_header(document_name)
        print(header)

        # --- Per-detector × per-entity-type table ---
        rows = self._build_per_type_rows(results)
        table = tabulate(
            rows,
            headers=[
                "Detector",
                "Entity Type",
                "Precision",
                "Recall",
                "F1",
                "FNR",
                "FPR",
                "Token-Recall",
                "Span-Recall",
                "Status",
            ],
            tablefmt="pipe",
            floatfmt=".3f",
        )
        print(
            "\n[METRICS] Per-Detector x Per-Entity-Type Metrics (Token-Level Primary)\n"
        )
        print(table)

        # --- Overall summary table ---
        summary_rows = self._build_summary_rows(results)
        summary_table = tabulate(
            summary_rows,
            headers=[
                "Detector",
                "Overall Precision",
                "Overall Recall",
                "Overall F1",
                "FNR",
                "HIPAA Coverage",
                "Status",
            ],
            tablefmt="pipe",
            floatfmt=".3f",
        )
        print("\n[SUMMARY] Overall Summary (All Entity Types)\n")
        print(summary_table)

        # --- HIPAA Coverage analysis ---
        self._print_coverage_analysis(results)

    def write_json(
        self,
        results: Dict[str, DetectorMetrics],
        document_name: str = "unknown_document",
        output_dir: Optional[str] = None,
    ) -> Path:
        """Write evaluation results to a timestamped JSON file.

        Args:
            results: Dict mapping detector label → DetectorMetrics.
            document_name: Document stem used in the filename.
            output_dir: Override output directory. Defaults to evaluation/results/.

        Returns:
            Path to the written JSON file.

        Example:
            >>> path = generator.write_json(results, "home_health_assessment_patient_01")
            >>> print(f"Report saved to: {path}")
        """
        results_dir = Path(output_dir) if output_dir else _DEFAULT_RESULTS_DIR
        results_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"eval_{document_name}_{timestamp}.json"
        output_path = results_dir / filename

        payload = self._build_json_payload(results, document_name)
        output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        logger.info("Evaluation report written: %s", output_path)
        print(f"\n[SAVED] JSON report saved: {output_path}")
        return output_path

    def render_llm_console(self, result: dict[str, Any]) -> None:
        """Print an annotation-free LLM evaluation report."""
        print(self._build_header(result.get("document")))

        detector_rows = []
        for detector_name, detector_result in result.get(
            "detector_entities", {}
        ).items():
            detector_rows.append(
                [
                    _shorten_detector_name(detector_name),
                    detector_result.get("status", "unknown"),
                    len(detector_result.get("entities", [])),
                    detector_result.get("error_message") or "",
                ]
            )

        print("\n[DETECTORS] Detector Output Summary\n")
        print(
            tabulate(
                detector_rows,
                headers=["Detector", "Status", "Entities", "Error"],
                tablefmt="pipe",
            )
        )

        status = result.get("llm_status", "unknown")
        judgment = result.get("llm_judgment") or {}
        expected_entities = result.get("llm_expected_entities") or []

        print("\n[LLM JUDGE] HIPAA Safe Harbor Coverage\n")
        if status != "ok":
            print(
                f"[ERROR] {result.get('llm_error_message') or 'LLM evaluation failed'}"
            )
            return

        coverage_score = judgment.get("coverage_score")
        coverage_display = (
            f"{coverage_score:.1%}"
            if isinstance(coverage_score, (int, float))
            else "N/A"
        )
        pass_display = "[PASS]" if judgment.get("overall_pass") else "[FAIL]"
        print(f"Status          : {pass_display}")
        print(f"Coverage Score  : {coverage_display}")
        print(f"Expected PHI    : {len(expected_entities)}")
        print(f"Missed PHI      : {len(judgment.get('missed_entities', []))}")
        print(f"False Positives : {len(judgment.get('false_positives', []))}")
        print(f"Mismatches      : {len(judgment.get('category_mismatches', []))}")

        if judgment.get("risk_summary"):
            print(f"\nRisk Summary:\n{judgment['risk_summary']}")

        recommendations = judgment.get("recommendations") or []
        if recommendations:
            print("\nRecommendations:")
            for item in recommendations:
                print(f"- {item}")

        missed = judgment.get("missed_entities") or []
        if missed:
            print("\nMissed PHI:")
            for entity in missed:
                print(
                    f"- [{entity.get('severity', 'unknown')}] "
                    f"{entity.get('category', 'PHI')}: {entity.get('text', '')}"
                )

        # ── Label evaluation: show every category mismatch, not just the count ──
        # A mismatch means the entity text WAS detected but with the wrong
        # HIPAA category (e.g., a provider name labelled as LOCATION).
        mismatches = judgment.get("category_mismatches") or []
        if mismatches:
            print("\nLabel Mismatches (text detected, wrong category):")
            for m in mismatches[:15]:
                print(
                    f"  [{m.get('detector', '?')}] "
                    f"{m.get('text', '')!r:30s}"
                    f"  expected={m.get('expected_category', '?'):20s}"
                    f"  detected={m.get('detected_category', '?')}"
                )
            if len(mismatches) > 15:
                print(f"  ... and {len(mismatches) - 15} more (see JSON report)")

        # ── Span evaluation: deterministic token-level and span-level metrics ──
        # gold_spans_count: how many character spans the LLM resolved from its
        # expected_entities list (one span per occurrence in the document).
        # These are used as ground truth for the metrics below.
        span_metrics = result.get("span_metrics")
        gold_count = result.get("llm_gold_spans_count", 0)

        if span_metrics:
            print(
                f"\n[SPAN METRICS] Deterministic Token & Span-Level Metrics"
                f" ({gold_count} gold spans resolved from LLM ground truth)\n"
            )
            print(
                "  Token-level: every character is a unit — partial span detection\n"
                "               scores proportionally (primary HIPAA metric).\n"
                "  Span-level : a prediction must cover ≥50 % of a gold span\n"
                "               to count as TP — binary, no partial credit.\n"
            )

            # ── Overall summary table (one row per detector) ──────────────────
            overall_rows = []
            for det_name, sm in span_metrics.items():
                ov = sm.get("overall", {})
                overall_rows.append(
                    [
                        _shorten_detector_name(det_name),
                        f"{ov.get('token_precision', 0.0) or 0.0:.3f}",
                        f"{ov.get('token_recall', 0.0) or 0.0:.3f}",
                        f"{ov.get('token_f1', 0.0) or 0.0:.3f}",
                        f"{ov.get('token_false_negative_rate', 0.0) or 0.0:.3f}",
                        f"{ov.get('span_precision', 0.0) or 0.0:.3f}",
                        f"{ov.get('span_recall', 0.0) or 0.0:.3f}",
                        f"{ov.get('span_f1', 0.0) or 0.0:.3f}",
                    ]
                )

            print(
                tabulate(
                    overall_rows,
                    headers=[
                        "Detector",
                        "Tok-P",
                        "Tok-R",
                        "Tok-F1",
                        "Tok-FNR",
                        "Span-P",
                        "Span-R",
                        "Span-F1",
                    ],
                    tablefmt="pipe",
                    floatfmt=".3f",
                )
            )

            # ── Per-entity-type breakdown (one block per detector) ─────────────
            for det_name, sm in span_metrics.items():
                per_type = sm.get("per_type", {})
                if not per_type:
                    continue

                type_rows = []
                for etype in sorted(per_type):
                    pt = per_type[etype]
                    # Skip rows where detector had no activity for this type
                    tok_r = pt.get("token_recall") or 0.0
                    spn_r = pt.get("span_recall") or 0.0
                    tok_fnr = pt.get("token_false_negative_rate") or 0.0
                    if tok_r == 0.0 and spn_r == 0.0 and tok_fnr == 0.0:
                        continue
                    type_rows.append(
                        [
                            f"  {etype}",
                            f"{pt.get('token_precision') or 0.0:.3f}",
                            f"{tok_r:.3f}",
                            f"{pt.get('token_f1') or 0.0:.3f}",
                            f"{tok_fnr:.3f}",
                            f"{pt.get('span_precision') or 0.0:.3f}",
                            f"{spn_r:.3f}",
                            f"{pt.get('span_f1') or 0.0:.3f}",
                        ]
                    )

                if type_rows:
                    print(
                        f"\n  {_shorten_detector_name(det_name)}"
                        f" — Per-Entity-Type Breakdown:"
                    )
                    print(
                        tabulate(
                            type_rows,
                            headers=[
                                "Entity Type",
                                "Tok-P",
                                "Tok-R",
                                "Tok-F1",
                                "Tok-FNR",
                                "Span-P",
                                "Span-R",
                                "Span-F1",
                            ],
                            tablefmt="pipe",
                            floatfmt=".3f",
                        )
                    )

    def write_llm_json(
        self,
        result: dict[str, Any],
        document_name: str = "unknown_document",
        output_dir: Optional[str] = None,
    ) -> Path:
        """Write an annotation-free LLM evaluation report to JSON."""
        configured_output = (
            result.get("evaluation_config", {}).get("reports", {}).get("output_dir")
        )
        results_dir = Path(output_dir or configured_output or _DEFAULT_RESULTS_DIR)
        results_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = results_dir / f"eval_{document_name}_{timestamp}.json"
        payload = dict(result)
        payload["timestamp_utc"] = datetime.now(tz=timezone.utc).isoformat()
        output_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        logger.info("LLM evaluation report written: %s", output_path)
        print(f"\n[SAVED] JSON report saved: {output_path}")
        return output_path

    # -----------------------------------------------------------------------
    # Private rendering helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _build_header(document_name: Optional[str]) -> str:
        """Build a formatted header block for the console output."""
        doc_label = document_name or "Unknown Document"
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return (
            "\n" + "=" * 80 + "\n"
            f"  PHI DETECTION EVALUATION REPORT\n"
            f"  Document : {doc_label}\n"
            f"  Timestamp: {timestamp}\n"
            f"  Standard : HIPAA Safe Harbor (45 CFR section 164.514(b))\n" + "=" * 80
        )

    @staticmethod
    def _build_per_type_rows(results: Dict[str, DetectorMetrics]) -> list[list]:
        """Build table rows for per-detector × per-entity-type breakdown.

        Args:
            results: Evaluation results dict.

        Returns:
            List of row lists for tabulate.
        """
        rows: list[list] = []

        for detector_name, metrics in results.items():
            # Shorten long detector names for display
            short_name = _shorten_detector_name(detector_name)

            if metrics.status == "error":
                rows.append(
                    [
                        short_name,
                        "ERROR",
                        "-",
                        "-",
                        "-",
                        "-",
                        "-",
                        "-",
                        "-",
                        metrics.error_message or "Detector failed",
                    ]
                )
                rows.append(
                    [
                        "-" * 30,
                        "-" * 20,
                        "-" * 9,
                        "-" * 6,
                        "-" * 6,
                        "-" * 6,
                        "-" * 6,
                        "-" * 12,
                        "-" * 11,
                        "-" * 20,
                    ]
                )
                continue

            # Overall row first
            span_overall = metrics.per_type.get("_ALL_span")
            rows.append(
                [
                    short_name,
                    "ALL (overall)",
                    f"{metrics.precision:.3f}",
                    f"{metrics.recall:.3f}",
                    f"{metrics.f1:.3f}",
                    f"{metrics.false_negative_rate:.3f}",
                    f"{metrics.overall.false_positive_rate:.3f}",
                    f"{metrics.recall:.3f}",
                    f"{span_overall.recall:.3f}" if span_overall else "-",
                    "ok",
                ]
            )

            # Per-type rows (only types in our display list)
            for entity_type in _DISPLAY_ENTITY_TYPES:
                tm = metrics.per_type.get(entity_type)
                sm = metrics.per_type.get(f"{entity_type}_span")

                if tm is None:
                    continue

                # Skip types where nothing was detected AND no gold
                if (
                    tm.true_positives == 0
                    and tm.false_negatives == 0
                    and tm.false_positives == 0
                ):
                    continue

                rows.append(
                    [
                        "",  # No detector name repeat — visual grouping
                        f"  {entity_type}",
                        f"{tm.precision:.3f}",
                        f"{tm.recall:.3f}",
                        f"{tm.f1:.3f}",
                        f"{tm.false_negative_rate:.3f}",
                        f"{tm.false_positive_rate:.3f}",
                        f"{tm.recall:.3f}",
                        f"{sm.recall:.3f}" if sm else "-",
                        "ok",
                    ]
                )

            rows.append(
                [
                    "-" * 30,
                    "-" * 20,
                    "-" * 9,
                    "-" * 6,
                    "-" * 6,
                    "-" * 6,
                    "-" * 6,
                    "-" * 12,
                    "-" * 11,
                    "-" * 6,
                ]
            )

        return rows

    @staticmethod
    def _build_summary_rows(results: Dict[str, DetectorMetrics]) -> list[list]:
        """Build summary table rows (one row per detector).

        Args:
            results: Evaluation results dict.

        Returns:
            List of row lists for tabulate.
        """
        rows: list[list] = []
        for detector_name, metrics in results.items():
            short_name = _shorten_detector_name(detector_name)
            if metrics.status == "error":
                rows.append(
                    [
                        short_name,
                        "-",
                        "-",
                        "-",
                        "-",
                        "-",
                        f"[ERROR] {metrics.error_message or 'Detector failed'}",
                    ]
                )
                continue

            coverage_score = getattr(metrics, "hipaa_coverage_score", None)
            coverage_pass = getattr(metrics, "hipaa_coverage_pass", None)

            rows.append(
                [
                    short_name,
                    f"{metrics.precision:.3f}",
                    f"{metrics.recall:.3f}",
                    f"{metrics.f1:.3f}",
                    f"{metrics.false_negative_rate:.3f}",
                    f"{coverage_score:.3f}" if coverage_score is not None else "-",
                    "[PASS]" if coverage_pass else "[FAIL]",
                ]
            )

        return rows

    @staticmethod
    def _print_coverage_analysis(results: Dict[str, DetectorMetrics]) -> None:
        """Print the LM Studio judge analysis for each detector's failures.

        Args:
            results: Evaluation results dict.
        """
        print("\n[ANALYSIS] HIPAA Coverage Analysis & LM Studio Judge Verdicts\n")
        print("-" * 80)

        for detector_name, metrics in results.items():
            short_name = _shorten_detector_name(detector_name)
            if metrics.status == "error":
                print(f"\n[ERROR] {short_name}")
                print(f"   Detector failed: {metrics.error_message or 'Unknown error'}")
                continue

            reason = getattr(metrics, "hipaa_coverage_reason", None)
            score = getattr(metrics, "hipaa_coverage_score", None)
            passed = getattr(metrics, "hipaa_coverage_pass", False)

            status_icon = "[PASS]" if passed else "[FAIL]"
            score_str = f"{score:.1%}" if score is not None else "N/A"

            print(f"\n{status_icon} {short_name}")
            print(f"   Critical Entity Recall: {score_str}")

            if reason:
                # Indent the reason for readability
                for line in reason.split("\n"):
                    print(f"   {line}")

        print("\n" + "-" * 80 + "\n")

    @staticmethod
    def _build_json_payload(
        results: Dict[str, DetectorMetrics],
        document_name: str,
    ) -> dict:
        """Serialize evaluation results to a JSON-serializable dict.

        Args:
            results: Evaluation results dict.
            document_name: Document identifier.

        Returns:
            JSON-serializable dict.
        """
        payload: dict = {
            "document": document_name,
            "timestamp_utc": datetime.now(tz=timezone.utc).isoformat(),
            "standard": "HIPAA Safe Harbor 45 CFR §164.514(b)",
            "detectors": {},
        }

        for detector_name, metrics in results.items():
            per_type_serialized = {}
            for etype, tm in metrics.per_type.items():
                per_type_serialized[etype] = {
                    "precision": round(tm.precision, 4),
                    "recall": round(tm.recall, 4),
                    "f1": round(tm.f1, 4),
                    "false_negative_rate": round(tm.false_negative_rate, 4),
                    "false_positive_rate": round(tm.false_positive_rate, 4),
                    "true_positives": tm.true_positives,
                    "false_positives": tm.false_positives,
                    "false_negatives": tm.false_negatives,
                }

            payload["detectors"][detector_name] = {
                "status": metrics.status,
                "error_message": metrics.error_message,
                "overall": {
                    "precision": round(metrics.precision, 4),
                    "recall": round(metrics.recall, 4),
                    "f1": round(metrics.f1, 4),
                    "false_negative_rate": round(metrics.false_negative_rate, 4),
                },
                "hipaa_coverage_score": getattr(metrics, "hipaa_coverage_score", None),
                "hipaa_coverage_pass": getattr(metrics, "hipaa_coverage_pass", None),
                "hipaa_coverage_reason": getattr(
                    metrics, "hipaa_coverage_reason", None
                ),
                "per_type": per_type_serialized,
                "missed_gold_indices": metrics.missed_gold_indices,
                "fp_predicted_indices": metrics.fp_predicted_indices,
            }

        return payload


# ---------------------------------------------------------------------------
# Module-level utility
# ---------------------------------------------------------------------------


def _shorten_detector_name(name: str) -> str:
    """Shorten long detector names for table display.

    Args:
        name: Full detector label.

    Returns:
        Shortened label (≤30 chars) for console display.
    """
    short_map = {
        "HFIdentifier (obi/deid_bert_i2b2)": "HF (obi/deid_bert_i2b2)",
        "PresidioIdentifier + spaCy (en_core_web_lg)": "Presidio + spaCy",
        "Clinical Heuristics (section_headers + ages + numeric_ids)": "Heuristics",
        "Full Pipeline (HF + Presidio + Heuristics, merged)": "Full Pipeline",
    }
    return short_map.get(name, name[:30])
