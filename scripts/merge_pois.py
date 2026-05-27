#!/usr/bin/env python3
"""Merged community-pois.geojson + osm-weirs.geojson → pois.geojson + manifest.json."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
COMMUNITY_PATH = ROOT / "community-pois.geojson"
OSM_PATH = ROOT / "osm-weirs.geojson"
POIS_PATH = ROOT / "pois.geojson"
MANIFEST_PATH = ROOT / "manifest.json"
LEGACY_POIS_PATH = POIS_PATH

SPATIAL_DEDUP_METERS = 50.0


def load_geojson(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"type": "FeatureCollection", "features": []}
    return json.loads(path.read_text(encoding="utf-8"))


def write_geojson(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def feature_point(feature: dict[str, Any]) -> tuple[float, float] | None:
    geometry = feature.get("geometry") or {}
    if geometry.get("type") != "Point":
        return None
    coords = geometry.get("coordinates") or []
    if len(coords) < 2:
        return None
    return float(coords[1]), float(coords[0])


def blocked_osm_ids(community: list[dict[str, Any]]) -> set[str]:
    blocked: set[str] = set()
    for feature in community:
        props = feature.get("properties") or {}
        replaces = props.get("replaces_osm_id", "").strip()
        if replaces:
            blocked.add(replaces)
    return blocked


def filter_osm_features(
    osm_features: list[dict[str, Any]],
    community: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    blocked = blocked_osm_ids(community)
    community_weirs = [
        feature_point(f)
        for f in community
        if (f.get("properties") or {}).get("type") == "Wehr" and feature_point(f)
    ]

    filtered: list[dict[str, Any]] = []
    for feature in osm_features:
        props = feature.get("properties") or {}
        osm_id = props.get("osm_id", "")
        if osm_id and osm_id in blocked:
            continue

        pt = feature_point(feature)
        if pt and community_weirs:
            lat, lon = pt
            too_close = any(
                haversine_meters(lat, lon, c_lat, c_lon) <= SPATIAL_DEDUP_METERS
                for c_lat, c_lon in community_weirs
            )
            if too_close:
                continue

        filtered.append(feature)

    filtered.sort(key=lambda f: (f["properties"].get("river", ""), f["properties"]["name"]))
    return filtered


def split_legacy_pois(legacy_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    data = load_geojson(legacy_path)
    features = data.get("features", [])
    community = [f for f in features if (f.get("properties") or {}).get("source") != "osm"]
    osm = [f for f in features if (f.get("properties") or {}).get("source") == "osm"]
    return community, osm


def write_community_file(community: list[dict[str, Any]], version: str) -> None:
    write_geojson(
        COMMUNITY_PATH,
        {
            "type": "FeatureCollection",
            "metadata": {
                "name": "FlowTrail Community POIs",
                "description": "Von Maintainers und Community gepflegte Kanu-POIs.",
                "version": version,
            },
            "features": community,
        },
    )


def write_osm_file(osm_features: list[dict[str, Any]], version: str) -> None:
    write_geojson(
        OSM_PATH,
        {
            "type": "FeatureCollection",
            "metadata": {
                "name": "FlowTrail OSM Weirs",
                "description": "Automatisch aus OpenStreetMap importierte Wehre (© OSM ODbL).",
                "version": version,
            },
            "features": osm_features,
        },
    )


def merge_and_write(version: str | None = None) -> dict[str, int]:
    community_data = load_geojson(COMMUNITY_PATH)
    osm_data = load_geojson(OSM_PATH)
    community = community_data.get("features", [])
    osm_raw = osm_data.get("features", [])
    osm_filtered = filter_osm_features(osm_raw, community)

    now = datetime.now(timezone.utc)
    if version is None:
        version = now.strftime("%Y-%m-%dT%H%M")

    merged = {
        "type": "FeatureCollection",
        "metadata": {
            "name": "FlowTrail Community POIs",
            "description": (
                "Community-POIs und OSM-Wehre für Kanufahrer in Deutschland. "
                "Wehre: © OpenStreetMap contributors (ODbL)."
            ),
            "version": version,
        },
        "features": community + osm_filtered,
    }
    write_geojson(POIS_PATH, merged)

    manifest = {
        "version": version,
        "updatedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "label": f"FlowTrail POIs ({len(community)} Community + {len(osm_filtered)} OSM-Wehre)",
        "dataUrl": "https://raw.githubusercontent.com/3ddruck12/flowtrail-pois/main/pois.geojson",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    stats = {
        "community": len(community),
        "osm_raw": len(osm_raw),
        "osm_merged": len(osm_filtered),
        "total": len(merged["features"]),
    }
    print(
        f"Merge: {stats['community']} community + {stats['osm_merged']} osm "
        f"({stats['osm_raw'] - stats['osm_merged']} osm gefiltert) = {stats['total']} gesamt"
    )
    return stats


def migrate_from_legacy() -> None:
    if not LEGACY_POIS_PATH.exists():
        print("Kein pois.geojson für Migration gefunden.", file=sys.stderr)
        sys.exit(1)
    community, osm = split_legacy_pois(LEGACY_POIS_PATH)
    version = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M")
    write_community_file(community, version)
    write_osm_file(osm, version)
    print(f"Split: {len(community)} community → {COMMUNITY_PATH.name}")
    print(f"Split: {len(osm)} osm → {OSM_PATH.name}")
    merge_and_write(version)


def main() -> None:
    parser = argparse.ArgumentParser(description="Community + OSM → pois.geojson mergen")
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="pois.geojson einmalig in community-pois + osm-weirs splitten und mergen",
    )
    parser.add_argument("--version", default=None, help="Manifest-Version (Default: jetzt UTC)")
    args = parser.parse_args()

    if args.migrate:
        migrate_from_legacy()
    else:
        merge_and_write(args.version)


if __name__ == "__main__":
    main()
