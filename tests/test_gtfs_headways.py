import zipfile
from datetime import datetime
from pathlib import Path

from services.routing.gtfs import GtfsHeadways


def feed(path: Path, *, overnight: bool = False) -> None:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(
            "trips.txt",
            "route_id,service_id,trip_id,direction_id\nr,weekday,t1,0\nr,weekday,t2,0\n",
        )
        z.writestr(
            "stop_times.txt", "trip_id,stop_id,departure_time\nt1,s,06:00:00\nt2,s,06:12:00\n"
        )
        z.writestr(
            "calendar.txt",
            "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nweekday,1,1,1,1,1,0,0,20260101,20261231\n",
        )
        z.writestr("calendar_dates.txt", "service_id,date,exception_type\nweekday,20261015,2\n")
        z.writestr(
            "frequencies.txt",
            "trip_id,start_time,end_time,headway_secs\n"
            + ("t1,24:00:00,26:00:00,900\n" if overnight else "t1,07:00:00,09:00:00,600\n"),
        )


def test_headway_from_departures_frequency_and_calendar_exceptions(tmp_path: Path) -> None:
    path = tmp_path / "test.zip"
    feed(path)
    gtfs = GtfsHeadways({"test": path})
    assert (
        gtfs.headway("test:t1", "test:s", datetime.fromisoformat("2026-10-14T06:05:00+07:00"))
        == 720
    )
    assert (
        gtfs.headway("test:t1", "test:s", datetime.fromisoformat("2026-10-14T08:00:00+07:00"))
        == 600
    )
    assert (
        gtfs.headway("test:t1", "test:s", datetime.fromisoformat("2026-10-15T08:00:00+07:00"))
        is None
    )
    assert (
        gtfs.headway("missing:t1", "test:s", datetime.fromisoformat("2026-10-14T08:00:00+07:00"))
        is None
    )


def test_after_midnight_service_times(tmp_path: Path) -> None:
    path = tmp_path / "test.zip"
    feed(path, overnight=True)
    gtfs = GtfsHeadways({"test": path})
    assert (
        gtfs.headway("test:t1", "test:s", datetime.fromisoformat("2026-10-15T00:30:00+07:00"))
        == 900
    )
    assert (
        gtfs.headway("test:t1", "test:s", datetime.fromisoformat("2026-10-14T00:30:00+07:00"))
        == 900
    )
