"""The lifts the app analyzes."""
from typing import Literal

Lift = Literal["squat", "deadlift", "bench_press", "overhead_press", "romanian_deadlift"]
# US-28 added the overhead press and the Romanian deadlift after the original three.
LIFTS: tuple[str, ...] = ("squat", "deadlift", "bench_press", "overhead_press", "romanian_deadlift")
LIFT_LABELS = {"squat": "Squat", "deadlift": "Deadlift", "bench_press": "Bench Press",
               "overhead_press": "Overhead Press", "romanian_deadlift": "Romanian Deadlift"}
# Used in sentences: "the video shows a bench press".
LIFT_NOUNS = {"squat": "squat", "deadlift": "deadlift", "bench_press": "bench press",
              "overhead_press": "overhead press", "romanian_deadlift": "Romanian deadlift"}


def with_article(noun: str) -> str:
    """'a squat', 'an overhead press'."""
    return f"{'an' if noun[:1].lower() in 'aeiou' else 'a'} {noun}"
