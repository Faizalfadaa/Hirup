"""Small deterministic GTFS fixtures, independent of downloads and Docker."""

from __future__ import annotations

import zipfile
import json
from pathlib import Path

import pytest

from infra.scripts.routing_data import (
    Bounds,
    FeedError,
    manual_feeds,
    prepare_gtfs,
    stage,
    validate_feed,
)


def tables() -> dict[str, str]:
    return {
        "agency.txt": "agency_id,agency_name,agency_url,agency_timezone\n"
        "a,Test,https://example.invalid,Asia/Jakarta\n",
        "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\n"
        "s1,Inside,-6.2,106.8\ns2,Outside,-6.4,106.8\n",
        "routes.txt": "route_id,agency_id,route_short_name,route_type\nr,a,R,3\n",
        "trips.txt": "route_id,service_id,trip_id,shape_id\nr,c,t,sh\n",
        "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "t,08:00:00,08:00:00,s1,1\nt,08:10:00,08:10:00,s2,2\n",
        "shapes.txt": "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n"
        "sh,-6.2,106.8,1\nsh,-6.4,106.8,2\n",
        "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,"
        "saturday,sunday,start_date,end_date\nc,1,1,1,1,1,1,1,20260101,20261231\n",
    }


def write_feed(path: Path, content: dict[str, str] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, text in (tables() if content is None else content).items():
            archive.writestr(name, text)
    return path


def test_buffer_and_coordinate_order() -> None:
    bounds = Bounds().buffered()
    # Hand estimate: 2 km / ~110.6 km per latitude degree = ~0.0181 degrees.
    assert bounds.south == pytest.approx(-6.3181, abs=0.0001)
    assert bounds.north == pytest.approx(-6.1119, abs=0.0001)
    assert bounds.west == pytest.approx(106.7419, abs=0.0001)
    assert bounds.east == pytest.approx(106.8681, abs=0.0001)
    assert bounds.contains(106.76, -6.30)
    assert not Bounds().contains(-6.2, 106.8)
    assert Bounds().osmium() == "106.76000000,-6.30000000,106.85000000,-6.13000000"


@pytest.mark.parametrize("distance", [-1, float("nan"), float("inf")])
def test_invalid_buffer(distance: float) -> None:
    with pytest.raises(ValueError, match="Buffer"):
        Bounds().buffered(distance)


def test_feed_summary_keeps_outside_stops_without_changing_schedules(
    tmp_path: Path,
) -> None:
    feed = write_feed(tmp_path / "bus.gtfs.zip")
    before = feed.read_bytes()
    summary = validate_feed(feed)
    assert summary["stops_in_pilot"] == 1
    assert summary["stops_outside_pilot"] == 1
    assert summary["shapes"] == 1
    assert summary["trips"] == 1
    assert summary["service_start"] == "2026-01-01"
    assert summary["service_end"] == "2026-12-31"
    assert feed.read_bytes() == before


@pytest.mark.parametrize("missing", ["stops.txt", "shapes.txt", "stop_times.txt"])
def test_missing_table(tmp_path: Path, missing: str) -> None:
    content = tables()
    del content[missing]
    with pytest.raises(FeedError, match=missing):
        validate_feed(write_feed(tmp_path / "bad.zip", content))


@pytest.mark.parametrize("coordinate", ["nan", "inf", "91", "-91", ""])
def test_invalid_stop_coordinates(tmp_path: Path, coordinate: str) -> None:
    content = tables()
    content["stops.txt"] = content["stops.txt"].replace("-6.2", coordinate)
    with pytest.raises(FeedError, match="coordinates"):
        validate_feed(write_feed(tmp_path / "bad.zip", content))


@pytest.mark.parametrize(
    "table,old,new,message",
    [
        ("stops.txt", "-6.2", "-6.5", "No stops"),
        ("agency.txt", "Asia/Jakarta", "UTC", "Asia/Jakarta"),
        ("trips.txt", "r,c,t,sh", "r,c,t,missing", "shape"),
        ("trips.txt", "r,c,t,sh", "missing,c,t,sh", "route"),
        ("trips.txt", "r,c,t,sh", "r,missing,t,sh", "calendar"),
        ("stop_times.txt", ",s1,", ",missing,", "unknown stop"),
        ("calendar.txt", "20261231", "20250101", "start is after"),
    ],
)
def test_invalid_references(
    tmp_path: Path,
    table: str,
    old: str,
    new: str,
    message: str,
) -> None:
    content = tables()
    content[table] = content[table].replace(old, new)
    with pytest.raises(FeedError, match=message):
        validate_feed(write_feed(tmp_path / "bad.zip", content))


def test_calendar_dates_only(tmp_path: Path) -> None:
    content = tables()
    del content["calendar.txt"]
    content["calendar_dates.txt"] = "service_id,date,exception_type\nc,20261014,1\n"
    summary = validate_feed(write_feed(tmp_path / "dates.zip", content))
    assert summary["service_end"] == "2026-10-14"


def test_empty_shapes_and_duplicate_tables_fail(tmp_path: Path) -> None:
    content = tables()
    content["shapes.txt"] = content["shapes.txt"].splitlines()[0] + "\n"
    with pytest.raises(FeedError, match="empty"):
        validate_feed(write_feed(tmp_path / "bad.zip", content))
    content = tables()
    content["duplicate/stops.txt"] = content["stops.txt"]
    with pytest.raises(FeedError, match="exactly one stops.txt"):
        validate_feed(write_feed(tmp_path / "duplicates.zip", content))


def test_unreadable_feed(tmp_path: Path) -> None:
    path = tmp_path / "html.zip"
    path.write_text("<html>upstream error</html>")
    with pytest.raises(FeedError, match="Unreadable"):
        validate_feed(path)


def test_manual_zip_and_tables_are_separate_namespaced_otp_inputs(
    tmp_path: Path,
) -> None:
    write_feed(tmp_path / "data/gtfs/transjakarta.gtfs.zip")
    manual = tmp_path / "data_prep/gtfs_manual"
    source = write_feed(manual / "mrt.zip")
    before = source.read_bytes()
    (manual / "lrt").mkdir()
    for name, text in tables().items():
        (manual / "lrt" / name).write_text(text)
    assert len(manual_feeds(tmp_path)) == 2
    summaries = prepare_gtfs(tmp_path)
    assert len(summaries) == 3
    assert source.read_bytes() == before
    assert (tmp_path / "data/gtfs/manual-mrt.gtfs.zip").is_file()
    assert (tmp_path / "data/gtfs/manual-lrt.gtfs.zip").is_file()
    # Both manual feeds may reuse bus IDs safely: ZIPs remain separate.
    assert {summary["trips"] for summary in summaries} == {1}
    assert [summary["data_quality"] for summary in summaries] == [
        "real",
        "approximated",
        "approximated",
    ]


def test_stage_refuses_missing_osm_and_removes_stale_feed_copies(
    tmp_path: Path,
) -> None:
    with pytest.raises(FeedError, match="Missing pilot"):
        stage(tmp_path)
    write_feed(tmp_path / "data/gtfs/transjakarta.gtfs.zip")
    osm = tmp_path / "data/osm"
    osm.mkdir()
    (osm / "pilot.osm.pbf").write_bytes(b"test OSM input")
    configs = tmp_path / "infra/otp"
    configs.mkdir(parents=True)
    for name in ("build-config.json", "router-config.json", "otp-config.json"):
        (configs / name).write_text("{}")
    target = tmp_path / "data/otp"
    target.mkdir()
    (target / "stale.gtfs.zip").write_bytes(b"obsolete")
    stage(tmp_path)
    assert not (target / "stale.gtfs.zip").exists()
    assert (target / "pilot.osm.pbf").read_bytes() == b"test OSM input"
    assert (target / "transjakarta.gtfs.zip").is_file()
    assert json.loads((target / "build-config.json").read_text())["transitFeeds"] == [
        {
            "type": "gtfs",
            "feedId": "transjakarta",
            "source": "file:///var/opentripplanner/transjakarta.gtfs.zip",
        }
    ]


def test_csv_with_bom(tmp_path: Path) -> None:
    content = tables()
    content["stops.txt"] = "\ufeff" + content["stops.txt"]
    assert validate_feed(write_feed(tmp_path / "bom.zip", content))["stops"] == 2


def test_csv_missing_fields_fail(tmp_path: Path) -> None:
    content = tables()
    content["stops.txt"] = "stop_id,stop_lat,stop_lon\ns1,-6.2\n"
    with pytest.raises(FeedError, match="Malformed CSV"):
        validate_feed(write_feed(tmp_path / "malformed.zip", content))
