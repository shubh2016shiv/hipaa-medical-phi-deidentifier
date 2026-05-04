# Post-Detection False Positive Guardrail

**Module:** `hipaa_deidentifier/phi_detection/post_detection_fp_guardrail/`  
**Status:** Implemented  
**Last Updated:** 2026-05-03  
**Author:** HIPAA De-identification System

---

## 1. The Need

### 1.1 Root Cause

The detection pipeline combines two fundamentally different detectors whose
confidence scores are not comparable:

| Detector | Score behaviour | Meaning |
|---|---|---|
| HF (`obi/deid_bert_i2b2`) | Real model probability (0.70–0.999) | Statistically calibrated |
| Presidio custom recognizers (SSN, MRN, Date…) | Hardcoded 0.95 | Pattern matched with structural check |
| Presidio spaCy NER (NAME, LOCATION, ORG, DATE) | **Flat 0.85 always** | spaCy does not produce per-entity probabilities; Presidio assigns a fixed default |

The flat 0.85 from Presidio spaCy NER is the root problem. It makes
threshold-based filtering useless for spaCy-sourced entities — raising the
threshold would also discard real PHI that legitimately scores 0.85.

### 1.2 Observed False Positives (confirmed in eval results)

The following entities were detected by Presidio spaCy and entered the
redactor despite being clinically meaningless:

| Text | Category assigned | Why it is a FP |
|---|---|---|
| `"accessible"` | ACCOUNT_NUMBER | Common adjective; no account-number structure |
| `"daily"` | DATE | Frequency adverb, not a date |
| `"weekly"` | DATE | Frequency adverb, not a date |
| `"3x/week"` | DATE | Dosing frequency, not a calendar date |
| `"7-8 hours/night"` | DATE | Sleep duration, not a date |
| `"Falls\nGoal"` | NAME | Section header fragment |
| `"verbalized understanding"` | NAME | Clinical phrase, not a person's name |
| `"devices\n- Monitor"` | DEVICE_ID | Free text containing the word "device" |

### 1.3 Observed False Negatives (confirmed in eval results)

| Text | Category missed | Root cause |
|---|---|---|
| `FIN-556677889` | MRN | `FIN-` prefix not covered in `MRNRecognizer` patterns |

False negatives are primarily a detection-coverage problem. This module does
not fix them (that belongs in the recognizers), but it does ensure that the
guardrail never introduces *additional* false negatives.

---

## 2. The Plan

Apply a **post-detection, pre-redaction filter** that validates each entity
before it reaches the redactor. The redactor itself stays dumb and complete —
it redacts everything it receives. All judgement about *what deserves to be
redacted* lives in this module.

### 2.1 Strategy per source

```
entity.source == "hf"
    └── HFConfidenceFilter
          confidence >= configurable threshold (default 0.9) → KEEP
          confidence <  threshold                            → DROP

entity.source == "presidio"  AND  entity.confidence == 0.95
    └── came from a custom pattern recognizer (structural match already done)
          → KEEP unconditionally

entity.source == "presidio"  AND  entity.confidence == 0.85  (spaCy NER)
    └── PresidioStructuralValidator
          category has structural patterns (ACCOUNT_NUMBER, DATE, DEVICE_ID,
          LOCATION, US_SSN, MRN, PHONE_NUMBER, FAX_NUMBER, …)
              → run category regex against entity text → KEEP if matches
          category is NAME or ORGANIZATION (no structural fingerprint)
              → NameOrganizationContextFilter
                    deny-list check (clinical terms + section headers) → KEEP / DROP

entity.source == "presidio_clinical"
    └── NameOrganizationContextFilter (same deny-list logic)

entity.source == "unknown"  (heuristics, age detector, etc.)
    └── KEEP unconditionally — these are purpose-built pattern detectors
```

### 2.2 What is NOT changed

- The detection pipeline (`_detect_phi_entities`) is unchanged.
- The redactor (`PHIRedactor`) is unchanged.
- The orchestrator adds a single call between detection and redaction.
- No new third-party packages are introduced.

---

## 3. Architecture

```
pipeline_orchestrator.py
        │
        │  _detect_phi_entities() → List[PHIEntity]
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│              FalsePositiveGuardrail.filter()              │
│                                                           │
│  ┌─────────────────────┐                                  │
│  │  HFConfidenceFilter │  source="hf"                    │
│  │  (confidence gate)  │  threshold configurable          │
│  └─────────────────────┘                                  │
│                                                           │
│  ┌──────────────────────────────┐                         │
│  │  PresidioStructuralValidator │  source="presidio"      │
│  │  (category regex check)      │  flat-0.85 entities     │
│  └──────────────────────────────┘                         │
│                                                           │
│  ┌──────────────────────────────────┐                     │
│  │  NameOrganizationContextFilter   │  NAME / ORG         │
│  │  (deny-list: clinical + headers) │  from any source    │
│  └──────────────────────────────────┘                     │
│                                                           │
└───────────────────────────────────────────────────────────┘
        │
        │  Validated List[PHIEntity]
        ▼
  PHIRedactor.redact_text()
```

### 3.1 Module layout

```
post_detection_fp_guardrail/
├── __init__.py                    public API: FalsePositiveGuardrail
├── GUARDRAIL_DESIGN.md            this file
├── fp_guardrail.py                FalsePositiveGuardrail (orchestrator)
├── hf_confidence_filter.py        HFConfidenceFilter
├── structural_validator.py        PresidioStructuralValidator
└── name_context_filter.py         NameOrganizationContextFilter
```

Each file has a single responsibility and stays under the 500-line / 300-line
class limit enforced by Agents.md.

### 3.2 Integration point in orchestrator

```python
# pipeline_orchestrator.py  — deidentify()

entities = self._detect_phi_entities(text)           # existing
entities = self.fp_guardrail.filter(entities, text)  # NEW — one line
deidentified_text = self.redactor.redact_text(...)   # existing
```

`HIPAAPipelineOrchestrator.__init__` constructs `FalsePositiveGuardrail` with
the pipeline configuration so thresholds remain configurable without touching
this module.

---

## 4. Design Decisions and Trade-offs

### 4.1 Why post-detection rather than pre-redaction

Moving validation *before* the redactor (rather than inside it) keeps the
redactor's concern pure — transformation only. The current redactor already
contains ad-hoc `_is_common_header` and `_is_clinical_term` guards mixed with
transformation logic; this module replaces that pattern with a dedicated,
testable stage.

### 4.2 Why structural validators reuse recognizer patterns directly

The recognizer classes (`MRNRecognizer`, `DateRecognizer`, etc.) already
encode the structural fingerprints for each HIPAA identifier category. Rather
than duplicating those regexes, `PresidioStructuralValidator` imports the
pattern strings from the recognizers' configuration constants
(`recognizer_config.py`, `date_recognizer.py` pattern lists, etc.) and
applies them with `re.search`. This follows DRY and ensures the validation
stays in sync when recognizer patterns are updated.

### 4.3 Why NAME / ORGANIZATION use a deny-list instead of structural patterns

Personal names and organisation names have no reliable structural fingerprint
in free text. A structural regex would miss real names just as often as it
would catch false positives. The deny-list approach (clinical terms +
section headers already in `RedactionConfig`) is the most precise tool
available without adding a separate NLP call.

### 4.4 Why HF threshold is 0.9 (default)

Observed from eval: all HF detections at ≥ 0.92 were confirmed true
positives. The lowest HF score for a genuine entity in the eval was the MRN
`55667` at 0.929. Setting the threshold at 0.9 captures all confirmed true
positives while leaving headroom for future evaluation to tighten or loosen.
The threshold is a constructor parameter — not a hardcoded constant — so it
can be tuned per deployment without code changes.

### 4.5 Why "unknown" source entities pass through unconditionally

Entities with `source="unknown"` originate from purpose-built heuristic
detectors (`detect_ages_over_89`, `detect_long_numeric_ids`,
`detect_section_headers`) that already contain their own structural logic.
Applying a second structural check would risk discarding valid heuristic
detections and provides no benefit since these detectors are not subject to
spaCy's flat-0.85 problem.

---

## 5. Configurable Parameters

| Parameter | Default | Where set |
|---|---|---|
| `hf_confidence_threshold` | `0.9` | `PipelineConfiguration` or constructor |
| `presidio_custom_recognizer_min_confidence` | `0.9` | `FalsePositiveGuardrail` constant |

Both thresholds can be overridden per-deployment through the existing
`detection_thresholds` section in the YAML configuration file.

---

## 6. Future Extensions

- **Calibrated Presidio scores**: If Presidio ever exposes calibrated spaCy
  NER probabilities (e.g. via `NlpArtifacts`), the flat-0.85 branch of
  `PresidioStructuralValidator` can be replaced with a simple threshold check
  identical to the HF path.

- **Cross-detector agreement boost**: If HF and Presidio both detect the same
  span, confidence could be boosted rather than evaluated independently. This
  would require a pre-filter aggregation step before this module runs.

- **Per-document threshold tuning**: For radiology reports vs. nursing notes,
  different thresholds may be appropriate. `FalsePositiveGuardrail` accepts
  the threshold as a constructor argument, making per-document-type
  instantiation straightforward.
