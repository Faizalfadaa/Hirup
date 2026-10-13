from datetime import datetime

import pytest

from infra.scripts.smoke import (
    positive_duration,
    road_duration,
    transit_duration,
    transit_payload,
)


@pytest.mark.parametrize("value", [None, True, 0, -1, float("nan"), float("inf"), "10"])
def test_invalid_duration(value: object) -> None:
    with pytest.raises(ValueError):
        positive_duration(value)


def test_road_and_transit_durations() -> None:
    assert road_duration({"code": "Ok", "routes": [{"duration": 120}]}) == 120
    assert (
        transit_duration(
            {
                "data": {
                    "plan": {
                        "itineraries": [
                            {"duration": 60, "legs": [{"transitLeg": False}]},
                            {"duration": 300, "legs": [{"transitLeg": True}]},
                            {"duration": 180, "legs": [{"transitLeg": True}]},
                        ]
                    }
                }
            }
        )
        == 180
    )


def test_walk_only_is_not_a_successful_transit_smoke() -> None:
    with pytest.raises(ValueError, match="no transit itinerary"):
        transit_duration(
            {
                "data": {
                    "plan": {
                        "itineraries": [
                            {"duration": 60, "legs": [{"transitLeg": False}]},
                        ]
                    }
                }
            }
        )


def test_upstream_errors_fail() -> None:
    with pytest.raises(ValueError, match="OSRM route failed"):
        road_duration({"code": "NoRoute"})
    with pytest.raises(ValueError, match="GraphQL error"):
        transit_duration({"errors": [{"message": "Bad query"}]})


def test_departure_is_explicit_in_graphql() -> None:
    payload = transit_payload(datetime.fromisoformat("2026-10-14T08:00:00+07:00"))
    assert payload["variables"] == {"date": "2026-10-14", "time": "08:00:00"}
