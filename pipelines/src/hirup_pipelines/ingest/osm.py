"""OpenStreetMap layers: roads, junctions, buildings and kelurahan boundaries.

Roads and buildings come from a local index built once from the Geofabrik Java extract
(`data/osm/java-latest.osm.pbf`, the same file `infra/scripts/fetch_osm.sh` downloads).
Overpass is the fallback for areas the index does not cover and the source of the admin
boundaries; its raw responses are cached under `data/raw/osm/`.
Data (c) OpenStreetMap contributors, ODbL.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import numpy.typing as npt
import shapely
from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import polygonize, unary_union

from hirup_pipelines import store
from hirup_pipelines.grid import CRS
from hirup_pipelines.http import Client, HttpError
from hirup_pipelines.ingest.rasters import download
from hirup_pipelines.settings import BBox, data_dir, load_config, map_bbox, pilot_bbox

log = logging.getLogger(__name__)
Coords = list[tuple[float, float]]


@dataclass
class OsmLayers:
    roads: gpd.GeoDataFrame  # LineString in EPSG:32748, column `road_class`
    junctions: npt.NDArray[np.float64]  # (n, 2) UTM coordinates
    buildings: gpd.GeoDataFrame  # Polygon in EPSG:32748


def road_class_of() -> dict[str, str]:
    classes = load_config()["osm"]["road_classes"]
    return {tag: name for name, tags in classes.items() for tag in tags}


def junctions_of(ways: list[Coords]) -> Coords:
    """Vertices where at least three road segments meet."""
    degree: dict[tuple[float, float], int] = defaultdict(int)
    for coords in ways:
        for index, point in enumerate(coords):
            degree[point] += 1 if index in (0, len(coords) - 1) else 2
    return [point for point, count in degree.items() if count >= 3]


def _layers(
    road_rows: list[dict[str, Any]], road_coords: list[Coords], building_coords: list[Coords]
) -> OsmLayers:
    """Assemble layers from WGS84 coordinate lists."""
    roads = gpd.GeoDataFrame(
        road_rows, geometry=[LineString(c) for c in road_coords], crs="EPSG:4326"
    )
    buildings = gpd.GeoDataFrame(
        geometry=[shapely.make_valid(Polygon(c)) for c in building_coords], crs="EPSG:4326"
    )
    points = np.array(junctions_of(road_coords), dtype=float).reshape(-1, 2)
    junctions = gpd.GeoSeries(gpd.points_from_xy(points[:, 0], points[:, 1]), crs="EPSG:4326")
    return OsmLayers(
        roads=roads.to_crs(CRS),
        junctions=shapely.get_coordinates(junctions.to_crs(CRS).values).reshape(-1, 2),
        buildings=buildings.to_crs(CRS),
    )


# --- local index from a .osm.pbf extract ------------------------------------------------------


def index_dir() -> Path:
    return data_dir() / "raw" / "osm" / "index"


def index_area() -> BBox:
    """Everything a feature build can ask for: the station search area and the map, plus a
    margin. Changing it means rebuilding the index (`hirup-pipelines osm-index`)."""
    cfg = load_config()
    stations = pilot_bbox().expand_km(float(cfg["stations"]["buffer_km"]))
    return stations.union(map_bbox()).expand_km(2.0)


def pbf_path() -> Path:
    url = load_config()["osm"]["pbf_url"]
    return download(url, data_dir() / "osm" / url.rsplit("/", 1)[-1])


def read_pbf(path: Path, area: BBox) -> tuple[list[dict[str, Any]], list[Coords], list[Coords]]:
    """Road and building ways whose first node lies within `area` (+5 km for long ways)."""
    import osmium

    class_of = road_class_of()
    reach = area.expand_km(5.0)
    road_rows: list[dict[str, Any]] = []
    road_coords: list[Coords] = []
    building_coords: list[Coords] = []
    processor = (
        osmium.FileProcessor(str(path))
        .with_locations()
        .with_filter(osmium.filter.KeyFilter("highway", "building"))
    )
    entity: Any
    for entity in processor:
        if not entity.is_way():
            continue
        first = entity.nodes[0].location
        if not first.valid() or not reach.contains(first.lat, first.lon):
            continue
        highway = entity.tags.get("highway")
        is_building = "building" in entity.tags
        if highway not in class_of and not is_building:
            continue
        coords = [(n.lon, n.lat) for n in entity.nodes if n.location.valid()]
        if highway in class_of and len(coords) >= 2:
            road_rows.append({"osm_id": entity.id, "road_class": class_of[highway]})
            road_coords.append(coords)
        elif is_building and len(coords) >= 4 and coords[0] == coords[-1]:
            building_coords.append(coords)
    return road_rows, road_coords, building_coords


def build_index(path: Path | None = None) -> dict[str, Any]:
    """Parse the extract once into two GeoParquet layers covering `index_area()`."""
    source = path or pbf_path()
    area = index_area()
    layers = _layers(*read_pbf(source, area))
    target = index_dir()
    target.mkdir(parents=True, exist_ok=True)
    layers.roads.to_parquet(target / "roads.parquet", index=False)
    layers.buildings.to_parquet(target / "buildings.parquet", index=False)
    meta = {
        "source": source.name,
        "source_bytes": source.stat().st_size,
        "bbox": {
            "min_lat": area.min_lat,
            "max_lat": area.max_lat,
            "min_lon": area.min_lon,
            "max_lon": area.max_lon,
        },
        "roads": len(layers.roads),
        "buildings": len(layers.buildings),
    }
    store.write_json(meta, target / "meta.json")
    _load_index.cache_clear()
    log.info("OSM index: %d roads, %d buildings", meta["roads"], meta["buildings"])
    return meta


@lru_cache(maxsize=1)
def _load_index(folder: Path) -> tuple[BBox, gpd.GeoDataFrame, gpd.GeoDataFrame] | None:
    meta = store.read_json(folder / "meta.json")
    if meta is None:
        return None
    return (
        BBox(**meta["bbox"]),
        gpd.read_parquet(folder / "roads.parquet"),
        gpd.read_parquet(folder / "buildings.parquet"),
    )


def from_index(bbox: BBox) -> OsmLayers | None:
    """Layers clipped from the local index, or None when it is missing or too small."""
    loaded = _load_index(index_dir())
    if loaded is None:
        return None
    area, roads, buildings = loaded
    if not (
        area.contains(bbox.min_lat, bbox.min_lon) and area.contains(bbox.max_lat, bbox.max_lon)
    ):
        return None
    corners = gpd.GeoSeries(
        [shapely.box(bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat)], crs="EPSG:4326"
    ).to_crs(CRS)
    window = shapely.box(*corners.total_bounds)
    near_roads = roads.iloc[roads.sindex.query(window, predicate="intersects")]
    near_buildings = buildings.iloc[buildings.sindex.query(window, predicate="intersects")]
    coords = [list(map(tuple, shapely.get_coordinates(g))) for g in near_roads.geometry.values]
    junctions = np.array(junctions_of(coords), dtype=float).reshape(-1, 2)
    return OsmLayers(
        near_roads.reset_index(drop=True), junctions, near_buildings.reset_index(drop=True)
    )


# --- Overpass ---------------------------------------------------------------------------------


def overpass(query: str, http: Client | None = None, *, use_cache: bool = True) -> dict[str, Any]:
    cache = data_dir() / "raw" / "osm" / f"{hashlib.sha1(query.encode()).hexdigest()}.json.gz"
    if use_cache and cache.is_file():
        with gzip.open(cache, "rt", encoding="utf-8") as stream:
            return dict(json.load(stream))
    own = http is None
    http = http or Client(min_interval_s=2.0, retries=1, timeout_s=240.0)
    error: Exception | None = None
    try:
        # Public Overpass instances are often busy; rotate through them twice.
        for endpoint in list(load_config()["osm"]["endpoints"]) * 2:
            try:
                body = http.request("POST", endpoint, data={"data": query}).json()
            except (HttpError, ValueError) as exc:
                error = exc
                continue
            if "elements" not in body or body.get("remark", "").startswith("runtime error"):
                error = RuntimeError(f"Overpass error: {body.get('remark', 'no elements')}"[:200])
                continue
            if use_cache:
                cache.parent.mkdir(parents=True, exist_ok=True)
                with gzip.open(cache, "wt", encoding="utf-8") as stream:
                    json.dump(body, stream)
            return dict(body)
    finally:
        if own:
            http.close()
    raise RuntimeError("All Overpass endpoints failed; they are often busy, try again") from error


def _box(bbox: BBox) -> str:
    return f"({bbox.min_lat:.6f},{bbox.min_lon:.6f},{bbox.max_lat:.6f},{bbox.max_lon:.6f})"


def tiles(bbox: BBox, step: float) -> list[BBox]:
    lats = np.arange(bbox.min_lat, bbox.max_lat, step)
    lons = np.arange(bbox.min_lon, bbox.max_lon, step)
    return [
        BBox(
            float(a),
            float(min(a + step, bbox.max_lat)),
            float(o),
            float(min(o + step, bbox.max_lon)),
        )
        for a in lats
        for o in lons
    ]


def _line(geometry: list[dict[str, float]] | None) -> Coords:
    return [(p["lon"], p["lat"]) for p in geometry or [] if p is not None]


def from_overpass(bbox: BBox, http: Client | None = None) -> OsmLayers:
    """Roads and buildings queried in small tiles and de-duplicated."""
    cfg = load_config()["osm"]
    class_of = road_class_of()
    highway = "|".join(class_of)
    seen: set[tuple[str, int]] = set()
    road_rows: list[dict[str, Any]] = []
    road_coords: list[Coords] = []
    building_coords: list[Coords] = []
    for tile in tiles(bbox, float(cfg["tile_deg"])):
        box = _box(tile)
        query = (
            f'[out:json][timeout:120];(way["highway"~"^({highway})$"]{box};'
            f'way["building"]{box};);out geom;'
        )
        for element in overpass(query, http)["elements"]:
            key = (element["type"], element["id"])
            if key in seen or element["type"] != "way":
                continue
            seen.add(key)
            tags = element.get("tags", {})
            coords = _line(element.get("geometry"))
            if tags.get("highway") in class_of and len(coords) >= 2:
                road_rows.append({"osm_id": element["id"], "road_class": class_of[tags["highway"]]})
                road_coords.append(coords)
            elif "building" in tags and len(coords) >= 4 and coords[0] == coords[-1]:
                building_coords.append(coords)
    return _layers(road_rows, road_coords, building_coords)


def fetch_layers(bbox: BBox, http: Client | None = None) -> OsmLayers:
    """Local index when it covers `bbox`, otherwise Overpass."""
    local = from_index(bbox)
    if local is not None:
        return local
    log.info("OSM index does not cover this area; using Overpass")
    return from_overpass(bbox, http)


def _relation_polygon(element: dict[str, Any]) -> BaseGeometry | None:
    """Assemble a multipolygon relation from its member ways."""
    rings: dict[str, list[LineString]] = defaultdict(list)
    for member in element.get("members", []):
        coords = _line(member.get("geometry"))
        if member.get("type") == "way" and len(coords) >= 2:
            rings["inner" if member.get("role") == "inner" else "outer"].append(LineString(coords))
    if not rings["outer"]:
        return None
    outer = unary_union(list(polygonize(unary_union(rings["outer"]))))
    if rings["inner"]:
        outer = outer.difference(unary_union(list(polygonize(unary_union(rings["inner"])))))
    return outer if not outer.is_empty else None


def _polygons(elements: list[dict[str, Any]]) -> list[tuple[dict[str, Any], BaseGeometry]]:
    found = []
    for element in elements:
        geometry: BaseGeometry | None = None
        if element["type"] == "way":
            coords = _line(element.get("geometry"))
            if len(coords) >= 4 and coords[0] == coords[-1]:
                geometry = Polygon(coords)
        elif element["type"] == "relation":
            geometry = _relation_polygon(element)
        if geometry is not None and not geometry.is_empty:
            found.append((element, shapely.make_valid(geometry)))
    return found


def fetch_admin(bbox: BBox, http: Client | None = None) -> gpd.GeoDataFrame:
    """Kelurahan (admin_level 7) polygons with their kecamatan (admin_level 6), in WGS84."""
    query = (
        f'[out:json][timeout:180];relation["boundary"="administrative"]'
        f'["admin_level"~"^(6|7)$"]{_box(bbox)};out geom;'
    )
    rows, geometries = [], []
    for element, geometry in _polygons(overpass(query, http)["elements"]):
        tags = element.get("tags", {})
        rows.append(
            {
                "osm_id": int(element["id"]),
                "admin_level": int(tags["admin_level"]),
                "name": tags.get("name"),
            }
        )
        geometries.append(geometry)
    admin = gpd.GeoDataFrame(rows, geometry=geometries, crs="EPSG:4326")
    kelurahan = admin[admin["admin_level"] == 7].copy()
    kecamatan = admin[admin["admin_level"] == 6][["name", "geometry"]].rename(
        columns={"name": "kecamatan"}
    )
    # A kelurahan belongs to the kecamatan that contains its interior point.
    points = kelurahan.copy()
    points["geometry"] = kelurahan.geometry.representative_point()
    joined = gpd.sjoin(points, kecamatan, how="left", predicate="within")
    kelurahan["kecamatan"] = joined.groupby(level=0)["kecamatan"].first()
    kelurahan["kelurahan_id"] = "osm_r" + kelurahan["osm_id"].astype(str)
    columns = ["kelurahan_id", "name", "kecamatan", "osm_id", "geometry"]
    return kelurahan[columns].sort_values("kelurahan_id").reset_index(drop=True)
