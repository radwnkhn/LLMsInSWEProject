"""The fault list for each lift: what the AI may report and how each fault is confirmed.

A fault is confirmed on a rep when that rep's `metric` is above (or below) `threshold`.
`views` lists the camera angles the metric can be measured from, and `joints` the landmark
groups it depends on (a group is "not clearly visible" when its pose confidence is low).

`FAULTS` holds the Alpha definitions. They seed the saved fault list (US-25), which admins can
edit, disable or extend; each analysis uses a `FaultCatalog` snapshot of that saved list.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from typing import Iterable


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
    enabled: bool = True  # US-25: disabled faults are not offered to, or accepted from, the LLM

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
    # US-28. Every threshold below is a first guess, to be tuned with trainer grading (US-22) and threshold
    # editing (US-24); docs/tdd/us28.md gives the reasoning for each value.
    "overhead_press": (
        _f("overhead_press", "excessive_back_arch", "Lower back arches as you press", "back arch", "safety",
           "torso_lean_back_max_deg", "backward lean", 15, "above", "°", SIDE, ("shoulders", "hips"),
           "Lean back {value:.0f}°"),
        _f("overhead_press", "bar_path_drift", "Bar drifts forward away from your head", "bar drift", "technique",
           "bar_drift_ratio", "bar drift", 0.30, "above", "", SIDE, ("wrists", "shoulders", "hips"),
           "Bar drift {value:.2f}"),
        _f("overhead_press", "incomplete_lockout", "Arms don't fully lock out overhead", "incomplete lockout",
           "technique", "lockout_elbow_angle_deg", "elbow angle at lockout", 165, "below", "°", SIDE,
           ("shoulders", "elbows", "wrists"), "Elbow {value:.0f}°"),
    ),
    "romanian_deadlift": (
        _f("romanian_deadlift", "rounded_back", "Your back rounds as you hinge", "rounded back", "safety",
           "back_rounding_deg", "back rounding", 20, "above", "°", SIDE, ("ears", "shoulders", "hips"),
           "Back {value:.0f}°"),
        _f("romanian_deadlift", "knees_bend_too_much", "Knees bend too much, turning it into a deadlift", "knee bend",
           "technique", "knee_angle_min_deg", "knee angle", 140, "below", "°", SIDE, ("hips", "knees", "ankles"),
           "Knee {value:.0f}°"),
        _f("romanian_deadlift", "bar_path_drift", "Bar drifts away from your legs", "bar drift", "technique",
           "bar_drift_ratio", "bar drift", 0.15, "above", "", SIDE, ("wrists", "hips", "knees"),
           "Bar drift {value:.2f}"),
    ),
}


# ---------------------------------------------------------------- measurements a fault can use (US-25)

@dataclass(frozen=True)
class MetricSpec:
    """A per-rep measurement that app.measure computes, and what a fault built on it needs."""
    metric: str
    label: str
    unit: str
    views: frozenset[str]
    joints: tuple[str, ...]
    label_format: str


def _m(metric, label, unit, views, joints, fmt):
    return MetricSpec(metric, label, unit, views, joints, fmt)


_BAR_LEGS = ("wrists", "hips", "knees")
# Every metric measure_set() writes into a rep's metrics, per lift (test_us25 checks they stay in step).
METRICS: dict[str, dict[str, MetricSpec]] = {
    lift: {spec.metric: spec for spec in specs} for lift, specs in {
        "squat": (
            _m("knee_angle_min_deg", "knee angle at the bottom", "°", SIDE, ("hips", "knees", "ankles"), "Knee {value:.0f}°"),
            _m("hip_angle_min_deg", "hip angle at the bottom", "°", SIDE, ("shoulders", "hips", "knees"), "Hip {value:.0f}°"),
            _m("torso_lean_max_deg", "torso lean", "°", SIDE, ("shoulders", "hips"), "Torso {value:.0f}°"),
            _m("torso_lean_increase_deg", "torso lean increase", "°", SIDE, ("shoulders", "hips"), "Torso +{value:.0f}°"),
            _m("depth_margin", "hip depth below the knee", "", ANY_VIEW, ("hips", "knees"),
               "Hip {value:+.2f} thigh below knee"),
            _m("bar_drift_ratio", "bar drift", "", SIDE, ("shoulders", "hips", "knees"), "Bar drift {value:.2f}"),
            _m("knee_valgus_deg", "valgus", "°", FRONT, ("hips", "knees", "ankles"), "Valgus {value:.0f}°"),
        ),
        "deadlift": (
            _m("knee_angle_min_deg", "knee angle at the bottom", "°", SIDE, ("hips", "knees", "ankles"), "Knee {value:.0f}°"),
            _m("hip_angle_min_deg", "hip angle at the bottom", "°", SIDE, ("shoulders", "hips", "knees"), "Hip {value:.0f}°"),
            _m("torso_lean_max_deg", "torso lean", "°", SIDE, ("shoulders", "hips"), "Torso {value:.0f}°"),
            _m("torso_lean_increase_deg", "torso lean increase", "°", SIDE, ("shoulders", "hips"), "Torso +{value:.0f}°"),
            _m("back_rounding_deg", "back rounding", "°", SIDE, ("ears", "shoulders", "hips"), "Back {value:.0f}°"),
            _m("lockout_hip_angle_deg", "hip angle at lockout", "°", SIDE, ("shoulders", "hips", "knees"), "Hip {value:.0f}°"),
            _m("bar_drift_ratio", "bar drift", "", SIDE, _BAR_LEGS, "Bar drift {value:.2f}"),
        ),
        "bench_press": (
            _m("elbow_angle_min_deg", "elbow angle at the bottom", "°", SIDE, ("shoulders", "elbows", "wrists"),
               "Elbow {value:.0f}°"),
            _m("lockout_elbow_angle_deg", "elbow angle at lockout", "°", SIDE, ("shoulders", "elbows", "wrists"),
               "Elbow {value:.0f}°"),
            _m("bar_drift_ratio", "bar drift", "", SIDE, _BAR_LEGS, "Bar drift {value:.2f}"),
            _m("elbow_flare_deg", "elbow flare", "°", FRONT, ("shoulders", "elbows", "hips"), "Flare {value:.0f}°"),
            _m("wrist_height_diff_ratio", "wrist height difference", "", FRONT, ("wrists", "shoulders"), "Uneven {value:.2f}"),
        ),
        "overhead_press": (  # US-28
            _m("elbow_angle_min_deg", "elbow angle in the rack", "°", SIDE, ("shoulders", "elbows", "wrists"),
               "Elbow {value:.0f}°"),
            _m("lockout_elbow_angle_deg", "elbow angle at lockout", "°", SIDE, ("shoulders", "elbows", "wrists"),
               "Elbow {value:.0f}°"),
            _m("torso_lean_back_max_deg", "backward lean", "°", SIDE, ("shoulders", "hips"), "Lean back {value:.0f}°"),
            _m("bar_drift_ratio", "bar drift", "", SIDE, ("wrists", "shoulders", "hips"), "Bar drift {value:.2f}"),
        ),
        "romanian_deadlift": (  # US-28
            _m("knee_angle_min_deg", "knee angle", "°", SIDE, ("hips", "knees", "ankles"), "Knee {value:.0f}°"),
            _m("hip_angle_min_deg", "hip angle at the bottom of the hinge", "°", SIDE, ("shoulders", "hips", "knees"),
               "Hip {value:.0f}°"),
            _m("torso_lean_max_deg", "torso lean", "°", SIDE, ("shoulders", "hips"), "Torso {value:.0f}°"),
            _m("back_rounding_deg", "back rounding", "°", SIDE, ("ears", "shoulders", "hips"), "Back {value:.0f}°"),
            _m("bar_drift_ratio", "bar drift", "", SIDE, _BAR_LEGS, "Bar drift {value:.2f}"),
        ),
    }.items()
}

# ---------------------------------------------------------------- admin changes (US-25)

# Fields an admin may change on a saved fault. US-24 added "threshold"; the repository logs each
# threshold change (who, when, old and new value).
FAULT_EDITABLE_FIELDS = frozenset({"name", "short_name", "enabled", "threshold"})
CATEGORIES = ("safety", "technique")
DIRECTIONS = ("above", "below")
MAX_NAME, MAX_SHORT_NAME = 80, 40
FAULT_ID = re.compile(r"^[a-z][a-z0-9_]{2,39}$")


class FaultError(ValueError):
    """An admin change that would make a fault invalid or unmeasurable. The message is shown to the admin."""


class FaultExists(FaultError):
    """The lift already has a fault with this ID."""


# US-24: the values a threshold may take, by the kind of measurement it is compared with.
ANGLE_RANGE, DEPTH_RANGE, RATIO_RANGE = (0, 180), (-1, 1), (0, 2)


def threshold_range(fault: Fault | MetricSpec) -> tuple[int, int]:
    """Lowest and highest allowed threshold for a fault (or the measurement a new fault would use).
    Hip depth is signed (hips above or below the knee, in thigh lengths); other ratios can't be negative."""
    if fault.metric == "depth_margin":
        return DEPTH_RANGE
    return ANGLE_RANGE if fault.unit == "°" else RATIO_RANGE


def _threshold(value, fault: Fault | MetricSpec) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise FaultError("Threshold must be a number")
    low, high = threshold_range(fault)
    if not low <= value <= high:
        raise FaultError(f"Threshold must be between {low} and {high}")
    return float(value)


def _text(value, label: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FaultError(f"{label} is required")
    value = value.strip()
    if len(value) > limit:
        raise FaultError(f"{label} must be {limit} characters or fewer")
    return value


def edit_fault(fault: Fault, **fields) -> Fault:
    """The fault with an admin's edits applied. Only FAULT_EDITABLE_FIELDS may change."""
    unknown = set(fields) - FAULT_EDITABLE_FIELDS
    if unknown:
        raise FaultError(f"can't change {', '.join(sorted(unknown))} here")
    if "name" in fields:
        fields["name"] = _text(fields["name"], "Display name", MAX_NAME)
    if "short_name" in fields:
        fields["short_name"] = _text(fields["short_name"], "Short description", MAX_SHORT_NAME)
    if "enabled" in fields and not isinstance(fields["enabled"], bool):
        raise FaultError("enabled must be true or false")
    if "threshold" in fields:
        fields["threshold"] = _threshold(fields["threshold"], fault)
    return replace(fault, **fields)


def new_fault(lift: str, id: str, name: str, short_name: str, category: str, metric: str, threshold: float,
              direction: str) -> Fault:
    """A new fault built on a measurement the app already computes for the lift.

    Camera angles, joints, unit and frame label come from that measurement, never from free text,
    so every reportable fault stays measurable. The threshold gets the same range check as US-24 edits."""
    if lift not in METRICS:
        raise FaultError(f"unknown lift '{lift}'")
    spec = METRICS[lift].get(metric)
    if spec is None:
        raise FaultError(f"'{metric}' isn't a measurement the app computes for this lift")
    if not isinstance(id, str) or not FAULT_ID.match(id):
        raise FaultError("Fault ID must be 3-40 lowercase letters, digits or underscores, starting with a letter")
    if category not in CATEGORIES:
        raise FaultError("category must be safety or technique")
    if direction not in DIRECTIONS:
        raise FaultError("direction must be above or below")
    threshold = _threshold(threshold, spec)
    return Fault(id=id, lift=lift, name=_text(name, "Display name", MAX_NAME),
                 short_name=_text(short_name, "Short description", MAX_SHORT_NAME), category=category, metric=metric,
                 metric_label=spec.label, threshold=threshold, direction=direction, unit=spec.unit,
                 views=spec.views, joints=spec.joints, label_format=spec.label_format)


# ---------------------------------------------------------------- the fault list an analysis uses

class FaultCatalog:
    """A snapshot of the saved fault list. New analyses take one when they start (US-25)."""

    def __init__(self, faults: Iterable[Fault]):
        self._by_lift: dict[str, tuple[Fault, ...]] = {}
        for f in faults:
            self._by_lift[f.lift] = (*self._by_lift.get(f.lift, ()), f)

    def all_for(self, lift: str) -> tuple[Fault, ...]:
        """Every fault of the lift, disabled ones included (for showing saved results)."""
        return self._by_lift.get(lift, ())

    def faults_for(self, lift: str) -> tuple[Fault, ...]:
        """The faults the AI may report: enabled ones, in list order."""
        return tuple(f for f in self.all_for(lift) if f.enabled)

    def fault_ids(self, lift: str) -> list[str]:
        return [f.id for f in self.faults_for(lift)]

    def get(self, lift: str, fault_id: str | None) -> Fault | None:
        """Any fault of the lift by ID, disabled or not."""
        return next((f for f in self.all_for(lift) if f.id == fault_id), None)


def default_faults() -> list[Fault]:
    return [f for lift in FAULTS for f in FAULTS[lift]]


DEFAULT_CATALOG = FaultCatalog(default_faults())


def faults_for(lift: str, catalog: FaultCatalog | None = None) -> tuple[Fault, ...]:
    return (catalog or DEFAULT_CATALOG).faults_for(lift)


def fault_ids(lift: str, catalog: FaultCatalog | None = None) -> list[str]:
    return (catalog or DEFAULT_CATALOG).fault_ids(lift)


def get_fault(lift: str, fault_id: str | None, catalog: FaultCatalog | None = None) -> Fault | None:
    return (catalog or DEFAULT_CATALOG).get(lift, fault_id)
