"""Opt-in test that extracts and routes a tiny road graph in the pinned OSRM."""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
IMAGE = "ghcr.io/project-osrm/osrm-backend:v5.27.1"
pytestmark = pytest.mark.skipif(
    os.environ.get("HIRUP_TEST_OSRM") != "1",
    reason="Set HIRUP_TEST_OSRM=1 to run the Docker OSRM profile regression",
)


def docker(*args: str) -> str:
    return subprocess.check_output(
        ["docker", *args],
        text=True,
        stderr=subprocess.STDOUT,
        timeout=120,
    ).strip()


def fixture_osm() -> str:
    nodes = [
        '<node id="1" lat="-6.2000" lon="106.7900"/>',
        '<node id="2" lat="-6.2000" lon="106.7920"/>',
        '<node id="3" lat="-6.1980" lon="106.7910"/>',
    ]
    ways = [
        '<way id="1"><nd ref="1"/><nd ref="3"/><nd ref="2"/>'
        '<tag k="highway" v="primary"/><tag k="maxspeed" v="90"/></way>',
    ]
    forbidden = [
        '<tag k="toll" v="yes"/>',
        '<tag k="highway" v="motorway"/>',
        '<tag k="highway" v="motorway_link"/>',
        '<tag k="toll:motorcycle" v="yes"/>',
        '<tag k="toll:forward" v="yes"/>',
        '<tag k="toll:backward" v="yes"/>',
        '<tag k="motorcycle" v="no"/>',
        '<tag k="toll" v="true"/>',
    ]
    for number, tags in enumerate(forbidden, start=4):
        lat = -6.2 - (number - 4) * 0.00001
        nodes.append(f'<node id="{number}" lat="{lat}" lon="106.7910"/>')
        highway = "" if 'k="highway"' in tags else '<tag k="highway" v="primary"/>'
        ways.append(
            f'<way id="{number}"><nd ref="1"/><nd ref="{number}"/><nd ref="2"/>'
            f'{highway}<tag k="maxspeed" v="90"/>{tags}</way>'
        )
    nodes.append(
        '<node id="12" lat="-6.20009" lon="106.7910">'
        '<tag k="barrier" v="toll_booth"/></node>'
    )
    ways.append(
        '<way id="12"><nd ref="1"/><nd ref="12"/><nd ref="2"/>'
        '<tag k="highway" v="primary"/></way>'
    )
    return '<?xml version="1.0"?><osm version="0.6">' + "".join(nodes + ways) + "</osm>"


@pytest.fixture(scope="module")
def engines(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, str]]:
    running: list[str] = []
    urls: dict[str, str] = {}
    try:
        for profile in ("car", "motorcycle"):
            target = tmp_path_factory.mktemp(profile)
            (target / "tiny.osm").write_text(fixture_osm())
            mounts = (
                "--mount",
                f"type=bind,source={target},target=/data",
                "--mount",
                f"type=bind,source={ROOT / 'infra/osrm'},target=/profiles,readonly",
            )
            for command in (
                ("osrm-extract", "-p", f"/profiles/{profile}.lua", "/data/tiny.osm"),
                ("osrm-partition", "/data/tiny.osrm"),
                ("osrm-customize", "/data/tiny.osrm"),
            ):
                docker("run", "--rm", *mounts, IMAGE, *command)
            container = docker(
                "run",
                "--rm",
                "-d",
                "-p",
                "127.0.0.1::5000",
                *mounts,
                IMAGE,
                "osrm-routed",
                "--algorithm",
                "MLD",
                "/data/tiny.osrm",
            )
            running.append(container)
            bindings = json.loads(docker("inspect", container))[0]["NetworkSettings"][
                "Ports"
            ]
            port = bindings["5000/tcp"][0]["HostPort"]
            urls[profile] = f"http://127.0.0.1:{port}"
            for attempt in range(30):
                try:
                    with urllib.request.urlopen(
                        urls[profile] + "/nearest/v1/driving/106.790,-6.200",
                        timeout=2,
                    ):
                        break
                except OSError:
                    if attempt == 29:
                        raise
                    time.sleep(0.2)
        yield urls
    finally:
        for container in running:
            docker("stop", container)


def route(base: str, coordinates: str) -> dict[str, Any]:
    url = (
        base
        + "/route/v1/driving/"
        + coordinates
        + "?geometries=geojson&annotations=true"
    )
    with urllib.request.urlopen(url, timeout=5) as response:
        result: dict[str, Any] = json.load(response)
    assert result["code"] == "Ok"
    return result["routes"][0]  # type: ignore[no-any-return]


def test_motorcycle_rejects_shortcuts_and_obeys_oneway_independent_toll_tags(
    engines: dict[str, str],
) -> None:
    coordinates = "106.7900,-6.2000;106.7920,-6.2000"
    car = route(engines["car"], coordinates)
    motorcycle = route(engines["motorcycle"], coordinates)
    assert car["distance"] < 300
    assert motorcycle["distance"] > 450
    assert [106.791, -6.198] in motorcycle["geometry"]["coordinates"]
    reverse = route(engines["motorcycle"], ";".join(reversed(coordinates.split(";"))))
    assert reverse["distance"] > 450


def test_motorcycle_caps_explicit_high_maxspeed_using_upstream_urban_default(
    engines: dict[str, str],
) -> None:
    coordinates = "106.7910,-6.1980;106.7920,-6.2000"
    car = route(engines["car"], coordinates)
    motorcycle = route(engines["motorcycle"], coordinates)
    assert motorcycle["duration"] > car["duration"]
    assert all(
        speed <= 50 / 3.6 + 0.1
        for speed in motorcycle["legs"][0]["annotation"]["speed"]
    )
