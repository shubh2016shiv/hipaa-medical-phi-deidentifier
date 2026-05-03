# PHI Detection System — Architecture and Design

This document explains how the PHI (Protected Health Information) detection system works,
why each architectural decision was made, and how the evaluation framework measures accuracy.
It is written for a general technical audience — no prior knowledge of HIPAA compliance
tooling or clinical NLP is assumed.

---

## What This System Does

When a patient is treated at a hospital, their clinical notes contain sensitive personal
information such as their name, date of birth, medical record number, home address, and
telephone number. Before these notes can be shared for research, quality improvement, or
inter-institutional transfer, every piece of identifying information must be found and
removed. This process is called de-identification, and it is required by US federal law
under the HIPAA Privacy Rule (45 CFR §164.514).

This system performs the detection half of that process. It reads a clinical note as plain
text and produces a list of character-level spans — each span carries a start position, an
end position, a category label, and a confidence score. A separate redaction layer then
replaces those spans with safe surrogates. This document focuses entirely on how the
detection spans are produced.

---

## The 18 HIPAA Safe Harbor Identifiers

HIPAA defines exactly 18 categories of information that must be removed before a document
is considered de-identified. This system detects all 18. The table below lists each
category and the primary detection mechanism used for it.

```
┌─────┬──────────────────────────┬──────────────────────────────────────────────────┐
│  #  │  HIPAA Category          │  Primary Detection Mechanism                     │
├─────┼──────────────────────────┼──────────────────────────────────────────────────┤
│  1  │  NAME                    │  HF transformer NER (PATIENT, STAFF labels)      │
│     │  (patients and providers)│  + spaCy PERSON entity via Presidio              │
│     │                          │  + labeled-field regex ("Patient Name:")         │
│     │                          │  + initials and nickname heuristics              │
├─────┼──────────────────────────┼──────────────────────────────────────────────────┤
│  2  │  DATE                    │  HF transformer NER (DATE label)                 │
│     │  (all dates with month   │  + custom DateRecognizer (13 format patterns)    │
│     │   or day)                │  + spaCy DATE_TIME entity via Presidio           │
├─────┼──────────────────────────┼──────────────────────────────────────────────────┤
│  3  │  PHONE_NUMBER            │  Presidio built-in phone recognizer              │
│     │                          │  + custom labeled and standalone format patterns │
├─────┼──────────────────────────┼──────────────────────────────────────────────────┤
│  4  │  FAX_NUMBER              │  Custom FaxRecognizer (context-required: only    │
│     │                          │  fires when "fax" or "facsimile" appears nearby) │
├─────┼──────────────────────────┼──────────────────────────────────────────────────┤
│  5  │  EMAIL_ADDRESS           │  HF transformer NER (EMAIL label)               │
│     │                          │  + Presidio built-in email recognizer            │
├─────┼──────────────────────────┼──────────────────────────────────────────────────┤
│  6  │  US_SSN                  │  Custom SSNRecognizer with full SSA format       │
│     │  (Social Security Number)│  validation (NNN-NN-NNNN, rejects invalid       │
│     │                          │  area codes 000/666/900-999)                     │
├─────┼──────────────────────────┼──────────────────────────────────────────────────┤
│  7  │  MRN                     │  Custom MRNRecognizer on labeled fields          │
│     │  (Medical Record Number) │  ("MRN:", "Chart #:", "Patient ID:", etc.)       │
│     │                          │  + HF transformer NER (ID label)                │
├─────┼──────────────────────────┼──────────────────────────────────────────────────┤
│  8  │  ACCOUNT_NUMBER          │  Custom AccountNumberRecognizer on labeled       │
│     │  (financial account IDs) │  fields (FIN:, Account Number:, ACC-prefix)      │
├─────┼──────────────────────────┼──────────────────────────────────────────────────┤
│  9  │  HEALTH_PLAN_ID          │  Custom HealthPlanIDRecognizer on labeled        │
│     │  (insurance/member IDs)  │  fields + Medicare MBI format (CMS spec)        │
├─────┼──────────────────────────┼──────────────────────────────────────────────────┤
│ 10  │  LOCATION                │  HF transformer NER (LOC label)                 │
│     │  (addresses, facilities) │  + spaCy GPE/LOC entities via Presidio          │
│     │                          │  + USLocationRecognizer (address formats,        │
│     │                          │    state+ZIP, labeled "Location:" fields)        │
│     │                          │  + FacilityLocationRecognizer (spaCy ORG        │
│     │                          │    entities promoted to LOCATION for healthcare  │
│     │                          │    facilities — see design note below)           │
├─────┼──────────────────────────┼──────────────────────────────────────────────────┤
│ 11  │  URL                     │  Presidio built-in URL recognizer                │
├─────┼──────────────────────────┼──────────────────────────────────────────────────┤
│ 12  │  IP_ADDRESS              │  Presidio built-in IP address recognizer         │
├─────┼──────────────────────────┼──────────────────────────────────────────────────┤
│ 13  │  DEVICE_ID               │  Custom DeviceIDRecognizer on labeled fields     │
│     │  (device/implant serials)│  and known prefixes (PM-, SN-)                  │
├─────┼──────────────────────────┼──────────────────────────────────────────────────┤
│ 14  │  VEHICLE_ID              │  Custom VehicleIDRecognizer (17-char VIN format  │
│     │  (VIN, license plates)   │  per ISO 3779 + labeled license plate patterns) │
├─────┼──────────────────────────┼──────────────────────────────────────────────────┤
│ 15  │  LICENSE_NUMBER          │  Presidio built-in US driver license and         │
│     │  (professional licenses) │  passport recognizers                           │
├─────┼──────────────────────────┼──────────────────────────────────────────────────┤
│ 16  │  PHOTO_ID                │  Custom PhotoIDRecognizer on image file          │
│     │  (face photos, images)   │  extension patterns and labeled references       │
├─────┼──────────────────────────┼──────────────────────────────────────────────────┤
│ 17  │  BIOMETRIC_ID            │  Custom BiometricIDRecognizer on labeled         │
│     │  (fingerprints, scans)   │  fields ("Fingerprint ID:", "Retina Scan:")      │
├─────┼──────────────────────────┼──────────────────────────────────────────────────┤
│ 18  │  AGE_OVER_89             │  Custom AgeOver89Recognizer with threshold       │
│     │  (ages must be           │  gate (detects age vocabulary + numeric value    │
│     │   generalized to "90+")  │  ≥ 90) + HF transformer AGE label               │
└─────┴──────────────────────────┴──────────────────────────────────────────────────┘
```

---

## High-Level System Architecture

The detection system is a multi-layer pipeline. Each layer is independently runnable and
contributes detections that are merged before redaction.

```
                         ┌──────────────────────────────────┐
                         │         Input Clinical Note       │
                         │   (plain text, any EHR format)   │
                         └─────────────────┬────────────────┘
                                           │
                          ┌────────────────▼────────────────┐
                          │       Stage 0: Normalizer        │
                          │                                  │
                          │  Converts Unicode lookalikes,    │
                          │  non-breaking spaces, and smart  │
                          │  quotes to ASCII equivalents.    │
                          │  Maintains a character-position  │
                          │  mapping so that span offsets    │
                          │  always refer to the original    │
                          │  text, not the normalized copy.  │
                          └────────────────┬────────────────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
        ┌───────────▼──────────┐  ┌────────▼────────┐  ┌─────────▼─────────┐
        │   HF Transformer     │  │    Presidio      │  │   Clinical        │
        │   Identifier         │  │    Identifier    │  │   Heuristics      │
        │                      │  │                  │  │                   │
        │ obi/deid_bert_i2b2   │  │  AnalyzerEngine  │  │ Section headers   │
        │ (fine-tuned on i2b2  │  │  with spaCy      │  │ Initials and      │
        │  clinical NER data)  │  │  en_core_web_lg  │  │  nicknames        │
        │                      │  │  as NLP backend  │  │ Relatives and     │
        │ Detects: NAME, DATE, │  │                  │  │  contacts         │
        │ LOCATION, PHONE,     │  │  Detects: NAME,  │  │ Ages over 89      │
        │ EMAIL, AGE, MRN,     │  │  DATE, LOCATION, │  │ Long numeric IDs  │
        │ ORGANIZATION         │  │  SSN, PHONE,     │  │                   │
        │                      │  │  EMAIL, MRN,     │  │ These patterns    │
        │ Processes text in    │  │  ACCOUNT_NUMBER, │  │ target structures │
        │ sliding windows      │  │  and all 18      │  │ that model-based  │
        │ (512 token chunks    │  │  HIPAA types via │  │ NER reliably      │
        │  with overlap) to    │  │  custom          │  │ misses: document  │
        │ handle notes longer  │  │  recognizers     │  │ headers, kinship  │
        │ than BERT's context  │  │  registered in   │  │ references, and   │
        │ window               │  │  the registry    │  │ clinical shorthands│
        └──────────┬───────────┘  └────────┬────────┘  └─────────┬─────────┘
                   │                       │                      │
                   └───────────────────────┴──────────────────────┘
                                           │
                                           │  Raw merged entity list
                                           │  (duplicates and overlaps
                                           │   are resolved by keeping
                                           │   the highest-confidence
                                           │   span when two detections
                                           │   cover the same characters)
                                           │
                          ┌────────────────▼────────────────┐
                          │   False Positive Guardrail       │
                          │                                  │
                          │  Three ordered filter passes     │
                          │  applied to the merged list:     │
                          │                                  │
                          │  1. HF Confidence Filter         │
                          │     Drops HF entities whose      │
                          │     model probability falls      │
                          │     below the configured         │
                          │     threshold for that entity    │
                          │     type.                        │
                          │                                  │
                          │  2. Presidio Structural          │
                          │     Validator                    │
                          │     Drops flat-score (0.85)      │
                          │     spaCy entities that do not   │
                          │     match a format regex for     │
                          │     their claimed category.      │
                          │     Example: a spaCy LOCATION    │
                          │     entity that contains no      │
                          │     digits, street keyword, or   │
                          │     state abbreviation is        │
                          │     rejected.                    │
                          │                                  │
                          │  3. Name and Organization        │
                          │     Context Filter               │
                          │     Drops NAME and ORGANIZATION  │
                          │     entities whose text matches  │
                          │     a deny-list of clinical      │
                          │     phrases that NER models      │
                          │     commonly mislabel (e.g.      │
                          │     medication names, diagnosis  │
                          │     terms, section headings).    │
                          └────────────────┬────────────────┘
                                           │
                                           │  Clean entity list
                                           │
                          ┌────────────────▼────────────────┐
                          │         PHI Redactor             │
                          │                                  │
                          │  Replaces each detected span     │
                          │  with a category-appropriate     │
                          │  surrogate such as [NAME],       │
                          │  [DATE], or [LOCATION].          │
                          └──────────────────────────────────┘
```

---

## The Three Detection Layers Explained

### Layer 1 — HuggingFace Transformer Identifier

The transformer model used here is `obi/deid_bert_i2b2`, a BERT-based model fine-tuned
on the i2b2 2014 clinical NLP de-identification dataset. This model was trained directly
on real US hospital discharge summaries and physician notes, which makes it highly
effective at recognizing entities in the natural, informal language that clinicians use.

The model assigns a label to each token in the input text. The labels it produces
correspond to eight entity categories: patient names, staff names, hospital names,
locations, dates, ages, phone numbers, and medical record identifiers. These labels are
mapped onto the system's internal HIPAA category names during post-processing.

Because BERT has a maximum input length of 512 tokens, notes longer than this limit are
processed in overlapping windows. Entities detected in the overlap regions are
deduplicated so that a name appearing at the edge of one window is not emitted twice.

The transformer model is the best available tool for entities that require understanding
of context and word meaning — for example, recognizing that "Smith" in "Dr. Smith ordered
the test" is a person name, not a place or a clinical term.

### Layer 2 — Presidio Identifier with Custom Recognizers

Microsoft Presidio is an open-source framework for text anonymization. At its core,
Presidio's `AnalyzerEngine` maintains a registry of recognizers — each recognizer is
responsible for one entity type and can use any combination of pattern matching, NLP
models, and custom logic.

This system uses Presidio with `spaCy en_core_web_lg` as the NLP backend and registers
the following custom recognizers on top of Presidio's built-in ones:

**Why custom recognizers instead of relying on Presidio's defaults?**

Presidio's built-in recognizers are designed for general enterprise text (contracts,
emails, forms). Clinical notes have distinct structural conventions that Presidio's
defaults do not cover:

- Clinical notes always carry an MRN in a labeled header field. Presidio has no built-in
  MRN recognizer. The custom `MRNRecognizer` covers the labeled-field patterns that every
  major US EHR system (Epic, Cerner, Meditech) produces.

- Dates in clinical text appear in formats like `02/18/1965`, `Feb 18, 1965`, and
  `2/18/65` — all within the same document. Presidio's built-in date recognizer misses
  several of these formats. The custom `DateRecognizer` covers 13 distinct date formats
  found in clinical documentation.

- US Social Security Numbers have validation rules defined by the Social Security
  Administration: area codes 000, 666, and 900–999 are invalid; group number 00 is
  invalid; serial number 0000 is invalid. The custom `SSNRecognizer` encodes all these
  rules to avoid false positives from telephone numbers and account numbers that
  superficially resemble SSNs.

- HIPAA requires generalization of ages above 89 to a category such as "90 or older."
  This is a domain-specific rule that no general NER model encodes. The custom
  `AgeOver89Recognizer` applies a threshold gate: it fires only when age vocabulary
  ("years old", "y.o.", "aged") appears alongside a numeric value of 90 or greater.

**Design principle for all custom regex recognizers:**

Every pattern in the custom recognizers is either format-defined (the identifier has a
standardized structure, such as an SSN or a VIN) or field-label-anchored (the identifier
appears after a known label that the EHR system always prints, such as "MRN:" or
"Account Number:"). No pattern was written by looking at the evaluation test data and
reverse-engineering what would match it. This distinction is important because format and
label patterns generalize to any real clinical document, whereas test-set-derived patterns
would only inflate metrics on the specific notes used for evaluation.

### Layer 3 — Clinical Heuristics

Some PHI patterns are too small or too informal for a transformer model to catch reliably,
and too domain-specific for general regex to express correctly. The clinical heuristics
layer handles these cases with purpose-written detection functions:

- **Section header detection** parses the structured header block that every EHR note
  begins with (fields like "Patient Name:", "Date of Birth:", "Attending Physician:")
  and extracts the values following each label.

- **Initials and nickname detection** catches shortened name forms such as "J.D." or
  quoted names like `"Buddy"` that transformer models frequently miss because they
  appear too briefly to carry enough context for confident classification.

- **Relatives and contacts detection** finds name-like spans that are preceded by
  kinship words ("wife", "son", "emergency contact:") — another category that NER
  models often miss because the surrounding clinical narrative crowds out the name signal.

- **Long numeric identifier detection** catches sequences of 10 or more digits that were
  not picked up by any recognizer, as a conservative safety net.

---

## Design Note: Why FacilityLocationRecognizer Exists

Healthcare facility names such as "St. Mary's Hospital Emergency Department" or "Mercy
Behavioral Health Center" are a common and important form of LOCATION PHI. They appear
throughout clinical notes and must be de-identified.

The `spaCy en_core_web_lg` NER model correctly identifies these facility names — it labels
them as `ORG` (organization) entities, which is the right general-purpose label for named
institutions. However, Presidio's default configuration explicitly discards `ORG` entities
before they reach any recognizer. This is a deliberate Presidio design choice for general
enterprise text, where `ORG` spans are usually not PHI. In a healthcare context, the
opposite is true.

The `FacilityLocationRecognizer` solves this by holding a direct reference to the spaCy
model and reading `doc.ents` without going through Presidio's entity filter. It then
applies a domain keyword filter — words like "hospital", "clinic", "urgent care", and
"rehabilitation center" — to decide which `ORG` spans represent healthcare facilities
rather than, say, insurance company names or government agencies. The keyword set is a
filter on the NER model's output, not a span generator. The NER model decides where a
span begins and ends; the keywords decide whether that span qualifies as a healthcare
facility LOCATION.

This design avoids the temptation of writing a vocabulary-based regex that enumerates
facility name patterns. A regex like `[A-Z][a-zA-Z ]+(?:Hospital|Clinic|Medical Center)`
would only catch facilities that end with those exact suffixes, would miss names like
"Mass General" or "UCSF", and would add false positives for non-facility mentions.
Using the NER model for span detection and keywords only for domain classification is the
architecturally correct separation of concerns.

---

## Entity Detection Reliability

The following diagram shows, for each HIPAA-critical entity, which layer is the primary
detection source and what makes that source reliable for that entity type.

```
Entity        Primary Source       Why That Source Is Reliable
──────────────────────────────────────────────────────────────────────────────

NAME          HF transformer       Trained on i2b2 clinical text. Understands
              + spaCy PERSON       context ("Dr. Smith" vs. "Smith Street").
                                   Labeled-field regex ("Patient Name:") closes
                                   the gap for structured header blocks.

DATE          Custom regex         Date formats are completely format-defined.
              + HF DATE label      MM/DD/YYYY appears in documents because the
                                   EHR formats it that way — not because a
                                   clinician chose a date style. Regex is the
                                   correct tool; the HF model adds coverage for
                                   informal date references in narrative text.

LOCATION      HF LOC label         Addresses and ZIP codes are structural.
              + spaCy GPE/LOC      Facility names require NER (the model
              + USLocation regex   understands "St. Mary's" is a place name).
              + FacilityLocation   The combination covers both structural
                NER promotion      (address patterns) and semantic (facility
                                   names) forms of location PHI.

MRN           Labeled-field        MRNs in clinical notes always appear after
              regex only           a label ("MRN:", "Chart #:", "Patient ID:")
                                   printed by the EHR system. The label is the
                                   signal; regex on the label is correct and
                                   complete. NER is used as a secondary source
                                   for the rare unlabeled occurrence.

US_SSN        Custom regex         SSN is a fully format-defined 9-digit
              with SSA             identifier with published validation rules.
              validation           Regex encoding the SSA specification is
                                   more reliable than any NER model for this.

ACCOUNT_      Labeled-field        Financial account numbers only appear in
NUMBER        regex only           clinical notes in labeled administrative
                                   header blocks (FIN:, Account Number:).
                                   The label is always present; regex is correct.

AGE_OVER_89   Custom regex         This is a HIPAA rule, not a named entity.
              with threshold       The threshold (>89) is a regulatory value.
              gate                 A regex that combines age vocabulary with a
                                   numeric threshold is the only way to encode
                                   this rule deterministically.
```

---

## Evaluation Framework Architecture

The system includes a standalone evaluation framework that measures how accurately the
detection pipeline identifies PHI in real clinical notes, without requiring any manually
annotated ground-truth labels. Instead, a large language model serves as the judge.

```
                    ┌──────────────────────────────────┐
                    │      Clinical Note (text file)    │
                    └─────────────┬────────────────────┘
                                  │
              ┌───────────────────┴───────────────────┐
              │                                       │
   ┌──────────▼──────────────┐           ┌────────────▼────────────┐
   │   PHI Detection         │           │   LLM Judge             │
   │   Pipeline              │           │                         │
   │                         │           │   Reads the same note   │
   │   Runs the configured   │           │   and independently     │
   │   detector(s) against   │           │   identifies every PHI  │
   │   the note and produces │           │   span it can find,     │
   │   a list of detected    │           │   acting as a human     │
   │   spans with categories │           │   expert reviewer       │
   │   and confidence scores │           │   would.                │
   └──────────┬──────────────┘           └────────────┬────────────┘
              │                                       │
              │  Detected spans                       │  Expected spans
              │                                       │  (ground truth)
              └───────────────────┬───────────────────┘
                                  │
                     ┌────────────▼────────────┐
                     │   Recall Computation     │
                     │                         │
                     │  For each expected span  │
                     │  from the LLM judge,     │
                     │  check whether the       │
                     │  pipeline detected an    │
                     │  overlapping span of the │
                     │  same HIPAA category.    │
                     │                         │
                     │  Recall = TP / (TP + FN) │
                     │                         │
                     │  A HIPAA-critical entity │
                     │  type passes if recall   │
                     │  reaches 95% or higher.  │
                     └────────────┬────────────┘
                                  │
                     ┌────────────▼────────────┐
                     │   Evaluation Report      │
                     │                         │
                     │  Per-entity recall and  │
                     │  pass/fail table.        │
                     │  Full JSON results with  │
                     │  detected spans, missed  │
                     │  spans, and false        │
                     │  positive candidates     │
                     │  written to disk.        │
                     └─────────────────────────┘
```

### The LLM Judge

The LLM judge reads each clinical note and produces a complete list of PHI spans exactly
as a trained human annotator would. This approach eliminates the need to manually annotate
every document in the evaluation set — a process that is expensive, time-consuming, and
requires clinical expertise.

The judge is instructed to follow the HIPAA Safe Harbor specification precisely. It is
told which 18 categories are valid, given explicit guidance on boundary cases (all dates
with a month or day are PHI regardless of context; ages 89 and below are not PHI; year
values alone are not PHI), and told to reject common false positive categories such as
medications, diagnoses, vital signs, and laboratory results.

The judge's output becomes the ground truth for that evaluation run. The pipeline's
detected spans are then compared against the judge's spans to compute recall for each
entity category.

The system supports two judge backends. A local backend connects to LM Studio running on
the same machine, allowing evaluation to run entirely offline without any data leaving the
local environment — important given the sensitivity of clinical text. A cloud backend
connects to the OpenAI API for higher-quality judgments when the evaluation environment
permits external connections.

### Why Recall Is the Governing Metric

In de-identification, failing to detect a piece of PHI (a false negative) is categorically
worse than over-redacting a piece of clinical text (a false positive). A missed name or
address means a patient's identity may be re-linkable from a document that was supposed
to be anonymous. An extra redaction means a reader sees "[NAME]" where they expected a
clinical term — an inconvenience, but not a privacy violation.

For this reason, the evaluation framework reports recall as the primary metric and applies
a 95% recall threshold as the pass criterion for each HIPAA-critical entity type. An
entity type fails if the pipeline misses more than 5% of the instances the LLM judge
found. Precision is also reported but does not drive pass/fail.

### Configurable Detectors

The evaluation CLI supports running any combination of the detection layers independently
or together, which allows isolating the contribution of each component:

```
Detector name          What it runs
─────────────────────────────────────────────────────────────────────────
hf                     HuggingFace transformer only
presidio               Presidio + spaCy + custom recognizers only
heuristics             Clinical heuristics functions only
pipeline               All three layers merged (full production pipeline)
pipeline_filtered      Full pipeline with the false positive guardrail
                       applied after merging
```

Running the detectors in isolation makes it possible to answer questions such as: "Is the
HF model alone sufficient for NAME detection, or does the labeled-field regex materially
improve recall?" and "Does the false positive guardrail reduce precision-harming noise
without degrading recall below the 95% threshold?"

---

## Directory Structure

```
phi_detection/
│
├── identifier/                   Detection layer implementations
│   ├── base_identifier.py        Abstract base class for all identifiers
│   ├── huggingface_model_identifier.py   HF transformer layer
│   ├── presidio_identifier.py    Presidio + custom recognizers layer
│   └── identifier_config.py     Shared configuration constants
│
├── recognizer/                   Custom Presidio recognizers (one per entity)
│   ├── mrn_recognizer.py
│   ├── date_recognizer.py
│   ├── ssn_recognizer.py
│   ├── age_over_89_recognizer.py
│   ├── account_number_recognizer.py
│   ├── health_plan_id_recognizer.py
│   ├── us_location_recognizer.py
│   ├── facility_location_recognizer.py
│   ├── encounter_id_recognizer.py
│   ├── device_id_recognizer.py
│   ├── vehicle_id_recognizer.py
│   ├── fax_recognizer.py
│   ├── photo_id_recognizer.py
│   ├── biometric_id_recognizer.py
│   └── recognizer_config.py     Shared threshold and configuration constants
│
├── post_detection_fp_guardrail/  False positive filtering after detection
│   ├── fp_guardrail.py          Orchestrates all three filter passes
│   ├── hf_confidence_filter.py  Drops low-confidence HF entities
│   ├── structural_validator.py  Drops structurally invalid spaCy entities
│   └── name_context_filter.py  Drops clinical-phrase NAME/ORG false positives
│
├── clinical_patterns.py          Clinical heuristics detection functions
│
├── normalizer/                   Stage 0 text normalization
│
├── evaluation/                   Evaluation framework
│   ├── runners/
│   │   └── llm_evaluator.py     Orchestrates detector runs and LLM judging
│   ├── judges/
│   │   ├── openai_judge.py      OpenAI API judge backend
│   │   └── lm_studio_judge.py  Local LLM judge backend (LM Studio)
│   ├── evaluation_config.py     Evaluation configuration dataclass
│   └── evaluation.yaml          Active evaluation settings
│
└── phi_identification_evaluation_cli.py   Command-line entry point
```
