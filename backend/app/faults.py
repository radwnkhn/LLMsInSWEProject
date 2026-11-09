"""The fixed fault list for each lift: what the AI may report and how each fault is confirmed.

A fault is confirmed on a rep when that rep's `metric` is above (or below) `threshold`.
`views` lists the camera angles the metric can be measured from, and `joints` the landmark
groups it depends on (a group is "not clearly visible" when its pose confidence is low).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Fault:
    id: str
    lift: str
    name: str            # plain language, shown as the Top Fix
    short_name: str      # used inside validator messages
    category: str        # "safety" | "technique"
    metric: str
    metric_label: str
    threshold: float
    direction: str       # "above" | "below"
    unit: str            # "°" or "" (ratios)
    views: frozenset[str]
    joints: tuple[str, ...]
    label_format: str    # measurement label drawn on the annotated frame

    @property
    def safety(self) -> bool:
        return self.category == "safety"

    def is_confirmed(self, value: float | None) -> bool:
        if value is None:
            return False
        return value > self.threshold if self.direction == "above" else value < self.threshold

    def format_value(self, value: float) -> str:
        return f"{value:.0f}{self.unit}" if self.unit == "°" else f"{value:.2f}"


SIDE, FRONT = frozenset({"side"}), frozenset({"front"})
ANY_VIEW = frozenset({"side", "front", "angled"})  # hip-vs-knee height reads the same from any angle


def _f(lift, id, name, short, category, metric, label, threshold, direction, unit, views, joints, fmt):
    return Fault(id, lift, name, short, category, metric, label, threshold, direction, unit, views, joints, fmt)


FAULTS: dict[str, tuple[Fault, ...]] = {
    "squat": (
        _f("squat", "knee_cave", "Knees cave inward", "knee cave", "safety",
           "knee_valgus_deg", "valgus", 10, "above", "°", FRONT, ("hips", "knees", "ankles"), "Valgus {value:.0f}°"),
        _f("squat", "hips_rise_early", "Hips rise before your shoulders", "hips rising early", "technique",
           "torso_lean_increase_deg", "torso lean increase", 10, "above", "°", SIDE, ("shoulders", "hips"),
           "Torso +{value:.0f}°"),
        _f("squat", "insufficient_depth", "Squat isn't reaching depth", "shallow depth", "technique",
           "depth_margin", "hip depth below the knee", 0, "below", "", ANY_VIEW, ("hips", "knees"),
           "Hip {value:+.2f} thigh below knee"),
        _f("squat", "excessive_forward_lean", "Chest drops too far forward", "forward lean", "technique",
           "torso_lean_max_deg", "torso lean", 55, "above", "°", SIDE, ("shoulders", "hips"), "Torso {value:.0f}°"),
        _f("squat", "bar_path_drift", "Bar drifts forward and back", "bar drift", "technique",
           "bar_drift_ratio", "bar drift", 0.25, "above", "", SIDE, ("shoulders", "hips", "knees"),
           "Bar drift {value:.2f}"),
    ),
    "deadlift": (
        _f("deadlift", "rounded_back", "Your back rounds during the pull", "rounded back", "safety",
           "back_rounding_deg", "back rounding", 20, "above", "°", SIDE, ("ears", "shoulders", "hips"),
           "Back {value:.0f}°"),
        _f("deadlift", "hips_rise_early", "Hips shoot up before the bar leaves the floor", "hips rising early",
           "technique", "torso_lean_increase_deg", "torso lean increase", 10, "above", "°", SIDE,
           ("shoulders", "hips"), "Torso +{value:.0f}°"),
        _f("deadlift", "bar_path_drift", "Bar drifts away from your legs", "bar drift", "technique",
           "bar_drift_ratio", "bar drift", 0.15, "above", "", SIDE, ("wrists", "hips", "knees"),
           "Bar drift {value:.2f}"),
        _f("deadlift", "incomplete_lockout", "Hips don't fully lock out at the top", "incomplete lockout",
           "technique", "lockout_hip_angle_deg", "hip angle at lockout", 165, "below", "°", SIDE,
           ("shoulders", "hips", "knees"), "Hip {value:.0f}°"),
    ),
    "bench_press": (
        _f("bench_press", "elbow_flare", "Elbows flare out too wide", "elbow flare", "safety",
           "elbow_flare_deg", "elbow flare", 75, "above", "°", FRONT, ("shoulders", "elbows", "hips"),
           "Flare {value:.0f}°"),
        _f("bench_press", "bar_path_drift", "Bar drifts toward your face or belly", "bar drift", "technique",
           "bar_drift_ratio", "bar drift", 0.25, "above", "", SIDE, ("wrists", "hips", "knees"),
           "Bar drift {value:.2f}"),
        _f("bench_press", "incomplete_lockout", "Arms don't fully lock out", "incomplete lockout", "technique",
           "lockout_elbow_angle_deg", "elbow angle at lockout", 160, "below", "°", SIDE,
           ("shoulders", "elbows", "wrists"), "Elbow {value:.0f}°"),
        _f("bench_press", "uneven_press", "Bar presses unevenly", "uneven press", "technique",
           "wrist_height_diff_ratio", "wrist height difference", 0.1, "above", "", FRONT,
           ("wrists", "shoulders"), "Uneven {value:.2f}"),
    ),
}


def faults_for(lift: str) -> tuple[Fault, ...]:
    return FAULTS.get(lift, ())


def fault_ids(lift: str) -> list[str]:
    return [f.id for f in faults_for(lift)]


def get_fault(lift: str, fault_id: str) -> Fault | None:
    return next((f for f in faults_for(lift) if f.id == fault_id), None)
