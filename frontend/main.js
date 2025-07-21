document.addEventListener('DOMContentLoaded', () => {
    const API_URL = 'http://23.23.124.226:5000'; // URL del backend restaurada

    // --- Variables Globales ---
    let layerControl = null; // Para gestionar el control de capas dinámico
    let ndviLayer1 = null;
    let ndviLayer2 = null;
    let diffLayer = null;
    let deforestationLayer = null;
    let uploadedGeojsonLayer = null;

    let saviLayer1 = null;
    let saviLayer2 = null;
    let diffSaviLayer = null;
    let deforestationSaviLayer = null;

    let nbrLayer1 = null;
    let nbrLayer2 = null;
    let diffNbrLayer = null;
    let deforestationNbrLayer = null;

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

    const compareSaviBtn = document.getElementById('btn-comparar-savi');
    const diffSaviBtn = document.getElementById('btn-detectar-savi');
    const deforestationSaviBtn = document.getElementById('btn-zonas-poly-savi');

    const compareNbrBtn = document.getElementById('btn-comparar-nbr');
    const diffNbrBtn = document.getElementById('btn-detectar-nbr');
    const deforestationNbrBtn = document.getElementById('btn-zonas-poly-nbr');
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

    const saviLegendBtn = document.getElementById('btn-savi-legend');
    const diffSaviLegendBtn = document.getElementById('btn-diff-savi-legend');
    const deforestationSaviLegendBtn = document.getElementById('btn-deforestation-savi-legend');

    const nbrLegendBtn = document.getElementById('btn-nbr-legend');
    const diffNbrLegendBtn = document.getElementById('btn-diff-nbr-legend');
    const deforestationNbrLegendBtn = document.getElementById('btn-deforestation-nbr-legend');
    const startDateInput = document.getElementById('start-date');
    const endDateInput = document.getElementById('end-date');

    const saviLegendModal = document.getElementById('modal-savi-leyenda');
    const nbrLegendModal = document.getElementById('modal-nbr-leyenda');

    const closeSaviModal = saviLegendModal ? saviLegendModal.querySelector('.close') : null;
    const closeNbrModal = nbrLegendModal ? nbrLegendModal.querySelector('.close') : null;

    const searchStartDateBtn = document.getElementById('search-start-date');
    const searchEndDateBtn = document.getElementById('search-end-date');

    const candidateImagesModal = document.getElementById('candidate-images-modal');
    const candidateImagesCloseBtn = document.querySelector('#candidate-images-modal .close');
    const candidateImagesListContentDiv = document.getElementById('candidate-images-list-content');

    // --- Listeners de Eventos ---
    legendBtn.addEventListener('click', () => legendModal.style.display = 'block');
    closeModal.addEventListener('click', () => legendModal.style.display = 'none');
    window.addEventListener('click', (e) => { if (e.target == legendModal) { legendModal.style.display = 'none'; } });

    if (closeSaviModal) {
        closeSaviModal.addEventListener('click', () => saviLegendModal.style.display = 'none');
    }
    if (saviLegendModal) {
        window.addEventListener('click', (e) => { if (e.target == saviLegendModal) { saviLegendModal.style.display = 'none'; } });
    }

    if (closeNbrModal) {
        closeNbrModal.addEventListener('click', () => nbrLegendModal.style.display = 'none');
    }
    if (nbrLegendModal) {
        window.addEventListener('click', (e) => { if (e.target == nbrLegendModal) { nbrLegendModal.style.display = 'none'; } });
    }

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

    // Listeners para SAVI
    if (saviLegendBtn) {
        saviLegendBtn.addEventListener('click', () => {
            const saviModal = document.getElementById('modal-savi-leyenda');
            if (saviModal) saviModal.style.display = 'block';
        });
    }
    if (diffSaviLegendBtn) {
        diffSaviLegendBtn.addEventListener('click', () => {
            const diffSaviLegend = document.getElementById('diff-savi-legend');
            if (diffSaviLegend) diffSaviLegend.style.display = diffSaviLegend.style.display === 'block' ? 'none' : 'block';
        });
    }
    if (deforestationSaviLegendBtn) {
        deforestationSaviLegendBtn.addEventListener('click', () => {
            const deforestationSaviLegend = document.getElementById('deforestation-savi-legend');
            if (deforestationSaviLegend) deforestationSaviLegend.style.display = deforestationSaviLegend.style.display === 'block' ? 'none' : 'block';
        });
    }

    // Listeners para NBR
    if (nbrLegendBtn) {
        nbrLegendBtn.addEventListener('click', () => {
            const nbrModal = document.getElementById('modal-nbr-leyenda');
            if (nbrModal) nbrModal.style.display = 'block';
        });
    }
    if (diffNbrLegendBtn) {
        diffNbrLegendBtn.addEventListener('click', () => {
            const diffNbrLegend = document.getElementById('diff-nbr-legend');
            if (diffNbrLegend) diffNbrLegend.style.display = diffNbrLegend.style.display === 'block' ? 'none' : 'block';
        });
    }
    if (deforestationNbrLegendBtn) {
        deforestationNbrLegendBtn.addEventListener('click', () => {
            const deforestationNbrLegend = document.getElementById('deforestation-nbr-legend');
            if (deforestationNbrLegend) deforestationNbrLegend.style.display = deforestationNbrLegend.style.display === 'block' ? 'none' : 'block';
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

    compareSaviBtn.addEventListener('click', () => handleCompareIndex('savi'));
    diffSaviBtn.addEventListener('click', () => handleDiffIndex('savi'));
    deforestationSaviBtn.addEventListener('click', () => handleDeforestationFromPolygonIndex('savi'));

    compareNbrBtn.addEventListener('click', () => handleCompareIndex('nbr'));
    diffNbrBtn.addEventListener('click', () => handleDiffIndex('nbr'));
    deforestationNbrBtn.addEventListener('click', () => handleDeforestationFromPolygonIndex('nbr'));
    
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
            if (button.id === 'btn-comparar-savi') button.innerHTML = 'Comparar SAVI';
            if (button.id === 'btn-detectar-savi') button.innerHTML = 'Diferencia SAVI';
            if (button.id === 'btn-zonas-poly-savi') button.innerHTML = 'Zonas deforestadas desde polígono (SAVI)';
            if (button.id === 'btn-comparar-nbr') button.innerHTML = 'Comparar NBR';
            if (button.id === 'btn-detectar-nbr') button.innerHTML = 'Diferencia NBR';
            if (button.id === 'btn-zonas-poly-nbr') button.innerHTML = 'Zonas deforestadas desde polígono (NBR)';
        }
    }

    function updateButtonStates() {
        const datesSelected = startDateInput.value && endDateInput.value;
        const polygonDrawn = drawnItems.getLayers().length > 0;

        compareBtn.disabled = !datesSelected;
        diffBtn.disabled = !datesSelected;
        deforestationBtn.disabled = !datesSelected || !polygonDrawn;

        compareSaviBtn.disabled = !datesSelected;
        diffSaviBtn.disabled = !datesSelected;
        deforestationSaviBtn.disabled = !datesSelected || !polygonDrawn;

        compareNbrBtn.disabled = !datesSelected;
        diffNbrBtn.disabled = !datesSelected;
        deforestationNbrBtn.disabled = !datesSelected || !polygonDrawn;
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
            deforestationLegendBtn.style.display = 'block';
            
            const summary = data.deforestationSummary;
            const message = `${summary.zoneCount} zonas de deforestación detectadas. (Detección: ${summary.deforestationDetected})`;
            showStatus(message);

        } catch (err) {
            showStatus(err.message, true);
        } finally {
            toggleButtonLoading(deforestationBtn, false);
        }
    }

    async function handleCompareIndex(indexType) {
        const dates = getDates();
        if (!dates) return;

        clearMap({ keepPolygon: true });
        showStatus(`Cargando capas ${indexType.toUpperCase()}...`);
        const button = document.getElementById(`btn-comparar-${indexType}`);
        toggleButtonLoading(button, true);

        try {
            const [res1, res2] = await Promise.all([
                fetch(`${API_URL}/gee-${indexType}-tile-url?date=${dates.date1}`),
                fetch(`${API_URL}/gee-${indexType}-tile-url?date=${dates.date2}`)
            ]);

            if (!res1.ok) throw new Error(`Error con la fecha 1: ${res1.statusText}`);
            if (!res2.ok) throw new Error(`Error con la fecha 2: ${res2.statusText}`);

            const [data1, data2] = await Promise.all([res1.json(), res2.json()]);

            if (data1.error) throw new Error(`Error en GEE (Fecha 1): ${data1.error}`);
            if (data2.error) throw new Error(`Error en GEE (Fecha 2): ${data2.error}`);

            let layer1, layer2;
            if (indexType === 'savi') {
                saviLayer1 = L.tileLayer(data1.tileUrl, { opacity: 0.8 });
                saviLayer2 = L.tileLayer(data2.tileUrl, { opacity: 0.8 });
                layer1 = saviLayer1;
                layer2 = saviLayer2;
            } else if (indexType === 'nbr') {
                nbrLayer1 = L.tileLayer(data1.tileUrl, { opacity: 0.8 });
                nbrLayer2 = L.tileLayer(data2.tileUrl, { opacity: 0.8 });
                layer1 = nbrLayer1;
                layer2 = nbrLayer2;
            } else {
                // Esto no debería pasar si los botones están bien configurados
                throw new Error("Tipo de índice desconocido.");
            }

            const baseMaps = {
                [data1.name]: layer1.addTo(map),
                [data2.name]: layer2
            };

            if (layerControl) map.removeControl(layerControl);
            layerControl = L.control.layers(baseMaps, null, { position: 'topright', collapsed: false }).addTo(map);
            
            if (indexType === 'savi') {
                saviLegendBtn.style.display = 'block';
            } else if (indexType === 'nbr') {
                nbrLegendBtn.style.display = 'block';
            } else {
                legendBtn.style.display = 'block'; // Para NDVI
            }
            showStatus(`Capas ${indexType.toUpperCase()} cargadas. Seleccione una capa para visualizar.`);

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
                    toggleButtonLoading(button, false);
                    return;
                }
            }

        } catch (err) {
            showStatus(err.message, true);
        } finally {
            toggleButtonLoading(button, false);
        }
    }

    async function handleDiffIndex(indexType) {
        const dates = getDates();
        if (!dates) return;

        clearMap({ keepPolygon: true });
        showStatus(`Calculando diferencia de ${indexType.toUpperCase()}...`);
        const button = document.getElementById(`btn-detectar-${indexType}`);
        toggleButtonLoading(button, true);

        try {
            const response = await fetch(`${API_URL}/gee-${indexType}-diff?date1=${dates.date1}&date2=${dates.date2}`);
            if (!response.ok) throw new Error(`Error del servidor: ${response.statusText}`);
            const data = await response.json();
            if (data.error) throw new Error(data.error);

            let diffLayerToUse;
            if (indexType === 'savi') {
                diffSaviLayer = L.tileLayer(data.tileUrl, { opacity: 0.7 }).addTo(map);
                diffLayerToUse = diffSaviLayer;
            } else if (indexType === 'nbr') {
                diffNbrLayer = L.tileLayer(data.tileUrl, { opacity: 0.7 }).addTo(map);
                diffLayerToUse = diffNbrLayer;
            } else {
                throw new Error("Tipo de índice desconocido.");
            }

            if (indexType === 'savi') {
                document.getElementById('diff-savi-legend').style.display = 'block';
                diffSaviLegendBtn.style.display = 'block';
            } else if (indexType === 'nbr') {
                document.getElementById('diff-nbr-legend').style.display = 'block';
                diffNbrLegendBtn.style.display = 'block';
            } else {
                document.getElementById('diff-legend').style.display = 'block'; // Para NDVI
                diffLegendBtn.style.display = 'block';
            }
            showStatus(`Capa de diferencia ${indexType.toUpperCase()} cargada.`);

        } catch (err) {
            console.error(`Error en handleDiffIndex (${indexType}):`, err);
            showStatus(err.message, true);
        } finally {
            toggleButtonLoading(button, false);
        }
    }

    async function handleDeforestationFromPolygonIndex(indexType) {
        const dates = getDates();
        const geometry = getDrawnGeometry();
        if (!dates || !geometry) return;

        showStatus(`Analizando zonas de deforestación con ${indexType.toUpperCase()}...`);
        const button = document.getElementById(`btn-zonas-poly-${indexType}`);
        toggleButtonLoading(button, true);

        try {
            const response = await fetch(`${API_URL}/gee-deforestation-zones-from-geojson-${indexType}`, {
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

            let deforestationLayerToUse;
            if (indexType === 'savi') {
                if (deforestationSaviLayer) map.removeLayer(deforestationSaviLayer);
                deforestationSaviLayer = L.geoJSON(data.features, {
                    style: { color: '#ff0000', weight: 2, fillOpacity: 0.5 }
                }).addTo(map);
                deforestationLayerToUse = deforestationSaviLayer;
            } else if (indexType === 'nbr') {
                if (deforestationNbrLayer) map.removeLayer(deforestationNbrLayer);
                deforestationNbrLayer = L.geoJSON(data.features, {
                    style: { color: '#ff0000', weight: 2, fillOpacity: 0.5 }
                }).addTo(map);
                deforestationLayerToUse = deforestationNbrLayer;
            } else {
                throw new Error("Tipo de índice desconocido.");
            }

            if (indexType === 'savi') {
                deforestationSaviLegendBtn.style.display = 'block';
            } else if (indexType === 'nbr') {
                deforestationNbrLegendBtn.style.display = 'block';
            } else {
                deforestationLegendBtn.style.display = 'block'; // Para NDVI
            }
            
            const summary = data.deforestationSummary;
            const message = `${summary.zoneCount} zonas de deforestación detectadas con ${indexType.toUpperCase()}. (Detección: ${summary.deforestationDetected})`;
            showStatus(message);

        } catch (err) {
            showStatus(err.message, true);
        } finally {
            toggleButtonLoading(button, false);
        }
    }

    function clearMap(options = {}) {
        if (ndviLayer1) map.removeLayer(ndviLayer1);
        if (ndviLayer2) map.removeLayer(ndviLayer2);
        if (diffLayer) {
            map.removeLayer(diffLayer);
            document.getElementById('diff-legend').style.display = 'none';
            diffLegendBtn.style.display = 'none';
        }
        if (deforestationLayer) {
            map.removeLayer(deforestationLayer);
            document.getElementById('deforestation-legend').style.display = 'none';
            deforestationLegendBtn.style.display = 'none';
        }

        if (saviLayer1) map.removeLayer(saviLayer1);
        if (saviLayer2) map.removeLayer(saviLayer2);
        if (diffSaviLayer) {
            map.removeLayer(diffSaviLayer);
            document.getElementById('diff-savi-legend').style.display = 'none';
            if (diffSaviLegendBtn) diffSaviLegendBtn.style.display = 'none';
        }
        if (deforestationSaviLayer) {
            map.removeLayer(deforestationSaviLayer);
            document.getElementById('deforestation-savi-legend').style.display = 'none';
            if (deforestationSaviLegendBtn) deforestationSaviLegendBtn.style.display = 'none';
        }

        if (nbrLayer1) map.removeLayer(nbrLayer1);
        if (nbrLayer2) map.removeLayer(nbrLayer2);
        if (diffNbrLayer) {
            map.removeLayer(diffNbrLayer);
            document.getElementById('diff-nbr-legend').style.display = 'none';
            if (diffNbrLegendBtn) diffNbrLegendBtn.style.display = 'none';
        }
        if (deforestationNbrLayer) {
            map.removeLayer(deforestationNbrLayer);
            document.getElementById('deforestation-nbr-legend').style.display = 'none';
            if (deforestationNbrLegendBtn) deforestationNbrLegendBtn.style.display = 'none';
        }
        
        if (layerControl) map.removeControl(layerControl);
        
        legendBtn.style.display = 'none';
        document.getElementById('modal-leyenda').style.display = 'none';

        // Ocultar todas las leyendas específicas
        const allLegends = document.querySelectorAll('.legend-button');
        allLegends.forEach(btn => btn.style.display = 'none');
        const allLegendDivs = document.querySelectorAll('.leaflet-control.leaflet-bar');
        allLegendDivs.forEach(div => div.style.display = 'none');

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
        if (isError) {
            statusMessage.classList.add('error');
        } else {
            statusMessage.classList.remove('error');
        }

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
