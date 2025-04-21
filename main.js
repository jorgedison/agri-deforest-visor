import esriConfig from "https://js.arcgis.com/4.29/@arcgis/core/config.js";
import Map from "https://js.arcgis.com/4.29/@arcgis/core/Map.js";
import MapView from "https://js.arcgis.com/4.29/@arcgis/core/views/MapView.js";
import Sketch from "https://js.arcgis.com/4.29/@arcgis/core/widgets/Sketch.js";
import GraphicsLayer from "https://js.arcgis.com/4.29/@arcgis/core/layers/GraphicsLayer.js";
import ImageryLayer from "https://js.arcgis.com/4.29/@arcgis/core/layers/ImageryLayer.js";
import MosaicRule from "https://js.arcgis.com/4.29/@arcgis/core/layers/support/MosaicRule.js";
import Graphic from "https://js.arcgis.com/4.29/@arcgis/core/Graphic.js";
import Swipe from "https://js.arcgis.com/4.29/@arcgis/core/widgets/Swipe.js";
import Polygon from "https://js.arcgis.com/4.29/@arcgis/core/geometry/Polygon.js";

esriConfig.apiKey = "xxxxxxxxxxxxxxxxxxxxxx";

const graphicsLayer = new GraphicsLayer();

const map = new Map({
  basemap: "satellite",
  layers: [graphicsLayer]
});

const view = new MapView({
  container: "viewDiv",
  map: map,
  center: [-73.5, -3.5],
  zoom: 6
});

const sketch = new Sketch({
  layer: graphicsLayer,
  view: view,
  availableCreateTools: ["polygon"],
  creationMode: "single"
});
view.ui.add(sketch, "top-right");

let layerBefore = null;
let layerAfter = null;
let currentArea = null;

function renderHistorial(historial) {
  const ul = document.getElementById("historialList");
  if (!ul) return;
  ul.innerHTML = "";
  historial.forEach((item, index) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <strong>Captura ${index + 1}</strong><br>
      Fecha: ${new Date(item.fecha).toLocaleString()}<br>
      Rango: ${item.dateRange.start || '—'} a ${item.dateRange.end || '—'}<br>
      Imagen: <code>${item.imagen}</code><br>
      <button onclick="window.open('${item.url_imagen}', '_blank')">Ver imagen</button>
    `;
    ul.appendChild(li);
  });
}

document.getElementById("opacity").addEventListener("input", () => {
  const opacity = parseFloat(document.getElementById("opacity").value);
  if (layerBefore) layerBefore.opacity = opacity;
  if (layerAfter) layerAfter.opacity = opacity;
});

document.getElementById("load-images").addEventListener("click", () => {
  if (window._swipeWidget) {
    view.ui.remove(window._swipeWidget);
    window._swipeWidget.destroy();
    window._swipeWidget = null;
  }

  const startDate = document.getElementById("start-date").value;
  const endDate = document.getElementById("end-date").value;

  if (!startDate || !endDate) {
    alert("Selecciona ambas fechas.");
    return;
  }

  if (layerBefore) map.remove(layerBefore);
  if (layerAfter) map.remove(layerAfter);

  const mosaicBefore = new MosaicRule({
    where: `acquisitiondate <= DATE '${startDate}'`
  });

  const mosaicAfter = new MosaicRule({
    where: `acquisitiondate >= DATE '${endDate}'`
  });

  layerBefore = new ImageryLayer({
    url: "https://sentinel2.arcgis.com/arcgis/rest/services/Sentinel2/ImageServer",
    mosaicRule: mosaicBefore,
    opacity: parseFloat(document.getElementById("opacity").value)
  });

  layerAfter = new ImageryLayer({
    url: "https://sentinel2.arcgis.com/arcgis/rest/services/Sentinel2/ImageServer",
    mosaicRule: mosaicAfter,
    opacity: parseFloat(document.getElementById("opacity").value)
  });

  map.addMany([layerBefore, layerAfter]);

  const swipe = new Swipe({
    view: view,
    leadingLayers: [layerBefore],
    trailingLayers: [layerAfter],
    position: 50
  });

  view.ui.add(swipe);
  window._swipeWidget = swipe;
});

document.getElementById("clear-swipe").addEventListener("click", () => {
  if (window._swipeWidget) {
    view.ui.remove(window._swipeWidget);
    window._swipeWidget.destroy();
    window._swipeWidget = null;
  }
});

document.getElementById("capture").addEventListener("click", async () => {
  const screenshot = await view.takeScreenshot();
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const imageName = `screenshot-${timestamp}.png`;

  const link = document.createElement("a");
  link.href = screenshot.dataUrl;
  link.download = imageName;
  link.click();

  const polygonGraphic = graphicsLayer.graphics.at(0);
  const geometry = polygonGraphic ? {
    ...polygonGraphic.geometry.toJSON(),
    type: "polygon"
  } : null;

  if (!geometry) {
    alert("Primero dibuja o carga una parcela.");
    return;
  }

  const newEntry = {
    fecha: new Date().toISOString(),
    imagen: imageName,
    dateRange: {
      start: document.getElementById("start-date").value,
      end: document.getElementById("end-date").value
    },
    url_imagen: imageName
  };

  let historialData;

  if (currentArea) {
    historialData = {
      ...currentArea,
      historial: [...currentArea.historial, newEntry]
    };
  } else {
    const x = geometry.rings[0][0][0].toFixed(4);
    const y = geometry.rings[0][0][1].toFixed(4);
    const areaId = `area-${x}_${y}`;

    historialData = {
      id: areaId,
      geometry: geometry,
      historial: [newEntry]
    };
  }

  currentArea = historialData;
  renderHistorial(historialData.historial);

  const blob = new Blob([JSON.stringify(historialData, null, 2)], { type: "application/json" });
  const jsonLink = document.createElement("a");
  jsonLink.href = URL.createObjectURL(blob);
  jsonLink.download = `${historialData.id}.json`;
  jsonLink.click();
});

document.getElementById("load-history").addEventListener("change", function (event) {
  const file = event.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = function (e) {
    try {
      const data = JSON.parse(e.target.result);
      if (!data.geometry || !data.historial) {
        alert("El archivo no tiene el formato correcto.");
        return;
      }

      const geometry = new Polygon({
        ...data.geometry,
        type: "polygon"
      });

      graphicsLayer.removeAll();
      currentArea = data;

      const polygonGraphic = new Graphic({
        geometry: geometry,
        symbol: {
          type: "simple-fill",
          color: [0, 255, 0, 0.2],
          outline: {
            color: [0, 255, 0],
            width: 2
          }
        }
      });

      graphicsLayer.add(polygonGraphic);
      view.goTo(polygonGraphic.geometry.extent.expand(1.5));
      renderHistorial(data.historial);
    } catch (err) {
      alert("Error al leer el archivo.");
      console.error(err);
    }
  };

  reader.readAsText(file);
});