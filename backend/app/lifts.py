"""The lifts the app analyzes."""
from typing import Literal

Lift = Literal["squat", "deadlift", "bench_press"]
LIFTS: tuple[str, ...] = ("squat", "deadlift", "bench_press")
LIFT_LABELS = {"squat": "Squat", "deadlift": "Deadlift", "bench_press": "Bench Press"}
# Used in sentences: "the video shows a bench press".
LIFT_NOUNS = {"squat": "squat", "deadlift": "deadlift", "bench_press": "bench press"}
