"""Kinematic regression clips, with optional explicit tracking/camera disturbances.

These are synthetic hypotheses, not a reconstruction of the unavailable Red Team video.
"""
import math
from dataclasses import replace

from app.pose import Landmark, PoseFrame
from app.testing.synthetic import RepSpec, SetSpec, make_frames, squat, standing_still


def join(*clips):
    return [PoseFrame(i, i / 30, frame.landmarks) for i, frame in enumerate(f for clip in clips for f in clip)]


def forward_bend(occluded_hip_error=False):
    # A hip hinge with slight knee bend, not a squat. On the occluded far hip, a low-confidence
    # tracking error can put the estimate near the lower image edge; the visible side stays correct.
    frames = make_frames(SetSpec(lift="romanian_deadlift", reps=[RepSpec(rdl_knee_flex=25)]))
    if occluded_hip_error:
        for i, frame in enumerate(frames):
            if 15 <= i <= 38:
                frame.landmarks["right_hip"] = replace(frame.landmarks["right_hip"], y=0.99, confidence=0.1)
    return frames


def red_team_hypothesis():
    # Two completed, shallow squats still need two rep intervals (depth is separate form feedback).
    return join(make_frames(SetSpec(reps=[RepSpec(depth_deg=45), RepSpec(depth_deg=45)])),
                forward_bend(occluded_hip_error=True))


def walking(n=90):
    frames = standing_still(n)
    for i, frame in enumerate(frames):
        phase = 2 * math.pi * i / 30
        x = 0.4 + 0.15 * i / n
        hip_y = 0.5 + 0.02 * (1 - math.cos(2 * phase)) / 2
        for side, offset in (("left", 0), ("right", math.pi)):
            ankle = (x + 0.065 * math.cos(phase + offset), 0.9 - max(0, 0.025 * math.sin(phase + offset)))
            hip = (x, hip_y)
            dx, dy = ankle[0] - hip[0], ankle[1] - hip[1]
            distance = math.hypot(dx, dy)
            bend = math.sqrt(max(0, 0.2 ** 2 - (distance / 2) ** 2))
            knee = ((hip[0] + ankle[0]) / 2 + bend * dy / distance,
                    (hip[1] + ankle[1]) / 2 - bend * dx / distance)
            for joint, point in (("hip", hip), ("knee", knee), ("ankle", ankle)):
                frame.landmarks[f"{side}_{joint}"] = Landmark(*point, 0.95)
            for joint in ("shoulder", "elbow", "wrist", "ear"):
                original = frame.landmarks[f"{side}_{joint}"]
                frame.landmarks[f"{side}_{joint}"] = replace(original, x=original.x + x - 0.5, y=original.y + hip_y - 0.5)
    return frames
