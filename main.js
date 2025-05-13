// main.js actualizado

const map = L.map("map").setView([-9.2, -75.15], 6);

L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  {
    maxZoom: 22,
    attribution: "Tiles © Esri"
  }
).addTo(map);

map.zoomControl.setPosition('topright');

const drawnItems = new L.FeatureGroup().addTo(map);
const deforestationLayer = L.geoJSON(null, {
  style: { color: "red", weight: 2, fillOpacity: 0.5, opacity: 0.8 },
}).addTo(map);

const screenshoter = L.simpleMapScreenshoter({
  hidden: false,
  preventDownload: false,
  position: 'topright',
  screenName: () => `captura_${new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}`
});
map.addControl(screenshoter);

function formatDate(inputDate) {
  const parts = inputDate.split("-");
  return parts[0] + parts[1].padStart(2, "0") + parts[2].padStart(2, "0");
}

function limpiarMapa() {
  map.eachLayer(layer => {
    if (layer instanceof L.TileLayer && !layer._url.includes("World_Imagery")) {
      map.removeLayer(layer);
    }
  });
  deforestationLayer.clearLayers();
  drawnItems.clearLayers();
  document.getElementById("layer-label").textContent = "Capa activa: -";
  document.getElementById("legend").style.display = "none";
  document.getElementById("stats-panel").style.display = "none";
}

async function compararNDVI() {
  const date1 = formatDate(document.getElementById("start-date").value);
  const date2 = formatDate(document.getElementById("end-date").value);
  const res1 = await fetch(`http://127.0.0.1:8080/gee-tile-url?date=${date1}`);
  const res2 = await fetch(`http://127.0.0.1:8080/gee-tile-url?date=${date2}`);
  const data1 = await res1.json();
  const data2 = await res2.json();

  limpiarMapa();
  const capa1 = L.tileLayer(data1.tileUrl);
  const capa2 = L.tileLayer(data2.tileUrl);
  L.control.layers({ [`NDVI ${date1}`]: capa1, [`NDVI ${date2}`]: capa2 }, null, { collapsed: false }).addTo(map);
  capa1.addTo(map);
  document.getElementById("layer-label").textContent = `NDVI ${date1} vs ${date2}`;
}

async function detectarDiferencia() {
  const date1 = formatDate(document.getElementById("start-date").value);
  const date2 = formatDate(document.getElementById("end-date").value);
  const res = await fetch(`http://127.0.0.1:8080/gee-ndvi-diff?date1=${date1}&date2=${date2}`);
  const data = await res.json();
  limpiarMapa();
  L.tileLayer(data.tileUrl).addTo(map);
  document.getElementById("layer-label").textContent = data.name;
  document.getElementById("legend").style.display = "block";
}

async function detectarZonas() {
  const date1 = formatDate(document.getElementById("start-date").value);
  const date2 = formatDate(document.getElementById("end-date").value);
  const threshold = document.getElementById("threshold").value;
  const b = map.getBounds();
  const url = `http://127.0.0.1:8080/gee-deforestation-zones?date1=${date1}&date2=${date2}&threshold=${threshold}&minx=${b.getWest()}&miny=${b.getSouth()}&maxx=${b.getEast()}&maxy=${b.getNorth()}`;
  const res = await fetch(url);
  const data = await res.json();
  deforestationLayer.clearLayers();
  deforestationLayer.addData(data);
  document.getElementById("layer-label").textContent = "Zonas deforestadas";
}

async function mostrarEstadisticas() {
  const date = formatDate(document.getElementById("ndvi-date").value);
  const b = map.getBounds();
  const url = `http://127.0.0.1:8080/gee-ndvi-stats?date=${date}&minx=${b.getWest()}&miny=${b.getSouth()}&maxx=${b.getEast()}&maxy=${b.getNorth()}`;
  const res = await fetch(url);
  const data = await res.json();
  document.getElementById("stats-year").textContent = data.year;
  document.getElementById("stats-mean").textContent = data.mean.toFixed(3);
  document.getElementById("stats-min").textContent = data.min.toFixed(3);
  document.getElementById("stats-max").textContent = data.max.toFixed(3);
  document.getElementById("stats-std").textContent = data.stdDev.toFixed(3);
  document.getElementById("stats-panel").style.display = "block";
}

function activarDibujo() {
  if (!map.drawControl) {
    map.drawControl = new L.Control.Draw({
      position: 'topright',
      draw: {
        polygon: true,
        marker: false,
        polyline: false,
        rectangle: false,
        circle: false,
        circlemarker: false,
      },
      edit: {
        featureGroup: drawnItems,
        remove: true
      }
    });
    map.addControl(map.drawControl);
  }

  map.once(L.Draw.Event.CREATED, function (event) {
    drawnItems.clearLayers();
    drawnItems.addLayer(event.layer);
  });
}

function descargarGeoJSON() {
  if (drawnItems.getLayers().length === 0) {
    alert("Primero dibuja un polígono.");
    return;
  }
  const geojson = drawnItems.toGeoJSON();
  const blob = new Blob([JSON.stringify(geojson, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `area_${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

function capturarMapa() {
  map.once("rendercomplete", () => {
    setTimeout(() => screenshoter.takeScreen(), 300);
  });
  map.invalidateSize();
}

document.getElementById("input-geojson")?.addEventListener("change", function (e) {
  const file = e.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = function (event) {
    try {
      const geojson = JSON.parse(event.target.result);
      const layer = L.geoJSON(geojson, {
        style: { color: "#ff6600", weight: 2, fillOpacity: 0.2 },
      });
      drawnItems.clearLayers();
      drawnItems.addLayer(layer);
      map.fitBounds(layer.getBounds());
    } catch (err) {
      alert("El archivo no es un GeoJSON válido.");
    }
  };
  reader.readAsText(file);
});

async function mostrarEstadisticasDesdePoligono() {
  const date = formatDate(document.getElementById("ndvi-date").value);
  const geojson = drawnItems.toGeoJSON();

  if (!geojson.features.length) {
    alert("Primero dibuja un polígono.");
    return;
  }

  const geometry = geojson.features[0].geometry;

  const res = await fetch('http://127.0.0.1:8080/gee-ndvi-stats-from-geojson', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ date: date, geometry: geometry })
  });

  const data = await res.json();
  if (data.error) {
    alert("Error: " + data.error);
    return;
  }

  // Cambiar estilo del polígono dibujado según el promedio NDVI
  let color = '#00cc00'; // verde por defecto
  let mensaje = 'Vegetación saludable';
  if (data.mean < 0.4) {
    color = '#ff0000'; // rojo si bajo NDVI
    mensaje = '⚠ Posible deforestación';
  } else if (data.mean < 0.6) {
    color = '#ffcc00'; // amarillo si intermedio
    mensaje = 'Vegetación intermedia';
  }

  drawnItems.eachLayer(layer => {
    if (layer instanceof L.Polygon) {
      layer.setStyle({ color: color, weight: 3, fillOpacity: 0.3 });
    }
  });

  document.getElementById("stats-year").textContent = data.year;
  document.getElementById("stats-mean").textContent = data.mean.toFixed(3);
  document.getElementById("stats-min").textContent = data.min.toFixed(3);
  document.getElementById("stats-max").textContent = data.max.toFixed(3);
  document.getElementById("stats-std").textContent = data.stdDev.toFixed(3);
  document.getElementById("stats-msg").textContent = mensaje;
  document.getElementById("stats-panel").style.display = "block";
}

// Enlaces a botones
window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("btn-comparar-ndvi").addEventListener("click", compararNDVI);
  document.getElementById("btn-detectar").addEventListener("click", detectarDiferencia);
  document.getElementById("btn-zonas").addEventListener("click", detectarZonas);
  document.getElementById("btn-stats").addEventListener("click", mostrarEstadisticas);
  document.getElementById("btn-stats-poly").addEventListener("click", mostrarEstadisticasDesdePoligono);
  document.getElementById("btn-limpiar").addEventListener("click", limpiarMapa);
  document.getElementById("btn-dibujar").addEventListener("click", activarDibujo);
  document.getElementById("btn-descargar").addEventListener("click", descargarGeoJSON);
  document.getElementById("btn-capturar").addEventListener("click", capturarMapa);
});
