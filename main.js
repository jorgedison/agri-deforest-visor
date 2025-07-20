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

let activeLegendControl = null;

function generateNDVILegendHtml() {
  return `
    <div class="info legend">
      <h4>Leyenda NDVI</h4>
      <div><i style="background:#01665e"></i> > 0.8 (Vegetación densa)</div>
      <div><i style="background:#5ab4ac"></i> 0.6 - 0.8 (Vegetación abundante)</div>
      <div><i style="background:#c7eae5"></i> 0.4 - 0.6 (Vegetación moderada)</div>
      <div><i style="background:#f6e8c3"></i> 0.2 - 0.4 (Vegetación escasa o mixta)</div>
      <div><i style="background:#d8b365"></i> 0.1 - 0.2 (Vegetación muy degradada)</div>
      <div><i style="background:#8c510a"></i> < 0.1 (Suelo expuesto)</div>
    </div>
  `;
}

function generateNDVIDiffLegendHtml() {
  return `
    <div class="info legend">
      <h4>Diferencia NDVI</h4>
      <div><i style="background:green"></i> Gran aumento (Regeneración)</div>
      <div><i style="background:cyan"></i> Pequeño aumento</div>
      <div><i style="background:white"></i> Poco o ningún cambio</div>
      <div><i style="background:yellow"></i> Pequeña disminución</div>
      <div><i style="background:red"></i> Gran disminución (Deforestación)</div>
    </div>
  `;
}

function addLegendToMap(htmlContent) {
  if (activeLegendControl) {
    map.removeControl(activeLegendControl);
  }

  const LegendControl = L.Control.extend({
    onAdd: function(map) {
      const div = L.DomUtil.create('div', 'info legend');
      div.innerHTML = htmlContent;
      return div;
    },
    onRemove: function(map) {
      // Nada que hacer aquí
    }
  });

  activeLegendControl = new LegendControl({ position: 'bottomright' });
  activeLegendControl.addTo(map);
}

// Modal handling
const candidateImagesModal = document.getElementById("candidate-images-modal");
const closeModalSpan = document.getElementsByClassName("close")[0];

closeModalSpan.onclick = function() {
  candidateImagesModal.style.display = "none";
}

window.onclick = function(event) {
  if (event.target == candidateImagesModal) {
    candidateImagesModal.style.display = "none";
  }
}

function showCandidateImagesModal(images) {
  const contentDiv = document.getElementById("candidate-images-list-content");
  contentDiv.innerHTML = ''; // Clear previous content

  if (images && images.length > 0) {
    const ul = document.createElement('ul');
    images.forEach(img => {
      const li = document.createElement('li');
      li.textContent = `Fecha: ${img.date}, Nubosidad: ${img.cloud_cover.toFixed(2)}%`;
      ul.appendChild(li);
    });
    contentDiv.appendChild(ul);
  } else {
    contentDiv.textContent = 'No se encontraron imágenes candidatas.';
  }
  candidateImagesModal.style.display = "block";
}

async function fetchOptimalDate(dateInputId) {
  const dateInput = document.getElementById(dateInputId);
  const originalDate = dateInput.value;

  if (!originalDate) return;

  try {
    // Assuming the backend is at 127.0.0.1:8080 as per other fetch calls
    const res = await fetch(`http://127.0.0.1:8080/find-best-image-date?date=${originalDate}`);
    const data = await res.json();

    if (data.error) {
      console.error("Error fetching optimal date:", data.error);
      alert(`Error al buscar fecha óptima: ${data.error}`);
      return;
    }

    if (data.optimalDate && data.optimalDate !== originalDate) {
      dateInput.value = data.optimalDate; // Update the input field
      alert(`Fecha ajustada automáticamente a ${data.optimalDate} para una mejor calidad de imagen (nubosidad: ${data.cloudCover.toFixed(2)}%).`);
      showCandidateImagesModal(data.candidateImages);
    } else if (data.optimalDate === originalDate) {
      alert(`La fecha ${originalDate} ya es óptima (nubosidad: ${data.cloudCover.toFixed(2)}%).`);
      showCandidateImagesModal(data.candidateImages);
    } else {
      alert(`No se encontró una fecha óptima para ${originalDate}.`);
    }
  } catch (error) {
    console.error("Network or parsing error:", error);
    alert("Error de conexión al buscar fecha óptima.");
  }
}

// Modal handling
const candidateImagesModal = document.getElementById("candidate-images-modal");
const closeModalSpan = document.getElementsByClassName("close")[0];

closeModalSpan.onclick = function() {
  candidateImagesModal.style.display = "none";
}

window.onclick = function(event) {
  if (event.target == candidateImagesModal) {
    candidateImagesModal.style.display = "none";
  }
}

function showCandidateImagesModal(images) {
  const contentDiv = document.getElementById("candidate-images-list-content");
  contentDiv.innerHTML = ''; // Clear previous content

  if (images && images.length > 0) {
    const ul = document.createElement('ul');
    images.forEach(img => {
      const li = document.createElement('li');
      li.textContent = `Fecha: ${img.date}, Nubosidad: ${img.cloud_cover.toFixed(2)}%`;
      ul.appendChild(li);
    });
    contentDiv.appendChild(ul);
  } else {
    contentDiv.textContent = 'No se encontraron imágenes candidatas.';
  }
  candidateImagesModal.style.display = "block";
}

async function fetchOptimalDate(dateInputId) {
  const dateInput = document.getElementById(dateInputId);
  const originalDate = dateInput.value;

  if (!originalDate) return;

  try {
    // Assuming the backend is at 127.0.0.1:8080 as per other fetch calls
    const res = await fetch(`http://127.0.0.1:8080/find-best-image-date?date=${originalDate}`);
    const data = await res.json();

    if (data.error) {
      console.error("Error fetching optimal date:", data.error);
      alert(`Error al buscar fecha óptima: ${data.error}`);
      return;
    }

    if (data.optimalDate && data.optimalDate !== originalDate) {
      dateInput.value = data.optimalDate; // Update the input field
      alert(`Fecha ajustada automáticamente a ${data.optimalDate} para una mejor calidad de imagen (nubosidad: ${data.cloudCover.toFixed(2)}%).`);
      showCandidateImagesModal(data.candidateImages);
    } else if (data.optimalDate === originalDate) {
      alert(`La fecha ${originalDate} ya es óptima (nubosidad: ${data.cloudCover.toFixed(2)}%).`);
      showCandidateImagesModal(data.candidateImages);
    } else {
      alert(`No se encontró una fecha óptima para ${originalDate}.`);
    }
  } catch (error) {
    console.error("Network or parsing error:", error);
    alert("Error de conexión al buscar fecha óptima.");
  }
}


async function calculateCloudinessInView() {
  const date = formatDate(document.getElementById("cloudiness-date").value);
  const b = map.getBounds();
  const url = `http://127.0.0.1:8080/gee-cloudiness-in-view?date=${date}&minx=${b.getWest()}&miny=${b.getSouth()}&maxx=${b.getEast()}&maxy=${b.getNorth()}`;

  try {
    const res = await fetch(url);
    const data = await res.json();

    if (data.error) {
      document.getElementById("cloudiness-result").textContent = `Error: ${data.error}`;
      return;
    }

    document.getElementById("cloudiness-result").textContent = `Nubosidad en área visible: ${data.cloudiness.toFixed(2)}%`;
  } catch (error) {
    console.error("Error fetching cloudiness:", error);
    document.getElementById("cloudiness-result").textContent = "Error al calcular nubosidad.";
  }
}

async function compararNDVI() {
  const date1 = formatDate(document.getElementById("start-date").value);
  const date2 = formatDate(document.getElementById("end-date").value);
  const res1 = await fetch(`http://127.0.0.1:8080/gee-tile-url?date=${date1}`);
  const res2 = await fetch(`http://127.0.0.1:8080/gee-tile-url?date=${date2}`);
  const data1 = await res1.json();
  const data2 = await res2.json();

  const cloudThreshold = 20; // Umbral de cobertura de nubes en porcentaje

  if (data1.cloudCover > cloudThreshold || data2.cloudCover > cloudThreshold) {
    alert(`Advertencia: Una o ambas imágenes tienen alta cobertura de nubes (Imagen 1: ${data1.cloudCover.toFixed(2)}%, Imagen 2: ${data2.cloudCover.toFixed(2)}%). Considere seleccionar fechas alternativas para una mejor visualización.`);
  }

  limpiarMapa();
  const capa1 = L.tileLayer(data1.tileUrl);
  const capa2 = L.tileLayer(data2.tileUrl);
  L.control.layers({ [`NDVI ${data1.calculationStartDate} (${data1.cloudCover.toFixed(1)}% nubes)`]: capa1, [`NDVI ${data2.calculationStartDate} (${data2.cloudCover.toFixed(1)}% nubes)`]: capa2 }, null, { collapsed: false }).addTo(map);
  capa1.addTo(map);
  document.getElementById("layer-label").textContent = `NDVI ${data1.calculationStartDate} vs ${data2.calculationStartDate}`;
  addLegendToMap(generateNDVILegendHtml());

async function detectarDiferencia() {
  const date1 = formatDate(document.getElementById("start-date").value);
  const date2 = formatDate(document.getElementById("end-date").value);
  const res = await fetch(`http://127.0.0.1:8080/gee-ndvi-diff?date1=${date1}&date2=${date2}`);
  const data = await res.json();

  const cloudThreshold = 20; // Umbral de cobertura de nubes en porcentaje

  if (data.range1.cloudCover > cloudThreshold || data.range2.cloudCover > cloudThreshold) {
    alert(`Advertencia: Una o ambas imágenes tienen alta cobertura de nubes (Imagen 1: ${data.range1.cloudCover.toFixed(2)}%, Imagen 2: ${data.range2.cloudCover.toFixed(2)}%). Considere seleccionar fechas alternativas para una mejor visualización.`);
  }

  limpiarMapa();
  L.tileLayer(data.tileUrl).addTo(map);
  document.getElementById("layer-label").textContent = data.name;
  addLegendToMap(generateNDVIDiffLegendHtml());
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
  
  document.getElementById("btn-stats-poly").addEventListener("click", mostrarEstadisticasDesdePoligono);
  document.getElementById("btn-limpiar").addEventListener("click", limpiarMapa);
  document.getElementById("btn-dibujar").addEventListener("click", activarDibujo);
  document.getElementById("btn-descargar").addEventListener("click", descargarGeoJSON);
  document.getElementById("btn-capturar").addEventListener("click", capturarMapa);
  document.getElementById("btn-cloudiness").addEventListener("click", calculateCloudinessInView);

  // Add event listeners for date inputs to fetch optimal date
  document.getElementById("start-date").addEventListener("change", (event) => fetchOptimalDate(event.target.id));
  document.getElementById("end-date").addEventListener("change", (event) => fetchOptimalDate(event.target.id));
  document.getElementById("ndvi-date").addEventListener("change", (event) => fetchOptimalDate(event.target.id));
  document.getElementById("cloudiness-date").addEventListener("change", (event) => fetchOptimalDate(event.target.id));
});
