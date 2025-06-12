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
            'tileUrl': map_id_dict['tile_fetcher'].url_format,
            'minValue': min_val,
            'maxValue': max_val,
            'paletteUsed': palette,
            'processingDate': datetime.datetime.utcnow().isoformat() + 'Z',
            'year': int(date[:4]),
            'source': 'LANDSAT/LC08/C02/T1_L2',
            'legend': palette
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

        ndvi_mean = stats.get('NDVI_mean', 0)
        deforestation_detected = ndvi_mean < 0.1

        return jsonify({
            'year': int(date[:4]),
            'mean': ndvi_mean,
            'min': stats.get('NDVI_min', 0),
            'max': stats.get('NDVI_max', 0),
            'stdDev': stats.get('NDVI_stdDev', 0),
            'count': stats.get('NDVI_count', 0),
            'deforestationDetected': deforestation_detected
        })

    except Exception as e:
        logging.exception("Error en estadísticas NDVI")
        return jsonify({'error': f'Error al calcular estadísticas NDVI: {str(e)}'}), 500


@app.route('/gee-ndvi-diff')
def diferencia_ndvi():
    date1 = request.args.get('date1')
    date2 = request.args.get('date2')
    threshold = float(request.args.get('threshold', -0.02))  # Umbral de deforestación

    try:
        minx = float(request.args.get('minx'))
        miny = float(request.args.get('miny'))
        maxx = float(request.args.get('maxx'))
        maxy = float(request.args.get('maxy'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Debe proporcionar minx, miny, maxx y maxy'}), 400

    if not date1 or not date2:
        return jsonify({'error': 'Faltan parámetros date1 o date2'}), 400

    try:
        region = ee.Geometry.BBox(minx, miny, maxx, maxy)

        # Obtener NDVI de cada año
        ndvi1 = buscar_ndvi_anual(date1)
        ndvi2 = buscar_ndvi_anual(date2)
        diff = ndvi2.subtract(ndvi1).rename('NDVI_DIFF').clip(region)

        # Visualización
        vis_params = {
            'min': -0.1,
            'max': 0.1,
            'palette': ['#762a83', '#af8dc3', '#e7d4e8', '#7fbf7b', '#1b7837']
        }
        visual = diff.visualize(**vis_params)
        map_id = ee.data.getMapId({'image': visual})

        # Estadísticas del cambio NDVI en la región
        stats = diff.reduceRegion(
            reducer=ee.Reducer.mean()
                .combine(ee.Reducer.minMax(), sharedInputs=True)
                .combine(ee.Reducer.stdDev(), sharedInputs=True)
                .combine(ee.Reducer.count(), sharedInputs=True),
            geometry=region,
            scale=30,
            maxPixels=1e13
        ).getInfo()

        mean_diff = stats.get('NDVI_DIFF_mean', 0)
        deforestation_detected = mean_diff < threshold

        return jsonify({
            'name': f'Cambios NDVI ({date1[:4]} → {date2[:4]})',
            'tileUrl': map_id['tile_fetcher'].url_format,
            'paletteUsed': vis_params['palette'],
            'processingDate': datetime.datetime.utcnow().isoformat() + 'Z',
            'regionBBox': [minx, miny, maxx, maxy],
            'ndviChangeStats': {
                'mean': mean_diff,
                'min': stats.get('NDVI_DIFF_min', 0),
                'max': stats.get('NDVI_DIFF_max', 0),
                'stdDev': stats.get('NDVI_DIFF_stdDev', 0),
                'count': stats.get('NDVI_DIFF_count', 0)
            },
            'deforestationDetected': deforestation_detected,
            'threshold': threshold,
            'yearBase': int(date1[:4]),
            'yearFinal': int(date2[:4])
        })

    except Exception as e:
        return jsonify({'error': f'Error al calcular diferencia NDVI: {str(e)}'}), 500

@app.route('/gee-deforestation-zones')
def zonas_deforestadas():
    try:
        date1 = request.args.get('date1')
        date2 = request.args.get('date2')
        threshold = float(request.args.get('threshold', 0.2))

        if not date1 or not date2:
            return jsonify({'error': 'Faltan fechas date1 o date2'}), 400

        minx = float(request.args.get('minx'))
        miny = float(request.args.get('miny'))
        maxx = float(request.args.get('maxx'))
        maxy = float(request.args.get('maxy'))
        region = ee.Geometry.Rectangle([minx, miny, maxx, maxy])

        ndvi1 = buscar_ndvi_anual(date1)
        ndvi2 = buscar_ndvi_anual(date2)
        diff = ndvi1.subtract(ndvi2)

        ndvi_base_mask = ndvi1.gt(0.2)
        mask = diff.gte(threshold).And(ndvi_base_mask).selfMask()

        vectorized = mask.reduceToVectors(
            geometry=region,
            geometryType='polygon',
            scale=90,
            maxPixels=1e13,
            bestEffort=True,
            tileScale=4,
            geometryInNativeProjection=False,
            reducer=ee.Reducer.countEvery()
        )

        features = vectorized.limit(1000)
        feature_collection = features.getInfo()
        zone_count = len(feature_collection.get('features', []))

        area_total = region.area().divide(1e6).getInfo()  # en km²
        area_deforested = zone_count * (90 * 90) / 1e6     # en km² aprox
        pct = (area_deforested / area_total) * 100 if area_total else 0
        deforestation_detected = zone_count > 0

        feature_collection['deforestationSummary'] = {
            'zoneCount': zone_count,
            'threshold': threshold,
            'dateBase': date1,
            'dateFinal': date2,
            'regionBBox': [minx, miny, maxx, maxy],
            'areaTotal_km2': round(area_total, 4),
            'areaDeforested_km2': round(area_deforested, 4),
            'percentageAffected': round(pct, 2),
            'deforestationDetected': deforestation_detected
        }

        return jsonify(feature_collection)

    except Exception as e:
        logging.exception("Error en /gee-deforestation-zones")
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

        ndvi_mean = stats.get('NDVI_mean')
        if ndvi_mean is None:
            return jsonify({'error': 'No se encontraron datos NDVI en el polígono especificado'}), 400

        if ndvi_mean >= 0.6:
            status = "vegetacion_densa"
            message = "Área con vegetación saludable"
        elif ndvi_mean >= 0.3:
            status = "vegetacion_media"
            message = "Área con vegetación moderada"
        elif ndvi_mean >= 0.1:
            status = "posible_deforestacion"
            message = "Área posiblemente degradada o deforestada"
        else:
            status = "deforestada"
            message = "Área deforestada o sin vegetación"

        deforestation_detected = ndvi_mean < 0.1

        return jsonify({
            'year': int(date[:4]),
            'mean': round(ndvi_mean, 4),
            'min': round(stats.get('NDVI_min', 0), 4),
            'max': round(stats.get('NDVI_max', 0), 4),
            'stdDev': round(stats.get('NDVI_stdDev', 0), 4),
            'count': stats.get('NDVI_count', 0),
            'status': status,
            'message': message,
            'deforestationDetected': deforestation_detected
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


@app.route('/gee-landsat-dates')
def landsat_dates():
    try:
        # Parámetros esperados
        minx = float(request.args.get('minx'))
        miny = float(request.args.get('miny'))
        maxx = float(request.args.get('maxx'))
        maxy = float(request.args.get('maxy'))
        year = int(request.args.get('year', datetime.datetime.utcnow().year))

        region = ee.Geometry.Rectangle([minx, miny, maxx, maxy])

        start = f"{year}-01-01"
        end = f"{year}-12-31"

        collection = (
            ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
            .filterBounds(region)
            .filterDate(start, end)
            .filterMetadata('CLOUD_COVER', 'less_than', 50)
            .sort('system:time_start')
        )

        dates = collection.aggregate_array('system:time_start').map(
            lambda ts: ee.Date(ts).format("YYYY-MM-dd")
        ).getInfo()

        return jsonify({'dates': dates})

    except Exception as e:
        return jsonify({'error': f'Error al obtener fechas Landsat: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
