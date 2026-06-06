#!/usr/bin/env python3

from __future__ import annotations

import base64
import io
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import click
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MaxNLocator


def list_workouts(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT name FROM workouts ORDER BY name;").fetchall()
    return [row[0] for row in rows]


def print_workouts(conn: sqlite3.Connection) -> None:
    for name in list_workouts(conn):
        print(name)


def load_rows(
    conn: sqlite3.Connection, workout_name: str
) -> list[tuple[int, int, int]]:
    cursor = conn.execute(
        """
        SELECT date, lap, difference
        FROM sets
        WHERE workout_name = ?
        ORDER BY date ASC, lap ASC;
        """,
        (workout_name,),
    )
    return [(row[0], row[1], row[2]) for row in cursor.fetchall()]


def format_date(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def format_ms(ms: float) -> str:
    total_ms = int(round(ms))
    minutes, rem = divmod(total_ms, 60_000)
    seconds, millis = divmod(rem, 1_000)
    return f"{minutes}:{seconds:02d}.{millis:03d}"


def render_png_bytes(workout_name: str, rows: list[tuple[int, int, int]]) -> bytes:
    series_by_date: dict[int, list[tuple[int, int]]] = {}
    for date, lap, difference_ms in rows:
        x = lap - 1
        y = difference_ms
        series_by_date.setdefault(date, []).append((x, y))

    fig, ax = plt.subplots(figsize=(10, 6))

    for date in sorted(series_by_date):
        points = series_by_date[date]
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        ax.plot(xs, ys, marker="o", label=format_date(date))

    ax.set_title(workout_name)
    ax.set_xlabel("Set number")
    ax.set_ylabel("Split time")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: format_ms(value)))
    ax.grid(True, alpha=0.3)
    ax.legend(title="Workout date")

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    return buf.getvalue()


def print_kitty_png_bytes(png: bytes) -> None:
    data = base64.b64encode(png).decode("ascii")
    chunk_size = 4096
    chunks = [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]

    for i, chunk in enumerate(chunks):
        more = 1 if i < len(chunks) - 1 else 0
        if i == 0:
            header = f"a=T,f=100,m={more}"
        else:
            header = f"m={more}"
        sys.stdout.write(f"\033_G{header};{chunk}\033\\")

    sys.stdout.write("\n")
    sys.stdout.flush()


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("workout_name", required=False)
@click.option(
    "--db",
    default="workouts.sqlite",
    show_default=True,
    type=click.Path(dir_okay=False, path_type=Path),
)
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Also write the PNG to this path.",
)
@click.option(
    "--list",
    is_flag=True,
    help="List available workouts and exit.",
)
def main(
    workout_name: str | None,
    db: Path,
    output: Path | None,
    list: bool,
) -> None:
    """Graph workout split times."""
    if not list and not workout_name:
        raise click.UsageError("workout_name is required unless --list is used")

    if not db.exists():
        raise click.FileError(str(db), hint="database does not exist")

    conn = sqlite3.connect(db)
    try:
        if list:
            print_workouts(conn)
            return

        rows = load_rows(conn, workout_name)
        if not rows:
            available = "\n".join(f"  {name}" for name in list_workouts(conn))
            raise click.ClickException(
                f'no data found for workout: "{workout_name}"\n'
                f"available workouts:\n{available}"
            )

        png_bytes = render_png_bytes(workout_name, rows)

        if output:
            output.write_bytes(png_bytes)

        print_kitty_png_bytes(png_bytes)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
