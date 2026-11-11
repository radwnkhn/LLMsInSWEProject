"""Mocked LLMs and a fake video backend, for tests and test mode. Never call a real API."""
from __future__ import annotations

import json
import re
from typing import Callable, Sequence

import numpy as np

from app.faults import faults_for
from app.llm.client import LLMReply, LLMRequest
from app.pose import PoseFrame
from app.safety import mentions_pain
from app.testing.synthetic import scenario_frames
from app.video import VideoInfo, VideoUnreadable

CUES = {
    "knee_cave": "Push your knees out over your toes",
    "hips_rise_early": "Drive your chest up with your hips",
    "insufficient_depth": "Sit down until your hips pass your knees",
    "excessive_forward_lean": "Keep your chest proud the whole way down",
    "bar_path_drift": "Keep the bar over your midfoot",
    "rounded_back": "Brace hard and keep your chest up off the floor",
    "incomplete_lockout": "Finish tall at the top of every rep",
    "elbow_flare": "Tuck your elbows slightly as you lower the bar",
    "uneven_press": "Squeeze the bar evenly with both hands",
}
DEFAULT_CUE = "Move with control through every rep"  # for faults an admin added (US-25)
REFERRAL = "Please see a doctor or physical therapist about the pain before training through it."


MOCK_PROVIDER, MOCK_MODEL = "mock", "mock-coach"  # US-26: priced only in tests and test mode


def _reply(text: str, input_tokens: int, output_tokens: int) -> LLMReply:
    return LLMReply(text, input_tokens, output_tokens, provider=MOCK_PROVIDER, model=MOCK_MODEL)


def _tokens(request: LLMRequest, text: str) -> tuple[int, int]:
    return max(1, sum(len(m.content) for m in request.messages) // 4 + 300 * len(request.images)), max(1, len(text) // 4)


class RuleFollowingLLM:
    """Answers like a well-behaved model: reports the measured facts and puts the most important confirmed
    fault first (safety before technique, then the fault list's order)."""

    provider, model = MOCK_PROVIDER, MOCK_MODEL

    def __init__(self):
        self.requests: list[LLMRequest] = []

    @property
    def calls(self) -> int:
        return len(self.requests)

    def reply_for(self, request: LLMRequest) -> str:
        p = request.payload
        lift = p.get("analysis_lift") or p["lift"]
        # Follows the fault list in the request, as a real model would (US-25: it may be edited).
        offered = p.get("fault_list") or [{"id": f.id, "name": f.name, "category": f.category, "metric": f.metric}
                                          for f in faults_for(lift)]
        by_id = {f["id"]: f for f in offered}
        order = {f["id"]: (f["category"] != "safety", i) for i, f in enumerate(offered)}
        confirmed = sorted((fid for fid in p["confirmed_faults"] if fid in order), key=order.get)

        def cite(fault_id):
            reps = p["confirmed_faults"][fault_id]
            metric = by_id[fault_id]["metric"]
            value = p["reps"][reps[0] - 1]["metrics"][metric]
            return reps, {"metric": metric, "rep": reps[0], "value": value}

        out = {"lift": lift, "camera_angle": p["camera_angle"], "rep_count": p["rep_count"],
               "top_fault_id": None, "fault_reps": [], "supporting_measurement": None, "other_faults": [],
               "cue": "", "explanation": "Solid set. Every rep stayed within the measured limits.",
               "professional_recommendation": REFERRAL if mentions_pain(p.get("note")) else None}
        if confirmed:
            top, *others = confirmed
            out["top_fault_id"] = top
            out["fault_reps"], out["supporting_measurement"] = cite(top)
            out["cue"] = CUES.get(top, DEFAULT_CUE)
            out["explanation"] = f"{by_id[top]['name']} on the reps marked below."
            for fid in others:
                reps, sm = cite(fid)
                out["other_faults"].append({"fault_id": fid, "reps": reps, "supporting_measurement": sm})
        return json.dumps(out)

    def complete(self, request: LLMRequest) -> LLMReply:
        self.requests.append(request)
        text = self.reply_for(request)
        return _reply(text, *_tokens(request, text))


class SpyLLM(RuleFollowingLLM):
    """A RuleFollowingLLM used to check whether the LLM was called at all."""


class ScriptedLLM:
    """Replies with the given texts in order (repeating the last)."""

    provider, model = MOCK_PROVIDER, MOCK_MODEL

    def __init__(self, replies: Sequence[str]):
        self.replies = list(replies)
        self.requests: list[LLMRequest] = []

    @property
    def calls(self) -> int:
        return len(self.requests)

    def complete(self, request: LLMRequest) -> LLMReply:
        self.requests.append(request)
        return _reply(self.replies[min(len(self.requests), len(self.replies)) - 1], 100, 50)


class SequenceLLM(RuleFollowingLLM):
    """One behavior per call: "pass" answers correctly, "invalid" replies with non-JSON text."""

    def __init__(self, behaviors: Sequence[str]):
        super().__init__()
        self.behaviors = list(behaviors)

    def complete(self, request: LLMRequest) -> LLMReply:
        behavior = self.behaviors[min(len(self.requests), len(self.behaviors) - 1)]
        if behavior == "pass":
            return super().complete(request)
        self.requests.append(request)
        text = "this is not JSON"
        return _reply(text, *_tokens(request, text))


class FailingLLM:
    """Every call fails, like a provider outage."""

    provider, model = MOCK_PROVIDER, MOCK_MODEL

    def __init__(self):
        self.calls = 0

    def complete(self, request: LLMRequest) -> LLMReply:
        self.calls += 1
        raise RuntimeError("LLM provider unavailable")


class ScenarioLLM(RuleFollowingLLM):
    """Test mode: behaves like RuleFollowingLLM, but fails every attempt when the note contains "#fallback"."""

    def complete(self, request: LLMRequest) -> LLMReply:
        if re.search(r"#fallback\b", request.payload.get("note") or ""):
            self.requests.append(request)
            return _reply("this is not JSON", 10, 5)
        return super().complete(request)


class FakeVideoBackend:
    """Stands in for OpenCV + MediaPipe. Pose frames come from a synthetic scenario picked by file name."""

    def __init__(self, frames: Callable[[str], list[PoseFrame]] | list[PoseFrame] = scenario_frames,
                 duration: float = 10.0, fps: float = 30.0, unreadable: bool = False,
                 fail_on_poses: bool = False, probe_files: bool = False):
        self._frames = frames
        self.duration, self.fps = duration, fps
        self.unreadable, self.fail_on_poses, self.probe_files = unreadable, fail_on_poses, probe_files

    def probe(self, path: str) -> VideoInfo:
        if self.unreadable:
            raise VideoUnreadable("unreadable")
        if self.probe_files:
            from app.video import probe_video

            return probe_video(path)
        return VideoInfo(duration=self.duration, fps=self.fps, frame_count=int(self.duration * self.fps), width=640, height=360)

    def poses(self, path: str, info: VideoInfo, filename: str) -> list[PoseFrame]:
        if self.fail_on_poses:
            raise RuntimeError("pose estimation crashed")
        return self._frames(filename) if callable(self._frames) else list(self._frames)

    def frame(self, path: str, index: int) -> np.ndarray:
        return np.zeros((360, 640, 3), np.uint8)


class ScenarioVideoBackend(FakeVideoBackend):
    """Browser test mode: fail once for each `fail_once-...` filename, then allow retry."""

    def __init__(self):
        super().__init__(probe_files=True)
        self.failed_filenames: set[str] = set()

    def poses(self, path: str, info: VideoInfo, filename: str) -> list[PoseFrame]:
        if filename.startswith("fail_once-") and filename not in self.failed_filenames:
            self.failed_filenames.add(filename)
            raise RuntimeError("Simulated transient pose failure")
        return super().poses(path, info, filename)
