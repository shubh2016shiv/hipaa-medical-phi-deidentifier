"""
OpenAI API Judge — drop-in replacement for LMStudioJudge.

Uses the official openai SDK to call the OpenAI API.  Exposes the same
``generate_json`` interface as LMStudioJudge so LLMEvaluator can swap
backends with zero logic changes.

Configuration comes from evaluation.yaml:

    openai_api:
      enabled: true
      model: "gpt-4.1-nano"
      api_key_env: "OPENAI_API_KEY"
      timeout_seconds: 60
      temperature: 0.1
      max_tokens: 4096
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


class OpenAIJudge:
    """Calls the OpenAI chat completions API for structured PHI evaluation.

    Structured output uses OpenAI's ``response_format`` with ``json_schema``
    (strict mode), giving more reliable JSON than LM Studio on small models.

    Example:
        >>> judge = OpenAIJudge(model="gpt-4.1-nano", api_key_env="OPENAI_API_KEY")
        >>> result = judge.generate_json(prompt, schema, system_prompt=...)
        >>> result["status"]   # "ok" or "error"
    """

    def __init__(
        self,
        model: str = "gpt-4.1-nano",
        api_key_env: str = "OPENAI_API_KEY",
        timeout_seconds: float = 60.0,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai package is required for the OpenAI judge backend.\n"
                "Install it with: pip install openai"
            )

        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise EnvironmentError(
                f"OpenAI API key not found. Set the {api_key_env!r} environment variable."
            )

        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds)
        self.model_name = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout_seconds

        logger.info("OpenAIJudge initialised: model=%s, key_env=%s", model, api_key_env)

    def get_model_name(self) -> str:
        return f"OpenAI:{self.model_name}"

    def generate_json(
        self,
        prompt: str,
        schema: dict,
        *,
        system_prompt: Optional[str] = None,
        # The following kwargs mirror LMStudioJudge.generate_json for interface
        # compatibility — OpenAI uses self.model_name / self._* attributes instead.
        base_url: Optional[str] = None,  # noqa: ARG002
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,  # noqa: ARG002
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        use_response_format: bool = True,
    ) -> dict[str, Any]:
        """Call OpenAI and return a status envelope identical to LMStudioJudge.

        Returns:
            {"status": "ok"|"error", "data": dict|None,
             "raw_response": str|None, "error_message": str|None}
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        call_model = model or self.model_name
        call_max_tokens = max_tokens or self._max_tokens
        call_temperature = self._temperature if temperature is None else temperature

        # gpt-5-* and o-series reasoning models have two restrictions:
        #   1. require max_completion_tokens instead of max_tokens
        #   2. reject temperature (only the default value of 1 is supported)
        _reasoning = _is_reasoning_model(call_model)
        _tokens_key = "max_completion_tokens" if _reasoning else "max_tokens"

        kwargs: dict[str, Any] = dict(
            model=call_model,
            messages=messages,
            **{_tokens_key: call_max_tokens},
        )
        if not _reasoning:
            kwargs["temperature"] = call_temperature

        if use_response_format:
            if _reasoning:
                # Reasoning models (gpt-5-*, o1, o3, o4): both json_schema and
                # json_object response_format return empty content in practice.
                # Omit response_format entirely and rely on the system prompt
                # ("Return only JSON matching the provided schema. Do not include
                # markdown.") — reasoning models follow this reliably.
                pass
            else:
                kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": schema,
                }

        content: Optional[str] = None
        try:
            logger.debug(
                "Calling OpenAI judge: model=%s, prompt_len=%d",
                call_model,
                len(prompt),
            )
            response = self._client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            content = content.strip()
            parsed = _parse_json(content)
            logger.debug("OpenAI judge responded: tokens_used=%s", response.usage)
            return {
                "status": "ok",
                "data": parsed,
                "raw_response": content,
                "error_message": None,
            }

        except ImportError:
            raise  # propagate missing-package errors
        except EnvironmentError:
            raise  # propagate missing-key errors
        except Exception as exc:  # openai.APIError and its subclasses
            exc_name = type(exc).__name__
            # Auth errors — surface clearly
            if "auth" in exc_name.lower() or "authentication" in str(exc).lower():
                message = f"OpenAI authentication failed: {exc}"
            elif "rate" in exc_name.lower() or "rate_limit" in str(exc).lower():
                message = f"OpenAI rate limit hit: {exc}"
            elif "timeout" in exc_name.lower():
                message = f"OpenAI request timed out after {self._timeout:.0f}s."
            elif content is not None:
                message = f"Malformed JSON response from OpenAI judge: {exc}"
            else:
                message = f"OpenAI API error ({exc_name}): {exc}"

            logger.error(message)
            return {
                "status": "error",
                "data": None,
                "raw_response": content,
                "error_message": message,
            }


def _is_reasoning_model(model: str) -> bool:
    """Return True for models that use the reasoning/completion API conventions.

    These models:
    - require max_completion_tokens instead of max_tokens
    - do not accept a temperature parameter (only the default of 1 is supported)

    Covers: gpt-5-*, o1-*, o3-*, o4-*
    """
    m = model.lower()
    return (
        m.startswith("gpt-5")
        or m.startswith("o1")
        or m.startswith("o3")
        or m.startswith("o4")
    )


def _uses_completion_tokens(model: str) -> bool:
    return _is_reasoning_model(model)


def _parse_json(content: str) -> dict:
    """Parse JSON, stripping markdown fences if present."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
        return json.loads(cleaned)
