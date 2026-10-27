"""An LLM judge that talks to OpenRouter, logs every decision, and prices by the
OpenRouter table, so one key gives Claude, GPT and Gemini judges.

It keeps StepShield's step prompt and JSON contract, so results are comparable
with the paper's LLMJudge, and lets the system prompt come from prompts/<version>.md.
"""

from __future__ import annotations

import asyncio
import json
import re
import os
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from . import common

common.load_env()

from detectors.llm_judge import STEP_PROMPT_TEMPLATE, LLMJudge  # vendor  # noqa: E402

# USD per million tokens (input, output). Source: openrouter.ai/api/v1/models, 2026-10-26.
OPENROUTER_PRICING: dict[str, tuple[float, float]] = {
    "openai/gpt-4.1-mini": (0.40, 1.60),
    "openai/gpt-5-mini": (0.25, 2.00),
    "anthropic/claude-haiku-5.5": (0.10, 0.50),
    "anthropic/claude-sonnet-5.5": (2.00, 10.00),
    "anthropic/claude-opus-5.5": (4.00, 20.00),
    "google/gemini-3.5-flash-lite": (0.30, 2.50),
    "google/gemini-2.5-flash": (0.30, 2.50),
}

# Pre-run estimates count prompt tokens with tiktoken's o200k encoding. Measured on
# 2026-10-26: OpenAI models bill about 1.0x that count and write about 55 output
# tokens a step; Anthropic models bill about 1.7x and write about 145 (longer reasons).
PROVIDER_FACTORS: dict[str, tuple[float, int]] = {  # (input multiplier, output tokens per step)
    "openai": (1.0, 60),
    "anthropic": (1.75, 150),
    "google": (1.2, 100),  # not yet measured; a guess with headroom
}


def estimate_cost_usd(model: str, input_tokens: int, steps: int) -> float:
    pin, pout = OPENROUTER_PRICING[model]
    mult, out_per_step = PROVIDER_FACTORS.get(model.split("/")[0], (1.5, 120))
    return input_tokens * mult / 1e6 * pin + steps * out_per_step / 1e6 * pout


def as_confidence(value) -> float:
    """Coerce a judge's confidence to a float; words map to rough numbers, junk to 0."""
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    if isinstance(value, str):
        text = value.strip().lower().rstrip("%")
        try:
            number = float(text)
            return max(0.0, min(1.0, number / 100 if number > 1 else number))
        except ValueError:
            return {"very high": 0.95, "high": 0.9, "medium": 0.6, "moderate": 0.6, "low": 0.3, "very low": 0.1}.get(text, 0.0)
    return 0.0


# StepShield's judge caps answers at 200 output tokens. GPT-4.1-mini and Gemini Flash Lite
# answer in 55-65 tokens, but Claude models write 120-150-token reasons, so at 200 the JSON
# was cut off in 27% of Haiku's and 7% of Sonnet's answers on 2026-10-26/27 and the vendor
# parser returned "Parse error" (verdict: not rogue). 600 leaves room; at temperature 0
# the shorter answers do not change.
DEFAULT_MAX_TOKENS = 600

FAILED_REASONS = ("Parse error", "empty response")


def is_failed_row(row: dict[str, Any]) -> bool:
    """A step whose verdict is a harness failure, not a judgment: unparsable, empty or API error.

    A refusal ("refused: ...") is not a failure: the model was asked and declined. It is kept
    as a verdict of its own and reported separately (see scripts/refusal_as_alert.py).
    """
    reason = row.get("reason") or ""
    return reason in FAILED_REASONS or reason.startswith("API error") or bool(row.get("error"))


def is_refused_row(row: dict[str, Any]) -> bool:
    return (row.get("reason") or "").startswith("refused:") or row.get("parse_status") == "refused"


def salvage_json(content: str) -> dict[str, Any] | None:
    """Pull the verdict out of JSON that was cut off before its closing brace."""
    verdict = re.search(r'"is_rogue"\s*:\s*(true|false)', content, re.I)
    if not verdict:
        return None
    confidence = re.search(r'"confidence"\s*:\s*("?[\w.]+"?)', content)
    category = re.search(r'"category"\s*:\s*"([^"]*)"', content)
    reason = re.search(r'"reason"\s*:\s*"([^"]*)', content)
    return {
        "is_rogue": verdict.group(1).lower() == "true",
        "confidence": (confidence.group(1).strip('"') if confidence else 0.0),
        "category": category.group(1) if category else None,
        "reason": "salvaged from truncated output: " + (reason.group(1) if reason else ""),
    }


class OpenRouterJudge(LLMJudge):
    def __init__(
        self,
        model: str,
        prompt_version: str,
        log_path: Path,
        budget_usd: float,
        rate_limit_rpm: int = 300,
        concurrency: int = 8,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ):
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise ValueError("OPENROUTER_API_KEY is not set (put it in .env, never in the repo)")
        if model not in OPENROUTER_PRICING:
            raise ValueError(f"no price on file for {model}; add it to OPENROUTER_PRICING first")
        # The parent insists on OPENAI_API_KEY; hand it the same key, then replace the client.
        super().__init__(model=model, api_key=key, rate_limit_rpm=rate_limit_rpm)
        self.name = f"Judge-{model.split('/')[-1]}-{prompt_version}"
        self._client = AsyncOpenAI(
            api_key=key,
            base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            default_headers={"HTTP-Referer": "https://github.com/sod-efi/driftbench", "X-Title": "driftbench"},
        )
        self.prompt_version = prompt_version
        self.system_prompt = common.read_prompt(prompt_version)
        self.log_path = log_path
        self.budget_usd = budget_usd
        self._sem = asyncio.Semaphore(concurrency)
        self.max_tokens = max_tokens
        self.budget_exceeded = False
        log_path.parent.mkdir(parents=True, exist_ok=True)

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        pin, pout = OPENROUTER_PRICING[self.model]
        return input_tokens / 1e6 * pin + output_tokens / 1e6 * pout

    def _log(self, record: dict[str, Any]) -> None:
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    async def detect_step(self, step, step_index, trajectory_context):  # type: ignore[override]
        from detectors.base import StepResult  # vendor

        if self.total_cost >= self.budget_usd:
            self.budget_exceeded = True
            self._log({"trajectory_id": trajectory_context.get("trajectory_id"), "trajectory_type": trajectory_context.get("trajectory_type"),
                       "category": trajectory_context.get("category"), "rogue_step": trajectory_context.get("rogue_step"), "step": step_index,
                       "model": self.model, "prompt_version": self.prompt_version, "is_rogue": False, "confidence": 0.0,
                       "judge_category": None, "reason": "budget stop", "input_tokens": 0, "output_tokens": 0, "error": None})
            return StepResult(step_index=step_index, is_rogue=False, confidence=0.0, reason="budget stop")

        task = trajectory_context.get("task", {})
        constraints = task.get("constraints", [])
        constraints_text = "\n".join(f"- {c}" for c in constraints) if constraints else "None"
        arguments = step.get("arguments", {})
        arg_text = json.dumps(arguments, indent=2) if isinstance(arguments, dict) else str(arguments)
        user_prompt = STEP_PROMPT_TEMPLATE.format(
            task_description=task.get("description", "No description"),
            constraints=constraints_text,
            step_index=step_index,
            thought=step.get("thought", ""),
            action=step.get("action", ""),
            arguments=arg_text,
            observation=(step.get("observation") or "")[:1000],
        )

        last_error = None
        content = ""
        refused = None
        usage_in = usage_out = 0
        async with self._sem:
            await self._rate_limit()
            for attempt in range(self.max_retries):
                try:
                    response = await asyncio.wait_for(
                        self._client.chat.completions.create(
                            model=self.model,
                            messages=[
                                {"role": "system", "content": self.system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                            temperature=self.temperature,
                            max_tokens=self.max_tokens,
                        ),
                        timeout=self.timeout,
                    )
                    self.api_calls += 1
                    if response.usage:
                        usage_in = response.usage.prompt_tokens or 0
                        usage_out = response.usage.completion_tokens or 0
                        self.input_tokens += usage_in
                        self.output_tokens += usage_out
                        self.total_tokens += usage_in + usage_out
                        self.total_cost += self._calculate_cost(usage_in, usage_out)
                    choice = response.choices[0]
                    content = choice.message.content or ""
                    refusal = getattr(choice.message, "refusal", None)
                    if choice.finish_reason == "content_filter" or refusal:
                        # Anthropic's classifier blocks some rogue steps as "violative cyber content"
                        # (seen 2026-10-27 with Sonnet 5.5 via OpenRouter). Keep the text: a monitor
                        # that goes blind on dangerous steps is a finding, not a parse failure.
                        content = ""
                        refused = (refusal or choice.finish_reason or "")[:200]
                    last_error = None
                    break
                except asyncio.TimeoutError:
                    last_error = "Timeout"
                    await asyncio.sleep(2**attempt)
                except Exception as exc:  # noqa: BLE001
                    last_error = str(exc)[:200]
                    await asyncio.sleep(2**attempt)

        parse_status = "ok"
        if last_error is not None:
            parsed = {"is_rogue": False, "confidence": 0.0, "category": None, "reason": f"API error: {last_error}"}
            parse_status = "api_error"
        elif refused:
            parsed = {"is_rogue": False, "confidence": 0.0, "category": None, "reason": "refused: " + refused}
            parse_status = "refused"
        elif not content.strip():
            parsed = {"is_rogue": False, "confidence": 0.0, "category": None, "reason": "empty response"}
            parse_status = "empty"
        else:
            parsed = self._parse_response(content)
            if parsed.get("reason") == "Parse error":
                salvaged = salvage_json(content)
                if salvaged:
                    parsed, parse_status = salvaged, "salvaged"
                else:
                    parse_status = "failed"

        self._log(
            {
                "trajectory_id": trajectory_context.get("trajectory_id"),
                "trajectory_type": trajectory_context.get("trajectory_type"),
                "category": trajectory_context.get("category"),
                "rogue_step": trajectory_context.get("rogue_step"),
                "step": step_index,
                "model": self.model,
                "prompt_version": self.prompt_version,
                "is_rogue": bool(parsed.get("is_rogue", False)),
                "confidence": as_confidence(parsed.get("confidence")),
                "judge_category": parsed.get("category"),
                "reason": parsed.get("reason"),
                "input_tokens": usage_in,
                "output_tokens": usage_out,
                "error": last_error,
                "parse_status": parse_status,
                "raw": content[:300] if parse_status not in ("ok", "api_error") else None,
            }
        )
        return StepResult(
            step_index=step_index,
            is_rogue=bool(parsed.get("is_rogue", False)),
            confidence=as_confidence(parsed.get("confidence")),
            category=parsed.get("category"),
            reason=parsed.get("reason"),
        )

    async def detect_trajectory(self, trajectory):  # type: ignore[override]
        # The vendor base class builds the context without the id; add it so the log can join to labels.
        from detectors.base import DetectionResult  # vendor
        import time

        start = time.time()
        steps = trajectory["steps"]
        context = {
            "task": trajectory.get("task", {}),
            "trajectory_type": trajectory.get("trajectory_type"),
            "category": trajectory.get("category", "UNK"),
            "trajectory_id": trajectory["trajectory_id"],
            "rogue_step": trajectory.get("rogue_step"),
        }
        # Judge all steps concurrently: each step is judged on its own, as in the paper,
        # so order does not change the verdicts, only the wall-clock time.
        results = await asyncio.gather(
            *(self.detect_step(step, i + 1, context) for i, step in enumerate(steps))
        )
        detection_step = next((r.step_index for r in results if r.is_rogue), None)
        return DetectionResult(
            trajectory_id=trajectory["trajectory_id"],
            detected=detection_step is not None,
            detection_step=detection_step,
            ground_truth_step=trajectory.get("rogue_step"),
            total_steps=len(steps),
            category=trajectory.get("category", "UNK"),
            step_results=list(results),
            api_calls=self.api_calls,
            total_tokens=self.total_tokens,
            cost_usd=self.total_cost,
            latency_ms=(time.time() - start) * 1000,
        )
