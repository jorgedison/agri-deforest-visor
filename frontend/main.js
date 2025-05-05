// Inicializar el mapa
const map = L.map("map").setView([-9.2, -75.15], 6);

L.tileLayer(
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", 
  {
    maxZoom: 15,
    attribution: "Tiles © Esri — Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, etc."
  }
).addTo(map);

/* Mapa
const map = L.map("map").setView([-9.2, -75.15], 6);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "© OpenStreetMap contributors"
}).addTo(map);*/

// Agregar Leaflet.SimpleMapScreenshoter
const screenshoter = L.simpleMapScreenshoter({
  hidden: false,
  preventDownload: false,
  position: 'topright',
  screenName: function () {
    return `captura_${new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}`;
  },
});
map.addControl(screenshoter);

let ndviLayer, diffLayer, zonesLayer;
let drawnPolygon;
const drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);

const deforestationLayer = L.geoJSON(null, {
  style: { color: "red", weight: 2, fillOpacity: 0.5, opacity: 0.8 },
}).addTo(map);

// Mostrar controles de zoom en la esquina superior derecha
map.zoomControl.setPosition('topright');

function formatDate(inputDate) {
  const parts = inputDate.split("-");
  return parts[0] + parts[1].padStart(2, "0") + parts[2].padStart(2, "0");
}

function isFutureDate(dateStr) {
  const inputDate = new Date(dateStr);
  const today = new Date();
  return inputDate > today;
}

function limpiarMapa() {
  if (ndviLayer) {
    map.removeLayer(ndviLayer);
    ndviLayer = null;
  }
  if (diffLayer) {
    map.removeLayer(diffLayer);
    diffLayer = null;
  }
  if (zonesLayer) {
    map.removeLayer(zonesLayer);
    zonesLayer = null;
  }
  deforestationLayer.clearLayers();
  drawnItems.clearLayers();

  document.getElementById("layer-label").textContent = "Capa activa: -";
  document.getElementById("legend").style.display = "none";
}

let drawControl; // define fuera para controlarlo globalmente

function activarDibujo() {
  if (!drawControl) {
    drawControl = new L.Control.Draw({
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
        remove: true,
      },
    });
    map.addControl(drawControl);
  }

  map.off(L.Draw.Event.CREATED); // para evitar múltiples bindings
  map.on(L.Draw.Event.CREATED, function (event) {
    drawnItems.clearLayers();
    drawnPolygon = event.layer;
    drawnItems.addLayer(drawnPolygon);
  });
}


function guardarPoligono() {
  if (!drawnPolygon) {
    alert("Primero dibuja un polígono.");
    return;
  }
  const geojson = drawnPolygon.toGeoJSON();
  const timestamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
  const blob = new Blob([JSON.stringify(geojson, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `area_${timestamp}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

function capturarMapa() {
  map.once("rendercomplete", () => {
    setTimeout(() => screenshoter.takeScreen(), 300);
  });
  map.invalidateSize();
}

// Eventos de botones
document.getElementById("btn-ver-ndvi").addEventListener("click", async () => {
  const date = document.getElementById("ndvi-date").value;
  const formattedDate = formatDate(date);
  try {
    const res = await fetch(`http://127.0.0.1:8080/gee-tile-url?date=${formattedDate}`);
    const data = await res.json();
    if (ndviLayer) map.removeLayer(ndviLayer);
    ndviLayer = L.tileLayer(data.tileUrl).addTo(map);
    document.getElementById("layer-label").textContent = data.name;
    document.getElementById("legend").style.display = "none";
  } catch (error) {
    alert("Error al cargar NDVI");
  }
});

document.getElementById("btn-detectar").addEventListener("click", async () => {
  const date1 = formatDate(document.getElementById("start-date").value);
  const date2 = formatDate(document.getElementById("end-date").value);
  try {
    const res = await fetch(`http://127.0.0.1:8080/gee-ndvi-diff?date1=${date1}&date2=${date2}`);
    const data = await res.json();
    if (diffLayer) map.removeLayer(diffLayer);
    diffLayer = L.tileLayer(data.tileUrl).addTo(map);
    document.getElementById("layer-label").textContent = "Diferencia NDVI";
    document.getElementById("legend").style.display = "block";
  } catch (error) {
    alert("Error al detectar deforestación");
  }
});

document.getElementById("btn-zonas").addEventListener("click", async () => {
  const date1 = formatDate(document.getElementById("start-date").value);
  const date2 = formatDate(document.getElementById("end-date").value);
  const threshold = document.getElementById("threshold").value;
  try {
    const res = await fetch(`http://127.0.0.1:8080/gee-deforestation-zones?date1=${date1}&date2=${date2}&threshold=${threshold}`);
    const data = await res.json();
    deforestationLayer.clearLayers();
    deforestationLayer.addData(data);
    document.getElementById("layer-label").textContent = "Zonas deforestadas";
    document.getElementById("legend").style.display = "block";
  } catch (error) {
    alert("Error al obtener zonas deforestadas");
  }
});

document.getElementById("btn-limpiar").addEventListener("click", limpiarMapa);
document.getElementById("btn-dibujar").addEventListener("click", activarDibujo);
document.getElementById("btn-descargar").addEventListener("click", guardarPoligono);
document.getElementById("btn-capturar").addEventListener("click", capturarMapa);
