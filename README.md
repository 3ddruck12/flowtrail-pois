# FlowTrail Community POIs

Statischer POI-Datensatz für die [FlowTrail](https://github.com/3ddruck12/FlowTrail)-App.

## Dateien

| Datei | Zweck |
|-------|-------|
| `manifest.json` | Version, Label, URL zu `pois.geojson` |
| `community-pois.geojson` | Community-POIs (Editor, manuell gepflegt) |
| `osm-weirs.geojson` | OSM-Wehre (GitHub Action) |
| `pois.geojson` | Merge für die App (generiert) |

## POI-Editor (Karte)

**GitHub Pages:** [3ddruck12.github.io/flowtrail-pois](https://3ddruck12.github.io/flowtrail-pois/) (nach Pages-Aktivierung)

- Community-POIs anlegen, bearbeiten, löschen (Typ-Dropdown)
- OSM-Wehre im Kartenausschnitt anzeigen und **„Als Community übernehmen“**
- Export: `community-pois.geojson` herunterladen → ins Repo committen → mergen:

```bash
python scripts/merge_pois.py
git add community-pois.geojson pois.geojson manifest.json
git commit -m "Community-POIs aktualisiert"
git push
```

### OSM → Community

Beim Übernehmen wird `replaces_osm_id` gesetzt (z. B. `way/809169536`). Beim Merge und OSM-Re-Import wird dieses OSM-Wehr ausgeblendet — das Community-POI bleibt.

```json
{
  "properties": {
    "name": "Wehr Hattingen (geprüft)",
    "type": "Wehr",
    "source": "community",
    "replaces_osm_id": "way/809169536"
  }
}
```

## POI melden

1. **In der App:** Menü → „POI melden“ (GitHub Issue)
2. **Auf GitHub:** [Neues Issue](https://github.com/3ddruck12/flowtrail-pois/issues/new/choose)

## Moderation (Maintainer)

Community-POIs pflegst du am besten über den **Editor** oder direkt in `community-pois.geojson`. Danach immer `merge_pois.py` ausführen.

## App-Konfiguration

```properties
POI_FEED_MANIFEST_URL=https://raw.githubusercontent.com/3ddruck12/flowtrail-pois/main/manifest.json
POI_ISSUE_REPO=3ddruck12/flowtrail-pois
```

Die App unterscheidet `source: community` (Navigation) und `source: osm` (Gefahren-Layer).

## POI-Typen

`Einstieg` · `Ausstieg` · `Rastplatz` · `Wehr` · `Schleuse` · `Gefahrenstelle`

## OSM-Wehre importieren

[Actions → import-osm-weirs](https://github.com/3ddruck12/flowtrail-pois/actions/workflows/import-osm-weirs.yml)

```bash
pip install -r scripts/requirements.txt
python scripts/import_osm_weirs.py --region de
# oder nur mergen:
python scripts/merge_pois.py
```

Merge-Regel: `community-pois.geojson` bleibt unverändert; `osm-weirs.geojson` wird beim Import ersetzt; `replaces_osm_id` filtert OSM-Duplikate.

## Lizenz

POI-Daten: Community-Beiträge + Wehre aus OpenStreetMap (© OSM contributors, [ODbL](https://opendatacommons.org/licenses/odbl/)).
