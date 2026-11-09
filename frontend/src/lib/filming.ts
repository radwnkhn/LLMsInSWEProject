import type { Lift } from "@/lib/types";

export type FilmingGuide = { tips: string[]; image: string; imageAlt: string };

export const FILMING_GUIDES: Record<Lift, FilmingGuide> = {
  squat: {
    tips: [
      "Film from a side view so we can see your hips, knees and back.",
      "Set the phone at hip height, about 3 m (10 ft) away.",
      "Keep your whole body and the bar in frame, head to feet, on every rep.",
      "Want knee-cave checks? Film another set from the front.",
    ],
    image: "/framing/squat.svg",
    imageAlt: "Example of correct framing for a squat",
  },
  deadlift: {
    tips: [
      "Film from a side view so we can see your back and the bar path.",
      "Set the phone at hip height, about 3 m (10 ft) away.",
      "Keep your whole body and the bar in frame, plates on the floor included.",
      "Start recording before you set up so the first pull is in the video.",
    ],
    image: "/framing/deadlift.svg",
    imageAlt: "Example of correct framing for a deadlift",
  },
  bench_press: {
    tips: [
      "Film from a side view, level with the bench.",
      "Set the phone at hip height (about bench height), 2 m (6 ft) away.",
      "Keep your whole body and the bar in frame, bar at lockout included.",
      "Want elbow-flare checks? Film another set from behind your head.",
    ],
    image: "/framing/bench_press.svg",
    imageAlt: "Example of correct framing for a bench press",
  },
};
