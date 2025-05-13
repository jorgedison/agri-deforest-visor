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
    return ndvi_anual



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
        ndvi = buscar_ndvi_anual(date)
        vis_params = {
            'min': -0.2,
            'max': 0.8,
            'palette': ['#d73027', '#f46d43', '#fdae61', '#a6d96a', '#1a9850']
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
        minx = float(request.args.get('minx'))
        miny = float(request.args.get('miny'))
        maxx = float(request.args.get('maxx'))
        maxy = float(request.args.get('maxy'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Parámetros de región inválidos'}), 400

    if not date:
        return jsonify({'error': 'Falta parámetro date'}), 400

    try:
        ndvi = buscar_ndvi_anual(date)
        region = ee.Geometry.Rectangle([minx, miny, maxx, maxy])

        stats = ndvi.reduceRegion(
            reducer=ee.Reducer.mean().combine(ee.Reducer.minMax(), sharedInputs=True)
                                 .combine(ee.Reducer.stdDev(), sharedInputs=True),
            geometry=region,
            scale=30,
            maxPixels=1e13
        ).getInfo()

        return jsonify({
            'year': int(date[:4]),
            'mean': stats.get('NDVI_mean'),
            'min': stats.get('NDVI_min'),
            'max': stats.get('NDVI_max'),
            'stdDev': stats.get('NDVI_stdDev')
        })

    except Exception as e:
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
            'palette': ['#67000d', '#fcbba1', '#ffffff', '#ccece6', '#006d2c']
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
        region = ee.Geometry(geojson)
        ndvi = buscar_ndvi_anual(date)
        stats = ndvi.reduceRegion(
            reducer=ee.Reducer.mean().combine(ee.Reducer.minMax(), sharedInputs=True)
                                 .combine(ee.Reducer.stdDev(), sharedInputs=True),
            geometry=region,
            scale=30,
            maxPixels=1e13
        ).getInfo()

        return jsonify({
            'year': int(date[:4]),
            'mean': stats.get('NDVI_mean'),
            'min': stats.get('NDVI_min'),
            'max': stats.get('NDVI_max'),
            'stdDev': stats.get('NDVI_stdDev')
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/gee-ndvi-histogram')
def ndvi_histograma():
    date1 = request.args.get('date1')
    date2 = request.args.get('date2')
    if not date1 or not date2:
        return jsonify({'error': 'Faltan fechas date1 o date2'}), 400

    try:
        ndvi1 = buscar_ndvi_anual(date1)
        ndvi2 = buscar_ndvi_anual(date2)
        diferencia = ndvi2.subtract(ndvi1).rename('NDVI_DIFF')

        region = ee.Geometry.Rectangle([-74.5, -10.5, -74.0, -10.0])
        hist = diferencia.reduceRegion(
            reducer=ee.Reducer.histogram(maxBuckets=20),
            geometry=region,
            scale=120,
            maxPixels=1e13
        )

        return jsonify(hist.get('NDVI_DIFF').getInfo())

    except Exception as e:
        return jsonify({'error': f'Error al calcular histograma: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(port=8080)
