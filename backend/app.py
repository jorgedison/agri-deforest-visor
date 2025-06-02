import ee
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

# Inicializa Earth Engine
ee.Initialize(project='ornate-shine-310021')

app = Flask(__name__)
CORS(app)

# Función de utilidad para convertir bandas Landsat a reflectancia
def reflectance(image, band):
    return image.select(band).multiply(0.0000275).add(-0.2)

# Construir un mosaico NDVI promedio para un año

# Rango NDVI y su interpretación:
# < 0.1       → suelo expuesto (rojo oscuro)
# 0.1 - 0.2   → pasto / zonas degradadas (naranja)
# 0.2 - 0.6   → cultivos / vegetación baja (amarillo-verde)
# 0.6 - 0.8   → vegetación densa (verde)
# > 0.8       → bosque denso / selva (verde oscuro)

def buscar_ndvi_anual(fecha):
    anio = fecha[:4]
    start = f"{anio}-01-01"
    end = f"{anio}-12-31"

    coleccion = (
        ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
        .filterDate(start, end)
        .filterMetadata('CLOUD_COVER', 'less_than', 50)
    )

    def calcular_ndvi(img):
        # Aplicar máscara de nubes (bit 3 = cloud, bit 4 = cloud shadow)
        pixel_qa = img.select('QA_PIXEL')
        clear_mask = pixel_qa.bitwiseAnd(1 << 3).eq(0).And(
                      pixel_qa.bitwiseAnd(1 << 4).eq(0))

        nir = reflectance(img, 'SR_B5')
        red = reflectance(img, 'SR_B4')
        ndvi = nir.subtract(red).divide(nir.add(red)).rename('NDVI')
        ndvi_clamped = ndvi.clamp(-1, 1)

        return ndvi_clamped.updateMask(clear_mask)

    coleccion_ndvi = coleccion.map(calcular_ndvi)
    ndvi_anual = coleccion_ndvi.mean().rename('NDVI')
    ndvi_anual = ndvi_anual.clamp(-0.1, 0.9)
    return ndvi_anual

# Construir un mosaico SAVI promedio para un año
def buscar_savi_anual(fecha, L=0.5):
    anio = fecha[:4]
    start = f"{anio}-01-01"
    end = f"{anio}-12-31"

    coleccion = (
        ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
        .filterDate(start, end)
        .filterMetadata('CLOUD_COVER', 'less_than', 50)
    )

    def calcular_savi(img):
        pixel_qa = img.select('QA_PIXEL')
        clear_mask = pixel_qa.bitwiseAnd(1 << 3).eq(0).And(
                      pixel_qa.bitwiseAnd(1 << 4).eq(0))

        nir = reflectance(img, 'SR_B5')
        red = reflectance(img, 'SR_B4')
        savi = nir.subtract(red).multiply(1 + L).divide(nir.add(red).add(L)).rename('SAVI')
        savi_clamped = savi.clamp(-1, 1)

        return savi_clamped.updateMask(clear_mask)

    coleccion_savi = coleccion.map(calcular_savi)
    savi_anual = coleccion_savi.mean().rename('SAVI')
    savi_anual = savi_anual.clamp(-0.1, 0.9)
    return savi_anual



@app.route('/gee-tile-url')
def get_tile_url():
    date = request.args.get('date')
    if not date:
        return jsonify({'error': 'Fecha no proporcionada. Use formato YYYYMMDD.'}), 400

    try:
        datetime.datetime.strptime(date, "%Y%m%d")
    except ValueError:
        return jsonify({'error': 'Formato de fecha inválido. Use YYYYMMDD.'}), 400

    try:
        # NDVI y visualización
        ndvi = buscar_ndvi_anual(date)

        # Parámetros opcionales desde el frontend
        min_val = float(request.args.get('min', -0.2))
        max_val = float(request.args.get('max', 0.8))
        palette = request.args.getlist('palette') or ['#762a83', '#af8dc3', '#e7d4e8', '#d9f0d3', '#7fbf7b', '#1b7837']

        vis_params = {
            'min': min_val,
            'max': max_val,
            'palette': palette
        }

        visual = ndvi.visualize(**vis_params)
        map_id_dict = ee.data.getMapId({'image': visual})

        return jsonify({
            'name': f'NDVI promedio anual {date[:4]}',
            'tileUrl': map_id_dict['tile_fetcher'].url_format
        })

    except ee.ee_exception.EEException as e:
        return jsonify({'error': f'Error de Earth Engine: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Error inesperado: {str(e)}'}), 500

@app.route('/gee-ndvi-stats')
def ndvi_stats():
    date = request.args.get('date')
    try:
        datetime.datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return jsonify({'error': 'Fecha inválida. Use formato YYYY-MM-DD'}), 400

    try:
        minx = float(request.args.get('minx'))
        miny = float(request.args.get('miny'))
        maxx = float(request.args.get('maxx'))
        maxy = float(request.args.get('maxy'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Parámetros de región inválidos'}), 400

    try:
        ndvi = buscar_ndvi_anual(date)
        region = ee.Geometry.Rectangle([minx, miny, maxx, maxy])
        ndvi_clipped = ndvi.clip(region)

        stats = ndvi_clipped.reduceRegion(
            reducer=ee.Reducer.mean()
                .combine(ee.Reducer.minMax(), sharedInputs=True)
                .combine(ee.Reducer.stdDev(), sharedInputs=True)
                .combine(ee.Reducer.count(), sharedInputs=True),
            geometry=region,
            scale=30,
            maxPixels=1e13
        ).getInfo()

        if stats.get('NDVI_mean') is None:
            return jsonify({'error': 'No se encontraron datos NDVI en la región seleccionada'}), 400

        return jsonify({
            'year': int(date[:4]),
            'mean': stats.get('NDVI_mean', 0),
            'min': stats.get('NDVI_min', 0),
            'max': stats.get('NDVI_max', 0),
            'stdDev': stats.get('NDVI_stdDev', 0),
            'count': stats.get('NDVI_count', 0)
        })

    except Exception as e:
        logging.exception("Error en estadísticas NDVI")
        return jsonify({'error': f'Error al calcular estadísticas NDVI: {str(e)}'}), 500



@app.route('/gee-ndvi-diff')
def diferencia_ndvi():
    date1 = request.args.get('date1')
    date2 = request.args.get('date2')
    if not date1 or not date2:
        return jsonify({'error': 'Faltan parámetros date1 o date2'}), 400

    try:
        ndvi1 = buscar_ndvi_anual(date1)
        ndvi2 = buscar_ndvi_anual(date2)
        diferencia = ndvi2.subtract(ndvi1).rename('NDVI_DIFF')

        vis_params = {
            'min': -0.1,
            'max': 0.1,
            'palette': ['#762a83', '#af8dc3', '#e7d4e8', '#7fbf7b', '#1b7837']
        }

        map_id_dict = ee.data.getMapId({'image': diferencia.visualize(**vis_params)})

        return jsonify({
            'name': f'Cambios NDVI ({date1[:4]} → {date2[:4]})',
            'tileUrl': map_id_dict['tile_fetcher'].url_format
        })

    except Exception as e:
        return jsonify({'error': f'Error al calcular diferencia NDVI: {str(e)}'}), 500

@app.route('/gee-deforestation-zones')
def zonas_deforestadas():
    date1 = request.args.get('date1')
    date2 = request.args.get('date2')
    threshold = float(request.args.get('threshold', 0.2))

    try:
        minx = float(request.args.get('minx'))
        miny = float(request.args.get('miny'))
        maxx = float(request.args.get('maxx'))
        maxy = float(request.args.get('maxy'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Debe proporcionar minx, miny, maxx, maxy'}), 400

    if not date1 or not date2:
        return jsonify({'error': 'Faltan fechas date1 o date2'}), 400

    try:
        ndvi1 = buscar_ndvi_anual(date1)
        ndvi2 = buscar_ndvi_anual(date2)
        diff = ndvi1.subtract(ndvi2)
        mask = diff.gte(threshold).selfMask()
        region = ee.Geometry.Rectangle([minx, miny, maxx, maxy])

        vectorized = mask.reduceToVectors(
            geometry=region,
            geometryType='polygon',
            scale=90,
            maxPixels=1e13,
            geometryInNativeProjection=False,
            bestEffort=True,
            tileScale=4,
            reducer=ee.Reducer.countEvery()
        )

        return jsonify(vectorized.limit(5000).getInfo())

    except Exception as e:
        return jsonify({'error': f'Error al generar zonas deforestadas: {str(e)}'}), 500


@app.route('/gee-ndvi-stats-from-geojson', methods=['POST'])
def ndvi_stats_from_geojson():
    data = request.get_json()
    date = data.get('date')
    geojson = data.get('geometry')

    if not date or not geojson:
        return jsonify({'error': 'Faltan parámetros'}), 400

    try:
        datetime.datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return jsonify({'error': 'Fecha inválida. Use formato YYYY-MM-DD'}), 400

    try:
        # Soporte para FeatureCollection o geometría directa
        if geojson.get('type') == 'FeatureCollection':
            region = ee.FeatureCollection(geojson).geometry()
        elif geojson.get('type') == 'Feature':
            region = ee.Feature(geojson).geometry()
        else:
            region = ee.Geometry(geojson)

        ndvi = buscar_ndvi_anual(date)
        ndvi_clipped = ndvi.clip(region)

        stats = ndvi_clipped.reduceRegion(
            reducer=ee.Reducer.mean()
                .combine(ee.Reducer.minMax(), sharedInputs=True)
                .combine(ee.Reducer.stdDev(), sharedInputs=True)
                .combine(ee.Reducer.count(), sharedInputs=True),
            geometry=region,
            scale=30,
            maxPixels=1e13
        ).getInfo()

        if stats.get('NDVI_mean') is None:
            return jsonify({'error': 'No se encontraron datos NDVI en el polígono especificado'}), 400

        return jsonify({
            'year': int(date[:4]),
            'mean': stats.get('NDVI_mean', 0),
            'min': stats.get('NDVI_min', 0),
            'max': stats.get('NDVI_max', 0),
            'stdDev': stats.get('NDVI_stdDev', 0),
            'count': stats.get('NDVI_count', 0)
        })

    except Exception as e:
        logging.exception("Error en /gee-ndvi-stats-from-geojson")
        return jsonify({'error': str(e)}), 500


@app.route('/gee-ndvi-histogram', methods=['POST'])
def ndvi_histograma():
    data = request.get_json()
    date1 = data.get('date1')
    date2 = data.get('date2')
    geojson = data.get('geometry')

    if not date1 or not date2 or not geojson:
        return jsonify({'error': 'Faltan parámetros date1, date2 o geometry'}), 400

    try:
        region = ee.Geometry(geojson)
        ndvi1 = buscar_ndvi_anual(date1)
        ndvi2 = buscar_ndvi_anual(date2)
        diferencia = ndvi2.subtract(ndvi1).rename('NDVI_DIFF')

        hist = diferencia.reduceRegion(
            reducer=ee.Reducer.histogram(maxBuckets=20),
            geometry=region,
            scale=120,
            maxPixels=1e13
        ).getInfo()

        if not hist.get('NDVI_DIFF'):
            return jsonify({'error': 'No se encontraron datos de diferencia NDVI en la región'}), 400

        return jsonify(hist.get('NDVI_DIFF'))

    except Exception as e:
        return jsonify({'error': f'Error al calcular histograma: {str(e)}'}), 500

    except Exception as e:
        return jsonify({'error': f'Error al calcular histograma: {str(e)}'}), 500

@app.route('/gee-savi-stats')
def savi_stats():
    date = request.args.get('date')
    try:
        datetime.datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return jsonify({'error': 'Fecha inválida. Use formato YYYY-MM-DD'}), 400

    try:
        minx = float(request.args.get('minx'))
        miny = float(request.args.get('miny'))
        maxx = float(request.args.get('maxx'))
        maxy = float(request.args.get('maxy'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Parámetros de región inválidos'}), 400

    try:
        savi = buscar_savi_anual(date)
        region = ee.Geometry.Rectangle([minx, miny, maxx, maxy])
        savi_clipped = savi.clip(region)

        stats = savi_clipped.reduceRegion(
            reducer=ee.Reducer.mean()
                .combine(ee.Reducer.minMax(), sharedInputs=True)
                .combine(ee.Reducer.stdDev(), sharedInputs=True)
                .combine(ee.Reducer.count(), sharedInputs=True),
            geometry=region,
            scale=30,
            maxPixels=1e13
        ).getInfo()

        if stats.get('SAVI_mean') is None:
            return jsonify({'error': 'No se encontraron datos SAVI en la región seleccionada'}), 400

        return jsonify({
            'year': int(date[:4]),
            'mean': stats['SAVI_mean'],
            'min': stats['SAVI_min'],
            'max': stats['SAVI_max'],
            'stdDev': stats['SAVI_stdDev'],
            'count': stats['SAVI_count']
        })

    except Exception as e:
        return jsonify({'error': f'Error al calcular estadísticas SAVI: {str(e)}'}), 500

@app.route('/gee-savi-stats-from-geojson', methods=['POST'])
def savi_stats_from_geojson():
    data = request.get_json()
    date = data.get('date')
    geojson = data.get('geometry')

    if not date or not geojson:
        return jsonify({'error': 'Faltan parámetros'}), 400

    try:
        datetime.datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return jsonify({'error': 'Fecha inválida. Use formato YYYY-MM-DD'}), 400

    try:
        if geojson.get('type') == 'FeatureCollection':
            region = ee.FeatureCollection(geojson).geometry()
        elif geojson.get('type') == 'Feature':
            region = ee.Feature(geojson).geometry()
        else:
            region = ee.Geometry(geojson)

        savi = buscar_savi_anual(date)
        savi_clipped = savi.clip(region)

        stats = savi_clipped.reduceRegion(
            reducer=ee.Reducer.mean()
                .combine(ee.Reducer.minMax(), sharedInputs=True)
                .combine(ee.Reducer.stdDev(), sharedInputs=True)
                .combine(ee.Reducer.count(), sharedInputs=True),
            geometry=region,
            scale=30,
            maxPixels=1e13
        ).getInfo()

        if stats.get('SAVI_mean') is None:
            return jsonify({'error': 'No se encontraron datos SAVI en el polígono especificado'}), 400

        return jsonify({
            'year': int(date[:4]),
            'mean': stats['SAVI_mean'],
            'min': stats['SAVI_min'],
            'max': stats['SAVI_max'],
            'stdDev': stats['SAVI_stdDev'],
            'count': stats['SAVI_count']
        })

    except Exception as e:
        return jsonify({'error': f'Error al calcular estadísticas SAVI desde área: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
