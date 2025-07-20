import ee
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    ee.Initialize(project='ornate-shine-310021')
    logger.info("Conexión con Google Earth Engine exitosa.")
except Exception as e:
    logger.error(f"Error al inicializar Google Earth Engine: {e}")

app = Flask(__name__)
CORS(app)

def reflectance(image, band):
    return image.select(band).multiply(0.0000275).add(-0.2)

def crear_mosaico_ndvi_periodo(fecha_str):
    """Crea un mosaico NDVI de alta calidad para un período de 4 meses alrededor de una fecha."""
    fecha_obj = datetime.datetime.strptime(fecha_str, '%Y-%m-%d')
    start_date = (fecha_obj - datetime.timedelta(days=60)).strftime('%Y-%m-%d')
    end_date = (fecha_obj + datetime.timedelta(days=60)).strftime('%Y-%m-%d')

    coleccion = (
        ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
        .filterDate(start_date, end_date)
        .filterMetadata('CLOUD_COVER', 'less_than', 50)
    )

    def calcular_ndvi(img):
        pixel_qa = img.select('QA_PIXEL')
        # Máscara para nubes bajas y sombras de nubes bajas
        clear_mask = pixel_qa.bitwiseAnd(1 << 3).eq(0).And(pixel_qa.bitwiseAnd(1 << 4).eq(0))
        
        nir = reflectance(img, 'SR_B5')
        red = reflectance(img, 'SR_B4')
        ndvi = nir.subtract(red).divide(nir.add(red)).rename('NDVI')
        return ndvi.clamp(-1, 1).updateMask(clear_mask)

    coleccion_ndvi = coleccion.map(calcular_ndvi)
    # Usar 'qualityMosaic' en lugar de 'mean' para obtener los mejores píxeles
    mosaico = coleccion_ndvi.qualityMosaic('NDVI')
    best_image_for_cloud_cover = coleccion.sort('CLOUD_COVER').first()
    if best_image_for_cloud_cover:
        cloud_cover_value = ee.Number(best_image_for_cloud_cover.get('CLOUD_COVER') or 0).getInfo()
    else:
        cloud_cover_value = 100 # Default to 100% cloud cover if no image is found
    
    return mosaico, start_date, end_date, cloud_cover_value

@app.route('/gee-tile-url')
def get_tile_url():
    logger.info("Received request for /gee-tile-url")
    date = request.args.get('date')
    if not date:
        logger.warning("Missing date parameter for /gee-tile-url")
        return jsonify({'error': 'Fecha no proporcionada. Use formato YYYY-MM-DD.'}), 400
    
    try:
        logger.info(f"Creating NDVI mosaic for date: {date}")
        ndvi, start_date, end_date, cloud_cover_value = crear_mosaico_ndvi_periodo(date)
        
        if ndvi is None: # Handle case where no suitable images were found
            logger.warning(f"No suitable NDVI mosaic could be created for date: {date}")
            return jsonify({'error': 'No se pudo crear un mosaico NDVI para la fecha y criterios de nubosidad especificados. Intente con otra fecha o un área diferente.'}), 404

        logger.info(f"NDVI mosaic created. Cloud cover: {cloud_cover_value}")
        
        min_val, max_val = -0.1, 0.9
        palette = ['#8c510a', '#d8b365', '#f6e8c3', '#c7eae5', '#5ab4ac', '#01665e']
        vis_params = {'min': min_val, 'max': max_val, 'palette': palette}
        
        visual = ndvi.visualize(**vis_params)
        map_id_dict = ee.data.getMapId({'image': visual})
        logger.info("Map ID dictionary obtained.")
        
        return jsonify({
            'name': f'Mosaico NDVI ({start_date} a {end_date})',
            'tileUrl': map_id_dict['tile_fetcher'].url_format,
            'minValue': min_val,
            'maxValue': max_val,
            'paletteUsed': palette,
            'processingDate': datetime.datetime.utcnow().isoformat() + 'Z',
            'calculationStartDate': start_date,
            'calculationEndDate': end_date,
            'source': 'LANDSAT/LC08/C02/T1_L2',
            'legend': palette,
            'cloudCover': cloud_cover_value
        })
    except Exception as e:
        logger.error(f"Error en /gee-tile-url: {e}", exc_info=True)
        return jsonify({'error': f'Error de Earth Engine: {str(e)}'}), 500

@app.route('/gee-ndvi-diff')
def diferencia_ndvi():
    logger.info("Received request for /gee-ndvi-diff")
    date1 = request.args.get('date1')
    date2 = request.args.get('date2')
    if not all([date1, date2]):
        logger.warning("Missing date parameters for /gee-ndvi-diff")
        return jsonify({'error': 'Faltan parámetros de fecha (date1, date2)'}), 400
    
    try:
        logger.info(f"Creating NDVI mosaic for date1: {date1}")
        ndvi1, start1, end1, cloud_cover1 = crear_mosaico_ndvi_periodo(date1)
        logger.info(f"Creating NDVI mosaic for date2: {date2}")
        ndvi2, start2, end2, cloud_cover2 = crear_mosaico_ndvi_periodo(date2)
        diff = ndvi2.subtract(ndvi1).rename('NDVI_DIFF')
        logger.info("NDVI difference calculated.")
        
        vis_params = {'min': -0.5, 'max': 0.5, 'palette': ['red', 'yellow', 'white', 'cyan', 'green']}
        map_id = diff.getMapId(vis_params)
        logger.info("Map ID obtained for NDVI difference.")
        
        return jsonify({
            'name': f'Diferencia NDVI ({start1} a {end2})',
            'tileUrl': map_id['tile_fetcher'].url_format,
            'range1': {'start': start1, 'end': end1},
            'range2': {'start': start2, 'end': end2},
            'cloudCover1': cloud_cover1,
            'cloudCover2': cloud_cover2
        })
    except Exception as e:
        logger.error(f"Error en /gee-ndvi-diff: {e}", exc_info=True)
        return jsonify({'error': f'Error al calcular diferencia NDVI: {str(e)}'}), 500









@app.route('/gee-deforestation-zones-from-geojson', methods=['POST'])
def zonas_deforestadas_geojson():
    logger.info("Received request for /gee-deforestation-zones-from-geojson")
    data = request.get_json()
    if not data:
        logger.warning("Invalid JSON body for /gee-deforestation-zones-from-geojson")
        return jsonify({'error': 'Cuerpo de la solicitud no es JSON válido'}), 400

    date1 = data.get('date1')
    date2 = data.get('date2')
    geometry_data = data.get('geometry')
    threshold = float(data.get('threshold', 0.25))

    if not all([date1, date2, geometry_data]):
        logger.warning("Missing required parameters for /gee-deforestation-zones-from-geojson")
        return jsonify({'error': 'Faltan parámetros requeridos: date1, date2 o geometry'}), 400

    try:
        logger.info("Processing deforestation zones from GeoJSON.")
        region = ee.Geometry(geometry_data)
        ndvi1, start1, end1, cloud_cover1 = crear_mosaico_ndvi_periodo(date1)
        ndvi2, start2, end2, cloud_cover2 = crear_mosaico_ndvi_periodo(date2)
        
        diff = ndvi1.subtract(ndvi2).rename('NDVI_DIFF')
        deforestation_mask = ndvi1.gt(0.4).And(diff.gt(threshold)).selfMask()
        
        vectors = deforestation_mask.reduceToVectors(
            geometry=region, scale=90, geometryType='polygon', maxPixels=1e10
        )
        geojson = vectors.getInfo()
        zone_count = len(geojson.get('features', []))
        logger.info(f"Detected {zone_count} deforestation zones.")

        return jsonify({
            'features': geojson.get('features', []),
            'deforestationSummary': {
                'zoneCount': zone_count,
                'deforestationDetected': zone_count > 0,
                'threshold': threshold,
                'dateBase': {'start': start1, 'end': end1},
                'dateFinal': {'start': start2, 'end': end2},
                'cloudCover1': cloud_cover1,
                'cloudCover2': cloud_cover2
            }
        })
    except Exception as e:
        logger.error(f"Error en /gee-deforestation-zones-from-geojson: {e}", exc_info=True)
        return jsonify({'error': f'Error al detectar zonas de deforestación: {str(e)}'}), 500


@app.route('/find-best-image-date', methods=['POST'])
def find_best_image_date():
    logger.info("Received request for /find-best-image-date")
    data = request.get_json()
    if not data:
        logger.warning("Invalid JSON body for /find-best-image-date")
        return jsonify({'error': 'Cuerpo de la solicitud no es JSON válido'}), 400

    target_date_str = data.get('targetDate')
    geometry_data = data.get('geometry')

    logger.info(f"Received targetDate: {target_date_str}, geometry_data type: {type(geometry_data)}")

    if not target_date_str:
        logger.warning("Missing required parameter: targetDate")
        return jsonify({'error': 'Falta el parámetro requerido: targetDate'}), 400

    try:
        logger.info(f"Finding best image date near {target_date_str} for given geometry.")
        target_obj = datetime.datetime.strptime(target_date_str, '%Y-%m-%d')

        # Expand the date range to find a better image
        search_start_date = (target_obj - datetime.timedelta(days=15)).strftime('%Y-%m-%d')
        search_end_date = (target_obj + datetime.timedelta(days=15)).strftime('%Y-%m-%d')

        collection = (
            ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
            .filterDate(search_start_date, search_end_date)
            .sort('CLOUD_COVER')
        )

        if geometry_data:
            region = ee.Geometry(geometry_data)
            collection = collection.filterBounds(region)

        best_image = collection.first()

        if not best_image:
            logger.info("No image found for the specified criteria.")
            return jsonify({'message': 'No se encontró ninguna imagen para los criterios especificados.', 'bestDate': None}), 200

        date_info = ee.Date(best_image.get('system:time_start')).format('YYYY-MM-dd').getInfo()
        cloud_cover = ee.Number(best_image.get('CLOUD_COVER')).getInfo()
        logger.info(f"Best image found: Date {date_info}, Cloud Cover {cloud_cover}")

        return jsonify({
            'bestDate': date_info,
            'cloudCover': cloud_cover,
            'message': 'Fecha de imagen óptima encontrada.'
        })

    except Exception as e:
        logger.error(f"Error en /find-best-image-date: {e}", exc_info=True)
        return jsonify({'error': f'Error al buscar la mejor fecha de imagen: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)






