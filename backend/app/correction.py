"""Correction loop: validation errors go back to the LLM, at most 3 attempts in total."""
from __future__ import annotations

from dataclasses import dataclass

from app.llm.client import LLMClient, LLMRequest
from app.llm.prompt import build_retry_request
from app.llm.schema import CoachOutput, ValidationIssue
from app.validator import ValidationContext, validate

MAX_ATTEMPTS = 3


@dataclass
class AttemptLog:
    attempt_number: int
    output_text: str
    issues: list[ValidationIssue]
    input_tokens: int
    output_tokens: int

    @property
    def passed(self) -> bool:
        return not self.issues

    @property
    def messages(self) -> list[str]:
        return [i.message for i in self.issues]


@dataclass
class CorrectionResult:
    status: str                    # passed_first_try | passed_after_retry | fallback
    output: CoachOutput | None
    attempts: list[AttemptLog]


def run_correction_loop(llm: LLMClient, request: LLMRequest, ctx: ValidationContext,
                        max_attempts: int = MAX_ATTEMPTS) -> CorrectionResult:
    attempts: list[AttemptLog] = []
    current = request
    for n in range(1, max_attempts + 1):
        try:
            reply = llm.complete(current)
        except Exception as err:  # network errors, rate limits, provider outages
            attempts.append(AttemptLog(n, "", [ValidationIssue("llm_error", f"LLM request failed: {err}")], 0, 0))
            continue
        result = validate(reply.text, ctx)
        attempts.append(AttemptLog(n, reply.text, result.issues, reply.input_tokens, reply.output_tokens))
        if result.ok:
            return CorrectionResult("passed_first_try" if n == 1 else "passed_after_retry", result.output, attempts)
        current = build_retry_request(current, reply.text, result.messages)
    return CorrectionResult("fallback", None, attempts)
