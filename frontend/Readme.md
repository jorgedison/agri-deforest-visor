# 🖥️ Frontend - Visor de Deforestación

Este frontend es una aplicación web que permite visualizar el índice NDVI y detectar zonas de deforestación utilizando datos servidos por un backend conectado a Google Earth Engine. Utiliza **Leaflet.js** para el mapa y **Leaflet Draw** para herramientas interactivas.

---

## 📁 Estructura del Proyecto

```
frontend/
├── index.html       # Página principal con controles y mapa
├── main.js          # Lógica del visor y llamadas al backend
├── style.css        # Estilos personalizados
└── favicon.ico      # Icono del navegador
```

---

## 🚀 Requisitos

- Un servidor web simple como `http-server`, `nginx`, `python3 -m http.server`, etc.
- Un archivo `env.js` (opcional) para configurar dinámicamente el backend.

---

## ▶️ Ejecución local

```bash
# Desde la carpeta frontend
http-server -p 8081
```

Accede a `http://localhost:8081` en tu navegador.

---

## 🌍 Dependencias vía CDN

- [Leaflet.js](https://leafletjs.com/)
- [Leaflet Draw](https://github.com/Leaflet/Leaflet.draw)
- [html2canvas](https://html2canvas.hertzen.com/)
- [leaflet-image](https://github.com/mapbox/leaflet-image)
- [leaflet-simple-map-screenshoter](https://github.com/Igor-Vladyka/leaflet-simple-map-screenshoter)

Estas ya están incluidas mediante `<script src="...">` en el `index.html`.

---

## 🧠 Funcionalidades principales

- Visualización del mapa base satelital o de calles.
- Consulta NDVI de una fecha específica.
- Comparación NDVI entre dos fechas.
- Detección de zonas de deforestación (GeoJSON).
- Herramientas de dibujo, limpieza y descarga.

---

## 🔧 Configuración del backend (opcional)

Puedes agregar un archivo `env.js` para definir la URL del backend en tiempo de ejecución:

```js
// env.js
window.env = {
  API_URL: "http://localhost:8081"
};
```

Y en `main.js`, puedes usarlo así:

```js
fetch(`${window.env.API_URL}/gee-tile-url?date=20240101`)
```

---

## 🧪 Sugerencias para producción

- Servir con NGINX o como contenedor Docker.
- Usar HTTPS si se conecta a un backend en la nube.
- Minificar CSS/JS si se necesita performance.