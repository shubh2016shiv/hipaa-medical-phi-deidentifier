"""
LM Studio Judge — DeepEval-Compatible LLM Wrapper
===================================================

Wraps the locally-running LM Studio server (OpenAI-compatible mode) as a
deepeval DeepEvalBaseLLM. Used exclusively for qualitative analysis of
PHI detection failures — explaining why an entity was missed or
misclassified, and rating the HIPAA compliance risk.

Architecture:
-------------
    ┌──────────────────────┐
    │ hipaa_coverage_metric│  calls
    │ detector_evaluator   │──────▶ LMStudioJudge.generate(prompt)
    └──────────────────────┘              │
                                          ▼
                               POST /v1/chat/completions
                               http://localhost:1234
                               model: deepseek/deepseek-r1-0528-qwen3-8b

Dependencies:
    - deepeval  (DeepEvalBaseLLM base class)
    - httpx     (synchronous + async HTTP client, timeout-safe)

Author: HIPAA De-identification System
Last Updated: 2026-05-02
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx
from deepeval.models import DeepEvalBaseLLM

logger = logging.getLogger(__name__)

# System prompt engineering for HIPAA compliance evaluation
_SYSTEM_PROMPT = """You are a HIPAA compliance expert and clinical NLP specialist.
You evaluate de-identification systems against the HIPAA Safe Harbor standard (45 CFR §164.514(b)).

When given a missed or misclassified PHI entity, you must respond with EXACTLY three sections:

**WHY MISSED**: One concise paragraph explaining the technical root cause
(e.g., pattern mismatch, out-of-distribution format, wrong entity type mapping).

**HIPAA RISK**: One of: CRITICAL / HIGH / MEDIUM / LOW
- CRITICAL: Direct patient re-identification possible (name, MRN, full address, age≥90)
- HIGH: Indirect re-identification possible (date, phone, license number, organization)
- MEDIUM: Risk exists but requires combination with other data (time, partial address)
- LOW: Minimal re-identification risk alone

**RECOMMENDATION**: One concrete, technical recommendation for the engineering team
(e.g., "Add regex FIN-\\d+ to AccountNumberRecognizer", "Lower HF threshold for AGE label").

Keep each section to 2-3 sentences maximum. Do not add any other formatting."""


class LMStudioJudge(DeepEvalBaseLLM):
    """DeepEval-compatible wrapper for a locally-running LM Studio model.

    Calls LM Studio's OpenAI-compatible chat endpoint to provide qualitative
    analysis of PHI detection failures. This judge is NEVER used for span
    detection — only for explaining why detectors failed.

    Enterprise Features:
    - Explicit timeout (60s — reasoning models need time)
    - Graceful degradation if LM Studio is offline
    - Structured three-section response validation
    - Full async support for deepeval's async evaluation loop

    Example:
        >>> judge = LMStudioJudge()
        >>> verdict = judge.generate(
        ...     "Missed: 'MR-2024-223344' (MRN). Detector: HFIdentifier."
        ... )
        >>> print(verdict)
    """

    # LM Studio OpenAI-compat endpoint (confirmed active)
    _BASE_URL: str = "http://localhost:1234/v1/chat/completions"
    _MODEL: str = "deepseek/deepseek-r1-0528-qwen3-8b"
    _TIMEOUT_SECONDS: float = 60.0  # Reasoning models need more time than standard LLMs
    _MAX_TOKENS: int = 512           # Enough for 3-section structured response
    _TEMPERATURE: float = 0.1        # Near-deterministic for compliance judgments

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """Initialize the LM Studio judge.

        Args:
            base_url: Override the default LM Studio endpoint.
            model: Override the default model name.

        Example:
            >>> judge = LMStudioJudge()  # uses defaults
            >>> judge = LMStudioJudge(base_url="http://localhost:1234/v1/chat/completions")
        """
        self.base_url = base_url or self._BASE_URL
        self.model_name = model or self._MODEL
        logger.info(
            "LMStudioJudge initialized: model=%s, endpoint=%s",
            self.model_name,
            self.base_url,
        )

    def get_model_name(self) -> str:
        """Return the display name for this model.

        Returns:
            Human-readable model identifier string.
        """
        return f"LMStudio:{self.model_name}"

    def load_model(self):
        """No-op — LM Studio is a remote server; no local loading needed.

        Returns:
            Self (required by DeepEvalBaseLLM interface).
        """
        return self

    def generate(self, prompt: str) -> str:
        """Send a prompt to LM Studio and return the response.

        Makes a synchronous POST to the OpenAI-compatible chat endpoint.
        Falls back gracefully if LM Studio is unavailable.

        Args:
            prompt: The evaluation prompt (entity + context + question).

        Returns:
            Structured three-section verdict, or an error message if
            LM Studio is unreachable.

        Raises:
            Does NOT raise — returns a structured error string instead,
            so the evaluation pipeline continues without the judge.

        Example:
            >>> verdict = judge.generate("Missed entity: 'FIN-556677889'")
        """
        payload = self._build_payload(prompt)

        try:
            logger.debug("Calling LM Studio judge for prompt (len=%d)", len(prompt))
            with httpx.Client(timeout=self._TIMEOUT_SECONDS) as client:
                response = client.post(self.base_url, json=payload)
                response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()
            logger.debug("LM Studio judge responded (len=%d)", len(content))
            return content

        except httpx.ConnectError:
            logger.warning(
                "LM Studio not reachable at %s. "
                "Start LM Studio and enable OpenAI-compatible server.",
                self.base_url,
            )
            return (
                "**WHY MISSED**: LM Studio judge unavailable — server not reachable.\n"
                "**HIPAA RISK**: UNKNOWN\n"
                "**RECOMMENDATION**: Start LM Studio and re-run with --judge lm_studio."
            )
        except httpx.TimeoutException:
            logger.warning("LM Studio judge timed out after %.0fs.", self._TIMEOUT_SECONDS)
            return (
                "**WHY MISSED**: LM Studio judge timed out.\n"
                "**HIPAA RISK**: UNKNOWN\n"
                "**RECOMMENDATION**: Increase timeout or use a lighter model."
            )
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            logger.error("Unexpected LM Studio response format: %s", exc)
            return (
                f"**WHY MISSED**: Malformed response from judge: {exc}\n"
                "**HIPAA RISK**: UNKNOWN\n"
                "**RECOMMENDATION**: Check LM Studio response format."
            )

    def generate_json(
        self,
        prompt: str,
        schema: dict,
        *,
        system_prompt: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        use_response_format: bool = True,
    ) -> dict[str, Any]:
        """Call LM Studio and parse a structured JSON response.

        Returns a status envelope instead of raising, so evaluation reports can
        show LLM/runtime errors without hiding detector output.
        """
        payload = self._build_json_payload(
            prompt=prompt,
            schema=schema,
            system_prompt=system_prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            use_response_format=use_response_format,
        )
        endpoint = base_url or self.base_url
        timeout = timeout_seconds or self._TIMEOUT_SECONDS

        try:
            logger.debug("Calling LM Studio JSON judge for prompt (len=%d)", len(prompt))
            with httpx.Client(timeout=timeout) as client:
                response = client.post(endpoint, json=payload)
                response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()
            parsed = self._parse_json_content(content)
            return {
                "status": "ok",
                "data": parsed,
                "raw_response": content,
                "error_message": None,
            }

        except httpx.ConnectError:
            message = (
                f"LM Studio not reachable at {endpoint}. "
                "Start LM Studio and enable OpenAI-compatible server."
            )
            logger.warning(message)
            return {
                "status": "error",
                "data": None,
                "raw_response": None,
                "error_message": message,
            }
        except httpx.TimeoutException:
            message = f"LM Studio judge timed out after {timeout:.0f}s."
            logger.warning(message)
            return {
                "status": "error",
                "data": None,
                "raw_response": None,
                "error_message": message,
            }
        except (KeyError, IndexError, json.JSONDecodeError, ValueError) as exc:
            message = f"Malformed JSON response from LM Studio judge: {exc}"
            logger.error(message)
            return {
                "status": "error",
                "data": None,
                "raw_response": locals().get("content"),
                "error_message": message,
            }

    async def a_generate(self, prompt: str) -> str:
        """Async version of generate — used by deepeval's async evaluation loop.

        Args:
            prompt: The evaluation prompt.

        Returns:
            Structured three-section verdict string.

        Example:
            >>> verdict = await judge.a_generate("Missed entity: 'FIN-556677889'")
        """
        payload = self._build_payload(prompt)

        try:
            logger.debug("Async calling LM Studio judge (len=%d)", len(prompt))
            async with httpx.AsyncClient(timeout=self._TIMEOUT_SECONDS) as client:
                response = await client.post(self.base_url, json=payload)
                response.raise_for_status()

            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()
            logger.debug("LM Studio async judge responded (len=%d)", len(content))
            return content

        except httpx.ConnectError:
            logger.warning("LM Studio not reachable (async path).")
            return (
                "**WHY MISSED**: LM Studio judge unavailable.\n"
                "**HIPAA RISK**: UNKNOWN\n"
                "**RECOMMENDATION**: Start LM Studio and retry."
            )
        except Exception as exc:
            logger.error("Async LM Studio judge error: %s", exc)
            return f"**WHY MISSED**: Judge error: {exc}\n**HIPAA RISK**: UNKNOWN\n**RECOMMENDATION**: Check logs."

    def _build_payload(self, prompt: str) -> dict:
        """Construct the OpenAI-compatible chat completions request body.

        Args:
            prompt: User-side evaluation prompt.

        Returns:
            Dict matching the OpenAI chat completions API schema.
        """
        return {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": self._MAX_TOKENS,
            "temperature": self._TEMPERATURE,
            "stream": False,
        }

    def _build_json_payload(
        self,
        *,
        prompt: str,
        schema: dict,
        system_prompt: Optional[str],
        model: Optional[str],
        max_tokens: Optional[int],
        temperature: Optional[float],
        use_response_format: bool,
    ) -> dict:
        payload = {
            "model": model or self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt or _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens or self._MAX_TOKENS,
            "temperature": (
                self._TEMPERATURE if temperature is None else temperature
            ),
            "stream": False,
        }

        if use_response_format:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": schema,
            }

        return payload

    @staticmethod
    def _parse_json_content(content: str) -> dict:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`").strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
            return json.loads(cleaned)

    @staticmethod
    def build_missed_entity_prompt(
        entity_value: str,
        entity_type: str,
        detector_name: str,
        context_snippet: str,
        hipaa_rule: str,
    ) -> str:
        """Build a structured prompt for analysing a missed entity.

        Args:
            entity_value: The raw PHI text that was not detected.
            entity_type: HIPAA category (e.g. "MRN", "NAME").
            detector_name: Which detector missed it (e.g. "HFIdentifier").
            context_snippet: ±100 chars of surrounding text for context.
            hipaa_rule: The required transformation (e.g. "hash", "pseudonym").

        Returns:
            Formatted prompt string ready for generate().

        Example:
            >>> prompt = LMStudioJudge.build_missed_entity_prompt(
            ...     entity_value="MR-2024-223344",
            ...     entity_type="MRN",
            ...     detector_name="HFIdentifier",
            ...     context_snippet="Patient: Margaret Rose Sullivan\\nMRN: MR-2024-223344\\nFIN:",
            ...     hipaa_rule="hash",
            ... )
        """
        return (
            f"A PHI detection system MISSED the following entity:\n\n"
            f"Entity Value : {entity_value!r}\n"
            f"Entity Type  : {entity_type} (HIPAA Safe Harbor)\n"
            f"Required Rule: {hipaa_rule} (from base.yaml)\n"
            f"Detector     : {detector_name}\n"
            f"Context      :\n---\n{context_snippet}\n---\n\n"
            f"Analyse this failure and provide your structured verdict."
        )

    @staticmethod
    def build_false_positive_prompt(
        entity_value: str,
        predicted_type: str,
        detector_name: str,
        context_snippet: str,
    ) -> str:
        """Build a structured prompt for analysing a false positive detection.

        Args:
            entity_value: The text that was incorrectly flagged as PHI.
            predicted_type: The incorrectly predicted HIPAA category.
            detector_name: Which detector produced the false positive.
            context_snippet: ±100 chars of surrounding text.

        Returns:
            Formatted prompt string ready for generate().
        """
        return (
            f"A PHI detection system INCORRECTLY flagged this as PHI:\n\n"
            f"Flagged Text    : {entity_value!r}\n"
            f"Predicted Type  : {predicted_type}\n"
            f"Detector        : {detector_name}\n"
            f"Context         :\n---\n{context_snippet}\n---\n\n"
            f"This text is NOT PHI. Analyse why the detector made this error."
        )
