"""
Post-Detection False Positive Guardrail
========================================

Validates detected PHI entities after detection and before redaction.
Sits between the detection pipeline and the PHIRedactor.

Architecture:
-------------
    ┌────────────────────────────┐
    │  HIPAAPipelineOrchestrator │
    │  (pipeline_orchestrator.py)│
    └────────────┬───────────────┘
                 │ List[PHIEntity]  (raw detections)
                 ▼
    ┌────────────────────────────┐
    │   FalsePositiveGuardrail   │  ← this package
    │   (fp_guardrail.py)        │
    └────────┬───────────────────┘
             │
     ┌───────┼───────────────────┐
     ▼       ▼                   ▼
 HFConf  Presidio             Name/Org
 Filter  Structural           Context
         Validator            Filter
             │
             ▼
    ┌────────────────────────────┐
    │        PHIRedactor         │
    │  (phi_redaction/)          │
    └────────────────────────────┘

Public API:
    FalsePositiveGuardrail  — the single entry point; inject into orchestrator.

Author: HIPAA De-identification System
Last Updated: 2026-05-03
"""

from .fp_guardrail import FalsePositiveGuardrail

__all__ = ["FalsePositiveGuardrail"]
