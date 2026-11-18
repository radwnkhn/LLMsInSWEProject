"""Conservative squat segmentation from local, body-normalized pose evidence.

This estimates phases; it is not an independent verification of the pose model.
No clip-wide percentile, inferred coordinates, or language model decides a rep.
"""
from dataclasses import dataclass, field

import numpy as np


@dataclass
class SquatSegmentation:
    segments: list[tuple[int, int, int]] = field(default_factory=list)
    reliable: bool = True
    notes: list[str] = field(default_factory=list)

    def reject(self, reason: str) -> None:
        self.reliable = False
        if reason not in self.notes:
            self.notes.append(reason)


def segment_squats(height, knee, hip, torso, shin, times, *, front=False) -> SquatSegmentation:
    """standing -> descending -> bottom -> ascending -> standing.

    Height and shin are relative to the ankles, divided by visible torso length.
    Side views also require knee AND hip flexion. Front views use projected thigh
    shortening because sagittal joint angles are not observable from that view.
    Thresholds below are conservative engineering defaults, not clinical bounds.
    """
    result = SquatSegmentation()
    state = "standing"
    rest = []
    baseline = None
    start = turn = last_standing = 0
    previous = None
    return_since = None
    ascent_peak = None
    for i, t in enumerate(times):
        valid = all(np.isfinite(a[i]) for a in (height, knee, hip, torso, shin)) and torso[i] > 1e-6
        if not valid:
            if previous is not None and t - times[previous] > 0.20:
                result.reject("Pose tracking was lost between movements; the rep count is uncertain.")
                state, rest, baseline, return_since = "standing", [], None, None
            continue  # no interpolation across lost tracking
        if previous is not None:
            if t - times[previous] > 0.20:
                result.reject("Pose tracking was lost between movements; the rep count is uncertain.")
                state, rest, baseline, return_since = "standing", [], None, None
            if abs(torso[i] / torso[previous] - 1) > 0.35:
                result.reject("The camera scale or pose changed abruptly; use a steady camera and try again.")
                state, rest, baseline, return_since = "standing", [], None, None
        previous = i
        h, k, p, s = height[i], knee[i], hip[i], shin[i]
        upright = k >= 150 and p >= 140
        if state == "standing":
            if baseline is not None:
                bh, bk, bp, bs = baseline
                drop = bh - h
                flexion = (bs - s > 0.015) if front else (bk - k >= 12 and bp - p >= 8)
                if drop > 0.08 and flexion:
                    state, start, turn = "descending", last_standing, i
                    rest = []
                    continue
            if upright and (baseline is None or h >= baseline[0] - 0.06):
                rest.append((h, k, p, s))
                rest = rest[-8:]
                # At least 3 observations of standing before accepting a descent.
                if len(rest) >= 3:
                    baseline = tuple(np.median(rest, axis=0))
                    last_standing = i
            continue

        bh, bk, bp, bs = baseline
        if h < height[turn]:
            turn = i
        drop = bh - height[turn]
        bottom_evidence = (bs - shin[turn] >= 0.025) if front else (bk - knee[turn] >= 30 and bp - hip[turn] >= 20)
        qualified = drop >= 0.18 and bottom_evidence and times[turn] - times[start] >= 0.15
        if state == "descending" and qualified:
            state = "bottom"
        if state == "bottom" and h - height[turn] >= 0.03:
            state = "ascending"
            ascent_peak = i
        if state == "ascending":
            if h >= height[ascent_peak]:
                ascent_peak = i
            elif (height[ascent_peak] - h >= 0.12 and t - times[ascent_peak] >= 0.10
                  and (front or knee[ascent_peak] - k >= 10)):
                # Don't merge several valleys merely because a return threshold was missed.
                result.reject("Movement descended again before a clear standing return; the rep count is uncertain.")
                state, rest, baseline, return_since = "standing", [], None, None
                continue
        returned = h >= bh - 0.08 and k >= bk - 12 and p >= bp - 15
        if returned:
            if return_since is None:
                return_since = i
            if t - times[return_since] >= 0.04:
                if state == "ascending" and qualified and times[i] - times[turn] >= 0.15:
                    result.segments.append((start, turn, i))
                # A small bend that returned to standing isn't a squat.
                state, rest, return_since = "standing", [], None
                baseline, last_standing = (h, k, p, s), i
        else:
            return_since = None
    if state != "standing":
        result.notes.append("A movement without a complete return to standing was excluded.")
    return result
