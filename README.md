# FlowTrail Community POIs

Statischer POI-Datensatz für die [FlowTrail](https://github.com/3ddruck12/FlowTrail)-App.

## Dateien

| Datei | Zweck |
|-------|-------|
| `manifest.json` | Version, Label, URL zu `pois.geojson` |
| `pois.geojson` | GeoJSON FeatureCollection mit Kanu-POIs |

## POI melden

1. **In der App:** Menü → „POI melden“ (öffnet GitHub Issue mit vorausgefüllten Feldern)
2. **Auf GitHub:** [Neues Issue](https://github.com/3ddruck12/flowtrail-pois/issues/new/choose) → Vorlage „POI melden“

## Moderation (Maintainer)

Nach Prüfung einer Meldung:

1. POI als Feature in `pois.geojson` eintragen:
   ```json
   {
     "type": "Feature",
     "geometry": { "type": "Point", "coordinates": [lng, lat] },
     "properties": {
       "name": "...",
       "description": "...",
       "type": "Wehr",
       "river": "Ruhr",
       "source": "community"
     }
   }
   ```
2. `manifest.json` aktualisieren: `version` und `updatedAt` erhöhen
3. Commit + Push → App erkennt Update beim nächsten „POI-Daten aktualisieren“

## App-Konfiguration

In `gradle.properties` der FlowTrail-App:

```properties
POI_FEED_MANIFEST_URL=https://raw.githubusercontent.com/3ddruck12/flowtrail-pois/main/manifest.json
POI_ISSUE_REPO=3ddruck12/flowtrail-pois
```

## POI-Typen

`Einstieg` · `Ausstieg` · `Rastplatz` · `Wehr` · `Schleuse` · `Gefahrenstelle`

## OSM-Wehre importieren (Maintainer)

Wehre werden aus [OpenStreetMap](https://www.openstreetmap.org/) via Overpass API geladen.
Linien-Geometrien (Ways) werden automatisch in Mittelpunkte umgewandelt.

**GitHub Actions:** [Actions → import-osm-weirs → Run workflow](https://github.com/3ddruck12/flowtrail-pois/actions/workflows/import-osm-weirs.yml)

| Option | Bedeutung |
|--------|-----------|
| `de` | Alle 16 Bundesländer (empfohlen für Vollimport) |
| `nw`, `by`, … | Einzelnes Bundesland |

**Lokal:**

```bash
pip install -r scripts/requirements.txt
python scripts/import_osm_weirs.py --region nw --dry-run
python scripts/import_osm_weirs.py --region de
```

Merge-Regel: `source: community` bleibt erhalten, `source: osm` wird bei jedem Import ersetzt.

## Lizenz

POI-Daten: Community-Beiträge + Wehre aus OpenStreetMap (© OSM contributors, [ODbL](https://opendatacommons.org/licenses/odbl/)).
App: siehe [FlowTrail/LICENSE](https://github.com/3ddruck12/FlowTrail/blob/main/LICENSE).
