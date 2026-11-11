"""The strict JSON the LLM must reply with, and parsing of raw replies."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.faults import FaultCatalog, fault_ids
from app.lifts import LIFTS

COACH_OUTPUT_FIELDS = ("lift", "camera_angle", "rep_count", "top_fault_id", "fault_reps",
                       "supporting_measurement", "other_faults", "cue", "explanation")


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class SupportingMeasurement(_Strict):
    metric: str
    rep: int
    value: float


class FaultCitation(_Strict):
    fault_id: str
    reps: list[int]
    supporting_measurement: SupportingMeasurement


class CoachOutput(_Strict):
    lift: Literal["squat", "deadlift", "bench_press"]
    camera_angle: Literal["side", "front", "angled"]
    rep_count: int = Field(ge=0)
    top_fault_id: str | None
    fault_reps: list[int]
    supporting_measurement: SupportingMeasurement | None
    other_faults: list[FaultCitation]
    cue: str
    explanation: str
    professional_recommendation: str | None = None


def coach_output_json_schema(lift: str, catalog: FaultCatalog | None = None) -> dict:
    """JSON Schema sent to the LLM. Fault IDs are limited to the lift's enabled faults."""
    ids = fault_ids(lift, catalog)
    measurement = {
        "type": "object", "additionalProperties": False, "required": ["metric", "rep", "value"],
        "properties": {"metric": {"type": "string"}, "rep": {"type": "integer", "minimum": 1}, "value": {"type": "number"}},
    }
    reps = {"type": "array", "items": {"type": "integer", "minimum": 1}}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(COACH_OUTPUT_FIELDS),
        "properties": {
            "lift": {"enum": list(LIFTS)},
            "camera_angle": {"enum": ["side", "front", "angled"]},
            "rep_count": {"type": "integer", "minimum": 0},
            "top_fault_id": {"anyOf": [{"enum": ids}, {"type": "null"}]},
            "fault_reps": reps,
            "supporting_measurement": {"anyOf": [measurement, {"type": "null"}]},
            "other_faults": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["fault_id", "reps", "supporting_measurement"],
                "properties": {"fault_id": {"enum": ids}, "reps": reps, "supporting_measurement": measurement},
            }},
            "cue": {"type": "string", "description": "One cue for the next set, 12 words or fewer"},
            "explanation": {"type": "string"},
            "professional_recommendation": {"type": ["string", "null"]},
        },
    }


_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _schema_issue(err: ValidationError) -> ValidationIssue:
    parts = [f"{'.'.join(str(p) for p in e['loc']) or 'reply'}: {e['msg']}" for e in err.errors()]
    return ValidationIssue("schema", "reply doesn't match the JSON schema: " + "; ".join(parts))


def validate_output_dict(data) -> tuple[CoachOutput | None, list[ValidationIssue]]:
    if not isinstance(data, dict):
        return None, [ValidationIssue("schema", "reply must be a single JSON object")]
    try:
        return CoachOutput.model_validate(data), []
    except ValidationError as err:
        return None, [_schema_issue(err)]


def parse_coach_output(text: str) -> tuple[CoachOutput | None, list[ValidationIssue]]:
    """Parses a raw LLM reply. Never raises: bad replies come back as issues."""
    m = _FENCE.match(text or "")
    body = m.group(1) if m else (text or "")
    try:
        data = json.loads(body)
    except json.JSONDecodeError as err:
        return None, [ValidationIssue("invalid_json", f"reply was not valid JSON ({err.msg}); reply with JSON only")]
    return validate_output_dict(data)
