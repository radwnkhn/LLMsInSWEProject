"""US-11: Annotated frame showing where the fault happened. (Tap-to-play: frontend/e2e/us11-frame.spec.ts.)"""
import numpy as np
import pytest

from app.annotate import draw_annotation, measurement_label, select_annotation_frame
from app.faults import get_fault
from app.measure import measure_set, torso_lean_deg
from app.pipeline import analyze_set
from app.testing.fakes import RuleFollowingLLM
from app.testing.synthetic import squat
from tests.helpers import signup, upload_ok

H, W = 360, 640


def blank(_i):
    return np.zeros((H, W, 3), np.uint8)


def _mid(lm, name):
    return ((lm[f"left_{name}"].x + lm[f"right_{name}"].x) / 2, (lm[f"left_{name}"].y + lm[f"right_{name}"].y) / 2)


# ---- [unit] frame from the cited rep at the worst moment ----

def test_us11_frame_is_the_worst_moment_of_the_cited_rep():
    frames = squat(5, torso_bump={3: 25})
    rep = measure_set(frames, "squat", fps=30).reps[2]
    index = select_annotation_frame(rep, "torso_lean_increase_deg")
    assert rep.start_frame <= index <= rep.end_frame
    # Hand check: the worst moment is when the torso leans the most on the way up.
    ascent = range(rep.turn_frame, rep.end_frame + 1)
    leans = {i: torso_lean_deg(_mid(frames[i].landmarks, "shoulder"), _mid(frames[i].landmarks, "hip")) for i in ascent}
    assert index == max(leans, key=leans.get)


def test_us11_depth_frame_is_the_bottom_of_the_rep():
    rep = measure_set(squat(2, depth_deg={1: 70}), "squat", fps=30).reps[0]
    assert select_annotation_frame(rep, "depth_margin") == rep.turn_frame


# ---- [unit] skeleton and measurement label drawn on the frame ----

def test_us11_skeleton_and_label_are_drawn():
    frame = squat(1)[40]
    image = np.zeros((H, W, 3), np.uint8)
    out = draw_annotation(image, frame.landmarks, "Torso +14°")
    assert out.shape == image.shape
    assert not image.any(), "the original frame must not be modified"
    sx, sy = _mid(frame.landmarks, "shoulder")
    hx, hy = _mid(frame.landmarks, "hip")
    px, py = int((sx + hx) / 2 * W), int((sy + hy) / 2 * H)
    assert out[py - 2:py + 3, px - 2:px + 3].any(), "torso line of the skeleton not drawn"
    assert out[:48, :].any(), "measurement label not drawn"


@pytest.mark.parametrize("lift,fault_id,value,label", [
    ("squat", "hips_rise_early", 14.2, "Torso +14°"),
    ("squat", "knee_cave", 12.6, "Valgus 13°"),
    ("deadlift", "incomplete_lockout", 158.0, "Hip 158°"),
    ("squat", "bar_path_drift", 0.314, "Bar drift 0.31"),
])
def test_us11_measurement_label(lift, fault_id, value, label):
    assert measurement_label(get_fault(lift, fault_id), value) == label


# ---- [unit] rep number, timestamp and measurement equal the stored values ----

def test_us11_annotation_matches_stored_measurements():
    frames = squat(5, torso_bump={4: 25, 5: 25})
    outcome = analyze_set(frames, "squat", note=None, llm=RuleFollowingLLM(), fps=30, frame_loader=blank)
    meta = outcome.annotation
    cited = outcome.output.supporting_measurement
    assert meta.rep == cited.rep
    assert meta.fault_id == outcome.output.top_fault_id
    stored = outcome.measurements.reps[meta.rep - 1]
    assert meta.value == stored.metrics[meta.metric]
    assert meta.frame_index == stored.worst_frames[meta.metric]
    assert meta.timestamp == frames[meta.frame_index].timestamp
    assert meta.label == measurement_label(get_fault("squat", meta.fault_id), meta.value)
    assert outcome.annotated_png.startswith(b"\x89PNG")


def test_us11_no_annotation_without_a_top_fault():
    outcome = analyze_set(squat(3), "squat", note=None, llm=RuleFollowingLLM(), fps=30, frame_loader=blank)
    assert outcome.annotation is None and outcome.annotated_png is None


def test_us11_api_annotation_equals_stored_values(client, services):
    headers, _ = signup(client)
    analysis_id = upload_ok(client, headers)
    frame = client.get(f"/analyses/{analysis_id}", headers=headers).json()["annotated_frame"]
    stored = services.repo.list_rep_measurements(analysis_id)[frame["rep"] - 1]
    assert frame["value"] == stored.metrics[frame["metric"]]
    assert frame["frame_index"] == stored.worst_frames[frame["metric"]]
    assert frame["rep_start_time"] == stored.start_time
    assert frame["image_url"]
