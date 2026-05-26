#!/usr/bin/env python3
"""Importiert Wehre aus OpenStreetMap (Overpass) und merged sie in pois.geojson."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from shapely.geometry import LineString, Point, Polygon

ROOT = Path(__file__).resolve().parent.parent
POIS_PATH = ROOT / "pois.geojson"
MANIFEST_PATH = ROOT / "manifest.json"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "FlowTrail-POI-Import/1.0 (github.com/3ddruck12/flowtrail-pois)"

# ISO3166-2 Codes — einzeln abfragen, um Overpass-Timeouts zu vermeiden
BUNDESLAENDER: dict[str, str] = {
    "sh": 'area["ISO3166-2"="DE-SH"][admin_level=4]',
    "hh": 'area["ISO3166-2"="DE-HH"][admin_level=4]',
    "ni": 'area["ISO3166-2"="DE-NI"][admin_level=4]',
    "hb": 'area["ISO3166-2"="DE-HB"][admin_level=4]',
    "nw": 'area["ISO3166-2"="DE-NW"][admin_level=4]',
    "he": 'area["ISO3166-2"="DE-HE"][admin_level=4]',
    "rp": 'area["ISO3166-2"="DE-RP"][admin_level=4]',
    "bw": 'area["ISO3166-2"="DE-BW"][admin_level=4]',
    "by": 'area["ISO3166-2"="DE-BY"][admin_level=4]',
    "sl": 'area["ISO3166-2"="DE-SL"][admin_level=4]',
    "be": 'area["ISO3166-2"="DE-BE"][admin_level=4]',
    "bb": 'area["ISO3166-2"="DE-BB"][admin_level=4]',
    "mv": 'area["ISO3166-2"="DE-MV"][admin_level=4]',
    "sn": 'area["ISO3166-2"="DE-SN"][admin_level=4]',
    "st": 'area["ISO3166-2"="DE-ST"][admin_level=4]',
    "th": 'area["ISO3166-2"="DE-TH"][admin_level=4]',
}

OVERPASS_QUERY = """\
[out:json][timeout:180];
{area_selector}->.searchArea;
(
  node["waterway"="weir"](area.searchArea);
  way["waterway"="weir"](area.searchArea);
  relation["waterway"="weir"](area.searchArea);
  node["barrier"="weir"](area.searchArea);
  way["barrier"="weir"](area.searchArea);
);
out body geom qt;
"""


def build_query(area_selector: str) -> str:
    return OVERPASS_QUERY.format(area_selector=area_selector)


def fetch_overpass(area_selector: str, retries: int = 3) -> list[dict[str, Any]]:
    query = build_query(area_selector)
    headers = {"User-Agent": USER_AGENT}
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(
                OVERPASS_URL,
                data={"data": query},
                headers=headers,
                timeout=200,
            )
            response.raise_for_status()
            payload = response.json()
            return payload.get("elements", [])
        except (requests.RequestException, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < retries:
                wait = 15 * attempt
                print(f"  Overpass-Fehler ({exc}), Retry in {wait}s …", file=sys.stderr)
                time.sleep(wait)

    raise RuntimeError(f"Overpass-Abfrage fehlgeschlagen: {last_error}") from last_error


def geometry_to_point(element: dict[str, Any]) -> tuple[float, float] | None:
    elem_type = element.get("type")

    if elem_type == "node":
        if "lon" in element and "lat" in element:
            return float(element["lon"]), float(element["lat"])
        return None

    geometry = element.get("geometry")
    if not geometry:
        return None

    coords = [(float(node["lon"]), float(node["lat"])) for node in geometry]
    if not coords:
        return None
    if len(coords) == 1:
        return coords[0]

    if len(coords) >= 4 and coords[0] == coords[-1]:
        shape = Polygon(coords)
    else:
        shape = LineString(coords)

    if shape.is_empty:
        return None

    centroid = shape.centroid
    return centroid.x, centroid.y


def river_from_tags(tags: dict[str, str]) -> str:
    for key in ("river", "waterway:name", "destination", "waterway"):
        value = tags.get(key, "").strip()
        if value and value not in ("weir", "yes"):
            return value
    return ""


def name_from_tags(tags: dict[str, str], osm_id: str) -> str:
    for key in ("name", "ref", "operator"):
        value = tags.get(key, "").strip()
        if value:
            return value
    river = river_from_tags(tags)
    if river:
        return f"Wehr ({river})"
    return f"Wehr (OSM {osm_id})"


def description_from_tags(tags: dict[str, str]) -> str:
    for key in ("description", "note", "fixme"):
        value = tags.get(key, "").strip()
        if value:
            return value
    return "Automatisch aus OpenStreetMap importiert. Vor Ort prüfen."


def element_to_feature(element: dict[str, Any]) -> dict[str, Any] | None:
    coords = geometry_to_point(element)
    if coords is None:
        return None

    lng, lat = coords
    tags = element.get("tags") or {}
    osm_id = f"{element['type']}/{element['id']}"

    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
        "properties": {
            "name": name_from_tags(tags, osm_id),
            "description": description_from_tags(tags),
            "type": "Wehr",
            "river": river_from_tags(tags),
            "source": "osm",
            "osm_id": osm_id,
        },
    }


def load_community_features(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    features = data.get("features", [])
    community = [
        feature
        for feature in features
        if feature.get("properties", {}).get("source") != "osm"
    ]
    return data, community


def fetch_weirs_for_regions(region_codes: list[str]) -> list[dict[str, Any]]:
    by_osm_id: dict[str, dict[str, Any]] = {}

    for code in region_codes:
        selector = BUNDESLAENDER[code]
        print(f"Abfrage Bundesland {code.upper()} …")
        elements = fetch_overpass(selector)
        converted = 0
        skipped = 0

        for element in elements:
            if element.get("type") not in ("node", "way", "relation"):
                continue
            feature = element_to_feature(element)
            if feature is None:
                skipped += 1
                continue
            osm_id = feature["properties"]["osm_id"]
            by_osm_id[osm_id] = feature
            converted += 1

        print(f"  {len(elements)} Elemente, {converted} Wehre, {skipped} ohne Geometrie")

    return list(by_osm_id.values())


def resolve_regions(region: str) -> list[str]:
    region = region.lower()
    if region == "de":
        return list(BUNDESLAENDER.keys())
    if region not in BUNDESLAENDER:
        known = ", ".join(["de", *sorted(BUNDESLAENDER)])
        raise ValueError(f"Unbekannte Region '{region}'. Erlaubt: {known}")
    return [region]


def write_outputs(
    community: list[dict[str, Any]],
    osm_features: list[dict[str, Any]],
    version: str,
) -> None:
    now = datetime.now(timezone.utc)
    osm_features.sort(key=lambda f: (f["properties"].get("river", ""), f["properties"]["name"]))

    pois = {
        "type": "FeatureCollection",
        "metadata": {
            "name": "FlowTrail Community POIs",
            "description": (
                "Community-POIs und OSM-Wehre für Kanufahrer in Deutschland. "
                "Wehre: © OpenStreetMap contributors (ODbL)."
            ),
            "version": version,
        },
        "features": community + osm_features,
    }

    manifest = {
        "version": version,
        "updatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "label": f"FlowTrail POIs ({len(community)} Community + {len(osm_features)} OSM-Wehre)",
        "dataUrl": "https://raw.githubusercontent.com/3ddruck12/flowtrail-pois/main/pois.geojson",
    }

    POIS_PATH.write_text(json.dumps(pois, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"Geschrieben: {len(community)} Community-POIs + {len(osm_features)} OSM-Wehre "
        f"= {len(pois['features'])} gesamt (Version {version})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="OSM-Wehre in pois.geojson importieren")
    parser.add_argument(
        "--region",
        default="de",
        help="Region: de (alle Bundesländer) oder ISO-Code wie nw, by, bw …",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur abfragen und zählen, Dateien nicht schreiben",
    )
    args = parser.parse_args()

    region_codes = resolve_regions(args.region)
    _, community = load_community_features(POIS_PATH)
    osm_features = fetch_weirs_for_regions(region_codes)

    print(f"Gesamt: {len(osm_features)} eindeutige OSM-Wehre")

    if args.dry_run:
        print("Dry-run — keine Dateien geschrieben.")
        return

    version = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M")
    write_outputs(community, osm_features, version)


if __name__ == "__main__":
    main()
