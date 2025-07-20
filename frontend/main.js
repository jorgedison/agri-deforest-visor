document.addEventListener('DOMContentLoaded', () => {
    const API_URL = 'http://23.23.124.226:5000'; // URL del backend restaurada

    // --- Variables Globales ---
    let layerControl = null; // Para gestionar el control de capas dinámico
    let ndviLayer1 = null;
    let ndviLayer2 = null;
    let diffLayer = null;
    let deforestationLayer = null;
    let uploadedGeojsonLayer = null;

    // --- Inicialización del Mapa ---
    const map = L.map('map', { zoomControl: false }).setView([-9.19, -75.02], 6); // Centrado en Perú
    L.control.zoom({ position: 'topright' }).addTo(map);

    const satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles © Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
    });
    satelliteLayer.addTo(map); // Mapa satelital por defecto, sin selector

    let drawnItems = new L.FeatureGroup().addTo(map);

    // --- Controles de Dibujo ---
    const drawControl = new L.Control.Draw({
        position: 'topright',
        edit: { featureGroup: drawnItems },
        draw: { polygon: true, polyline: false, rectangle: false, circle: false, marker: false }
    });
    map.addControl(drawControl);

    map.on(L.Draw.Event.CREATED, (e) => {
        drawnItems.clearLayers();
        drawnItems.addLayer(e.layer);
        updateButtonStates(); // Habilitar botones que dependen del polígono
    });

    // --- Elementos del DOM ---
    const compareBtn = document.getElementById('btn-comparar-ndvi');
    const diffBtn = document.getElementById('btn-detectar');
    const deforestationBtn = document.getElementById('btn-zonas-poly');
    const thresholdInput = document.getElementById('threshold');
    const cleanBtn = document.getElementById('btn-limpiar');
    const drawBtn = document.getElementById('btn-dibujar');
    const downloadBtn = document.getElementById('btn-descargar');
    const captureBtn = document.getElementById('btn-capturar');
    const statusMessage = document.getElementById('status-message');
    const legendBtn = document.getElementById('btn-leyenda');
    const legendModal = document.getElementById('modal-leyenda');
    const closeModal = document.querySelector('.modal .close');
    const diffLegendBtn = document.getElementById('btn-diff-legend');
    const deforestationLegendBtn = document.getElementById('btn-deforestation-legend');
    const startDateInput = document.getElementById('start-date');
    const endDateInput = document.getElementById('end-date');

    const searchStartDateBtn = document.getElementById('search-start-date');
    const searchEndDateBtn = document.getElementById('search-end-date');

    const candidateImagesModal = document.getElementById('candidate-images-modal');
    const candidateImagesCloseBtn = document.querySelector('#candidate-images-modal .close');
    const candidateImagesListContentDiv = document.getElementById('candidate-images-list-content');

    // --- Listeners de Eventos ---
    legendBtn.addEventListener('click', () => legendModal.style.display = 'block');
    closeModal.addEventListener('click', () => legendModal.style.display = 'none');
    window.addEventListener('click', (e) => { if (e.target == legendModal) { legendModal.style.display = 'none'; } });

    // Listener para el nuevo botón de leyenda de Diferencia NDVI
    if (diffLegendBtn) {
        diffLegendBtn.addEventListener('click', () => {
            const diffLegend = document.getElementById('diff-legend');
            if (diffLegend.style.display === 'block') {
                diffLegend.style.display = 'none';
            } else {
                diffLegend.style.display = 'block';
            }
        });
    }

    // Listener para el nuevo botón de leyenda de Zonas Deforestadas
    if (deforestationLegendBtn) {
        deforestationLegendBtn.addEventListener('click', () => {
            const deforestationLegend = document.getElementById('deforestation-legend');
            if (deforestationLegend.style.display === 'block') {
                deforestationLegend.style.display = 'none';
            } else {
                deforestationLegend.style.display = 'block';
            }
        });
    }

    if (candidateImagesCloseBtn) {
        candidateImagesCloseBtn.addEventListener('click', () => candidateImagesModal.style.display = 'none');
    }
    if (candidateImagesModal) {
        window.addEventListener('click', (e) => { if (e.target == candidateImagesModal) { candidateImagesModal.style.display = 'none'; } });
    }

    searchStartDateBtn.addEventListener('click', () => findOptimalDate('start-date'));
    searchEndDateBtn.addEventListener('click', () => findOptimalDate('end-date'));

    compareBtn.addEventListener('click', handleCompareNdvi);
    diffBtn.addEventListener('click', handleNdviff);
    deforestationBtn.addEventListener('click', handleDeforestationFromPolygon);
    
    cleanBtn.addEventListener('click', () => clearMap({ all: true }));
    drawBtn.addEventListener('click', () => new L.Draw.Polygon(map, drawControl.options.draw.polygon).enable());
    downloadBtn.addEventListener('click', downloadGeoJSON);
    captureBtn.addEventListener('click', captureMap);

    startDateInput.addEventListener('change', updateButtonStates);
    endDateInput.addEventListener('change', updateButtonStates);

    // --- Lógica de la Aplicación ---

    function toggleButtonLoading(button, isLoading) {
        if (isLoading) {
            button.disabled = true;
            button.innerHTML = '<span class="spinner"></span>Cargando...';
        } else {
            button.disabled = false;
            // Restaurar texto original
            if (button.id === 'btn-comparar-ndvi') button.innerHTML = 'Comparar NDVI';
            if (button.id === 'btn-detectar') button.innerHTML = 'Diferencia NDVI';
            if (button.id === 'btn-zonas-poly') button.innerHTML = 'Zonas deforestadas desde polígono';
        }
    }

    function updateButtonStates() {
        const datesSelected = startDateInput.value && endDateInput.value;
        const polygonDrawn = drawnItems.getLayers().length > 0;

        compareBtn.disabled = !datesSelected;
        diffBtn.disabled = !datesSelected;
        deforestationBtn.disabled = !datesSelected || !polygonDrawn;
        downloadBtn.disabled = !polygonDrawn;
    }

    async function findOptimalDate(dateFieldId) {
        const dateInput = document.getElementById(dateFieldId);
        const dateValue = dateInput.value;
        if (!dateValue) {
            showStatus('Por favor, seleccione una fecha primero.', true);
            return;
        }

        let geometry = null;
        let statusMessageText = `Buscando fecha óptima cerca de ${dateValue}...`;

        if (drawnItems.getLayers().length > 0) {
            geometry = drawnItems.toGeoJSON().features[0].geometry;
        } else {
            statusMessageText = `Buscando fecha óptima globalmente cerca de ${dateValue} (no se dibujó un polígono)...`;
        }

        showStatus(statusMessageText);

        try {
            const response = await fetch(`${API_URL}/find-best-image-date`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    targetDate: dateValue, // Enviar solo la fecha objetivo
                    geometry: geometry
                })
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || `Error del servidor: ${response.statusText}`);
            }

            const data = await response.json();
            const cloudCoverThreshold = 20.0;

            if (data.bestDate) {
                if (data.cloudCover > cloudCoverThreshold) {
                    const confirmation = confirm(
                        `Atención: La imagen más clara encontrada tiene un ${typeof data.cloudCover === 'number' ? data.cloudCover.toFixed(2) : 'N/A'}% de nubes. ` +
                        `La calidad del análisis puede ser media. \n\n` +
                        `¿Deseas usar esta fecha (${data.bestDate}) de todas formas?`
                    );

                    if (confirmation) {
                        dateInput.value = data.bestDate;
                        showStatus(`Fecha actualizada a ${data.bestDate}. (Nubosidad: ${data.cloudCover.toFixed(2)}%).`);
                    } else {
                        showStatus('Búsqueda de fecha óptima cancelada por el usuario.');
                    }
                } else {
                    dateInput.value = data.bestDate;
                    showStatus(`Fecha actualizada a ${data.bestDate} (Nubosidad: ${data.cloudCover.toFixed(2)}%).`);
                }
            } else {
                showStatus(data.message || 'No se encontró ninguna fecha óptima.');
            }

        } catch (err) {
            showStatus(err.message, true);
        } finally {
            updateButtonStates();
        }
    }

    function getDates() {
        const date1 = startDateInput.value;
        const date2 = endDateInput.value;
        if (!date1 || !date2) {
            showStatus('Por favor, seleccione ambas fechas.', true);
            return null;
        }
        return { date1, date2 };
    }

    function getDrawnGeometry() {
        if (drawnItems.getLayers().length === 0) {
            showStatus('Por favor, dibuje un polígono en el mapa primero.', true);
            return null;
        }
        return drawnItems.toGeoJSON().features[0].geometry;
    }

    //const CLOUD_COVER_ALERT_THRESHOLD = 0.1; // Umbral de nubosidad para la alerta (temporalmente bajo para pruebas)
    const CLOUD_COVER_ALERT_THRESHOLD = 20; // Umbral de nubosidad para la alerta

    async function handleCompareNdvi() {
        const dates = getDates();
        if (!dates) return;

        clearMap({ keepPolygon: true });
        showStatus('Cargando capas NDVI...');
        toggleButtonLoading(compareBtn, true);

        try {
            const [res1, res2] = await Promise.all([
                fetch(`${API_URL}/gee-tile-url?date=${dates.date1}`),
                fetch(`${API_URL}/gee-tile-url?date=${dates.date2}`)
            ]);

            if (!res1.ok) throw new Error(`Error con la fecha 1: ${res1.statusText}`);
            if (!res2.ok) throw new Error(`Error con la fecha 2: ${res2.statusText}`);

            const [data1, data2] = await Promise.all([res1.json(), res2.json()]);

            if (data1.error) throw new Error(`Error en GEE (Fecha 1): ${data1.error}`);
            if (data2.error) throw new Error(`Error en GEE (Fecha 2): ${data2.error}`);

            ndviLayer1 = L.tileLayer(data1.tileUrl, { opacity: 0.8 });
            ndviLayer2 = L.tileLayer(data2.tileUrl, { opacity: 0.8 });

            const baseMaps = {
                [data1.name]: ndviLayer1.addTo(map),
                [data2.name]: ndviLayer2
            };

            if (layerControl) map.removeControl(layerControl);
            layerControl = L.control.layers(baseMaps, null, { position: 'topright', collapsed: false }).addTo(map);
            
            legendBtn.style.display = 'block'; // Mostrar el botón de leyenda principal
            showStatus('Capas NDVI cargadas. Seleccione una capa para visualizar.');

            // Verificar nubosidad y mostrar alerta si es necesario
            let cloudAlertMessage = '';
            if (data1.cloudCover > CLOUD_COVER_ALERT_THRESHOLD) {
                cloudAlertMessage += `La imagen para la fecha ${dates.date1} tiene ${data1.cloudCover.toFixed(2)}% de nubes. `; 
            }
            if (data2.cloudCover > CLOUD_COVER_ALERT_THRESHOLD) {
                cloudAlertMessage += `La imagen para la fecha ${dates.date2} tiene ${data2.cloudCover.toFixed(2)}% de nubes. `; 
            }

            if (cloudAlertMessage) {
                const userConfirmed = confirm(
                    `${cloudAlertMessage}La calidad del análisis puede verse afectada. \n\n` +
                    `¿Desea continuar con estas fechas o prefiere buscar una fecha distinta con menor nubosidad?`
                );
                if (!userConfirmed) {
                    showStatus('Operación cancelada por el usuario. Por favor, seleccione fechas con menor nubosidad.', true);
                    toggleButtonLoading(compareBtn, false);
                    return; // Detener la ejecución si el usuario cancela
                }
            }

        } catch (err) {
            showStatus(err.message, true);
        } finally {
            toggleButtonLoading(compareBtn, false);
        }
    }

    async function handleNdviff() {
        const dates = getDates();
        if (!dates) return;

        clearMap({ keepPolygon: true });
        showStatus('Calculando diferencia de NDVI...');
        toggleButtonLoading(diffBtn, true);

        try {
            const response = await fetch(`${API_URL}/gee-ndvi-diff?date1=${dates.date1}&date2=${dates.date2}`);
            if (!response.ok) throw new Error(`Error del servidor: ${response.statusText}`);
            const data = await response.json();
            if (data.error) throw new Error(data.error);

            diffLayer = L.tileLayer(data.tileUrl, { opacity: 0.7 }).addTo(map);
            console.log("Mostrando la leyenda de diferencia NDVI");
            document.getElementById('diff-legend').style.display = 'block';
            diffLegendBtn.style.display = 'block'; // Mostrar el botón de leyenda de diferencia
            showStatus('Capa de diferencia NDVI cargada.');

        } catch (err) {
            console.error("Error en handleNdviff:", err);
            showStatus(err.message, true);
        } finally {
            toggleButtonLoading(diffBtn, false);
        }
    }

    async function handleDeforestationFromPolygon() {
        const dates = getDates();
        const geometry = getDrawnGeometry();
        if (!dates || !geometry) return;

        showStatus('Analizando zonas de deforestación...');
        toggleButtonLoading(deforestationBtn, true);

        try {
            const response = await fetch(`${API_URL}/gee-deforestation-zones-from-geojson`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    date1: dates.date1,
                    date2: dates.date2,
                    geometry: geometry,
                    threshold: parseFloat(thresholdInput.value)
                })
            });

            if (!response.ok) throw new Error(`Error del servidor: ${response.statusText}`);
            const data = await response.json();
            if (data.error) throw new Error(data.error);

            if (deforestationLayer) {
                map.removeLayer(deforestationLayer);
            }

            deforestationLayer = L.geoJSON(data.features, {
                style: { color: '#ff0000', weight: 2, fillOpacity: 0.5 }
            }).addTo(map);
            deforestationLegendBtn.style.display = 'block'; // Mostrar el botón de leyenda de deforestación
            
            const summary = data.deforestationSummary;
            const message = `${summary.zoneCount} zonas de deforestación detectadas. (Detección: ${summary.deforestationDetected})`;
            showStatus(message);

        } catch (err) {
            showStatus(err.message, true);
        } finally {
            toggleButtonLoading(deforestationBtn, false);
        }
    }

    function clearMap(options = {}) {
        if (ndviLayer1) map.removeLayer(ndviLayer1);
        if (ndviLayer2) map.removeLayer(ndviLayer2);
        if (diffLayer) {
            map.removeLayer(diffLayer);
            document.getElementById('diff-legend').style.display = 'none';
            diffLegendBtn.style.display = 'none'; // Ocultar el botón de leyenda de diferencia
        }
        if (deforestationLayer) {
            map.removeLayer(deforestationLayer);
            document.getElementById('deforestation-legend').style.display = 'none'; // Ocultar la leyenda de deforestación
            deforestationLegendBtn.style.display = 'none'; // Ocultar el botón de leyenda de deforestación
        }
        
        if (layerControl) map.removeControl(layerControl);
        
        legendBtn.style.display = 'none'; // Ocultar el botón de leyenda principal
        document.getElementById('modal-leyenda').style.display = 'none'; // Asegurarse de que el modal de leyenda esté oculto

        if (options.all) {
            drawnItems.clearLayers();
        }
        
        showStatus('Mapa limpiado.');
        updateButtonStates();
    }

    function downloadGeoJSON() {
        if (drawnItems.getLayers().length === 0) {
            showStatus('No hay ningún área dibujada para descargar.', true);
            return;
        }
        const data = drawnItems.toGeoJSON();
        const blob = new Blob([JSON.stringify(data)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'area_seleccionada.geojson';
        a.click();
        URL.revokeObjectURL(url);
    }

    function captureMap() {
        showStatus('Capturando imagen del mapa...');
        L.simpleMapScreenshoter().takeScreen('image').then(blob => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'captura_mapa.png';
            a.click();
            URL.revokeObjectURL(url);
        }).catch(e => {
            showStatus(`No se pudo capturar el mapa: ${e.message}`, true);
        });
    }

    function showStatus(message, isError = false) {
        const statusTextSpan = document.getElementById('status-text');
        const candidateImagesModal = document.getElementById('candidate-images-modal');
        const candidateImagesListContentDiv = document.getElementById('candidate-images-list-content');

        statusTextSpan.textContent = message;
        statusMessage.style.display = 'block';
        statusMessage.style.backgroundColor = isError ? '#f8d7da' : '#d4edda';
        statusMessage.style.color = isError ? '#721c24' : '#155724';

        if (candidateImagesListContentDiv) {
            candidateImagesListContentDiv.innerHTML = '';
        }
        if (candidateImagesModal) {
            candidateImagesModal.style.display = 'none';
        }
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
                updateButtonStates();
            } catch (err) {
                alert("El archivo no es un GeoJSON válido.");
            }
        };
        reader.readAsText(file);
    });

    // Inicializar estados de los botones al cargar
    updateButtonStates();
});
