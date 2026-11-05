"""US-06: Measure my reps, angles, depth and bar path."""
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from app.measure import (bar_drift_ratio, bar_path_x, classify_camera_angle, count_reps, detect_lift,
                         height_signal, joint_angle, measure_set, squat_depth_reached, torso_lean_deg)
from app.pose import LANDMARK_NAMES, MediaPipePoseEstimator
from app.testing.synthetic import RepSpec, SetSpec, make_frames, squat
from tests.helpers import signup, upload_ok

LABELED = Path(__file__).parent / "fixtures" / "labeled_videos"


# ---- [unit] MediaPipe returns x, y and confidence for every landmark on every frame ----

class FakeLandmarker:
    """Stands in for mediapipe.tasks.vision.PoseLandmarker in VIDEO mode."""

    def __init__(self, people_on_frames):
        self.people_on_frames = people_on_frames
        self.timestamps = []

    def detect_for_video(self, image, timestamp_ms):
        n = len(self.timestamps)
        self.timestamps.append(timestamp_ms)
        if n not in self.people_on_frames:
            return SimpleNamespace(pose_landmarks=[])
        marks = [SimpleNamespace(x=0.01 * i, y=0.02 * i, z=0.0, visibility=0.9 - 0.01 * i, presence=0.99)
                 for i in range(33)]
        return SimpleNamespace(pose_landmarks=[marks])


def _video(n):
    return [np.zeros((48, 64, 3), dtype=np.uint8) for _ in range(n)]


def test_us06_pose_returns_xy_and_confidence_for_every_landmark_on_every_frame():
    estimator = MediaPipePoseEstimator(landmarker=FakeLandmarker({0, 1, 2, 3}))
    frames = estimator.estimate(_video(4), fps=30)
    assert len(frames) == 4
    for f in frames:
        assert list(f.landmarks) == LANDMARK_NAMES
        assert len(f.landmarks) == 33
        knee = f.landmarks["left_knee"]
        assert knee.x == pytest.approx(0.25) and knee.y == pytest.approx(0.5)
        assert knee.confidence == pytest.approx(0.65)


def test_us06_pose_frame_without_a_person_has_no_landmarks():
    frames = MediaPipePoseEstimator(landmarker=FakeLandmarker({1})).estimate(_video(3), fps=30)
    assert [f.landmarks is None for f in frames] == [True, False, True]


def test_us06_pose_frames_are_timestamped_in_order():
    landmarker = FakeLandmarker({0, 1, 2})
    frames = MediaPipePoseEstimator(landmarker=landmarker).estimate(_video(3), fps=30)
    assert landmarker.timestamps == [0, 33, 67]
    assert [f.index for f in frames] == [0, 1, 2]
    assert [f.timestamp for f in frames] == pytest.approx([0, 1 / 30, 2 / 30])


def test_us06_landmark_names_follow_mediapipe_order():
    assert len(LANDMARK_NAMES) == 33
    assert LANDMARK_NAMES[11:13] == ["left_shoulder", "right_shoulder"]
    assert LANDMARK_NAMES[23:29] == ["left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle"]


# ---- [unit] joint angles within ±1° of a hand-calculated value ----

@pytest.mark.parametrize("a,b,c,expected", [
    ((0, 0), (1, 0), (1, 1), 90.0),
    ((0.5, 0.5), (0.6, 0.7), (0.5, 0.9), 126.87),   # cos = -0.6
    ((0, 0), (1, 0), (2, 0), 180.0),
    ((1, 1), (0, 0), (1, 0), 45.0),
    ((0.2, 0.3), (0.2, 0.3 + 1e-9), (0.2, 0.9), 180.0),
])
def test_us06_joint_angle_matches_hand_calculation(a, b, c, expected):
    assert joint_angle(a, b, c) == pytest.approx(expected, abs=1.0)


def test_us06_joint_angle_of_coincident_points_is_nan():
    assert math.isnan(joint_angle((0.5, 0.5), (0.5, 0.5), (0.6, 0.6)))


@pytest.mark.parametrize("shoulder,hip,expected", [
    ((0.5, 0.2), (0.5, 0.5), 0.0),
    ((0.6, 0.2), (0.5, 0.5), 18.43),
    ((0.4, 0.2), (0.5, 0.5), 18.43),
    ((0.8, 0.5), (0.5, 0.5), 90.0),
])
def test_us06_torso_lean_from_vertical(shoulder, hip, expected):
    assert torso_lean_deg(shoulder, hip) == pytest.approx(expected, abs=1.0)


def test_us06_squat_angles_at_the_bottom_match_hand_calculation():
    # Synthetic bottom position: shin 35° and thigh 100° from vertical, torso balanced over the ankle.
    # Knee angle = 180 - (35 + 100) = 45°. Hip x = 0.5 + 0.2 sin35 - 0.2 sin100 = 0.4178, so
    # torso lean = asin(0.0822 / 0.3) = 15.9° and the shoulder-hip-knee angle is 64.1°.
    frames = squat(1)
    rep = measure_set(frames, "squat", fps=30).reps[0]
    assert rep.metrics["knee_angle_min_deg"] == pytest.approx(45.0, abs=1.0)
    assert rep.metrics["hip_angle_min_deg"] == pytest.approx(64.1, abs=1.0)
    bottom = frames[rep.turn_frame].landmarks
    assert torso_lean_deg(bottom["left_shoulder"], bottom["left_hip"]) == pytest.approx(15.9, abs=1.0)
    # The max lean happens mid-descent, so it's at least the bottom value.
    assert rep.metrics["torso_lean_max_deg"] >= 15.9 - 1.0


# ---- [unit] rep counting from the hip (squat, deadlift) or wrist (bench) height signal ----

@pytest.mark.parametrize("lift,n", [("squat", 1), ("squat", 3), ("squat", 8), ("deadlift", 3), ("bench_press", 5)])
def test_us06_rep_count_matches_true_count(lift, n):
    frames = make_frames(SetSpec(lift=lift, reps=[RepSpec() for _ in range(n)]))
    assert measure_set(frames, lift, fps=30).rep_count == n


def test_us06_reps_are_ordered_and_do_not_overlap():
    reps = measure_set(squat(4), "squat", fps=30).reps
    assert [r.rep for r in reps] == [1, 2, 3, 4]
    for r in reps:
        assert r.start_frame < r.turn_frame < r.end_frame
        assert r.start_time < r.end_time
    for a, b in zip(reps, reps[1:]):
        assert a.end_frame <= b.start_frame


def _mid_y(f, joint):
    return (f.landmarks[f"left_{joint}"].y + f.landmarks[f"right_{joint}"].y) / 2


def test_us06_height_signal_is_hips_above_ankles_for_squat_and_deadlift_and_wrists_above_shoulders_for_bench():
    # Measured from a body reference, not the frame edge, so a moving camera doesn't shift it.
    frames = squat(1)
    f = frames[40]
    assert height_signal(frames, "squat")[40] == pytest.approx(_mid_y(f, "ankle") - _mid_y(f, "hip"))
    assert height_signal(frames, "deadlift")[40] == pytest.approx(_mid_y(f, "ankle") - _mid_y(f, "hip"))
    assert height_signal(frames, "bench_press")[40] == pytest.approx(_mid_y(f, "shoulder") - _mid_y(f, "wrist"))


def test_us06_height_signal_falls_back_to_hip_height_when_the_feet_are_out_of_frame():
    frames = make_frames(SetSpec(reps=[RepSpec() for _ in range(3)], low_confidence={"ankles": 1.0}))
    f = frames[40]
    assert height_signal(frames, "squat")[40] == pytest.approx(1 - _mid_y(f, "hip"))
    assert measure_set(frames, "squat", fps=30).rep_count == 3


def _drift(frames, total):
    """Moves the whole body up the frame by `total` over the set, like a phone tilting while it records."""
    from app.pose import Landmark, PoseFrame

    n = len(frames)
    return [PoseFrame(f.index, f.timestamp, {k: Landmark(v.x, v.y - total * i / n, v.confidence)
                                             for k, v in f.landmarks.items()} if f.landmarks else None)
            for i, f in enumerate(frames)]


def _shrink(frames, final_scale):
    """Shrinks the body about the frame center over the set, like the lifter drifting away from the phone."""
    from app.pose import Landmark, PoseFrame

    n = len(frames)
    out = []
    for i, f in enumerate(frames):
        k = 1 + (final_scale - 1) * i / n
        out.append(PoseFrame(f.index, f.timestamp, {name: Landmark(0.5 + (v.x - 0.5) * k, 0.5 + (v.y - 0.5) * k,
                                                                   v.confidence)
                                                    for name, v in f.landmarks.items()} if f.landmarks else None))
    return out


@pytest.mark.parametrize("lift", ["squat", "deadlift", "bench_press"])
def test_us06_rep_count_survives_the_lifter_moving_away_from_the_camera(lift):
    # The body ends 25% smaller in the frame (the real clip that found the bug changed by about 7%). Past ~30%
    # a deadlift's shrinking reps no longer drop half the set's range, so that's outside what's supported.
    frames = _shrink(make_frames(SetSpec(lift=lift, reps=[RepSpec() for _ in range(3)])), 0.75)
    assert measure_set(frames, lift, fps=30).rep_count == 3


@pytest.mark.parametrize("lift", ["squat", "deadlift", "bench_press"])
def test_us06_rep_count_survives_the_camera_drifting(lift):
    # Found in manual testing: a 3-rep squat filmed on a slowly tilting phone was counted as 1 rep.
    frames = _drift(make_frames(SetSpec(lift=lift, reps=[RepSpec() for _ in range(3)])), 0.25)
    assert measure_set(frames, lift, fps=30).rep_count == 3


def test_us06_count_reps_on_a_clean_signal():
    t = np.linspace(0, 4 * 2 * np.pi, 400)
    signal = 0.5 + 0.1 * np.cos(t)          # starts high, four dips
    assert len(count_reps(signal, rest="high")) == 4


def test_us06_count_reps_ignores_noise_and_small_wiggles():
    rng = np.random.default_rng(0)
    t = np.linspace(0, 3 * 2 * np.pi, 300)
    noisy = 0.5 + 0.1 * np.cos(t) + rng.normal(0, 0.005, t.size)
    assert len(count_reps(noisy, rest="high")) == 3
    assert count_reps(0.5 + 0.004 * np.cos(t), rest="high") == []
    assert count_reps(np.full(100, 0.5), rest="high") == []


def test_us06_count_reps_for_lifts_that_start_at_the_bottom():
    t = np.linspace(0, 2 * 2 * np.pi, 200)
    deadlift_hip_height = 0.5 - 0.1 * np.cos(t)   # starts low (bar on the floor), two pulls
    assert len(count_reps(deadlift_hip_height, rest="low")) == 2


def test_us06_count_reps_tolerates_missing_frames():
    t = np.linspace(0, 2 * 2 * np.pi, 200)
    signal = 0.5 + 0.1 * np.cos(t)
    signal[50:55] = np.nan
    assert len(count_reps(signal, rest="high")) == 2


def _labeled():
    labels = LABELED / "labels.json"
    return json.loads(labels.read_text()) if labels.exists() else []


@pytest.mark.parametrize("item", _labeled() or [None], ids=lambda i: i["file"] if i else "none")
def test_us06_rep_count_matches_labeled_test_videos(item):
    if item is None:
        pytest.skip("add the team's labeled videos to tests/fixtures/labeled_videos/labels.json")
    from app.video import OpenCVMediaPipeBackend

    backend = OpenCVMediaPipeBackend()
    path = str(LABELED / item["file"])
    info = backend.probe(path)
    frames = backend.poses(path, info, item["file"])
    assert measure_set(frames, item["lift"], fps=info.fps).rep_count == item["reps"]


# ---- [unit] squat depth: hip below the knee at the bottom ----

def test_us06_depth_reached_only_when_hip_below_knee():
    assert squat_depth_reached(hip=(0.5, 0.75), knee=(0.6, 0.72)) is True
    assert squat_depth_reached(hip=(0.5, 0.70), knee=(0.6, 0.72)) is False
    assert squat_depth_reached(hip=(0.5, 0.72), knee=(0.6, 0.72)) is False  # level is not below


def test_us06_depth_marked_per_rep():
    frames = squat(3, depth_deg={2: 70})
    reps = measure_set(frames, "squat", fps=30).reps
    assert [r.depth_reached for r in reps] == [True, False, True]
    assert reps[0].metrics["depth_margin"] > 0 > reps[1].metrics["depth_margin"]


def test_us06_depth_is_only_marked_for_squats():
    frames = make_frames(SetSpec(lift="deadlift", reps=[RepSpec()]))
    assert measure_set(frames, "deadlift", fps=30).reps[0].depth_reached is None


# ---- [unit] bar path: wrist midpoint (bench, deadlift) or shoulder midpoint (squat), drift / thigh length ----

def test_us06_bar_path_uses_the_right_landmarks():
    frames = squat(1)
    f = frames[30].landmarks
    assert bar_path_x(frames, "squat")[30] == pytest.approx((f["left_shoulder"].x + f["right_shoulder"].x) / 2)
    assert bar_path_x(frames, "bench_press")[30] == pytest.approx((f["left_wrist"].x + f["right_wrist"].x) / 2)
    assert bar_path_x(frames, "deadlift")[30] == pytest.approx((f["left_wrist"].x + f["right_wrist"].x) / 2)


def test_us06_bar_drift_is_divided_by_thigh_length():
    assert bar_drift_ratio(np.array([0.50, 0.55, 0.53]), thigh_length=0.2) == pytest.approx(0.25)
    assert bar_drift_ratio(np.array([0.5, 0.5]), thigh_length=0.2) == 0.0


def test_us06_bar_drift_measured_per_rep():
    reps = measure_set(squat(3, bar_drift={2: 0.06}), "squat", fps=30).reps
    assert reps[1].metrics["bar_drift_ratio"] == pytest.approx(0.30, abs=0.03)
    assert reps[0].metrics["bar_drift_ratio"] < 0.05


# ---- [unit] camera angle ----

@pytest.mark.parametrize("view", ["side", "front", "angled"])
def test_us06_camera_angle_classified(view):
    frames = make_frames(SetSpec(view=view, reps=[RepSpec(), RepSpec()]))
    assert classify_camera_angle(frames) == view


def _turn(frames, half_gap):
    """Spreads each left/right landmark pair `half_gap` apart sideways, like a lifter turned slightly to the phone."""
    from app.pose import Landmark, PoseFrame

    def moved(name, v):
        dx = half_gap if name.startswith("left_") else -half_gap if name.startswith("right_") else 0.0
        return Landmark(v.x + dx, v.y, v.confidence)

    return [PoseFrame(f.index, f.timestamp, {k: moved(k, v) for k, v in f.landmarks.items()} if f.landmarks else None)
            for f in frames]


def test_us06_a_slightly_turned_side_view_is_still_side():
    # Found in manual testing: a real side view (MediaPipe width ratio about 0.19) was classified as angled, so
    # every side-view check, including hips rising early, was skipped.
    frames = _turn(make_frames(SetSpec(reps=[RepSpec(), RepSpec()])), 0.035)  # width ratio ~0.20
    assert classify_camera_angle(frames) == "side"


def test_us06_hips_rising_early_is_caught_on_a_slightly_turned_side_view():
    from app.rules import confirm_faults, not_measured_checks

    frames = _turn(squat(3, torso_bump={1: 20, 2: 20, 3: 20}), 0.035)
    m = measure_set(frames, "squat", fps=30)
    assert confirm_faults(m, not_measured_checks(m))["hips_rise_early"] == [1, 2, 3]


def test_us06_bench_from_the_side_is_side():
    frames = make_frames(SetSpec(lift="bench_press", reps=[RepSpec()]))
    assert classify_camera_angle(frames) == "side"


@pytest.mark.parametrize("lift", ["squat", "deadlift", "bench_press"])
def test_us06_detects_the_movement(lift):
    frames = make_frames(SetSpec(lift=lift, reps=[RepSpec(), RepSpec()]))
    assert detect_lift(frames) == lift


# ---- [integration] measurements are saved per rep and linked to the analysis ----

def test_us06_measurements_saved_per_rep(client, services):
    headers, _ = signup(client)
    analysis_id = upload_ok(client, headers, filename="clean.mp4")
    saved = services.repo.list_rep_measurements(analysis_id)
    assert [r.rep for r in saved] == [1, 2, 3, 4, 5]
    assert all("knee_angle_min_deg" in r.metrics for r in saved)
    assert services.repo.get_analysis(analysis_id).rep_count == 5
    assert services.repo.list_rep_measurements("some-other-analysis") == []


# ---- the OpenCV + MediaPipe video backend on a real (generated) video file ----

def _clip(tmp_path, seconds=2, fps=60):
    import cv2

    path = str(tmp_path / "clip.mp4")
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (1280, 720))
    for i in range(seconds * fps):
        writer.write(np.full((720, 1280, 3), i % 255, np.uint8))
    writer.release()
    return path


def test_us06_video_backend_probes_duration_and_fps(tmp_path):
    from app.video import OpenCVMediaPipeBackend

    info = OpenCVMediaPipeBackend().probe(_clip(tmp_path))
    assert info.fps == pytest.approx(60)
    assert info.duration == pytest.approx(2.0, abs=0.05)
    assert (info.width, info.height) == (1280, 720)


def test_us06_video_backend_rejects_files_that_are_not_video(tmp_path):
    from app.video import VideoUnreadable, probe_video

    bad = tmp_path / "notes.mp4"
    bad.write_bytes(b"definitely not a video")
    with pytest.raises(VideoUnreadable):
        probe_video(str(bad))


def test_us06_video_backend_samples_about_30_fps_and_keeps_original_frame_numbers(tmp_path):
    from app.video import MAX_POSE_WIDTH, OpenCVMediaPipeBackend

    seen_widths = []
    landmarker = FakeLandmarker(set(range(1000)))
    estimator = MediaPipePoseEstimator(landmarker=landmarker, image_factory=lambda img: seen_widths.append(img.shape[1]) or img)
    backend = OpenCVMediaPipeBackend(estimator=estimator)
    path = _clip(tmp_path)
    frames = backend.poses(path, backend.probe(path), "clip.mp4")
    assert len(frames) == 60                      # 120 frames at 60 fps -> every 2nd frame
    assert [f.index for f in frames[:3]] == [0, 2, 4]
    assert frames[1].timestamp == pytest.approx(2 / 60)
    assert set(seen_widths) == {MAX_POSE_WIDTH}   # downscaled before pose estimation
    assert backend.frame(path, 10).shape == (720, 1280, 3)


def test_us06_video_backend_needs_a_pose_model_for_real_runs():
    with pytest.raises(RuntimeError, match="POSE_MODEL_PATH"):
        MediaPipePoseEstimator().estimate([np.zeros((10, 10, 3), np.uint8)], fps=30)
