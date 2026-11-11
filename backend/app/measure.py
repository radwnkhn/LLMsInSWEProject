"""Measurements from pose frames: joint angles, reps, depth, bar path and camera angle.

All coordinates are normalized image coordinates (x right, y down). Plain NumPy; no AI.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from app.pose import Landmark, PoseFrame

CONFIDENCE_THRESHOLD = 0.5
HANDS_AT_SHOULDERS = 0.5  # hands_at_shoulders, in torso lengths (a bar on the back measures about 0.1-0.3)
SIDE_MAX_RATIO = 0.25  # classify_camera_angle: shoulder/hip width over torso length below this is a side view
GROUPS = {
    "shoulders": ("left_shoulder", "right_shoulder"),
    "elbows": ("left_elbow", "right_elbow"),
    "wrists": ("left_wrist", "right_wrist"),
    "hips": ("left_hip", "right_hip"),
    "knees": ("left_knee", "right_knee"),
    "ankles": ("left_ankle", "right_ankle"),
    "ears": ("left_ear", "right_ear"),
}
KEY_GROUPS = ("hips", "knees", "ankles", "shoulders")
# Which way the rep signal sits between reps: squat and bench start at the top, deadlift on the floor.
# US-28: the overhead press rests with the bar racked at the shoulders (low); the Romanian deadlift's hinge
# signal rests standing tall (high).
REST_POSITION = {"squat": "high", "deadlift": "low", "bench_press": "high", "overhead_press": "low",
                 "romanian_deadlift": "high"}
OVERHEAD_WRISTS = -1.5      # detect_lift: wrists this many torso lengths above the hips (0.5 above the shoulders)
OVERHEAD_SHARE = 0.10       # ... on at least this share of frames reads as pressing overhead
RDL_MIN_HINGE_DEG = 20.0    # count_reps: a Romanian deadlift rep must hinge at least this much at the hip

Point = tuple[float, float]


@dataclass(frozen=True)
class RepSegment:
    start: int
    turn: int   # bottom of a squat or bench rep, lockout of a deadlift
    end: int


@dataclass
class RepMeasurement:
    rep: int
    start_frame: int
    turn_frame: int
    end_frame: int
    start_time: float
    end_time: float
    metrics: dict[str, float | None] = field(default_factory=dict)
    worst_frames: dict[str, int] = field(default_factory=dict)
    depth_reached: bool | None = None

    def to_dict(self) -> dict:
        return {"rep": self.rep, "start_frame": self.start_frame, "turn_frame": self.turn_frame,
                "end_frame": self.end_frame, "start_time": self.start_time, "end_time": self.end_time,
                "metrics": dict(self.metrics), "worst_frames": dict(self.worst_frames),
                "depth_reached": self.depth_reached}

    @classmethod
    def from_dict(cls, d: dict) -> "RepMeasurement":
        return cls(**{k: d[k] for k in ("rep", "start_frame", "turn_frame", "end_frame", "start_time", "end_time")},
                   metrics=dict(d.get("metrics") or {}), worst_frames={k: int(v) for k, v in (d.get("worst_frames") or {}).items()},
                   depth_reached=d.get("depth_reached"))

    def to_view(self) -> dict:
        return {"rep": self.rep, "start_time": self.start_time, "end_time": self.end_time,
                "metrics": dict(self.metrics), "depth_reached": self.depth_reached}


@dataclass
class SetMeasurements:
    lift: str
    detected_lift: str | None
    camera_angle: str
    fps: float
    reps: list[RepMeasurement]
    low_confidence_groups: frozenset[str]
    frame_count: int
    thigh_length: float | None
    holds_bar: bool = True  # squat: hands at the shoulders, as with a bar on the back (see hands_at_shoulders)

    @property
    def rep_count(self) -> int:
        return len(self.reps)

    @property
    def analysis_lift(self) -> str:
        """The lift the feedback describes: the one the lifter selected, unless detection disagrees on lying down
        vs standing (a bench set uploaded as a squat). Detection can't reliably tell a squat from a deadlift
        (goblet, front and bodyweight squats hold the hands low), so the selection wins there."""
        d = self.detected_lift
        if d is not None and (d == "bench_press") != (self.lift == "bench_press"):
            return d
        # US-28: arms locked out overhead is unmistakable, so it wins over another standing lift. Romanian vs
        # conventional deadlift can't be told apart from pose alone, so the selection wins there too.
        if d == "overhead_press" and self.lift != "overhead_press":
            return d
        return self.lift


# ---------------------------------------------------------------- geometry

def _xy(p) -> Point:
    return (p.x, p.y) if isinstance(p, Landmark) else (float(p[0]), float(p[1]))


def joint_angle(a, b, c) -> float:
    """Angle ABC in degrees (0-180). NaN if a point coincides with the vertex."""
    ax, ay = _xy(a)
    bx, by = _xy(b)
    cx, cy = _xy(c)
    v1, v2 = (ax - bx, ay - by), (cx - bx, cy - by)
    n1, n2 = math.hypot(*v1), math.hypot(*v2)
    if n1 < 1e-12 or n2 < 1e-12:
        return float("nan")
    cos = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


def torso_lean_deg(shoulder, hip) -> float:
    """Angle of the hip-to-shoulder line from vertical, in degrees (0 = upright, 90 = horizontal)."""
    sx, sy = _xy(shoulder)
    hx, hy = _xy(hip)
    return math.degrees(math.atan2(abs(sx - hx), hy - sy))


def squat_depth_reached(hip, knee) -> bool:
    """Depth is reached when the hip is below the knee (larger y in image coordinates)."""
    return _xy(hip)[1] > _xy(knee)[1]


def bar_drift_ratio(xs: np.ndarray, thigh_length: float) -> float:
    """Forward/back range of the bar divided by thigh length."""
    xs = np.asarray(xs, dtype=float)
    if not np.isfinite(xs).any() or not thigh_length:
        return 0.0
    return float((np.nanmax(xs) - np.nanmin(xs)) / thigh_length)


# ---------------------------------------------------------------- per-frame helpers

def group_confidence(frame: PoseFrame, group: str) -> float:
    """Confidence of a joint group: the better-seen side (from the side, one side is always hidden)."""
    if not frame.landmarks:
        return 0.0
    left, right = GROUPS[group]
    return max(frame.landmarks[left].confidence, frame.landmarks[right].confidence)


def low_confidence_groups(frames: Sequence[PoseFrame]) -> frozenset[str]:
    """Groups below the confidence threshold on more than half the frames."""
    if not frames:
        return frozenset(GROUPS)
    low = set()
    for group in GROUPS:
        bad = sum(1 for f in frames if group_confidence(f, group) < CONFIDENCE_THRESHOLD)
        if bad > len(frames) / 2:
            low.add(group)
    return frozenset(low)


def _mid(frame: PoseFrame, group: str) -> Point | None:
    if not frame.landmarks:
        return None
    left, right = (frame.landmarks[n] for n in GROUPS[group])
    return ((left.x + right.x) / 2, (left.y + right.y) / 2)


def _side_point(frame: PoseFrame, side: str, joint: str) -> Point | None:
    if not frame.landmarks:
        return None
    lm = frame.landmarks[f"{side}_{joint}"]
    return (lm.x, lm.y)


def _visible_side(frames: Sequence[PoseFrame]) -> str:
    totals = {"left": 0.0, "right": 0.0}
    for f in frames:
        if f.landmarks:
            for side in totals:
                totals[side] += sum(f.landmarks[f"{side}_{j}"].confidence for j in ("shoulder", "hip", "knee", "ankle"))
    return "right" if totals["right"] > totals["left"] else "left"


def _series(frames: Sequence[PoseFrame], fn) -> np.ndarray:
    out = np.full(len(frames), np.nan)
    for i, f in enumerate(frames):
        if f.landmarks:
            v = fn(f)
            if v is not None:
                out[i] = v
    return out


def height_signal(frames: Sequence[PoseFrame], lift: str) -> np.ndarray:
    """Height of the hip midpoint above the ankles (squat, deadlift) or of the wrists above the shoulders (bench).

    Measuring from the body rather than the frame edge cancels a phone tilting or sliding while it records. (The
    lifter moving nearer or farther still scales it slowly; count_reps compares each rep with the standing height
    just before it, so that's tolerated.) When the reference joints are hidden on most frames (feet out of shot),
    falls back to height in the frame (1 - y). NaN where unseen.
    """
    group, reference = ("wrists", "shoulders") if lift in ("bench_press", "overhead_press") else ("hips", "ankles")

    def seen(f, g):
        return group_confidence(f, g) >= CONFIDENCE_THRESHOLD

    def relative(f):
        return _mid(f, reference)[1] - _mid(f, group)[1] if seen(f, group) and seen(f, reference) else None

    def absolute(f):
        return 1 - _mid(f, group)[1] if seen(f, group) else None

    with_reference = sum(1 for f in frames if seen(f, reference))
    return _series(frames, relative if with_reference > len(frames) / 2 else absolute)


def bar_path_x(frames: Sequence[PoseFrame], lift: str) -> np.ndarray:
    """Horizontal bar position: shoulder midpoint for the squat (bar on the back), wrist midpoint otherwise."""
    group = "shoulders" if lift == "squat" else "wrists"
    return _series(frames, lambda f: _mid(f, group)[0])


# ---------------------------------------------------------------- reps

def _fill_gaps(signal: np.ndarray) -> np.ndarray | None:
    s = np.asarray(signal, dtype=float).copy()
    ok = np.isfinite(s)
    if ok.sum() < 2:
        return None
    idx = np.arange(s.size)
    s[~ok] = np.interp(idx[~ok], idx[ok], s[ok])
    return s


def _smooth(s: np.ndarray, window: int = 5) -> np.ndarray:
    if s.size < window:
        return s
    pad = window // 2
    padded = np.pad(s, pad, mode="edge")
    return np.convolve(padded, np.ones(window) / window, mode="valid")


def count_reps(signal: Sequence[float], rest: str = "high", min_amplitude: float = 0.02) -> list[RepSegment]:
    """Splits a height signal into complete reps (rest -> turn -> rest) using hysteresis thresholds.

    rest="high": the signal sits high between reps (squat, bench). rest="low": it sits low (deadlift).
    Movements smaller than `min_amplitude` are ignored; a final rep that never returns to rest isn't counted.
    Each rep is judged against the rest height just before it rather than one level for the whole set, so a
    slow drift (the camera tilting, the lifter moving nearer or farther) doesn't hide reps.
    """
    filled = _fill_gaps(np.asarray(signal, dtype=float))
    if filled is None:
        return []
    s = _smooth(filled)
    if rest == "low":
        s = -s
    amp = np.percentile(s, 98) - np.percentile(s, 2)
    if amp < min_amplitude:
        return []
    # A rep must drop half the set's range below the rest height it left, so a shallow rep among deep ones still
    # counts, and must come back to within a fifth of the range of that height.
    down_by, back_within = 0.5 * amp, 0.2 * amp
    eps = 1e-6 * amp
    reps: list[RepSegment] = []
    state, peak = "up", s[0]  # a set that starts mid-rep has its peak raised before any descent counts
    cross_down = None
    floor = 0  # reps may not start before the previous rep's end
    for i, v in enumerate(s):
        if state == "up":
            peak = max(peak, v)
            if v < peak - down_by:
                state, cross_down = "down", i
        elif v >= peak - back_within:
            # Walk back from the descent to where the movement began, and forward to where it settled.
            start = cross_down
            while start > floor and s[start - 1] > s[start] + eps:
                start -= 1
            end = i
            while end + 1 < s.size and s[end + 1] > s[end] + eps:
                end += 1
            turn = start + int(np.argmin(s[start:end + 1]))
            reps.append(RepSegment(start, turn, end))
            floor = end
            state, peak = "up", v  # the next rep is judged against where this one finished
    return reps


# ---------------------------------------------------------------- camera and lift

def classify_camera_angle(frames: Sequence[PoseFrame]) -> str:
    """side, front or angled, from shoulder and hip width relative to torso length."""
    ratios = []
    for f in frames:
        if not f.landmarks or min(group_confidence(f, "shoulders"), group_confidence(f, "hips")) < CONFIDENCE_THRESHOLD:
            continue
        lm = f.landmarks
        sw = math.dist(_xy(lm["left_shoulder"]), _xy(lm["right_shoulder"]))
        hw = math.dist(_xy(lm["left_hip"]), _xy(lm["right_hip"]))
        torso = math.dist(_mid(f, "shoulders"), _mid(f, "hips"))
        if torso > 1e-6:
            ratios.append((sw + hw) / 2 / torso)
    if not ratios:
        return "angled"
    r = float(np.median(ratios))
    # MediaPipe never puts the two shoulders exactly on top of each other: real side views measure 0.13-0.19, so
    # side allows up to about 20° of turn.
    return "side" if r < SIDE_MAX_RATIO else "front" if r > 0.45 else "angled"


def hands_at_shoulders(frames: Sequence[PoseFrame]) -> bool:
    """Whether the hands stay at the shoulders, as they do holding a bar on the back: within HANDS_AT_SHOULDERS
    torso lengths of the shoulder midpoint on most frames where the wrists are seen. Arms held out front or hands
    clasped at the chest (bodyweight squats) are farther. True when the wrists are never seen clearly."""
    near = seen = 0
    for f in frames:
        if not f.landmarks or min(group_confidence(f, g) for g in ("wrists", "shoulders", "hips")) < CONFIDENCE_THRESHOLD:
            continue
        torso = math.dist(_mid(f, "shoulders"), _mid(f, "hips"))
        if torso < 1e-6:
            continue
        seen += 1
        near += math.dist(_mid(f, "wrists"), _mid(f, "shoulders")) / torso < HANDS_AT_SHOULDERS
    return seen == 0 or near > seen / 2


def detect_lift(frames: Sequence[PoseFrame]) -> str | None:
    """Which lift the movement looks like: lying down -> bench; wrists locked out overhead -> overhead press;
    bar at the shoulders -> squat; else deadlift (Romanian or conventional: pose alone can't tell them apart)."""
    leans, wrist_pos = [], []
    for f in frames:
        if not f.landmarks:
            continue
        shoulder, hip, wrist = _mid(f, "shoulders"), _mid(f, "hips"), _mid(f, "wrists")
        torso = math.dist(shoulder, hip)
        if torso < 1e-6:
            continue
        leans.append(torso_lean_deg(shoulder, hip))
        wrist_pos.append((wrist[1] - hip[1]) / torso)
    if not leans:
        return None
    if np.median(leans) > 60:
        return "bench_press"
    if np.mean(np.asarray(wrist_pos) < OVERHEAD_WRISTS) >= OVERHEAD_SHARE:
        return "overhead_press"
    return "squat" if np.median(wrist_pos) < -0.5 else "deadlift"


# ---------------------------------------------------------------- per-rep metrics

def _valgus(f: PoseFrame) -> float | None:
    lm = f.landmarks
    mid_x = (lm["left_hip"].x + lm["right_hip"].x) / 2
    worst = None
    for side in ("left", "right"):
        knee, ankle = lm[f"{side}_knee"], lm[f"{side}_ankle"]
        inward = (ankle.x - knee.x) if knee.x > mid_x else (knee.x - ankle.x)
        shin = ankle.y - knee.y
        if shin <= 1e-6:
            continue
        angle = math.degrees(math.atan2(inward, shin))
        worst = angle if worst is None else max(worst, angle)
    return worst


def _elbow_flare(f: PoseFrame) -> float | None:
    lm = f.landmarks
    return max(joint_angle(lm[f"{s}_elbow"], lm[f"{s}_shoulder"], lm[f"{s}_hip"]) for s in ("left", "right"))


def _wrist_diff(f: PoseFrame) -> float | None:
    lm = f.landmarks
    width = math.dist(_xy(lm["left_shoulder"]), _xy(lm["right_shoulder"]))
    return abs(lm["left_wrist"].y - lm["right_wrist"].y) / width if width > 1e-6 else None


def _lean_back_series(frames: Sequence[PoseFrame]) -> np.ndarray:
    """US-28: how far the hip-to-shoulder line tilts back behind the hips, in degrees (negative = forward).

    "Back" is away from where the lifter faces, taken from where the bar sits: in front of the shoulders in the
    rack and at the start of every press. A pose has no spine points, so this stands in for lower-back arch."""
    ahead = _series(frames, lambda f: _mid(f, "wrists")[0] - _mid(f, "shoulders")[0])
    facing = 1.0 if not np.isfinite(ahead).any() or np.nanmedian(ahead) >= 0 else -1.0

    def lean_back(f):
        shoulder, hip = _mid(f, "shoulders"), _mid(f, "hips")
        return math.degrees(math.atan2((hip[0] - shoulder[0]) * facing, hip[1] - shoulder[1]))

    return _series(frames, lean_back)


def _r(v) -> float | None:
    return None if v is None or not np.isfinite(v) else round(float(v), 2)


def measure_set(frames: Sequence[PoseFrame], lift: str, fps: float) -> SetMeasurements:
    frames = list(frames)
    camera = classify_camera_angle(frames)
    side = _visible_side(frames)

    def pt(joint):
        return lambda f: _side_point(f, side, joint)

    thighs = _series(frames, lambda f: math.dist(pt("hip")(f), pt("knee")(f)))
    thigh = float(np.nanmedian(thighs)) if np.isfinite(thighs).any() else None

    knee = _series(frames, lambda f: joint_angle(pt("hip")(f), pt("knee")(f), pt("ankle")(f)))
    hip = _series(frames, lambda f: joint_angle(pt("shoulder")(f), pt("hip")(f), pt("knee")(f)))
    elbow = _series(frames, lambda f: joint_angle(pt("shoulder")(f), pt("elbow")(f), pt("wrist")(f)))
    lean = _series(frames, lambda f: torso_lean_deg(_mid(f, "shoulders"), _mid(f, "hips")))
    back = _series(frames, lambda f: 180 - joint_angle(pt("ear")(f), pt("shoulder")(f), pt("hip")(f)))
    depth = _series(frames, lambda f: (_mid(f, "hips")[1] - _mid(f, "knees")[1]) / thigh if thigh else None)
    bar = bar_path_x(frames, lift)
    front = camera == "front"
    valgus = _series(frames, _valgus) if front else None
    flare = _series(frames, _elbow_flare) if front else None
    wrist_diff = _series(frames, _wrist_diff) if front else None

    if lift == "romanian_deadlift":
        # US-28: the hips move back, not down, so reps come from the hinge (shoulder-hip-knee angle).
        segments = count_reps(hip, rest=REST_POSITION[lift], min_amplitude=RDL_MIN_HINGE_DEG)
    else:
        segments = count_reps(height_signal(frames, lift), rest=REST_POSITION[lift],
                              min_amplitude=max(0.02, 0.25 * (thigh or 0)))
    lean_back = _lean_back_series(frames) if lift == "overhead_press" else None
    reps = []
    for n, seg in enumerate(segments, start=1):
        span = np.arange(seg.start, seg.end + 1)
        metrics: dict[str, float | None] = {}
        worst: dict[str, int] = {}

        def extreme(name, series, rng, mode):
            vals = series[rng]
            if not np.isfinite(vals).any():
                metrics[name] = None
                return None
            k = int(rng[np.nanargmax(vals) if mode == "max" else np.nanargmin(vals)])
            metrics[name] = _r(series[k])
            worst[name] = frames[k].index
            return k

        def increase(name, rng, base_k):
            k = extreme(name, lean, rng, "max")
            if k is not None:
                metrics[name] = _r(lean[k] - lean[base_k]) if np.isfinite(lean[base_k]) else None

        if lift == "squat":
            extreme("knee_angle_min_deg", knee, span, "min")
            extreme("hip_angle_min_deg", hip, span, "min")
            extreme("torso_lean_max_deg", lean, span, "max")
            increase("torso_lean_increase_deg", np.arange(seg.turn, seg.end + 1), seg.turn)
            metrics["depth_margin"] = _r(depth[seg.turn])
            worst["depth_margin"] = frames[seg.turn].index
        elif lift == "deadlift":
            extreme("knee_angle_min_deg", knee, span, "min")
            extreme("hip_angle_min_deg", hip, span, "min")
            extreme("torso_lean_max_deg", lean, span, "max")
            pull = np.arange(seg.start, seg.start + max(1, int(0.6 * (seg.turn - seg.start))) + 1)
            increase("torso_lean_increase_deg", pull, seg.start)
            extreme("back_rounding_deg", back, span, "max")
            extreme("lockout_hip_angle_deg", hip, span, "max")
        elif lift == "overhead_press":  # US-28
            extreme("elbow_angle_min_deg", elbow, span, "min")
            extreme("lockout_elbow_angle_deg", elbow, span, "max")
            extreme("torso_lean_back_max_deg", lean_back, span, "max")
        elif lift == "romanian_deadlift":  # US-28
            extreme("knee_angle_min_deg", knee, span, "min")
            extreme("hip_angle_min_deg", hip, span, "min")
            extreme("torso_lean_max_deg", lean, span, "max")
            extreme("back_rounding_deg", back, span, "max")
        else:
            extreme("elbow_angle_min_deg", elbow, span, "min")
            extreme("lockout_elbow_angle_deg", elbow, span, "max")

        metrics["bar_drift_ratio"] = _r(bar_drift_ratio(bar[span], thigh)) if thigh else None
        worst["bar_drift_ratio"] = frames[seg.turn].index
        if lift == "squat":
            if front:
                extreme("knee_valgus_deg", valgus, span, "max")
            else:
                metrics["knee_valgus_deg"] = None
        if lift == "bench_press":
            if front:
                extreme("elbow_flare_deg", flare, span, "max")
                extreme("wrist_height_diff_ratio", wrist_diff, span, "max")
            else:
                metrics["elbow_flare_deg"] = metrics["wrist_height_diff_ratio"] = None

        depth_reached = None
        if lift == "squat" and metrics["depth_margin"] is not None:
            f = frames[seg.turn]
            depth_reached = squat_depth_reached(_mid(f, "hips"), _mid(f, "knees"))
        reps.append(RepMeasurement(
            rep=n, start_frame=frames[seg.start].index, turn_frame=frames[seg.turn].index,
            end_frame=frames[seg.end].index, start_time=round(frames[seg.start].timestamp, 3),
            end_time=round(frames[seg.end].timestamp, 3), metrics=metrics, worst_frames=worst,
            depth_reached=depth_reached,
        ))

    return SetMeasurements(lift=lift, detected_lift=detect_lift(frames), camera_angle=camera, fps=fps, reps=reps,
                           low_confidence_groups=low_confidence_groups(frames), frame_count=len(frames),
                           thigh_length=thigh, holds_bar=lift != "squat" or hands_at_shoulders(frames))
