"""Checks every LLM reply against the measurements. Plain code: no LLM, no network.

Each problem becomes a ValidationIssue whose message is sent back to the LLM word for word.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.faults import get_fault
from app.lifts import LIFT_NOUNS
from app.llm.schema import CoachOutput, ValidationIssue, parse_coach_output, validate_output_dict
from app.measure import RepMeasurement, SetMeasurements
from app.rules import NotMeasured
from app.safety import find_medical_language, mentions_pain

__all__ = ["ValidationContext", "ValidationIssue", "ValidationResult", "build_validation_context", "validate"]

MAX_CUE_WORDS = 12
DEGREE_TOLERANCE = 1.0
RATIO_TOLERANCE = 0.02
_DEGREES = re.compile(r"(\d+(?:\.\d+)?)\s*°")
_REP_REF = re.compile(r"\brep\s*#?\s*(\d+)\b", re.IGNORECASE)
_REP_TOTAL = re.compile(r"\b(all\s+)?(\d+)\s+reps\b", re.IGNORECASE)
_PROFESSIONAL = re.compile(r"\b(doctor|physician|physical therapist|physiotherapist|physio)\b", re.IGNORECASE)


@dataclass
class ValidationContext:
    lift: str                      # SetMeasurements.analysis_lift
    camera_angle: str
    rep_count: int
    reps: list[RepMeasurement]
    not_measured: list[NotMeasured]
    confirmed: dict[str, list[int]]
    note_mentions_pain: bool


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)
    output: CoachOutput | None = None

    @property
    def ok(self) -> bool:
        return self.output is not None and not self.issues

    @property
    def messages(self) -> list[str]:
        return [i.message for i in self.issues]


def build_validation_context(m: SetMeasurements, not_measured: list[NotMeasured],
                             confirmed: dict[str, list[int]], note: str | None) -> ValidationContext:
    return ValidationContext(lift=m.analysis_lift, camera_angle=m.camera_angle, rep_count=m.rep_count,
                             reps=list(m.reps), not_measured=list(not_measured), confirmed=dict(confirmed),
                             note_mentions_pain=mentions_pain(note))


def validate(raw: str | dict, ctx: ValidationContext) -> ValidationResult:
    out, issues = parse_coach_output(raw) if isinstance(raw, str) else validate_output_dict(raw)
    if out is None:
        return ValidationResult(issues=issues)
    issues = []

    def add(code, message):
        issues.append(ValidationIssue(code, message))

    if out.lift != ctx.lift:
        add("lift_mismatch", f"feedback says {LIFT_NOUNS[out.lift]} but the video shows a {LIFT_NOUNS[ctx.lift]}")
    if out.camera_angle != ctx.camera_angle:
        add("camera_angle_mismatch",
            f"feedback says the camera angle is {out.camera_angle} but it was measured as {ctx.camera_angle}")
    if out.rep_count != ctx.rep_count:
        add("rep_count", f"feedback says {out.rep_count} reps but {ctx.rep_count} were detected")

    citations = []
    if out.top_fault_id is not None:
        citations.append((out.top_fault_id, out.fault_reps, out.supporting_measurement))
    citations += [(c.fault_id, c.reps, c.supporting_measurement) for c in out.other_faults]
    unmeasured = {c.check: c for c in ctx.not_measured}
    cited_ok = []
    for fault_id, reps, supporting in citations:
        fault = get_fault(ctx.lift, fault_id)
        if fault is None:
            add("unknown_fault", f"'{fault_id}' is not on the {LIFT_NOUNS[ctx.lift]} fault list")
            continue
        if fault_id in unmeasured:
            add("not_measurable", f"{fault.short_name} can't be measured: {unmeasured[fault_id].reason}")
            continue
        cited_ok.append(fault)
        _check_reps(fault, reps, ctx, add)
        _check_supporting(fault, reps, supporting, ctx, add)

    _check_text_numbers(out, ctx, add)
    _check_safety_first(out, cited_ok, ctx, add)

    if out.top_fault_id is not None:
        words = out.cue.split()
        if not words:
            add("missing_cue", "a cue for the next set is required with the top fix")
        elif len(words) > MAX_CUE_WORDS:
            add("cue_too_long", f"cue has {len(words)} words; the limit is {MAX_CUE_WORDS}")

    for text in (out.cue, out.explanation, out.professional_recommendation):
        for phrase in find_medical_language(text):
            add("medical_language", f'feedback contains medical or injury-prediction language: "{phrase}"')

    if ctx.note_mentions_pain and not _PROFESSIONAL.search(out.professional_recommendation or ""):
        add("missing_referral",
            "the lifter mentioned pain, so professional_recommendation must recommend seeing a doctor or physical therapist")

    return ValidationResult(issues=issues, output=out)


def _check_reps(fault, reps, ctx, add):
    if not reps:
        add("fault_not_confirmed", f"{fault.short_name} must cite at least one rep")
    for r in reps:
        if not 1 <= r <= ctx.rep_count:
            add("rep_out_of_range", f"rep {r} cited for {fault.short_name}, but only {ctx.rep_count} reps were detected")
            continue
        value = ctx.reps[r - 1].metrics.get(fault.metric)
        if value is None:
            add("fault_not_confirmed", f"{fault.short_name} cited on rep {r}, but {fault.metric_label} wasn't measured on that rep")
        elif not fault.is_confirmed(value):
            add("fault_not_confirmed", f"{fault.short_name} cited on rep {r}, but measured {fault.metric_label} is "
                                       f"{fault.format_value(value)} (threshold {fault.format_value(fault.threshold)})")


def _check_supporting(fault, reps, s, ctx, add):
    if s is None:
        add("number_mismatch", f"{fault.short_name} needs a supporting measurement")
        return
    if s.metric != fault.metric:
        add("number_mismatch", f"supporting measurement for {fault.short_name} must be {fault.metric}, not {s.metric}")
        return
    if s.rep not in reps or not 1 <= s.rep <= ctx.rep_count:
        add("number_mismatch", f"supporting measurement is from rep {s.rep}, which isn't a cited rep for {fault.short_name}")
        return
    measured = ctx.reps[s.rep - 1].metrics.get(fault.metric)
    tolerance = DEGREE_TOLERANCE if fault.unit == "°" else RATIO_TOLERANCE
    if measured is None or abs(s.value - measured) > tolerance:
        shown = "not measured" if measured is None else f"{measured:.1f}"
        add("number_mismatch", f"supporting measurement says {fault.metric_label} is {s.value:g} on rep {s.rep}, "
                               f"but the measured value is {shown}")


def _check_text_numbers(out, ctx, add):
    angles = [v for r in ctx.reps for v in r.metrics.values() if v is not None]
    text = " ".join(t for t in (out.cue, out.explanation, out.professional_recommendation) if t)
    for m in _DEGREES.finditer(text):
        if not any(abs(float(m.group(1)) - a) <= DEGREE_TOLERANCE for a in angles):
            add("number_mismatch", f"text mentions {m.group(1)}°, which doesn't match any measured angle")
    for m in _REP_REF.finditer(text):
        n = int(m.group(1))
        if not 1 <= n <= ctx.rep_count:
            add("number_mismatch", f"text mentions rep {n}, but only {ctx.rep_count} reps were detected")
    for m in _REP_TOTAL.finditer(text):
        n = int(m.group(2))
        if n > ctx.rep_count or (m.group(1) and n != ctx.rep_count):
            add("number_mismatch", f"text mentions {n} reps, but {ctx.rep_count} were detected")


def _check_safety_first(out, cited, ctx, add):
    safety = [f for f in (get_fault(ctx.lift, fid) for fid in ctx.confirmed) if f and f.safety]
    safety += [f for f in cited if f.safety and f not in safety]
    top = get_fault(ctx.lift, out.top_fault_id) if out.top_fault_id else None
    if safety and not (top and top.safety):
        for f in safety:
            add("safety_order", f"{f.short_name} is a safety fault and must be the top fix")
