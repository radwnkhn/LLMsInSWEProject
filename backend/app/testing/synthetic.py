"""Synthetic pose data with known reps and faults.

Used by the test suite and by test mode (ALIBI_TEST_MODE=1), so the analysis pipeline can be
exercised end to end without real videos or MediaPipe. Coordinates are normalized image
coordinates (x right, y down), like MediaPipe's.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.pose import LANDMARK_NAMES, Landmark, PoseFrame

FPS = 30
SHIN, THIGH, TORSO, ARM = 0.2, 0.2, 0.3, 0.25
REST, MOVE, HOLD = 10, 20, 2

# MediaPipe landmarks that aren't modeled copy the nearest modeled joint.
_COPIES = {
    "left_ear": ["nose", "left_eye_inner", "left_eye", "left_eye_outer", "mouth_left"],
    "right_ear": ["right_eye_inner", "right_eye", "right_eye_outer", "mouth_right"],
    "left_wrist": ["left_pinky", "left_index", "left_thumb"],
    "right_wrist": ["right_pinky", "right_index", "right_thumb"],
    "left_ankle": ["left_heel", "left_foot_index"],
    "right_ankle": ["right_heel", "right_foot_index"],
}
GROUP_OF = {"shoulder": "shoulders", "elbow": "elbows", "wrist": "wrists", "hip": "hips",
            "knee": "knees", "ankle": "ankles", "ear": "ears"}


@dataclass
class RepSpec:
    """Faults to put on one rep. Values are in the fault's own units."""
    torso_bump: float = 0.0        # squat/deadlift: extra torso lean early in the ascent (deg)
    depth_deg: float = 100.0       # squat: thigh angle from vertical at the bottom (>90 = below parallel)
    valgus: float = 0.0            # squat front view: inward shin tilt at the bottom (deg)
    rounding: float = 0.0          # deadlift: ear-shoulder-hip bend at the floor (deg)
    lockout_lean: float = 0.0      # deadlift: torso lean left at the top (deg)
    bar_drift: float = 0.0         # forward bar shift at the bottom/top (normalized x)
    bench_top_y: float = 0.30      # bench: wrist y at lockout (larger = less locked out)


@dataclass
class SetSpec:
    lift: str = "squat"
    reps: list[RepSpec] = field(default_factory=lambda: [RepSpec() for _ in range(5)])
    view: str = "side"             # side | front | angled
    confidence: float = 0.95
    low_confidence: dict[str, float] = field(default_factory=dict)  # group -> fraction of frames
    no_person_frames: int = 0      # frames with nothing detected, appended at the start
    trailing_partial: bool = False  # add a final descent with no ascent (incomplete rep)


def _ease(x: float) -> float:
    return (1 - math.cos(math.pi * max(0.0, min(1.0, x)))) / 2


def _timeline(n_reps: int, trailing_partial: bool):
    """Yields (rep_index or None, phase, progress) per frame. phase: rest | out | hold | back."""
    for r in range(n_reps):
        for _ in range(REST):
            yield r, "rest", 0.0
        for i in range(MOVE):
            yield r, "out", (i + 1) / MOVE
        for _ in range(HOLD):
            yield r, "hold", 1.0
        for i in range(MOVE):
            yield r, "back", (i + 1) / MOVE
    for _ in range(REST):
        yield None, "rest", 0.0
    if trailing_partial:
        for i in range(MOVE):
            yield n_reps, "out", (i + 1) / MOVE
        for _ in range(REST):
            yield n_reps, "hold", 1.0


def _add(p, v, length, angle_deg):
    a = math.radians(angle_deg)
    return (p[0] + length * math.sin(a) * v, p[1] - length * math.cos(a))


def _squat_side(spec: RepSpec, phase: str, prog: float):
    p = _ease(prog) if phase == "out" else 1.0 if phase == "hold" else 1 - _ease(prog) if phase == "back" else 0.0
    s, t = 35 * p, spec.depth_deg * p
    ankle = (0.5, 0.9)
    knee = (ankle[0] + SHIN * math.sin(math.radians(s)), ankle[1] - SHIN * math.cos(math.radians(s)))
    hip = (knee[0] - THIGH * math.sin(math.radians(t)), knee[1] - THIGH * math.cos(math.radians(t)))
    lean = math.degrees(math.asin(max(-1, min(1, (ankle[0] - hip[0]) / TORSO))))
    if phase == "back" and spec.torso_bump:
        lean += spec.torso_bump * math.sin(math.pi * min(prog / 0.6, 1.0))
    shoulder = (hip[0] + TORSO * math.sin(math.radians(lean)), hip[1] - TORSO * math.cos(math.radians(lean)))
    shoulder = (shoulder[0] + spec.bar_drift * p, shoulder[1])
    ear = (shoulder[0] + 0.07 * math.sin(math.radians(lean)), shoulder[1] - 0.07 * math.cos(math.radians(lean)))
    return {"ankle": ankle, "knee": knee, "hip": hip, "shoulder": shoulder, "ear": ear,
            "elbow": (shoulder[0] - 0.08, shoulder[1] + 0.08), "wrist": (shoulder[0] - 0.03, shoulder[1] + 0.02)}


def _deadlift_side(spec: RepSpec, phase: str, prog: float):
    # p = 0 at the floor, 1 at lockout. "out" is the pull, "back" is the lowering.
    p = _ease(prog) if phase == "out" else 1.0 if phase == "hold" else 1 - _ease(prog) if phase == "back" else 0.0
    s, t = 15 * (1 - p), 70 * (1 - p)
    lean = 45 * (1 - p) + spec.lockout_lean * p
    if phase == "out" and spec.torso_bump:
        lean += spec.torso_bump * math.sin(math.pi * min(prog / 0.6, 1.0))
    ankle = (0.5, 0.9)
    knee = (ankle[0] + SHIN * math.sin(math.radians(s)), ankle[1] - SHIN * math.cos(math.radians(s)))
    hip = (knee[0] - THIGH * math.sin(math.radians(t)), knee[1] - THIGH * math.cos(math.radians(t)))
    shoulder = (hip[0] + TORSO * math.sin(math.radians(lean)), hip[1] - TORSO * math.cos(math.radians(lean)))
    head_angle = lean + spec.rounding * (1 - p)
    ear = (shoulder[0] + 0.07 * math.sin(math.radians(head_angle)), shoulder[1] - 0.07 * math.cos(math.radians(head_angle)))
    bar_x = 0.5 + spec.bar_drift * (1 - p)
    dx = bar_x - shoulder[0]
    wrist = (bar_x, shoulder[1] + math.sqrt(max(ARM ** 2 - dx ** 2, 0.0)))
    elbow = ((shoulder[0] + wrist[0]) / 2, (shoulder[1] + wrist[1]) / 2)
    return {"ankle": ankle, "knee": knee, "hip": hip, "shoulder": shoulder, "ear": ear, "elbow": elbow, "wrist": wrist}


def _bench_side(spec: RepSpec, phase: str, prog: float):
    # Lying on a bench, head to the left. p = 0 at lockout, 1 with the bar on the chest.
    p = _ease(prog) if phase == "out" else 1.0 if phase == "hold" else 1 - _ease(prog) if phase == "back" else 0.0
    shoulder, hip, knee, ankle, ear = (0.35, 0.6), (0.65, 0.6), (0.8, 0.55), (0.85, 0.75), (0.28, 0.58)
    wrist = (0.37 + spec.bar_drift * p, spec.bench_top_y + (0.52 - spec.bench_top_y) * p)
    d = math.dist(shoulder, wrist)
    upper = fore = 0.15
    d = min(d, upper + fore - 1e-6)
    # Elbow from two-link geometry, bent toward the feet (+x).
    a = (upper ** 2 - fore ** 2 + d ** 2) / (2 * d)
    h = math.sqrt(max(upper ** 2 - a ** 2, 0.0))
    ux, uy = (wrist[0] - shoulder[0]) / d, (wrist[1] - shoulder[1]) / d
    base = (shoulder[0] + a * ux, shoulder[1] + a * uy)
    elbow = (base[0] + h * -uy, base[1] + h * ux) if -uy >= 0 else (base[0] - h * -uy, base[1] - h * ux)
    return {"ankle": ankle, "knee": knee, "hip": hip, "shoulder": shoulder, "ear": ear, "elbow": elbow, "wrist": wrist}


def _squat_front(spec: RepSpec, phase: str, prog: float):
    side = _squat_side(spec, phase, prog)
    p = _ease(prog) if phase == "out" else 1.0 if phase == "hold" else 1 - _ease(prog) if phase == "back" else 0.0
    joints = {}
    for name, half in (("shoulder", 0.10), ("elbow", 0.13), ("wrist", 0.12), ("ear", 0.03), ("hip", 0.07), ("ankle", 0.07)):
        y = side[name][1]
        joints[f"left_{name}"] = (0.5 + half, y)
        joints[f"right_{name}"] = (0.5 - half, y)
    knee_y = side["knee"][1]
    inward = math.tan(math.radians(spec.valgus * p)) * (0.9 - knee_y)
    joints["left_knee"] = (0.5 + 0.07 - inward, knee_y)
    joints["right_knee"] = (0.5 - 0.07 + inward, knee_y)
    return joints


_SIDE_POSES = {"squat": _squat_side, "deadlift": _deadlift_side, "bench_press": _bench_side}


def _to_landmarks(joints: dict, view: str, conf: float, low: set[str]) -> dict[str, Landmark]:
    if view == "front":
        both = joints
    else:
        offset = 0.01 if view == "side" else 0.09
        both = {}
        for name, (x, y) in joints.items():
            both[f"left_{name}"] = (x, y)
            both[f"right_{name}"] = (x + offset, y + offset / 2)
    marks: dict[str, Landmark] = {}
    for full, (x, y) in both.items():
        joint = full.split("_", 1)[1]
        c = 0.3 if GROUP_OF[joint] in low else conf
        marks[full] = Landmark(x, y, c)
        for extra in _COPIES.get(full, []):
            marks[extra] = Landmark(x, y, c)
    for name in LANDMARK_NAMES:
        marks.setdefault(name, Landmark(0.5, 0.5, conf))
    return {name: marks[name] for name in LANDMARK_NAMES}


def make_frames(spec: SetSpec) -> list[PoseFrame]:
    """Build pose frames for a set described by `spec`."""
    if spec.view == "front" and spec.lift != "squat":
        raise ValueError("front-view synthetic data exists only for the squat")
    pose = _squat_front if spec.view == "front" else _SIDE_POSES[spec.lift]
    frames: list[PoseFrame] = []
    for _ in range(spec.no_person_frames):
        frames.append(PoseFrame(index=len(frames), timestamp=len(frames) / FPS, landmarks=None))
    timeline = list(_timeline(len(spec.reps), spec.trailing_partial))
    total = len(timeline)
    for i, (rep, phase, prog) in enumerate(timeline):
        rep_spec = spec.reps[rep] if rep is not None and rep < len(spec.reps) else RepSpec()
        joints = pose(rep_spec, phase, prog)
        low = {g for g, frac in spec.low_confidence.items() if i < frac * total}
        frames.append(PoseFrame(index=len(frames), timestamp=len(frames) / FPS,
                                landmarks=_to_landmarks(joints, spec.view, spec.confidence, low)))
    return frames


def standing_still(n: int = 90, lift: str = "squat") -> list[PoseFrame]:
    """A person in the start position who never moves."""
    pose = _SIDE_POSES[lift]
    joints = pose(RepSpec(), "rest", 0.0)
    return [PoseFrame(index=i, timestamp=i / FPS, landmarks=_to_landmarks(joints, "side", 0.95, set())) for i in range(n)]


def empty_frames(n: int = 60) -> list[PoseFrame]:
    return [PoseFrame(index=i, timestamp=i / FPS, landmarks=None) for i in range(n)]


def squat(n_reps: int = 5, view: str = "side", **faults_by_rep) -> list[PoseFrame]:
    """Shortcut: squat(5, torso_bump={3: 25, 4: 25}) puts a 25 deg torso bump on reps 3 and 4 (1-based)."""
    reps = [RepSpec() for _ in range(n_reps)]
    for attr, per_rep in faults_by_rep.items():
        for rep_no, value in per_rep.items():
            setattr(reps[rep_no - 1], attr, value)
    return make_frames(SetSpec(lift="squat", reps=reps, view=view))


def scenario_frames(name: str) -> list[PoseFrame]:
    """Named scenarios for test mode. Picked from the uploaded file name."""
    name = name.lower()
    if "no_person" in name:
        return empty_frames()
    if "blurry" in name:
        return make_frames(SetSpec(low_confidence={"hips": 0.8, "knees": 0.8}))
    if "no_reps" in name:
        return standing_still()
    if "deadlift" in name:
        return make_frames(SetSpec(lift="deadlift", reps=[RepSpec() for _ in range(3)]))
    if "bench" in name:
        return make_frames(SetSpec(lift="bench_press", reps=[RepSpec() for _ in range(5)]))
    if "clean" in name:
        return squat(5)
    return squat(5, torso_bump={4: 25, 5: 25})
