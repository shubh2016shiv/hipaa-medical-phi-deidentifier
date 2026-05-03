"""
PHI Detection Evaluation — CLI Entry Point
==========================================

Run as:
    python -m hipaa_deidentifier.phi_detection.evaluation \\
        --document "data/Long-term and Supportive Care/home_health_assessment_patient_01.txt" \\
        --detectors all \\
        --judge lm_studio

    python -m hipaa_deidentifier.phi_detection.evaluation \\
        --document "data/Outpatient Documentation/consultation_note_patient_01.txt" \\
        --no-judge

Author: HIPAA De-identification System
Last Updated: 2026-05-02
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def _configure_logging(verbose: bool) -> None:
    """Configure structured logging for the evaluation run.

    Args:
        verbose: If True, set DEBUG level; otherwise INFO.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    # Suppress noisy third-party loggers
    for noisy_logger in ("transformers", "presidio_analyzer", "httpx", "deepeval"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed Namespace object.
    """
    parser = argparse.ArgumentParser(
        prog="python -m hipaa_deidentifier.phi_detection.evaluation",
        description=(
            "Evaluate PHI detection quality against HIPAA Safe Harbor.\n"
            "By default, runs annotation-free LLM evaluation using LM Studio.\n"
            "Annotation-based deterministic scoring remains available with\n"
            "--eval-mode annotations."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  Evaluate all detectors with LM Studio judge:\n"
            '    python -m ... --document "data/Specialized Care/obstetric_history_patient_01.txt"\n\n'
            "  Evaluate against annotation ground truth:\n"
            '    python -m ... --document "data/.../note.txt" --eval-mode annotations\n\n'
            "  Save JSON report:\n"
            '    python -m ... --document "data/.../note.txt" --output-json evaluation/results/'
        ),
    )

    parser.add_argument(
        "--document",
        required=True,
        help=(
            "Path to the clinical note to evaluate. Annotation JSON is only "
            "required in --eval-mode annotations."
        ),
    )

    parser.add_argument(
        "--detectors",
        default="all",
        help=(
            "Comma-separated detector names to run. "
            "Valid values: hf, presidio, heuristics, pipeline, pipeline_filtered, all. "
            "pipeline_filtered applies the FP guardrail after detection, matching "
            "what production actually redacts. "
            "Default: all"
        ),
    )

    parser.add_argument(
        "--no-judge",
        action="store_true",
        default=False,
        help=(
            "Disable the LM Studio judge. In LLM mode, this records an LLM "
            "evaluation error while still reporting detector output."
        ),
    )

    parser.add_argument(
        "--eval-mode",
        choices=["llm", "annotations", "auto"],
        default=None,
        help=(
            "Evaluation mode. Default comes from evaluation.yaml (llm). "
            "llm does not require annotations; annotations requires ground truth; "
            "auto uses annotations if present and otherwise falls back to llm."
        ),
    )

    parser.add_argument(
        "--eval-config",
        default=None,
        metavar="PATH",
        help="Optional YAML config for evaluation-specific settings.",
    )

    parser.add_argument(
        "--output-json",
        default=None,
        metavar="DIR",
        help=(
            "Directory to write the JSON evaluation report. "
            "Default: evaluation/results/"
        ),
    )

    parser.add_argument(
        "--annotation-dir",
        default=None,
        metavar="DIR",
        help=(
            "Override the annotation JSON directory. "
            "Default: evaluation/ground_truth/annotations/"
        ),
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Enable DEBUG-level logging.",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point for the evaluation CLI.

    Args:
        argv: Optional argument list (for testing). Defaults to sys.argv[1:].

    Returns:
        Exit code: 0 on success, 1 on failure.

    Example:
        >>> import sys
        >>> sys.exit(main())
    """
    args = _parse_args(argv)
    _configure_logging(args.verbose)

    logger = logging.getLogger("evaluation.cli")

    document_path = Path(args.document)
    use_judge = not args.no_judge

    # Validate document path
    if not document_path.exists():
        logger.error("Document not found: %s", document_path)
        print(
            f"\n[ERROR] Document not found: {document_path}\n"
            f"   Provide a valid path to a file in data/",
            file=sys.stderr,
        )
        return 1

    print("\n[EVAL] Starting PHI Detection Evaluation")
    print(f"   Document : {document_path.name}")
    print(f"   Detectors: {args.detectors}")

    try:
        from .evaluation_config import load_evaluation_config
        from .reports.report_generator import ReportGenerator
        from .runners.llm_evaluator import LLMEvaluator

        from .evaluation_config import EvaluationMode
        from typing import cast

        eval_config = load_evaluation_config(args.eval_config)
        if args.eval_mode:
            eval_config.eval_mode = cast(EvaluationMode, args.eval_mode)
        if args.annotation_dir:
            eval_config.annotations.annotation_dir = args.annotation_dir

        judge_label = (
            f"LM Studio ({eval_config.lm_studio.model})"
            if use_judge
            else "disabled (--no-judge)"
        )
        print(f"   Judge    : {judge_label}")

        mode = eval_config.eval_mode
        if mode == "auto":
            mode = "llm"

        print(f"   Mode     : {mode}")

        generator = ReportGenerator()

        if mode == "llm":
            llm_ev = LLMEvaluator(
                document_path=str(document_path),
                detectors=args.detectors,
                config=eval_config,
                use_judge=use_judge,
            )
            llm_result = llm_ev.run()
            generator.render_llm_console(llm_result)
            generator.write_llm_json(
                llm_result,
                document_name=document_path.stem,
                output_dir=args.output_json,
            )
            return 0

        results = {}
        from .runners.detector_evaluator import DetectorEvaluator
        from .runners.pipeline_evaluator import PipelineEvaluator

        # --- Run isolated detector evaluation ---
        detector_ev = DetectorEvaluator(
            document_path=str(document_path),
            detectors=args.detectors,
            use_judge=use_judge,
        )
        results.update(detector_ev.run())

        # --- Run full pipeline if requested ---
        detectors_lower = args.detectors.strip().lower()
        if "pipeline" in detectors_lower or detectors_lower == "all":
            pipeline_ev = PipelineEvaluator(
                document_path=str(document_path),
                use_judge=use_judge,
                use_guardrail=False,
            )
            pipeline_metrics = pipeline_ev.run()
            results["Full Pipeline (HF + Presidio + Heuristics, merged)"] = (
                pipeline_metrics
            )

        # --- Run post-guardrail pipeline if requested ---
        if "pipeline_filtered" in detectors_lower or detectors_lower == "all":
            filtered_ev = PipelineEvaluator(
                document_path=str(document_path),
                use_judge=use_judge,
                use_guardrail=True,
            )
            filtered_metrics = filtered_ev.run()
            results["Full Pipeline + FP Guardrail (post-filter)"] = filtered_metrics

        # --- Render report ---
        generator.render_console(results, document_name=document_path.stem)

        # --- Write JSON (always, to results dir) ---
        generator.write_json(
            results,
            document_name=document_path.stem,
            output_dir=args.output_json,
        )

        return 0

    except FileNotFoundError as exc:
        logger.error("File not found: %s", exc)
        print(
            f"\n[ERROR] File not found: {exc}\n"
            f"   Make sure an annotation JSON exists for this document in:\n"
            f"   evaluation/ground_truth/annotations/{document_path.stem}.json",
            file=sys.stderr,
        )
        return 1

    except KeyboardInterrupt:
        print("\n[WARN] Evaluation interrupted by user.", file=sys.stderr)
        return 130

    except Exception as exc:
        logger.exception("Unexpected error during evaluation: %s", exc)
        print(f"\n[ERROR] Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
