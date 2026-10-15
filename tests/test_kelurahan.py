import asyncio
import json
import math
import random
import sys
import threading
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from services.api import runtime as runtime_module
from services.api.main import create_app
from services.api.refresh import hourly, refresh
from services.api.runtime import Runtime
from services.api.schemas.insights import KelurahanInsightsResponse
from services.exposure import kelurahan as kelurahan_module
from services.exposure.aq_provider import AQUnavailableError
from services.exposure.aq_service import AQService
from services.exposure.kelurahan import (
    KelurahanArtifact,
    KelurahanService,
    aggregate_kelurahan,
    mean_daily_values,
)
from services.exposure.params import UnverifiedParamsWarning
from tests.test_aq_provider import BOUNDS
from tests.test_plan_api import FlatAQ

FROM = date(2026, 10, 12)
TO = date(2026, 10, 13)
NOW = datetime.fromisoformat("2026-10-14T08:30:00+07:00")


def seeded_document(seed=20261014):
    """Seeded ordering with hand-computed synthetic concentrations, never real P2 evidence."""
    rng = random.Random(seed)
    regions = [
        {"kelurahan_id": "test-a", "name": "Wilayah Tes A", "kecamatan": "Kecamatan Tes"},
        {"kelurahan_id": "test-b", "name": "Wilayah Tes B", "kecamatan": "Kecamatan Tes"},
    ]
    days = []
    for day, generated, values in (
        (FROM, "2026-10-13T00:15:00+07:00", (10, 40)),
        (TO, "2026-10-14T00:15:00+07:00", (30, 60)),
    ):
        items = []
        for region, value in zip(regions, values, strict=True):
            hours = list(range(24))
            rng.shuffle(hours)
            items.append(
                {"kelurahan_id": region["kelurahan_id"], "mean_pm25": value, "hours_covered": hours}
            )
        rng.shuffle(items)
        days.append(
            {
                "date": day.isoformat(),
                "generated_at": generated,
                "boundaries_version": "synthetic-test-boundaries-v1",
                "source_kind": "model",
                "model_version": "synthetic-test-only",
                "contains_forecast": False,
                "data_quality": "synthetic",
                "items": items,
            }
        )
    rng.shuffle(regions)
    rng.shuffle(days)
    return {
        "source": "seeded hand-computed unit fixture, not production data",
        "aggregation_method": "unit fixture of complete spatial P50 daily means, no real rasters",
        "units": "ug/m3",
        "boundaries_version": "synthetic-test-boundaries-v1",
        "regions": regions,
        "days": days,
    }


def document():
    raw = seeded_document()
    # Order helpers only for specific corruption tests; production accepts either order.
    raw["days"].sort(key=lambda day: day["date"])
    for day in raw["days"]:
        day["items"].sort(key=lambda item: item["kelurahan_id"])
    return raw


def loaded(tmp_path, raw=None, *, allow_synthetic=True):
    path = tmp_path / "kelurahan.json"
    path.write_text(json.dumps(document() if raw is None else raw), encoding="utf-8")
    service = KelurahanService(path, allow_synthetic=allow_synthetic, now=lambda: NOW)
    service.reload()
    return service


def test_hand_computed_complete_inclusive_range_and_stable_ids(tmp_path: Path) -> None:
    service = loaded(tmp_path, seeded_document())
    result = service.summarize(FROM, TO)
    assert result.from_date == FROM
    assert result.to_date == TO
    assert result.boundaries_version == "synthetic-test-boundaries-v1"
    assert [(item.kelurahan_id, item.mean_pm25) for item in result.items] == [
        ("test-a", 20),
        ("test-b", 50),
    ]
    assert result.data_quality == "synthetic"
    single = service.summarize(TO, TO)
    assert [item.mean_pm25 for item in single.items] == [30, 60]
    assert [item.name for item in single.items] == ["Wilayah Tes A", "Wilayah Tes B"]


@pytest.mark.parametrize(
    ("qualities", "forecast", "source_kind", "expected"),
    [
        (("real", "real"), False, "model", "real"),
        (("real", "approximated"), False, "model", "approximated"),
        (("approximated", "real"), False, "model", "approximated"),
        (("real", "real"), True, "model", "approximated"),
        (("real", "real"), False, "cams", "approximated"),
        (("real", "synthetic"), True, "model", "synthetic"),
    ],
)
def test_quality_metadata_policy_only_no_production_data(
    qualities, forecast, source_kind, expected
) -> None:
    # Metadata mutations exercise quality propagation; underlying values stay a unit-only fake.
    raw = document()
    for day, quality in zip(raw["days"], qualities, strict=True):
        day.update(data_quality=quality, contains_forecast=forecast, source_kind=source_kind)
    result = aggregate_kelurahan(
        KelurahanArtifact.model_validate(raw), FROM, TO, NOW, allow_synthetic=True
    )
    assert result.data_quality == expected


@pytest.mark.parametrize(
    "case",
    [
        "missing-hour",
        "duplicate-hour",
        "outside-hour",
        "boolean-hour",
        "missing-region",
        "unknown-region",
        "duplicate-region",
        "duplicate-roster",
        "duplicate-date",
        "wrong-boundaries",
        "empty-roster",
        "empty-days",
        "blank-source",
        "blank-method",
        "wrong-units",
        "blank-name",
        "blank-id",
        "negative-mean",
        "nan-mean",
        "infinite-mean",
        "missing-model",
        "naive-time",
        "partial-observed-day",
        "extra-index",
        "unknown-quality",
        "coerced-forecast",
    ],
)
def test_invalid_coverage_provenance_and_values_rejected_at_ingestion(case) -> None:
    raw = document()
    day, item = raw["days"][0], raw["days"][0]["items"][0]
    if case == "missing-hour":
        item["hours_covered"].pop()
    elif case == "duplicate-hour":
        item["hours_covered"] = [0] * 24
    elif case == "outside-hour":
        item["hours_covered"] = [*range(23), 24]
    elif case == "boolean-hour":
        item["hours_covered"] = [False, *range(1, 24)]
    elif case == "missing-region":
        day["items"].pop()
    elif case == "unknown-region":
        item["kelurahan_id"] = "not-in-boundary-roster"
    elif case == "duplicate-region":
        day["items"].append(deepcopy(item))
    elif case == "duplicate-roster":
        raw["regions"].append(deepcopy(raw["regions"][0]))
    elif case == "duplicate-date":
        raw["days"].append(deepcopy(day))
    elif case == "wrong-boundaries":
        day["boundaries_version"] = "different-boundaries"
    elif case == "empty-roster":
        raw["regions"] = []
    elif case == "empty-days":
        raw["days"] = []
    elif case == "blank-source":
        raw["source"] = "  "
    elif case == "blank-method":
        raw["aggregation_method"] = "\n "
    elif case == "wrong-units":
        raw["units"] = "mg/m3"
    elif case == "blank-name":
        raw["regions"][0]["name"] = " "
    elif case == "blank-id":
        raw["regions"][0]["kelurahan_id"] = " "
    elif case in ("negative-mean", "nan-mean", "infinite-mean"):
        item["mean_pm25"] = {"negative-mean": -1, "nan-mean": math.nan, "infinite-mean": math.inf}[
            case
        ]
    elif case == "missing-model":
        day["model_version"] = None
    elif case == "naive-time":
        day["generated_at"] = "2026-10-13T00:15:00"
    elif case == "partial-observed-day":
        day["generated_at"] = "2026-10-12T23:59:00+07:00"
    elif case == "extra-index":
        item["inequality_index"] = 0.5
    elif case == "unknown-quality":
        day["data_quality"] = "dummy"
    else:
        day["contains_forecast"] = "false"
    with pytest.raises(ValidationError):
        KelurahanArtifact.model_validate(raw)


@pytest.mark.parametrize(
    ("start", "end"),
    [(FROM - timedelta(days=1), TO), (FROM, TO + timedelta(days=1)), (date.min, date.max)],
)
def test_uncovered_or_extreme_date_range_returns_no_partial_result(
    tmp_path: Path, start, end
) -> None:
    with pytest.raises(AQUnavailableError, match="complete"):
        loaded(tmp_path).summarize(start, end)


def test_gap_in_middle_is_not_filled_or_skipped(tmp_path: Path) -> None:
    raw = document()
    raw["days"][1]["date"] = "2026-10-14"
    raw["days"][1]["contains_forecast"] = True
    service = loaded(tmp_path, raw)
    with pytest.raises(AQUnavailableError, match="complete"):
        service.summarize(FROM, date(2026, 10, 14))


def test_unpublished_aggregate_is_rejected_and_previous_snapshot_retained(tmp_path: Path) -> None:
    service = loaded(tmp_path)
    raw = document()
    raw["days"][1]["generated_at"] = (NOW + timedelta(minutes=1)).isoformat()
    service.path.write_text(json.dumps(raw))
    with pytest.raises(AQUnavailableError, match="future"):
        service.reload()
    assert service.summarize(FROM, TO).items[0].mean_pm25 == 20
    service.now = lambda: NOW - timedelta(days=1)
    with pytest.raises(AQUnavailableError, match="published"):
        service.summarize(FROM, TO)


def test_current_and_future_daily_forecast_never_claim_real() -> None:
    raw = document()
    raw["days"] = [raw["days"][0]]
    raw["days"][0].update(
        date="2026-10-15", generated_at=NOW.isoformat(), contains_forecast=True, data_quality="real"
    )
    artifact = KelurahanArtifact.model_validate(raw)
    result = aggregate_kelurahan(artifact, date(2026, 10, 15), date(2026, 10, 15), NOW)
    assert result.data_quality == "approximated"
    raw["days"][0]["contains_forecast"] = False
    with pytest.raises(ValidationError, match="incomplete"):
        KelurahanArtifact.model_validate(raw)


def test_production_refuses_any_synthetic_publication(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.json"
    path.write_text(json.dumps(document()))
    service = KelurahanService(path, now=lambda: NOW)
    with pytest.raises(AQUnavailableError, match="Synthetic"):
        service.reload()
    with pytest.raises(AQUnavailableError, match="complete"):
        service.summarize(FROM, TO)
    with pytest.raises(AQUnavailableError, match="Synthetic"):
        aggregate_kelurahan(KelurahanArtifact.model_validate(document()), FROM, TO, NOW)


def test_missing_service_and_reversed_domain_range() -> None:
    service = KelurahanService()
    with pytest.raises(AQUnavailableError):
        service.reload()
    with pytest.raises(AQUnavailableError):
        service.summarize(FROM, TO)
    with pytest.raises(ValueError, match="ordered"):
        service.summarize(TO, FROM)


def test_service_reuses_snapshot_without_reading_file_per_request(
    tmp_path: Path, monkeypatch
) -> None:
    service = loaded(tmp_path)

    def unexpected_read(*args, **kwargs):
        pytest.fail("File was read during request aggregation")

    monkeypatch.setattr(Path, "read_text", unexpected_read)
    assert service.summarize(FROM, TO).items[0].mean_pm25 == 20


async def test_concurrent_reload_keeps_one_immutable_request_snapshot(
    tmp_path: Path, monkeypatch
) -> None:
    service = loaded(tmp_path)
    entered, release = threading.Event(), threading.Event()
    original = aggregate_kelurahan

    def paused(artifact, *args, **kwargs):
        entered.set()
        if not release.wait(5):
            raise RuntimeError("Snapshot test timed out")
        return original(artifact, *args, **kwargs)

    monkeypatch.setattr(kelurahan_module, "aggregate_kelurahan", paused)
    pending = asyncio.create_task(asyncio.to_thread(service.summarize, FROM, TO))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        raw = document()
        for day in raw["days"]:
            for item in day["items"]:
                item["mean_pm25"] += 100
        service.path.write_text(json.dumps(raw))
        await asyncio.to_thread(service.reload)
    finally:
        release.set()
    old = await pending
    assert old.items[0].mean_pm25 == 20
    assert service.summarize(FROM, TO).items[0].mean_pm25 == 120


@pytest.mark.parametrize("values", [[], [-1], [math.nan], [math.inf]])
def test_pure_mean_rejects_invalid_values(values) -> None:
    with pytest.raises(AQUnavailableError):
        mean_daily_values(values)


def test_pure_mean_zero_fractional_and_numeric_overflow() -> None:
    assert mean_daily_values([0, 0]) == 0
    assert mean_daily_values([10, 20, 60]) == 30
    assert mean_daily_values([1, 2]) == 1.5
    assert mean_daily_values([1e308, 1e308]) == 1e308
    with pytest.raises(AQUnavailableError, match="precision"):
        mean_daily_values([sys.float_info.max] * 24)


async def test_http_contract_full_period_null_indices_and_errors(tmp_path: Path) -> None:
    configured = Runtime(AQService(FlatAQ(), BOUNDS), kelurahan=loaded(tmp_path))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app(configured)), base_url="http://test"
    ) as client:
        query = {"from": FROM.isoformat(), "to": TO.isoformat()}
        reply = await client.get("/v1/insights/kelurahan", params=query)
        assert reply.status_code == 200
        body = KelurahanInsightsResponse.model_validate(reply.json())
        assert body.from_ == FROM
        assert body.to == TO
        assert body.data_quality == "synthetic"
        assert [item.mean_pm25 for item in body.items] == [20, 50]
        assert all(
            item.inequality_index is None and item.priority_rank is None for item in body.items
        )
        assert "from" in reply.json()
        assert "from_" not in reply.json()
        for invalid in (
            {"from": TO.isoformat(), "to": FROM.isoformat()},
            {"from": "not-a-date", "to": TO.isoformat()},
            {"from": FROM.isoformat()},
        ):
            error = await client.get("/v1/insights/kelurahan", params=invalid)
            assert error.status_code == 400
            assert error.json()["type"] == "validation_error"
            assert error.headers["content-type"] == "application/problem+json"
        missing = await client.get("/v1/insights/kelurahan", params={**query, "to": "2026-10-15"})
        assert missing.status_code == 503
        assert missing.json()["type"] == "data_unavailable"
        configured.kelurahan.allow_synthetic = False
        denied = await client.get("/v1/insights/kelurahan", params=query)
        assert denied.status_code == 503
        configured.kelurahan = None
        absent = await client.get("/v1/insights/kelurahan", params=query)
        assert absent.status_code == 503
        reversed_missing = await client.get(
            "/v1/insights/kelurahan", params={"from": TO.isoformat(), "to": FROM.isoformat()}
        )
        assert reversed_missing.status_code == 400


def test_refresh_valid_update_and_invalid_input_retains_snapshot(tmp_path: Path, caplog) -> None:
    service = loaded(tmp_path)
    configured = Runtime(AQService(FlatAQ(), BOUNDS), kelurahan=service)
    raw = document()
    for day in raw["days"]:
        for item in day["items"]:
            item["mean_pm25"] += 5
    service.path.write_text(json.dumps(raw))
    refresh(configured, NOW, (), None, None)
    assert service.summarize(FROM, TO).items[0].mean_pm25 == 25
    service.path.write_text("{}")
    refresh(configured, NOW, (), None, None)
    assert service.summarize(FROM, TO).items[0].mean_pm25 == 25
    assert "retaining prior valid input" in caplog.text


def test_region_refresh_still_runs_when_other_aq_input_fails(tmp_path: Path) -> None:
    service = loaded(tmp_path)
    configured = Runtime(AQService(FlatAQ(), BOUNDS), kelurahan=service)
    raw = document()
    raw["days"][0]["items"][0]["mean_pm25"] = 90
    service.path.write_text(json.dumps(raw))
    invalid = tmp_path / "bad-aq.json"
    invalid.write_text("{}")
    with pytest.raises(KeyError):
        refresh(configured, NOW, (), invalid, None)
    assert service.summarize(FROM, TO).items[0].mean_pm25 == 60


async def test_hourly_worker_watches_late_regional_publication(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "late.json"
    service = KelurahanService(path, allow_synthetic=True, now=lambda: NOW)
    configured = Runtime(AQService(FlatAQ(), BOUNDS), kelurahan=service)
    calls = 0

    async def tick(delay):
        nonlocal calls
        calls += 1
        if calls == 1:
            await asyncio.to_thread(path.write_text, json.dumps(document()))
        else:
            raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "sleep", tick)
    with pytest.raises(asyncio.CancelledError):
        await hourly(configured, (), None, None)
    assert service.summarize(FROM, TO).items[0].mean_pm25 == 20


async def test_startup_configures_test_adapter_and_production_rejects_synthetic(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "kelurahan.json"
    path.write_text(json.dumps(document()))
    async with httpx.AsyncClient() as client:
        with pytest.warns(UnverifiedParamsWarning):
            production = Runtime.from_env(
                client, {"HIRUP_DATA_DIR": str(tmp_path), "HIRUP_KELURAHAN_SUMMARIES": str(path)}
            )
        assert production.planner is not None
        assert production.kelurahan.path == path
        with pytest.raises(AQUnavailableError):
            production.kelurahan.summarize(FROM, TO)

        def test_service(input_path=None):
            return KelurahanService(input_path, allow_synthetic=True, now=lambda: NOW)

        monkeypatch.setattr(runtime_module, "KelurahanService", test_service)
        with pytest.warns(UnverifiedParamsWarning):
            fixture = Runtime.from_env(
                client, {"HIRUP_DATA_DIR": str(tmp_path), "HIRUP_KELURAHAN_SUMMARIES": str(path)}
            )
        assert fixture.kelurahan.summarize(FROM, TO).data_quality == "synthetic"


@pytest.mark.parametrize("input_kind", ["absent", "missing-file", "malformed", "demo"])
async def test_startup_inputs_never_manufacture_insights(tmp_path: Path, input_kind) -> None:
    env = {"HIRUP_DATA_DIR": str(tmp_path)}
    if input_kind != "absent":
        path = tmp_path / "input.json"
        env["HIRUP_KELURAHAN_SUMMARIES"] = str(path)
        if input_kind == "malformed":
            path.write_text("not-json")
        elif input_kind == "demo":
            path.write_text(json.dumps(document()))
            env.update(
                HIRUP_DEMO="true",
                HIRUP_DEMO_MIN_PM25="10",
                HIRUP_DEMO_MAX_PM25="80",
                HIRUP_DEMO_REFERENCE_PM25="40",
            )
    async with httpx.AsyncClient() as client:
        with pytest.warns(UnverifiedParamsWarning):
            configured = Runtime.from_env(client, env)
        assert configured.kelurahan is not None
        with pytest.raises(AQUnavailableError):
            configured.kelurahan.summarize(FROM, TO)


def test_observed_date_completion_uses_wib_not_utc(tmp_path: Path) -> None:
    raw = document()
    # 17:15 UTC on the 12th is after the complete WIB day, even with the earlier UTC date.
    raw["days"][0]["generated_at"] = "2026-10-12T17:15:00+00:00"
    assert loaded(tmp_path, raw).summarize(FROM, FROM).items[0].mean_pm25 == 10
    raw["days"][0]["generated_at"] = "2026-10-12T16:59:00+00:00"
    with pytest.raises(ValidationError, match="incomplete"):
        KelurahanArtifact.model_validate(raw)


def test_clock_can_be_utc_without_changing_wib_date_selection(tmp_path: Path) -> None:
    service = loaded(tmp_path)
    service.now = lambda: NOW.astimezone(UTC)
    assert service.summarize(FROM, TO).items[0].mean_pm25 == 20


@pytest.mark.parametrize("value", [True, "20"])
def test_concentration_requires_a_number_without_boolean_or_string_coercion(value) -> None:
    raw = document()
    raw["days"][0]["items"][0]["mean_pm25"] = value
    with pytest.raises(ValidationError):
        KelurahanArtifact.model_validate(raw)
