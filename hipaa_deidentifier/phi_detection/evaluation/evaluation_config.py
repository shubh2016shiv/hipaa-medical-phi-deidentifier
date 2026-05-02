"""Evaluation-specific configuration loading.

This module keeps evaluation and judging settings separate from the main
de-identification pipeline configuration. Detector initialization can still use
the global project config; this config controls evaluation mode, LM Studio, and
reporting behavior.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Literal, Optional

import yaml

EvaluationMode = Literal["llm", "annotations", "auto"]


@dataclass
class LMStudioConfig:
    base_url: str = "http://localhost:1234/v1/chat/completions"
    model: str = "deepseek/deepseek-r1-0528-qwen3-8b"
    timeout_seconds: float = 60.0
    temperature: float = 0.1
    max_tokens: int = 4096


@dataclass
class LLMJudgeConfig:
    use_response_format: bool = True
    coverage_pass_threshold: float = 0.95
    max_expected_entities: int = 100


@dataclass
class ReportConfig:
    output_dir: Optional[str] = None
    include_raw_detector_entities: bool = True
    include_llm_raw_response: bool = False


@dataclass
class AnnotationConfig:
    annotation_dir: Optional[str] = None


@dataclass
class EvaluationConfig:
    eval_mode: EvaluationMode = "llm"
    lm_studio: LMStudioConfig = field(default_factory=LMStudioConfig)
    llm_judge: LLMJudgeConfig = field(default_factory=LLMJudgeConfig)
    reports: ReportConfig = field(default_factory=ReportConfig)
    annotations: AnnotationConfig = field(default_factory=AnnotationConfig)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EvaluationConfigurationError(ValueError):
    """Raised when evaluation configuration is invalid."""


def load_evaluation_config(config_path: str | Path | None = None) -> EvaluationConfig:
    """Load package-local evaluation config with optional YAML override."""
    default_path = Path(__file__).with_name("evaluation.yaml")
    data = _load_yaml(default_path)

    if config_path is not None:
        override_path = Path(config_path)
        if not override_path.exists():
            raise EvaluationConfigurationError(
                f"Evaluation config not found: {override_path}"
            )
        data = _merge_dicts(data, _load_yaml(override_path))

    return _build_config(data)


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise EvaluationConfigurationError(
            f"Failed to load evaluation config from {path}: {exc}"
        ) from exc


def _merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def _build_config(data: Dict[str, Any]) -> EvaluationConfig:
    mode = data.get("eval_mode", "llm")
    if mode not in {"llm", "annotations", "auto"}:
        raise EvaluationConfigurationError(
            "eval_mode must be one of: llm, annotations, auto"
        )

    lm_data = data.get("lm_studio", {}) or {}
    judge_data = data.get("llm_judge", {}) or {}
    report_data = data.get("reports", {}) or {}
    annotation_data = data.get("annotations", {}) or {}

    threshold = float(judge_data.get("coverage_pass_threshold", 0.95))
    if not 0 <= threshold <= 1:
        raise EvaluationConfigurationError(
            "llm_judge.coverage_pass_threshold must be between 0 and 1"
        )

    return EvaluationConfig(
        eval_mode=mode,
        lm_studio=LMStudioConfig(
            base_url=str(lm_data.get("base_url", LMStudioConfig.base_url)),
            model=str(lm_data.get("model", LMStudioConfig.model)),
            timeout_seconds=float(lm_data.get("timeout_seconds", 60.0)),
            temperature=float(lm_data.get("temperature", 0.1)),
            max_tokens=int(lm_data.get("max_tokens", 4096)),
        ),
        llm_judge=LLMJudgeConfig(
            use_response_format=bool(judge_data.get("use_response_format", True)),
            coverage_pass_threshold=threshold,
            max_expected_entities=int(judge_data.get("max_expected_entities", 100)),
        ),
        reports=ReportConfig(
            output_dir=report_data.get("output_dir"),
            include_raw_detector_entities=bool(
                report_data.get("include_raw_detector_entities", True)
            ),
            include_llm_raw_response=bool(
                report_data.get("include_llm_raw_response", False)
            ),
        ),
        annotations=AnnotationConfig(
            annotation_dir=annotation_data.get("annotation_dir"),
        ),
    )
