# Visor de Deforestación con Imágenes Satelitales

Este proyecto permite visualizar y capturar evidencia de deforestación a partir de imágenes satelitales Sentinel-2 usando ArcGIS JavaScript API.

## Funcionalidades

- Visualización de mapa satelital
- Dibujo de parcelas (Sketch)
- Comparación de imágenes satelitales por rango de fechas (Swipe)
- Captura de pantalla (`takeScreenshot()`)
- Exportación de historial en formato `.json`
- Carga de historial previo
- Control de opacidad de capas

## Requisitos

- Node.js instalado
- Paquete `http-server` instalado globalmente

```bash
npm install -g http-server
```

## Uso en entorno local

1. Clona este repositorio:

```bash
git https://github.com/jorgedison/agri-deforest-visor.git
cd agri-deforest-visor
```

2. Inicia el servidor local sin caché:

```bash
http-server -c-1
```

3. Abre en tu navegador:

```
http://localhost:8080
```

## 🧠 Consideraciones

- El visor usa ArcGIS JS API 4.29, se requiere una [API Key de ArcGIS](https://developers.arcgis.com/) válida para cargar imágenes de Sentinel-2.
- Para evitar errores por archivos en caché durante el desarrollo, se recomienda:
  - Usar `http-server -c-1`
  - O cambiar la versión del script:  
    `<script type="module" src="main.js?v=1.0.0"></script>`

## 📁 Estructura del proyecto

```
📦 visor-deforestacion/
├── index.html           → Interfaz del visor
├── style.css            → Estilos del visor
├── main.js              → Lógica del visor y controles
├── README.md            → Este archivo
```

## 📸 Capturas y Evidencias

Cada captura genera:
- Imagen PNG (`screenshot-YYYY-MM-DDTHH-MM-SS.png`)
- Archivo `.json` con coordenadas, fechas y metadatos
