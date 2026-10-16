"""Parquet/JSON storage under `data/`: atomic writes, daily partitions and the ingest run log."""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from hirup_pipelines import schemas
from hirup_pipelines.settings import data_dir


def atomic_path(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")


def replace(tmp: Path, path: Path, attempts: int = 10, wait_s: float = 0.2) -> None:
    """`os.replace` that rides out short Windows locks (sync clients, scanners, readers)."""
    for attempt in range(attempts):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == attempts - 1:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(wait_s * (attempt + 1))


def write_parquet(frame: pd.DataFrame, path: Path) -> None:
    tmp = atomic_path(path)
    frame.to_parquet(tmp, index=False)
    replace(tmp, path)


def write_json(payload: Any, path: Path) -> None:
    tmp = atomic_path(path)
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    replace(tmp, path)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_parquet(path: Path, columns: list[str] | None = None) -> pd.DataFrame | None:
    return pd.read_parquet(path, columns=columns) if path.is_file() else None


def upsert(frame: pd.DataFrame, path: Path, keys: list[str]) -> pd.DataFrame:
    """Merge new rows into a parquet file; on a key clash the new row wins."""
    old = read_parquet(path)
    merged = frame if old is None else pd.concat([old, frame], ignore_index=True)
    merged = merged.drop_duplicates(keys, keep="last").sort_values(keys).reset_index(drop=True)
    write_parquet(merged, path)
    return merged


def write_daily(frame: pd.DataFrame, root: Path, keys: list[str], *, replace: bool = False) -> int:
    """Write rows into `root/date=YYYY-MM-DD/part.parquet` by the UTC date of `ts`."""
    if frame.empty:
        return 0
    days = frame["ts"].dt.tz_convert("UTC").dt.strftime("%Y-%m-%d")
    for day, part in frame.groupby(days):
        target = root / f"date={day}" / "part.parquet"
        if replace:
            write_parquet(part.sort_values(keys).reset_index(drop=True), target)
        else:
            upsert(part, target, keys)
    return len(frame)


def read_daily(
    root: Path, start: datetime | None = None, end: datetime | None = None
) -> pd.DataFrame:
    """Read a daily-partitioned table with DuckDB, optionally filtered to [start, end)."""
    if not any(root.glob("date=*/part.parquet")):
        return pd.DataFrame()
    pattern = (root / "date=*" / "part.parquet").as_posix()
    query = "SELECT * FROM read_parquet(?, union_by_name = true)"
    params: list[Any] = [pattern]
    clauses = []
    if start is not None:
        clauses.append("ts >= ?")
        params.append(start)
    if end is not None:
        clauses.append("ts < ?")
        params.append(end)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    with duckdb.connect() as con:
        con.execute("SET TimeZone = 'UTC'")
        frame = con.execute(query + " ORDER BY ts", params).df()
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    return frame


@dataclass
class Run:
    source: str
    rows: int = 0
    notes: dict[str, Any] = field(default_factory=dict)


@contextmanager
def log_run(source: str) -> Iterator[Run]:
    """Record one pipeline step in `ingest_runs.parquet`; failures are logged then re-raised."""
    run = Run(source)
    started = datetime.now(UTC)
    status, error = "ok", None
    try:
        yield run
    except BaseException as exc:
        status, error = "failed", f"{type(exc).__name__}: {exc}"[:500]
        raise
    finally:
        row = pd.DataFrame(
            [
                {
                    "run_id": uuid.uuid4().hex,
                    "source": source,
                    "start": started,
                    "end": datetime.now(UTC),
                    "status": status,
                    "rows": int(run.rows),
                    "error": error,
                }
            ]
        )
        row["error"] = row["error"].astype("string")
        path = data_dir() / "ingest_runs.parquet"
        old = read_parquet(path)
        merged = row if old is None else pd.concat([old, row], ignore_index=True)
        write_parquet(schemas.validate(merged, schemas.INGEST_RUNS), path)
