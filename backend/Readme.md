# 🛰️ Backend - Visor de Deforestación con NDVI

Este backend expone una API REST en Flask que se conecta a **Google Earth Engine (GEE)** para obtener datos de vegetación (NDVI) y detectar deforestación mediante comparación temporal.

---

## 📁 Estructura del Proyecto

```
backend/
├── app.py              # Código principal de la API en Flask
├── requirements.txt    # Dependencias del proyecto
└── credentials.json    # (opcional) Credenciales del servicio GEE para producción
```

---

## 🚀 Requisitos

- Python 3.8 o superior
- Acceso a Google Earth Engine
- Autenticación configurada

---

## 🔧 Instalación

```bash
# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

---

## 🔐 Autenticación con Google Earth Engine

### Opción 1: Interactivo (modo desarrollo)

```bash
earthengine authenticate
```

Esto abrirá una URL en el navegador para autorizar la cuenta. Se generará automáticamente un archivo de credenciales en `~/.config/earthengine/credentials`.

### Opción 2: Producción (con cuenta de servicio)

1. Crea una cuenta de servicio en Google Cloud con acceso a GEE.
2. Descarga el archivo `credentials.json`.
3. Exporta la ruta como variable de entorno:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="backend/credentials.json"
```

---

## ▶️ Ejecución

```bash
python app.py
```

La API quedará disponible en `http://localhost:8080`.

---

## 🌐 Endpoints disponibles

### `GET /gee-tile-url?date=YYYYMMDD`

Devuelve la URL de una capa de tiles NDVI para una fecha específica.

### `GET /gee-ndvi-diff?date1=YYYYMMDD&date2=YYYYMMDD`

Devuelve la visualización de la diferencia NDVI entre dos fechas.

### `GET /gee-deforestation-zones?date1=YYYYMMDD&date2=YYYYMMDD&threshold=0.2`

Retorna un GeoJSON con zonas donde la reducción de NDVI indica posible deforestación.

---

## 🧪 Ejemplo de llamada

```http
GET http://localhost:8080/gee-ndvi-diff?date1=20240101&date2=20240301
```


