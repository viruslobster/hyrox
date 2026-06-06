#!/usr/bin/env python3

import argparse
from math import floor, sqrt

threshold_pace_min_per_km = 4 + 45/60


def parse_pace(pace: str) -> float:
    try:
        minutes_str, seconds_str = pace.split(":", maxsplit=1)
        minutes = int(minutes_str)
        seconds = int(seconds_str)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid pace '{pace}'; expected M:SS"
        ) from exc

    if minutes < 0 or not 0 <= seconds < 60:
        raise argparse.ArgumentTypeError(
            f"invalid pace '{pace}'; seconds must be between 00 and 59"
        )

    return minutes + seconds / 60

def pace_effort(pace: float, threshold: float) -> int:
    pace_velocity = 1 / pace
    threshold_velocity = 1 / threshold
    percent = (pace_velocity / threshold_velocity)**2
    
    return floor(percent * 100 + 0.5)

def pace_str(pace: float) -> str:
    minutes = int(pace)
    seconds_dec = pace - minutes
    seconds = floor(seconds_dec * 60 + 0.5)
    return f"{minutes}:{seconds:02}"


def effort_pace(effort: int, threshold: float) -> float:
    if not effort:
        return 0

    percent = sqrt(effort / 100)
    pace_velocity = percent / threshold
    return 1 / pace_velocity


def pace_km_to_mi(pace: float) -> float:
    return pace / 0.6213712


def workout_tempo(threshold_pace: float) -> list[float]:
    # - Tempo: 2mi @ 85%
    return [
        effort_pace(85, threshold_pace)
    ]


def workout_tempo_str(threshold_pace: float) -> str:
    paces = workout_tempo(threshold_pace)
    assert len(paces) == 1
    pace = pace_km_to_mi(paces[0])
            
    return (
        "## Tempo Run\n"
        f"2 miles @ {pace_str(pace)} min / mi\n"
    )


def workout_progressive(threshold_pace: float) -> list[float]:
    # - Progressive: 4x800m @ 70%, 80%, 90%, 100% (no rest)
    return [
        effort_pace(70, threshold_pace),
        effort_pace(80, threshold_pace),
        effort_pace(90, threshold_pace),
        effort_pace(100, threshold_pace),
    ]


def workout_progressive_str(threshold_pace: float) -> str:
    paces = workout_progressive(threshold_pace)
    return (
        "## Progressive Run\n"
        "Paces in min / km\n"
        f"- 800m @ {pace_str(paces[0])}\n"
        f"- 800m @ {pace_str(paces[1])}\n"
        f"- 800m @ {pace_str(paces[2])}\n"
        f"- 800m @ {pace_str(paces[3])}\n"
    )


def workout_race_intervals(threshold: float) -> list[float]:
    # - Race intervals: 3x1000m @ 90-100% (120 sec rest)
    return [
        effort_pace(90, threshold),
        effort_pace(100, threshold),
    ]


def workout_race_intervals_str(threshold: float) -> str:
    paces = workout_race_intervals(threshold)
    assert len(paces) == 2

    pace_min, pace_max = paces
    return (
        "## Race Interval Run\n"
        "Paces in min / km\n"
        f"- 1000m run @ {pace_str(pace_max)} - {pace_str(pace_min)}\n"
        "- 120 sec rest\n"
        f"- 1000m run @ {pace_str(pace_max)} - {pace_str(pace_min)}\n"
        "- 120 sec rest\n"
        f"- 1000m run @ {pace_str(pace_max)} - {pace_str(pace_min)}\n"
    )


def workout_short_intervals(threshold: float) -> list[float]:
    # - Short intervals: 8x400m @ 120% (60 sec rest)
    return [effort_pace(120, threshold)]

def workout_short_intervals_str(threshold: float) -> str:
    paces = workout_short_intervals(threshold)
    assert len(paces) == 1
    pace = paces[0]

    return (
        "## Short Interval Run\n"
        "Paces in min / km\n"
        f"- 400m run @ {pace_str(pace)}\n"
        "- 60 sec rest\n"
        f"- 400m run @ {pace_str(pace)}\n"
        "- 60 sec rest\n"
        f"- 400m run @ {pace_str(pace)}\n"
        "- 60 sec rest\n"
        f"- 400m run @ {pace_str(pace)}\n"
        "- 60 sec rest\n"
        f"- 400m run @ {pace_str(pace)}\n"
        "- 60 sec rest\n"
        f"- 400m run @ {pace_str(pace)}\n"
        "- 60 sec rest\n"
        f"- 400m run @ {pace_str(pace)}\n"
        "- 60 sec rest\n"
        f"- 400m run @ {pace_str(pace)}\n"
    )




if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--threshold",
        type=parse_pace,
        default=threshold_pace_min_per_km,
        help="threshold pace in min/km, formatted as M:SS",
    )
    args = parser.parse_args()

    print("# Running workouts")
    print(workout_tempo_str(args.threshold))
    print(workout_progressive_str(args.threshold))
    print(workout_race_intervals_str(args.threshold))
    print(workout_short_intervals_str(args.threshold))
#$

