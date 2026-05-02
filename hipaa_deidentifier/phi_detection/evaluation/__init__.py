"""
PHI Detection Evaluation Module
================================

Evaluates the detection quality of each PHI identifier in isolation and
as a combined pipeline. Produces per-detector, per-entity-type metrics
(Precision, Recall, F1, FNR, FPR) and uses a local LM Studio reasoning
model as a qualitative judge for missed or misclassified entities.

Architecture:
-------------
    ┌──────────────────────────┐
    │  CLI Entry Point         │  ← python -m evaluation --document <path>
    │  (__main__.py)           │
    └───────────┬──────────────┘
                │
    ┌───────────▼──────────────┐
    │  Runners                 │  ← detector_evaluator, pipeline_evaluator
    │  (runners/)              │
    └──────┬──────────┬────────┘
           │          │
    ┌──────▼───┐  ┌───▼──────────┐
    │ Metrics  │  │ LM Studio    │
    │(metrics/)│  │ Judge        │
    └──────────┘  │ (judges/)    │
                  └──────────────┘
    Ground truth annotations: ground_truth/annotations/*.json
    Reports:                  reports/report_generator.py

Dependencies:
    - hipaa_deidentifier/phi_detection/identifier/  — detectors under test
    - hipaa_deidentifier/pipeline_orchestrator.py   — full pipeline
    - deepeval                                       — metric framework
    - httpx                                          — LM Studio HTTP client
    - tabulate                                       — console table rendering

Author: HIPAA De-identification System
Last Updated: 2026-05-02
"""

from __future__ import annotations

from .evaluation_config import EvaluationMode

__all__ = [
    "run_evaluation",
]


def run_evaluation(
    document_path: str,
    detectors: str = "all",
    use_judge: bool = True,
    eval_mode: EvaluationMode | None = None,
    eval_config_path: str | None = None,
) -> dict:
    """Run the full PHI detection evaluation on a single document.

    This is the public API used by __main__.py. It loads the document,
    finds the matching ground truth annotation, runs every requested
    detector, computes metrics, optionally calls the LM Studio judge,
    and returns a structured result dict.

    Args:
        document_path: Absolute or relative path to the clinical note file.
        detectors: Comma-separated detector names or "all".
                   Valid values: hf, presidio, heuristics, pipeline, all.
        use_judge: If True, call the LM Studio judge on failures.
        eval_mode: Evaluation mode override: llm, annotations, or auto.
        eval_config_path: Optional path to evaluation-specific YAML config.

    Returns:
        Dict containing per-detector DetectorMetrics and the judge report.

    Example:
        >>> results = run_evaluation(
        ...     "data/Long-term and Supportive Care/home_health_assessment_patient_01.txt"
        ... )
        >>> print(results["pipeline"]["recall"])
    """
    from .evaluation_config import load_evaluation_config
    from .runners.llm_evaluator import LLMEvaluator
    from .reports.report_generator import ReportGenerator

    config = load_evaluation_config(eval_config_path)
    if eval_mode is not None:
        config.eval_mode = eval_mode

    mode = config.eval_mode
    if mode == "auto":
        mode = "llm"

    if mode == "llm":
        result = LLMEvaluator(
            document_path=document_path,
            detectors=detectors,
            config=config,
            use_judge=use_judge,
        ).run()
        ReportGenerator().render_llm_console(result)
        return result

    from .runners.detector_evaluator import DetectorEvaluator
    from .runners.pipeline_evaluator import PipelineEvaluator

    evaluator = DetectorEvaluator(
        document_path=document_path,
        detectors=detectors,
        use_judge=use_judge,
    )
    results = evaluator.run()

    if "pipeline" in detectors or detectors == "all":
        pipeline_ev = PipelineEvaluator(
            document_path=document_path,
            use_judge=use_judge,
        )
        results["pipeline"] = pipeline_ev.run()

    ReportGenerator().render_console(results)
    return results
