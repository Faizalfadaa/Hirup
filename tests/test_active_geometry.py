from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from services.exposure.geometry import GEOD, Point, distance_m, hour_key, sample_polyline
from services.routing.active_params import DEFAULT_PATH, load_active_params


def east(point: Point, metres: float) -> Point:
    lon, lat, _ = GEOD.fwd(point.lon, point.lat, 90, metres)
    return Point(lon, lat)


def test_sampling_does_not_restart_at_vertices() -> None:
    start = Point(106.8, -6.2)
    samples = sample_polyline((start, east(start, 10), east(start, 60)), 25)
    assert len(samples) == 4
    assert [distance_m(start, p) for p in samples] == pytest.approx([0, 25, 50, 60], abs=1e-5)
    assert samples[-1] == east(start, 60)


def test_duplicate_and_zero_length_geometry() -> None:
    point = Point(106.8, -6.2)
    assert sample_polyline((point, point), 25) == (point,)
    assert len(sample_polyline((point, point, east(point, 50)), 25)) == 3


@pytest.mark.parametrize("spacing", [0, -1, float("nan"), float("inf")])
def test_invalid_spacing(spacing: float) -> None:
    with pytest.raises(ValueError, match="spacing"):
        sample_polyline((Point(106.8, -6.2),), spacing)


def test_hour_normalization_and_naive_rejection() -> None:
    assert hour_key(datetime.fromisoformat("2026-10-14T08:59:00+07:00")) == datetime(
        2026, 10, 14, 1, tzinfo=UTC
    )
    with pytest.raises(ValueError, match="timezone"):
        hour_key(datetime(2026, 10, 14))


def test_active_parameters_come_from_frozen_contract() -> None:
    params = load_active_params()
    assert (params.walk_speed_m_s, params.bike_speed_m_s) == (1.2, 4.2)
    assert (params.max_detour_frac, params.max_detour_s) == (0.5, 480)
    assert params.lambdas == (0, 0.5, 1.5, 3)
    assert params.sample_spacing_m == 25


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("walk_speed_m_s", 0),
        ("bike_speed_m_s", True),
        ("sample_spacing_m", -1),
        ("max_detour_frac", float("nan")),
        ("lambdas", [0.5, 3]),
        ("lambdas", [0, -1]),
    ],
)
def test_invalid_contract_parameters_rejected(tmp_path: Path, name: str, value: object) -> None:
    document = yaml.safe_load(DEFAULT_PATH.read_text())
    document["active_routing"][name]["value"] = value
    path = tmp_path / "params.yaml"
    path.write_text(yaml.safe_dump(document))
    with pytest.raises(ValueError, match="routing"):
        load_active_params(path)
