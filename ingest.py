#!/usr/bin/env python3

from __future__ import annotations

import csv
import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import time

import click

DATE_FORMAT = "%B %d, %Y %I:%M %p"


@dataclass
class ParsedSet:
    lap: int
    total_time_ms: int
    difference_ms: int


@dataclass
class ParsedWorkoutFile:
    path: Path
    file_hash: str
    workout_name: str
    workout_date: int
    sets: list[ParsedSet]


def parse_file(path: Path, workout_name: str) -> ParsedWorkoutFile:
    data = path.read_bytes()
    digest = file_sha256(data)
    text = data.decode("utf-8-sig")
    lines = text.splitlines()

    non_empty = [line.strip() for line in lines if line.strip()]
    if len(non_empty) < 3:
        raise ValueError(f"Unexpected Stopwatch Pro format in {path}")
    if non_empty[0] != "Stopwatch Pro":
        raise ValueError(f"Unexpected first line in {path}: {non_empty[0]!r}")

    workout_date = parse_workout_date(non_empty[1])

    time_line = next((line for line in non_empty if line.startswith("Time:")), None)
    if time_line is None:
        raise ValueError(f"Missing Time line in {path}")
    final_time = time_line.split(":", 1)[1].strip()

    sets: list[ParsedSet] = []
    try:
        header_index = next(
            i
            for i, line in enumerate(lines)
            if line.strip() == "Lap,Total time,Difference"
        )
    except StopIteration:
        duration = parse_duration_ms(final_time)
        sets.append(ParsedSet(lap=1, total_time_ms=duration, difference_ms=duration))
    else:
        table_text = "\n".join(line for line in lines[header_index:] if line.strip())
        reader = csv.DictReader(table_text.splitlines())
        for row in reader:
            sets.append(
                ParsedSet(
                    lap=int(row["Lap"]),
                    total_time_ms=parse_duration_ms(row["Total time"]),
                    difference_ms=parse_duration_ms(row["Difference"]),
                )
            )
        if not sets:
            raise ValueError(f"Lap table in {path} did not contain any rows")

    return ParsedWorkoutFile(
        path=path,
        file_hash=digest,
        workout_name=workout_name,
        workout_date=workout_date,
        sets=sets,
    )


def ingest_files(
    paths: list[Path],
    db_path: Path,
    workout_name: str,
) -> None:
    conn = sqlite3.connect(db_path)
    try:
        init_db(conn)
        inserted = 0
        skipped = 0

        for path in paths:
            parsed = parse_file(path, workout_name)
            if ingest_parsed_file(conn, parsed):
                click.echo(f"ingested {path}")
                inserted += 1
            else:
                click.echo(f"skipped already-ingested {path}")
                skipped += 1

        click.echo(f"done: {inserted} ingested, {skipped} skipped")
    finally:
        conn.close()


def ingest_parsed_file(conn: sqlite3.Connection, parsed: ParsedWorkoutFile) -> bool:
    """Return True if inserted, False if skipped."""
    if already_ingested(conn, parsed.file_hash):
        return False

    with conn:
        conn.executemany(
            """
            INSERT INTO sets (
                workout_name,
                date,
                lap,
                total_time,
                difference
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    parsed.workout_name,
                    parsed.workout_date,
                    item.lap,
                    item.total_time_ms,
                    item.difference_ms,
                )
                for item in parsed.sets
            ],
        )

        conn.execute(
            "INSERT INTO ingested (time, data_hash) VALUES (?, ?)",
            (int(time()), parsed.file_hash),
        )

    return True


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS workouts (
            name TEXT PRIMARY KEY,
            description TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workout_name TEXT NOT NULL,
            date INTEGER NOT NULL,
            lap INTEGER NOT NULL,
            total_time INTEGER NOT NULL,
            difference INTEGER NOT NULL,
            FOREIGN KEY (workout_name) REFERENCES workouts(name)
        );

        CREATE TABLE IF NOT EXISTS ingested (
            time INTEGER NOT NULL,
            data_hash TEXT PRIMARY KEY
        );
        """
    )


def discover_csv_files(csv_files: tuple[Path, ...], csv_dir: Path | None) -> list[Path]:
    if csv_files:
        paths = list(csv_files)
    else:
        if csv_dir is None:
            csv_dir = Path("csv")
        if not csv_dir.exists():
            raise FileNotFoundError(f"CSV directory does not exist: {csv_dir}")
        if not csv_dir.is_dir():
            raise NotADirectoryError(f"CSV path is not a directory: {csv_dir}")
        paths = sorted(csv_dir.glob("*.csv"))

    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"CSV file does not exist: {path}")
        if not path.is_file():
            raise ValueError(f"CSV path is not a file: {path}")

    return paths


def already_ingested(conn: sqlite3.Connection, data_hash: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM ingested WHERE data_hash = ?",
        (data_hash,),
    ).fetchone()
    return row is not None


def file_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_duration_ms(value: str) -> int:
    value = value.strip()
    parts = value.split(":")

    if len(parts) == 2:
        hours = 0
        minutes = int(parts[0])
        seconds_part = parts[1]
    elif len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds_part = parts[2]
    else:
        raise ValueError(f"Unsupported duration format: {value!r}")

    if "." in seconds_part:
        seconds_text, fraction_text = seconds_part.split(".", 1)
        seconds = int(seconds_text)
        millis = int((fraction_text + "000")[:3])
    else:
        seconds = int(seconds_part)
        millis = 0

    return ((hours * 3600 + minutes * 60 + seconds) * 1000) + millis


def parse_workout_date(value: str) -> int:
    dt = datetime.strptime(value.strip(), DATE_FORMAT)
    return int(dt.timestamp())


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument(
    "csv_files",
    nargs=-1,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--csv-dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    help="Directory of CSV files to ingest when no CSV files are passed.",
)
@click.option(
    "--db",
    default=Path("workouts.sqlite"),
    show_default=True,
    type=click.Path(dir_okay=False, path_type=Path),
)
@click.option(
    "--workout-name",
    required=True,
    help="Existing workout row/name these CSV files belong to.",
)
def main(csv_files: tuple[Path, ...], csv_dir: Path | None, db: Path, workout_name: str) -> None:
    """Ingest Stopwatch Pro CSV splits into SQLite."""
    paths = discover_csv_files(csv_files, csv_dir)
    ingest_files(paths, db, workout_name)


if __name__ == "__main__":
    main()
