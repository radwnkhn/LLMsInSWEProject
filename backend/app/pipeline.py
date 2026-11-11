"""The analysis pipeline: measure -> decide if analyzable -> LLM with validation and correction -> annotate."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np

from app.analyzability import check_analyzable
from app.annotate import AnnotationMeta, draw_annotation, encode_png, measurement_label, select_annotation_frame
from app.correction import CorrectionResult, run_correction_loop
from app.faults import DEFAULT_CATALOG, FaultCatalog
from app.llm.client import KeyFrame, LLMClient
from app.llm.prompt import build_llm_request, encode_jpeg, select_key_frames
from app.llm.schema import CoachOutput
from app.measure import SetMeasurements, measure_set
from app.pose import PoseFrame
from app.rules import NotMeasured, confirm_faults, not_measured_checks
from app.validator import build_validation_context

FrameLoader = Callable[[int], np.ndarray]


def _blank(_index: int) -> np.ndarray:
    return np.zeros((360, 640, 3), np.uint8)


@dataclass
class AnalysisOutcome:
    final_status: str                       # passed_first_try | passed_after_retry | fallback | unanalyzable
    measurements: SetMeasurements
    unanalyzable_reason: str | None = None
    not_measured: list[NotMeasured] = field(default_factory=list)
    confirmed: dict[str, list[int]] = field(default_factory=dict)
    correction: CorrectionResult | None = None
    output: CoachOutput | None = None
    annotation: AnnotationMeta | None = None
    annotated_png: bytes | None = None
    key_frame_indices: list[int] = field(default_factory=list)
    catalog: FaultCatalog = DEFAULT_CATALOG


def analyze_set(frames: Sequence[PoseFrame], lift: str, note: str | None, llm: LLMClient, fps: float,
                frame_loader: FrameLoader | None = None,
                on_stage: Callable[[str], None] | None = None,
                catalog: FaultCatalog | None = None) -> AnalysisOutcome:
    """`catalog` is the saved fault list when the analysis started (defaults to the Alpha list)."""
    catalog = catalog or DEFAULT_CATALOG
    frames = list(frames)
    load = frame_loader or _blank
    m = measure_set(frames, lift, fps)
    reason = check_analyzable(frames, m.rep_count)
    if reason:
        return AnalysisOutcome(final_status="unanalyzable", measurements=m, unanalyzable_reason=reason, catalog=catalog)

    not_measured = not_measured_checks(m, catalog)
    confirmed = confirm_faults(m, not_measured, catalog)
    ctx = build_validation_context(m, not_measured, confirmed, note, catalog)
    by_index = {f.index: f for f in frames}
    picks = select_key_frames(m, confirmed, [f.index for f in frames], catalog)
    key_frames = [KeyFrame(i, by_index[i].timestamp, rep, encode_jpeg(load(i))) for i, rep in picks]
    correction = run_correction_loop(llm, build_llm_request(m, not_measured, confirmed, note, key_frames, catalog), ctx,
                                     on_stage=on_stage)

    outcome = AnalysisOutcome(final_status=correction.status, measurements=m, not_measured=not_measured,
                              confirmed=confirmed, correction=correction, output=correction.output,
                              key_frame_indices=[i for i, _ in picks], catalog=catalog)
    out = correction.output
    if out and out.top_fault_id and out.supporting_measurement:
        fault = catalog.get(ctx.lift, out.top_fault_id)
        rep = m.reps[out.supporting_measurement.rep - 1]
        index = select_annotation_frame(rep, fault.metric)
        value = rep.metrics[fault.metric]
        label = measurement_label(fault, value)
        outcome.annotation = AnnotationMeta(fault_id=fault.id, rep=rep.rep, frame_index=index,
                                            timestamp=by_index[index].timestamp, rep_start_time=rep.start_time,
                                            metric=fault.metric, value=value, label=label)
        outcome.annotated_png = encode_png(draw_annotation(load(index), by_index[index].landmarks, label))
    return outcome
