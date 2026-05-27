(function () {
  "use strict";

  var REPO = "3ddruck12/flowtrail-pois";
  var BRANCH = "main";
  var RAW_BASE = "https://raw.githubusercontent.com/" + REPO + "/" + BRANCH + "/";
  var POI_TYPES = ["Einstieg", "Ausstieg", "Rastplatz", "Wehr", "Schleuse", "Gefahrenstelle"];
  var VIEWPORT_OSM_LIMIT = 500;

  var map = L.map("map", { zoomControl: false }).setView([51.1657, 10.4515], 6);
  L.control.zoom({ position: "bottomright" }).addTo(map);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
    attribution: "&copy; OSM &copy; CARTO",
    maxZoom: 19,
    subdomains: "abcd"
  }).addTo(map);

  var communityLayer = L.layerGroup().addTo(map);
  var osmLayer = L.layerGroup().addTo(map);

  var communityFeatures = [];
  var osmFeatures = [];
  var osmLoaded = false;
  var addMode = false;
  var communityMarkers = [];
  var osmMarkers = [];

  var statusBar = document.getElementById("statusBar");
  var sidebar = document.getElementById("sidebar");
  var poiForm = document.getElementById("poiForm");

  function setStatus(msg) {
    statusBar.textContent = msg;
  }

  function pinColor(type) {
    var t = (type || "").toLowerCase();
    if (t.indexOf("einstieg") >= 0) return "#4CAF50";
    if (t.indexOf("ausstieg") >= 0) return "#F44336";
    if (t.indexOf("rast") >= 0) return "#FF9800";
    if (t.indexOf("schleuse") >= 0) return "#2563EB";
    if (t.indexOf("wehr") >= 0) return "#DC2626";
    if (t.indexOf("gefahr") >= 0) return "#9C27B0";
    return "#0078FF";
  }

  function makeCommunityIcon(type) {
    var label = (type || "P").substring(0, 3);
    return L.divIcon({
      className: "",
      html: '<div class="community-pin" style="background:' + pinColor(type) + '"><span>' + label + "</span></div>",
      iconSize: [22, 22],
      iconAnchor: [11, 22]
    });
  }

  function makeOsmIcon() {
    return L.divIcon({
      className: "",
      html: '<div class="osm-pin"></div>',
      iconSize: [14, 14],
      iconAnchor: [7, 7]
    });
  }

  function featureLatLng(feature) {
    var c = feature.geometry.coordinates;
    return L.latLng(c[1], c[0]);
  }

  function newCommunityFeature(lat, lng, props) {
    return {
      type: "Feature",
      geometry: { type: "Point", coordinates: [lng, lat] },
      properties: Object.assign({
        name: "Neuer POI",
        description: "",
        type: "Einstieg",
        river: "",
        source: "community"
      }, props || {})
    };
  }

  function buildCommunityCollection() {
    return {
      type: "FeatureCollection",
      metadata: {
        name: "FlowTrail Community POIs",
        description: "Von Maintainers und Community gepflegte Kanu-POIs.",
        version: new Date().toISOString().slice(0, 16).replace("T", "T")
      },
      features: communityFeatures
    };
  }

  function redrawCommunity() {
    communityLayer.clearLayers();
    communityMarkers = [];
    communityFeatures.forEach(function (feature, index) {
      var props = feature.properties;
      var marker = L.marker(featureLatLng(feature), {
        icon: makeCommunityIcon(props.type),
        draggable: true
      }).addTo(communityLayer);

      marker.on("dragend", function () {
        var ll = marker.getLatLng();
        feature.geometry.coordinates = [ll.lng, ll.lat];
      });
      marker.on("click", function (e) {
        L.DomEvent.stopPropagation(e);
        openCommunityEditor(index);
      });
      communityMarkers.push(marker);
    });
  }

  function featuresInViewport(features, limit) {
    var bounds = map.getBounds();
    var filtered = features.filter(function (f) {
      var ll = featureLatLng(f);
      return bounds.contains(ll);
    });
    if (filtered.length > limit) {
      return filtered.slice(0, limit);
    }
    return filtered;
  }

  function redrawOsm() {
    osmLayer.clearLayers();
    osmMarkers = [];
    if (!document.getElementById("osmLayerToggle").checked) return;

    var visible = featuresInViewport(osmFeatures, VIEWPORT_OSM_LIMIT);
    visible.forEach(function (feature) {
      var props = feature.properties || {};
      var blocked = communityFeatures.some(function (c) {
        return c.properties.replaces_osm_id === props.osm_id;
      });
      if (blocked) return;

      var marker = L.marker(featureLatLng(feature), { icon: makeOsmIcon() }).addTo(osmLayer);
      marker.bindPopup(
        "<b>" + (props.name || "OSM Wehr") + "</b><br>" +
        (props.description || "") +
        '<br><button type="button" class="btn primary adopt-btn" data-osm-id="' + (props.osm_id || "") + '">Als Community übernehmen</button>'
      );
      marker.on("popupopen", function () {
        var btn = document.querySelector(".adopt-btn[data-osm-id='" + props.osm_id + "']");
        if (btn) {
          btn.onclick = function () {
            adoptOsmFeature(feature);
            map.closePopup();
          };
        }
      });
      osmMarkers.push(marker);
    });
    setStatus(
      communityFeatures.length + " Community-POIs · " +
      visible.length + " OSM im Ausschnitt" +
      (osmFeatures.length ? " (" + osmFeatures.length + " gesamt)" : "")
    );
  }

  function openCommunityEditor(index) {
    var feature = communityFeatures[index];
    if (!feature) return;
    var props = feature.properties;
    document.getElementById("poiIndex").value = String(index);
    document.getElementById("poiName").value = props.name || "";
    document.getElementById("poiType").value = POI_TYPES.indexOf(props.type) >= 0 ? props.type : "Einstieg";
    document.getElementById("poiRiver").value = props.river || "";
    document.getElementById("poiDescription").value = props.description || "";
    var replaces = props.replaces_osm_id || "";
    document.getElementById("poiReplacesOsm").value = replaces;
    document.getElementById("replacesRow").classList.toggle("hidden", !replaces);
    document.getElementById("btnDelete").classList.toggle("hidden", index < 0);
    document.getElementById("sidebarTitle").textContent = "Community-POI bearbeiten";
    sidebar.classList.remove("hidden");
  }

  function closeSidebar() {
    sidebar.classList.add("hidden");
    document.getElementById("poiIndex").value = "-1";
  }

  function adoptOsmFeature(osmFeature) {
    var props = osmFeature.properties || {};
    var ll = featureLatLng(osmFeature);
    var feature = newCommunityFeature(ll.lat, ll.lng, {
      name: props.name || "Wehr",
      description: props.description || "",
      type: props.type || "Wehr",
      river: props.river || "",
      source: "community",
      replaces_osm_id: props.osm_id || ""
    });
    communityFeatures.push(feature);
    redrawCommunity();
    redrawOsm();
    openCommunityEditor(communityFeatures.length - 1);
    setStatus("OSM-POI übernommen. Bitte prüfen und exportieren.");
  }

  poiForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var index = parseInt(document.getElementById("poiIndex").value, 10);
    if (index < 0 || !communityFeatures[index]) return;
    var feature = communityFeatures[index];
    var props = feature.properties;
    props.name = document.getElementById("poiName").value.trim();
    props.type = document.getElementById("poiType").value;
    props.river = document.getElementById("poiRiver").value.trim();
    props.description = document.getElementById("poiDescription").value.trim();
    props.source = "community";
    redrawCommunity();
    closeSidebar();
    setStatus("Community-POI gespeichert (lokal). Export nicht vergessen!");
  });

  document.getElementById("btnDelete").addEventListener("click", function () {
    var index = parseInt(document.getElementById("poiIndex").value, 10);
    if (index < 0) return;
    if (!confirm("Diesen Community-POI wirklich löschen?")) return;
    communityFeatures.splice(index, 1);
    redrawCommunity();
    redrawOsm();
    closeSidebar();
  });

  document.getElementById("btnClose").addEventListener("click", closeSidebar);

  document.getElementById("btnAddMode").addEventListener("click", function () {
    addMode = !addMode;
    document.getElementById("btnAddMode").classList.toggle("active", addMode);
    setStatus(addMode ? "Klicke auf die Karte, um einen POI zu setzen." : "POI-Setzen beendet.");
  });

  map.on("click", function (e) {
    if (!addMode) return;
    var feature = newCommunityFeature(e.latlng.lat, e.latlng.lng, {});
    communityFeatures.push(feature);
    addMode = false;
    document.getElementById("btnAddMode").classList.remove("active");
    redrawCommunity();
    openCommunityEditor(communityFeatures.length - 1);
  });

  map.on("moveend", redrawOsm);

  document.getElementById("osmLayerToggle").addEventListener("change", function () {
    if (this.checked && !osmLoaded) {
      loadOsmWeirs();
    } else {
      redrawOsm();
    }
  });

  document.getElementById("btnExport").addEventListener("click", function () {
    var json = JSON.stringify(buildCommunityCollection(), null, 2);
    var blob = new Blob([json], { type: "application/geo+json" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "community-pois.geojson";
    a.click();
    URL.revokeObjectURL(a.href);
    setStatus("Export gestartet. Datei ins Repo legen und scripts/merge_pois.py ausführen.");
  });

  function loadCommunity() {
    return fetch(RAW_BASE + "community-pois.geojson")
      .then(function (r) {
        if (!r.ok) throw new Error("community-pois.geojson HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        communityFeatures = data.features || [];
        redrawCommunity();
        setStatus(communityFeatures.length + " Community-POIs geladen.");
      });
  }

  function loadOsmWeirs() {
    setStatus("Lade OSM-Wehre (kann einige Sekunden dauern) …");
    return fetch(RAW_BASE + "osm-weirs.geojson")
      .then(function (r) {
        if (!r.ok) throw new Error("osm-weirs.geojson HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        osmFeatures = data.features || [];
        osmLoaded = true;
        redrawOsm();
      })
      .catch(function (err) {
        setStatus("OSM-Layer Fehler: " + err.message);
      });
  }

  loadCommunity().catch(function (err) {
    setStatus("Fehler: " + err.message);
  });
})();
