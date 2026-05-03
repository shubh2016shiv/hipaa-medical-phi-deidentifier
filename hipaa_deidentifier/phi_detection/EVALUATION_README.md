# PHI Identification Batch Evaluation

Step-by-step guide to running exhaustive PHI detection evaluation across all clinical note categories using the `uv` package manager.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Install Dependencies](#2-install-dependencies)
3. [Start LM Studio (Local LLM Judge)](#3-start-lm-studio-local-llm-judge)
4. [Run the Evaluation — All Scenarios](#4-run-the-evaluation--all-scenarios)
5. [Output Structure](#5-output-structure)
6. [Metrics Reference](#6-metrics-reference)
7. [Excel Workbook Layout](#7-excel-workbook-layout)
8. [Conditional Formatting Cheat-Sheet](#8-conditional-formatting-cheat-sheet)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | ≥ 3.10 | `python --version` |
| uv | latest | `pip install uv` or `winget install astral-sh.uv` |
| LM Studio | latest | Only needed without `--no-judge` |
| Disk space | ~4 GB | HF model cache + spaCy en_core_web_lg |

---

## 2. Install Dependencies

The `eval` dependency group (`openpyxl`, `httpx`, `deepeval`) is included in `default-groups` in `pyproject.toml`, so a plain `uv sync` is all that is needed.

```bash
# From the project root (where pyproject.toml lives)
uv sync
```

To verify the eval group is present:

```bash
uv sync --group eval --dry-run
# Should report: Nothing to install (already satisfied)
```

To install without the eval group (e.g., CI unit tests only):

```bash
uv sync --no-group eval
```

---

## 3. Start LM Studio (Local LLM Judge)

The evaluation uses a local LLM to identify expected PHI entities in each document. This is the "judge" that serves as pseudo ground truth.

1. Open **LM Studio** and load a model (default config expects `deepseek/deepseek-r1-0528-qwen3-8b` but any instruction model works).
2. Go to **Local Server** tab → click **Start Server**.
3. The server should be listening on `http://localhost:1234`.

> Skip this step if you plan to use `--no-judge` (count-only mode — no TP/FP/FN scoring).

---

## 4. Run the Evaluation — All Scenarios

All commands below are run from the **project root** using `uv run`.

### 4.1 Full evaluation — entire data/ tree (all categories, all notes)

```bash
uv run python hipaa_deidentifier/phi_detection/phi_identification_evaluation_cli.py \
    --input-folder data/
```

Evaluates every `.txt` file across all subdirectory categories. Runs all 5 detectors (hf, presidio, heuristics, pipeline, pipeline_filtered) with LM Studio judge.

---

### 4.2 Single note category

```bash
uv run python hipaa_deidentifier/phi_detection/phi_identification_evaluation_cli.py \
    --input-folder "data/Long-term and Supportive Care/"
```

Faster when you want to focus on one note type. Output is still written per category + overall summary.

---

### 4.3 Custom output folder

```bash
uv run python hipaa_deidentifier/phi_detection/phi_identification_evaluation_cli.py \
    --input-folder data/ \
    --output-folder results/eval_run_may_2026/
```

All Excel workbooks are written under the specified folder instead of the default `phi_eval_results/`.

---

### 4.4 Post-guardrail pipeline only (production-equivalent)

```bash
uv run python hipaa_deidentifier/phi_detection/phi_identification_evaluation_cli.py \
    --input-folder data/ \
    --detectors pipeline_filtered
```

Evaluates only `pipeline_filtered` — the detector that runs all three detectors (HF + Presidio + heuristics) then applies the `FalsePositiveGuardrail`. This is what production actually redacts.

---

### 4.5 Compare raw pipeline vs post-guardrail side-by-side

```bash
uv run python hipaa_deidentifier/phi_detection/phi_identification_evaluation_cli.py \
    --input-folder data/ \
    --detectors pipeline,pipeline_filtered
```

Both detectors appear in the same workbooks and summary sheets. Useful for measuring how much the FP guardrail changes recall and precision.

---

### 4.6 Individual detectors

```bash
# HuggingFace NER model only (obi/deid_bert_i2b2)
uv run python hipaa_deidentifier/phi_detection/phi_identification_evaluation_cli.py \
    --input-folder data/ \
    --detectors hf

# Presidio + spaCy only
uv run python hipaa_deidentifier/phi_detection/phi_identification_evaluation_cli.py \
    --input-folder data/ \
    --detectors presidio

# Rule-based heuristics only (section headers, ages over 89, long numeric IDs)
uv run python hipaa_deidentifier/phi_detection/phi_identification_evaluation_cli.py \
    --input-folder data/ \
    --detectors heuristics

# Comma-separate to combine any subset
uv run python hipaa_deidentifier/phi_detection/phi_identification_evaluation_cli.py \
    --input-folder data/ \
    --detectors hf,presidio
```

---

### 4.7 No LM Studio (count-only mode)

```bash
uv run python hipaa_deidentifier/phi_detection/phi_identification_evaluation_cli.py \
    --input-folder data/ \
    --no-judge
```

Detectors still run and entity counts are recorded, but TP/FP/FN/TN and all derived metrics (Precision, Recall, F1, FNR, FPR) are omitted — cells are blank. Use this when LM Studio is unavailable or for a quick sanity-check of raw detection volume.

---

### 4.8 Verbose / debug mode

```bash
uv run python hipaa_deidentifier/phi_detection/phi_identification_evaluation_cli.py \
    --input-folder data/ \
    --verbose
```

Sets log level to DEBUG. Prints per-entity matching decisions, LM Studio request/response timings, and full pipeline step logs.

---

### 4.9 Custom evaluation config (LM Studio model / thresholds)

```bash
uv run python hipaa_deidentifier/phi_detection/phi_identification_evaluation_cli.py \
    --input-folder data/ \
    --eval-config hipaa_deidentifier/phi_detection/evaluation/evaluation.yaml
```

Override LM Studio base URL, model name, timeout, coverage pass threshold, etc. without changing source code.

---

### 4.10 Focused single-category run with post-guardrail + custom output + debug

```bash
uv run python hipaa_deidentifier/phi_detection/phi_identification_evaluation_cli.py \
    --input-folder "data/Outpatient Documentation/" \
    --detectors pipeline_filtered \
    --output-folder results/outpatient_filtered/ \
    --verbose
```

---

## 5. Output Structure

After a full run on `data/`, the output folder looks like:

```
phi_eval_results/
├── Administrative_and_Transitional_Care/
│   └── evaluation.xlsx
├── Diagnostic_and_Ancillary_Services/
│   └── evaluation.xlsx
├── Inpatient_Documentation/
│   └── evaluation.xlsx
├── Long-term_and_Supportive_Care/
│   └── evaluation.xlsx
├── Outpatient_Documentation/
│   └── evaluation.xlsx
├── Specialized_Care/
│   └── evaluation.xlsx
├── Surgical_and_Procedural_Notes/
│   └── evaluation.xlsx
└── overall_summary.xlsx
```

One workbook per category, plus a master summary workbook.

---

## 6. Metrics Reference

### 6.1 Core confusion-matrix counts

Each row in the output represents one detector evaluated on one entity type within one clinical note. The counts are derived by greedy case-insensitive substring matching of detected entity text against the LLM's expected entity list (pseudo ground truth).

| Column | Full Name | What it counts |
|---|---|---|
| **TP** | True Positives | PHI entities the LLM expected AND the detector found |
| **FP** | False Positives | Entities the detector flagged that the LLM did NOT expect (over-detection) |
| **FN** | False Negatives | PHI entities the LLM expected that the detector MISSED |
| **TN** | True Negatives | Estimated non-PHI tokens correctly left alone |

**Example — NAME entities in one discharge summary:**

The LLM identifies 4 patient/provider names as expected PHI. The HF detector finds 3 of them and also flags the hospital name (not expected).

```
Expected (LLM): ["John Smith", "Dr. Emily Chen", "Margaret Sullivan", "James O'Brien"]
Detected (HF):  ["John Smith", "Dr. Emily Chen", "Margaret Sullivan", "Metro General Hospital"]

TP = 3  (three names matched)
FP = 1  (Metro General Hospital — not in expected list)
FN = 1  (James O'Brien — missed)
TN = ~  (estimated from document word count)
```

---

### 6.2 Derived metrics

| Column | Formula | Interpretation |
|---|---|---|
| **Precision** | TP / (TP + FP) | Of everything the detector flagged, what fraction was real PHI? High precision = low over-redaction. |
| **Recall** | TP / (TP + FN) | Of all real PHI, what fraction did the detector catch? **Primary HIPAA metric — missing PHI is a compliance risk.** |
| **F1** | 2 × Precision × Recall / (Precision + Recall) | Harmonic mean. Balanced score when both precision and recall matter. |
| **FNR** | FN / (TP + FN) | False Negative Rate. Proportion of real PHI that was missed. FNR = 1 − Recall. |
| **FPR** | FP / (FP + TN) | False Positive Rate. Proportion of non-PHI incorrectly flagged. High FPR degrades document utility. |

**Continuing the NAME example above:**

```
Precision = 3 / (3 + 1) = 0.75   (75% — one false alarm)
Recall    = 3 / (3 + 1) = 0.75   (75% — one real name missed)
F1        = 2 × 0.75 × 0.75 / (0.75 + 0.75) = 0.75
FNR       = 1 / (3 + 1) = 0.25   (25% of names missed — compliance risk!)
FPR       ≈ small (only 1 FP across thousands of non-PHI tokens)
```

> For HIPAA Safe Harbor compliance, **Recall ≥ 0.95** is the target for critical PHI types. A Recall of 0.75 on NAME would be a failing result.

---

### 6.3 HIPAA-specific columns

| Column | Values | Meaning |
|---|---|---|
| **HIPAA Critical** | TRUE / FALSE | Whether this entity type is one of the 7 high-risk HIPAA categories: NAME, MRN, DATE, AGE_OVER_89, LOCATION, ACCOUNT_NUMBER, US_SSN |
| **HIPAA Pass** | TRUE / FALSE / blank | TRUE if Recall ≥ 0.95 for a critical type (or if type is not critical). FALSE = compliance gap. Blank if no ground truth available (--no-judge). |

---

### 6.4 LLM judge columns

| Column | Values | Meaning |
|---|---|---|
| **LLM Coverage** | 0.0 – 1.0 | The LLM judge's own estimate of what fraction of expected PHI was covered across all detectors |
| **LLM Pass** | TRUE / FALSE | Whether the LLM judge rated overall coverage as passing (≥ 0.95 threshold) |
| **LLM Status** | ok / error | Whether the LM Studio call succeeded. `error` means the row's LLM columns are unreliable |

---

### 6.5 Entity types evaluated

The exact set of entity types in the output depends on what the LLM finds and what detectors report. Common types you will see:

| Entity Type | Description |
|---|---|
| NAME | Patient and provider names |
| MRN | Medical Record Numbers |
| DATE | Dates (admission, discharge, DOB, etc.) |
| AGE_OVER_89 | Age values above 89 (HIPAA Safe Harbor rule) |
| LOCATION | Addresses, cities, zip codes |
| ACCOUNT_NUMBER | Financial account identifiers |
| US_SSN | Social Security Numbers |
| PHONE_NUMBER | Phone/fax numbers |
| EMAIL_ADDRESS | Email addresses |
| URL | Web URLs |
| DEVICE_ID | Device serial numbers or implant IDs |
| ORGANIZATION | Hospital/clinic names |
| OVERALL | Aggregate across all entity types for this detector × note |

---

## 7. Excel Workbook Layout

### Per-category workbook (`evaluation.xlsx`)

Each workbook has one sheet per clinical note plus a summary:

```
Sheet tabs (left to right):
  CATEGORY_SUMMARY          ← first tab; aggregate OVERALL rows for this category
  home_health_assessment_patient_01
  home_health_assessment_patient_02
  home_health_assessment_patient_03
  ...
```

Within each note sheet, rows are sorted:

1. HIPAA critical entity types first (NAME, MRN, DATE, etc.)
2. Non-critical entity types alphabetically
3. OVERALL row last (aggregate across all types for that detector)
4. Repeated for each detector in the run

### Overall summary workbook (`overall_summary.xlsx`)

| Sheet | Contents |
|---|---|
| **All_Results** | Every single row from every note, every category, every detector |
| **Summary_by_Note** | OVERALL rows only — one row per note × detector — for quick cross-note comparison |
| **Aggregated_by_Cat** | TP/FP/FN/TN summed per category × entity_type — for category-level benchmarking |

---

## 8. Conditional Formatting Cheat-Sheet

The Excel workbooks use colour coding to make failures visible at a glance:

| Element | Colour | Condition |
|---|---|---|
| Header row | Blue fill, white bold text | Always |
| OVERALL rows | Light grey fill | Row has entity_type = OVERALL |
| HIPAA Pass = TRUE | Green fill | HIPAA critical type passed recall threshold |
| HIPAA Pass = FALSE | Red fill | HIPAA critical type failed — compliance gap |
| Recall (critical type) | Green | ≥ 0.95 |
| Recall (critical type) | Orange | 0.80 – 0.94 |
| Recall (critical type) | Red | < 0.80 |

Row 1 is frozen so the header stays visible while scrolling.

---

## 9. Troubleshooting

**`ModuleNotFoundError: openpyxl`**
```bash
uv sync --group eval
```

**`ConnectionRefusedError` or LLM status = error in output**

LM Studio server is not running. Either start it (step 3) or re-run with `--no-judge`:
```bash
uv run python hipaa_deidentifier/phi_detection/phi_identification_evaluation_cli.py \
    --input-folder data/ --no-judge
```

**`FileNotFoundError` for a document**

The path passed to `--input-folder` is relative to where you run the command. Always run from the project root.

**Models take too long to load**

The first run downloads and caches the HF model (`obi/deid_bert_i2b2`, ~400 MB) and loads `en_core_web_lg`. Subsequent runs use the cache. Use `--detectors heuristics` for a fast first test with no model loading.

**LLM returns unexpected JSON / schema errors**

Some models don't support `response_format` structured output. Set `use_response_format: false` in `evaluation.yaml` or add `--eval-config` pointing to a config with that flag disabled.

**Blank TP/FP/FN cells in the spreadsheet**

This is expected when `--no-judge` is used — only entity counts are available without the LLM's expected-PHI list as ground truth.
