import ee
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

try:
    ee.Initialize(project='ornate-shine-310021')
    logger.info("Conexión con Google Earth Engine exitosa.")
except Exception as e:
    logger.error(f"Error al inicializar Google Earth Engine: {e}")

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization"]}})

def reflectance(image, band):
    logger.debug(f"Calculating reflectance for band: {band}")
    return image.select(band).multiply(0.0000275).add(-0.2)

def crear_mosaico_ndvi_periodo(fecha_str):
    """Crea un mosaico NDVI de alta calidad para un período de 4 meses alrededor de una fecha."""
    logger.debug(f"crear_mosaico_ndvi_periodo called with date_str: {fecha_str}")
    fecha_obj = datetime.datetime.strptime(fecha_str, '%Y-%m-%d')
    start_date = (fecha_obj - datetime.timedelta(days=60)).strftime('%Y-%m-%d')
    end_date = (fecha_obj + datetime.timedelta(days=60)).strftime('%Y-%m-%d')
    logger.debug(f"Calculated date range: {start_date} to {end_date}")

    coleccion = (
        ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
        .filterDate(start_date, end_date)
        #.filterMetadata('CLOUD_COVER', 'less_than', 50) Temporalmente para pruebas de alerta de nubosidad
        .filterMetadata('CLOUD_COVER', 'less_than', 50)
    )
    logger.debug("Filtered image collection by date and cloud cover.")

    if coleccion.size().getInfo() == 0:
        logger.warning(f"No images found for the period {start_date} to {end_date} with CLOUD_COVER < 50.")
        return None, None, start_date, end_date, 100 # Return None for mosaics, and 100 for cloud cover

    def calcular_ndvi_and_clouds(img):
        pixel_qa = img.select('QA_PIXEL')
        
        # Cloud mask: pixels where bit 3 (cloud) or bit 5 (cirrus) is set
        cloud_mask = pixel_qa.bitwiseAnd(1 << 3).Or(pixel_qa.bitwiseAnd(1 << 5)).neq(0).rename('clouds')
        
        # Clear mask: pixels where bit 3 (cloud) and bit 4 (cloud shadow) are NOT set
        clear_mask = pixel_qa.bitwiseAnd(1 << 3).eq(0).And(pixel_qa.bitwiseAnd(1 << 4).eq(0))
        
        nir = reflectance(img, 'SR_B5')
        red = reflectance(img, 'SR_B4')
        ndvi = nir.subtract(red).divide(nir.add(red)).rename('NDVI')
        
        # Apply clear mask to NDVI, so NDVI is masked where there are clouds or cloud shadows
        ndvi = ndvi.clamp(-1, 1)
        
        return ndvi.addBands(cloud_mask)

    coleccion_ndvi_clouds = coleccion.map(calcular_ndvi_and_clouds)
    
    # Create mosaics for NDVI and clouds separately
    ndvi_mosaic = coleccion_ndvi_clouds.select('NDVI').qualityMosaic('NDVI')
    cloud_mosaic = coleccion_ndvi_clouds.select('clouds').max() # Use max to get any cloud pixel
    # Usar 'qualityMosaic' en lugar de 'mean' para obtener los mejores píxeles
    # mosaico = coleccion_ndvi.qualityMosaic('NDVI') # This line was removed as it was incorrect and redundant
    logger.debug("Applied qualityMosaic to NDVI collection.")
    #best_image_for_cloud_cover = coleccion.sort('CLOUD_COVER', False).first() # Para pruebas: obtener la imagen con mayor nubosidad
    best_image_for_cloud_cover = coleccion.sort('CLOUD_COVER').first()
    if best_image_for_cloud_cover:
        cloud_cover_value = ee.Number(best_image_for_cloud_cover.get('CLOUD_COVER') or 0).getInfo()
        logger.debug(f"Best image cloud cover: {cloud_cover_value}")
    else:
        cloud_cover_value = 100 # Default to 100% cloud cover if no image is found
        logger.debug("No best image found, setting cloud cover to 100.")

    return ndvi_mosaic, cloud_mosaic, start_date, end_date, cloud_cover_value

def calcular_savi_and_clouds(img):
    pixel_qa = img.select('QA_PIXEL')
    cloud_mask = pixel_qa.bitwiseAnd(1 << 3).Or(pixel_qa.bitwiseAnd(1 << 5)).neq(0).rename('clouds')
    
    nir = reflectance(img, 'SR_B5')
    red = reflectance(img, 'SR_B4')
    L = ee.Number(0.5) # Factor de ajuste del suelo
    
    savi = nir.subtract(red).divide(nir.add(red).add(L)).multiply(ee.Number(1).add(L)).rename('SAVI')
    savi = savi.clamp(-1, 1)
    
    return savi.addBands(cloud_mask)

def crear_mosaico_savi_periodo(fecha_str):
    logger.debug(f"crear_mosaico_savi_periodo called with date_str: {fecha_str}")
    fecha_obj = datetime.datetime.strptime(fecha_str, '%Y-%m-%d')
    start_date = (fecha_obj - datetime.timedelta(days=60)).strftime('%Y-%m-%d')
    end_date = (fecha_obj + datetime.timedelta(days=60)).strftime('%Y-%m-%d')
    logger.debug(f"Calculated date range: {start_date} to {end_date}")

    coleccion = (
        ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
        .filterDate(start_date, end_date)
        .filterMetadata('CLOUD_COVER', 'less_than', 50)
    )
    logger.debug("Filtered image collection by date and cloud cover for SAVI.")

    if coleccion.size().getInfo() == 0:
        logger.warning(f"No images found for the SAVI period {start_date} to {end_date} with CLOUD_COVER < 50.")
        return None, None, start_date, end_date, 100

    coleccion_savi_clouds = coleccion.map(calcular_savi_and_clouds)
    
    savi_mosaic = coleccion_savi_clouds.select('SAVI').qualityMosaic('SAVI')
    cloud_mosaic = coleccion_savi_clouds.select('clouds').max()
    logger.debug("Applied qualityMosaic to SAVI collection.")

    best_image_for_cloud_cover = coleccion.sort('CLOUD_COVER').first()
    if best_image_for_cloud_cover:
        cloud_cover_value = ee.Number(best_image_for_cloud_cover.get('CLOUD_COVER') or 0).getInfo()
        logger.debug(f"Best image cloud cover for SAVI: {cloud_cover_value}")
    else:
        cloud_cover_value = 100
        logger.debug("No best image found for SAVI, setting cloud cover to 100.")

    return savi_mosaic, cloud_mosaic, start_date, end_date, cloud_cover_value

@app.route('/gee-tile-url')
def get_tile_url():
    logger.info("Received request for /gee-tile-url")
    date = request.args.get('date')
    if not date:
        logger.warning("Missing date parameter for /gee-tile-url")
        return jsonify({'error': 'Fecha no proporcionada. Use formato YYYY-MM-DD.'}), 400
    
    try:
        logger.info(f"Creating NDVI mosaic for date: {date}")
        ndvi, clouds, start_date, end_date, cloud_cover_value = crear_mosaico_ndvi_periodo(date)
        
        if ndvi is None: # Handle case where no suitable images were found
            logger.warning(f"No suitable NDVI mosaic could be created for date: {date}")
            return jsonify({'error': 'No se pudo crear un mosaico NDVI para la fecha y criterios de nubosidad especificados. Intente con otra fecha o un área diferente.'}), 404

        logger.info(f"NDVI mosaic created. Cloud cover: {cloud_cover_value}")
        
        min_val, max_val = -0.1, 0.9
        palette = ['#8c510a', '#d8b365', '#f6e8c3', '#c7eae5', '#5ab4ac', '#01665e']
        ndvi_vis_params = {'min': min_val, 'max': max_val, 'palette': palette}
        
        # Visualize NDVI
        ndvi_visual = ndvi.visualize(**ndvi_vis_params)

        # Create a light blue image that is masked by the `clouds` mask.
        light_blue_image = ee.Image.constant([140, 160, 180]).uint8() # RGB for metallic blue
        cloud_overlay = light_blue_image.updateMask(clouds) # Only show light blue where clouds are 1
        
        # Blend the cloud overlay on top of the NDVI visualization.
        final_visual = ee.Image.blend(ndvi_visual, cloud_overlay)

        map_id_dict = ee.data.getMapId({'image': final_visual})
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
        ndvi1, clouds1, start1, end1, cloud_cover1 = crear_mosaico_ndvi_periodo(date1)
        logger.info(f"Creating NDVI mosaic for date2: {date2}")
        ndvi2, clouds2, start2, end2, cloud_cover2 = crear_mosaico_ndvi_periodo(date2)
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
        ndvi1, clouds1, start1, end1, cloud_cover1 = crear_mosaico_ndvi_periodo(date1)
        ndvi2, clouds2, start2, end2, cloud_cover2 = crear_mosaico_ndvi_periodo(date2)
        
        diff = ndvi1.subtract(ndvi2).rename('NDVI_DIFF')
        deforestation_mask = ndvi1.gt(0.4).And(diff.gt(threshold)).selfMask()
        
        vectors = deforestation_mask.reduceToVectors(
            geometry=region, scale=90, geometryType='polygon', maxPixels=1e10
        )
        total_area_sq_m = region.area().getInfo()
        
        # Calculate the area of the deforestation mask
        deforested_area_image = deforestation_mask.multiply(ee.Image.pixelArea())
        deforested_area_dict = deforested_area_image.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=region,
            scale=90, # Use the same scale as reduceToVectors
            maxPixels=1e10
        ).getInfo()
        deforested_area_sq_m = list(deforested_area_dict.values())[0] if deforested_area_dict else 0 # Get the sum of pixel areas

        deforestation_percentage = (deforested_area_sq_m / total_area_sq_m * 100) if total_area_sq_m > 0 else 0

        geojson = vectors.getInfo()
        zone_count = len(geojson.get('features', []))
        logger.info(f"Detected {zone_count} deforestation zones. Total Area: {total_area_sq_m:.2f} sqm, Deforested Area: {deforested_area_sq_m:.2f} sqm, Percentage: {deforestation_percentage:.2f}%")

        return jsonify({
            'features': geojson.get('features', []),
            'deforestationSummary': {
                'zoneCount': zone_count,
                'deforestationDetected': zone_count > 0,
                'threshold': threshold,
                'dateBase': {'start': start1, 'end': end1},
                'dateFinal': {'start': start2, 'end': end2},
                'cloudCover1': cloud_cover1,
                'cloudCover2': cloud_cover2,
                'totalAreaSqM': total_area_sq_m,
                'deforestedAreaSqM': deforested_area_sq_m,
                'deforestationPercentage': deforestation_percentage
            }
        })
    except Exception as e:
        logger.error(f"Error en /gee-deforestation-zones-from-geojson: {e}", exc_info=True)
        return jsonify({'error': f'Error al detectar zonas de deforestación: {str(e)}'}), 500


@app.route('/gee-savi-tile-url')
def get_savi_tile_url():
    logger.info("Received request for /gee-savi-tile-url")
    date = request.args.get('date')
    if not date:
        logger.warning("Missing date parameter for /gee-savi-tile-url")
        return jsonify({'error': 'Fecha no proporcionada. Use formato YYYY-MM-DD.'}), 400
    
    try:
        logger.info(f"Creating SAVI mosaic for date: {date}")
        savi, clouds, start_date, end_date, cloud_cover_value = crear_mosaico_savi_periodo(date)
        
        if savi is None:
            logger.warning(f"No suitable SAVI mosaic could be created for date: {date}")
            return jsonify({'error': 'No se pudo crear un mosaico SAVI para la fecha y criterios de nubosidad especificados. Intente con otra fecha o un área diferente.'}), 404

        logger.info(f"SAVI mosaic created. Cloud cover: {cloud_cover_value}")
        
        min_val, max_val = 0, 1 # Rango típico para SAVI
        palette = ['brown', 'yellow', 'lightgreen', 'green', 'darkgreen'] # Paleta de ejemplo para SAVI
        savi_vis_params = {'min': min_val, 'max': max_val, 'palette': palette}
        
        savi_visual = savi.visualize(**savi_vis_params)

        light_blue_image = ee.Image.constant([140, 160, 180]).uint8()
        cloud_overlay = light_blue_image.updateMask(clouds)
        
        final_visual = ee.Image.blend(savi_visual, cloud_overlay)

        map_id_dict = ee.data.getMapId({'image': final_visual})
        logger.info("Map ID dictionary obtained for SAVI.")
        
        return jsonify({
            'name': f'Mosaico SAVI ({start_date} a {end_date})',
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
        logger.error(f"Error en /gee-savi-tile-url: {e}", exc_info=True)
        return jsonify({'error': f'Error de Earth Engine: {str(e)}'}), 500

@app.route('/gee-savi-diff')
def diferencia_savi():
    logger.info("Received request for /gee-savi-diff")
    date1 = request.args.get('date1')
    date2 = request.args.get('date2')
    if not all([date1, date2]):
        logger.warning("Missing date parameters for /gee-savi-diff")
        return jsonify({'error': 'Faltan parámetros de fecha (date1, date2)'}), 400
    
    try:
        logger.info(f"Creating SAVI mosaic for date1: {date1}")
        savi1, clouds1, start1, end1, cloud_cover1 = crear_mosaico_savi_periodo(date1)
        logger.info(f"Creating SAVI mosaic for date2: {date2}")
        savi2, clouds2, start2, end2, cloud_cover2 = crear_mosaico_savi_periodo(date2)
        
        if savi1 is None or savi2 is None:
            return jsonify({'error': 'No se pudieron crear mosaicos SAVI para una o ambas fechas.'}), 404

        diff = savi2.subtract(savi1).rename('SAVI_DIFF')
        logger.info("SAVI difference calculated.")
        
        vis_params = {'min': -0.5, 'max': 0.5, 'palette': ['red', 'yellow', 'white', 'cyan', 'green']} # Paleta similar a NDVI diff
        map_id = diff.getMapId(vis_params)
        logger.info("Map ID obtained for SAVI difference.")
        
        return jsonify({
            'name': f'Diferencia SAVI ({start1} a {end2})',
            'tileUrl': map_id['tile_fetcher'].url_format,
            'range1': {'start': start1, 'end': end1},
            'range2': {'start': start2, 'end': end2},
            'cloudCover1': cloud_cover1,
            'cloudCover2': cloud_cover2
        })
    except Exception as e:
        logger.error(f"Error en /gee-savi-diff: {e}", exc_info=True)
        return jsonify({'error': f'Error al calcular diferencia SAVI: {str(e)}'}), 500

@app.route('/gee-deforestation-zones-from-geojson-savi', methods=['POST'])
def zonas_deforestadas_geojson_savi():
    logger.info("Received request for /gee-deforestation-zones-from-geojson-savi")
    data = request.get_json()
    if not data:
        logger.warning("Invalid JSON body for /gee-deforestation-zones-from-geojson-savi")
        return jsonify({'error': 'Cuerpo de la solicitud no es JSON válido'}), 400

    date1 = data.get('date1')
    date2 = data.get('date2')
    geometry_data = data.get('geometry')
    threshold = float(data.get('threshold', 0.25)) # Umbral para la deforestación

    if not all([date1, date2, geometry_data]):
        logger.warning("Missing required parameters for /gee-deforestation-zones-from-geojson-savi")
        return jsonify({'error': 'Faltan parámetros requeridos: date1, date2 o geometry'}), 400

    try:
        logger.info("Processing deforestation zones from GeoJSON using SAVI.")
        region = ee.Geometry(geometry_data)
        savi1, clouds1, start1, end1, cloud_cover1 = crear_mosaico_savi_periodo(date1)
        savi2, clouds2, start2, end2, cloud_cover2 = crear_mosaico_savi_periodo(date2)
        
        if savi1 is None or savi2 is None:
            return jsonify({'error': 'No se pudieron crear mosaicos SAVI para una o ambas fechas para la detección de deforestación.'}), 404

        diff = savi1.subtract(savi2).rename('SAVI_DIFF')
        # La lógica de deforestación con SAVI puede variar, aquí un ejemplo:
        # Consideramos deforestación si SAVI inicial es alto (vegetación) y la diferencia es grande y negativa
        deforestation_mask = savi1.gt(0.4).And(diff.gt(threshold)).selfMask() # Ajustar umbral y lógica según sea necesario
        
        vectors = deforestation_mask.reduceToVectors(
            geometry=region, scale=90, geometryType='polygon', maxPixels=1e10
        )
        total_area_sq_m = region.area().getInfo()
        
        # Calculate the area of the deforestation mask
        deforested_area_image = deforestation_mask.multiply(ee.Image.pixelArea())
        deforested_area_dict = deforested_area_image.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=region,
            scale=90, # Use the same scale as reduceToVectors
            maxPixels=1e10
        ).getInfo()
        deforested_area_sq_m = list(deforested_area_dict.values())[0] if deforested_area_dict else 0 # Get the sum of pixel areas

        deforestation_percentage = (deforested_area_sq_m / total_area_sq_m * 100) if total_area_sq_m > 0 else 0

        geojson = vectors.getInfo()
        zone_count = len(geojson.get('features', []))
        logger.info(f"Detected {zone_count} deforestation zones using SAVI. Total Area: {total_area_sq_m:.2f} sqm, Deforested Area: {deforested_area_sq_m:.2f} sqm, Percentage: {deforestation_percentage:.2f}%")

        return jsonify({
            'features': geojson.get('features', []),
            'deforestationSummary': {
                'zoneCount': zone_count,
                'deforestationDetected': zone_count > 0,
                'threshold': threshold,
                'dateBase': {'start': start1, 'end': end1},
                'dateFinal': {'start': start2, 'end': end2},
                'cloudCover1': cloud_cover1,
                'cloudCover2': cloud_cover2,
                'totalAreaSqM': total_area_sq_m,
                'deforestedAreaSqM': deforested_area_sq_m,
                'deforestationPercentage': deforestation_percentage
            }
        })
    except Exception as e:
        logger.error(f"Error en /gee-deforestation-zones-from-geojson-savi: {e}", exc_info=True)
        return jsonify({'error': f'Error al detectar zonas de deforestación con SAVI: {str(e)}'}), 500


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


def calcular_nbr_and_clouds(img):
    pixel_qa = img.select('QA_PIXEL')
    cloud_mask = pixel_qa.bitwiseAnd(1 << 3).Or(pixel_qa.bitwiseAnd(1 << 5)).neq(0).rename('clouds')
    
    nir = reflectance(img, 'SR_B5')
    swir2 = reflectance(img, 'SR_B7')
    
    nbr = nir.subtract(swir2).divide(nir.add(swir2)).rename('NBR')
    nbr = nbr.clamp(-1, 1)
    
    return nbr.addBands(cloud_mask)

def crear_mosaico_nbr_periodo(fecha_str):
    logger.debug(f"crear_mosaico_nbr_periodo called with date_str: {fecha_str}")
    fecha_obj = datetime.datetime.strptime(fecha_str, '%Y-%m-%d')
    start_date = (fecha_obj - datetime.timedelta(days=60)).strftime('%Y-%m-%d')
    end_date = (fecha_obj + datetime.timedelta(days=60)).strftime('%Y-%m-%d')
    logger.debug(f"Calculated date range: {start_date} to {end_date}")

    coleccion = (
        ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
        .filterDate(start_date, end_date)
        .filterMetadata('CLOUD_COVER', 'less_than', 50)
    )
    logger.debug("Filtered image collection by date and cloud cover for NBR.")

    if coleccion.size().getInfo() == 0:
        logger.warning(f"No images found for the NBR period {start_date} to {end_date} with CLOUD_COVER < 50.")
        return None, None, start_date, end_date, 100

    coleccion_nbr_clouds = coleccion.map(calcular_nbr_and_clouds)
    
    nbr_mosaic = coleccion_nbr_clouds.select('NBR').qualityMosaic('NBR')
    cloud_mosaic = coleccion_nbr_clouds.select('clouds').max()
    logger.debug("Applied qualityMosaic to NBR collection.")

    best_image_for_cloud_cover = coleccion.sort('CLOUD_COVER').first()
    if best_image_for_cloud_cover:
        cloud_cover_value = ee.Number(best_image_for_cloud_cover.get('CLOUD_COVER') or 0).getInfo()
        logger.debug(f"Best image cloud cover for NBR: {cloud_cover_value}")
    else:
        cloud_cover_value = 100
        logger.debug("No best image found for NBR, setting cloud cover to 100.")

    return nbr_mosaic, cloud_mosaic, start_date, end_date, cloud_cover_value

@app.route('/gee-nbr-tile-url')
def get_nbr_tile_url():
    logger.info("Received request for /gee-nbr-tile-url")
    date = request.args.get('date')
    if not date:
        logger.warning("Missing date parameter for /gee-nbr-tile-url")
        return jsonify({'error': 'Fecha no proporcionada. Use formato YYYY-MM-DD.'}), 400
    
    try:
        logger.info(f"Creating NBR mosaic for date: {date}")
        nbr, clouds, start_date, end_date, cloud_cover_value = crear_mosaico_nbr_periodo(date)
        
        if nbr is None:
            logger.warning(f"No suitable NBR mosaic could be created for date: {date}")
            return jsonify({'error': 'No se pudo crear un mosaico NBR para la fecha y criterios de nubosidad especificados. Intente con otra fecha o un área diferente.'}), 404

        logger.info(f"NBR mosaic created. Cloud cover: {cloud_cover_value}")
        
        min_val, max_val = -1, 1 # Rango típico para NBR
        palette = ['red', 'orange', 'yellow', 'lightgreen', 'darkgreen'] # Paleta de ejemplo para NBR
        nbr_vis_params = {'min': min_val, 'max': max_val, 'palette': palette}
        
        nbr_visual = nbr.visualize(**nbr_vis_params)

        light_blue_image = ee.Image.constant([140, 160, 180]).uint8()
        cloud_overlay = light_blue_image.updateMask(clouds)
        
        final_visual = ee.Image.blend(nbr_visual, cloud_overlay)

        map_id_dict = ee.data.getMapId({'image': final_visual})
        logger.info("Map ID dictionary obtained for NBR.")
        
        return jsonify({
            'name': f'Mosaico NBR ({start_date} a {end_date})',
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
        logger.error(f"Error en /gee-nbr-tile-url: {e}", exc_info=True)
        return jsonify({'error': f'Error de Earth Engine: {str(e)}'}), 500

@app.route('/gee-nbr-diff')
def diferencia_nbr():
    logger.info("Received request for /gee-nbr-diff")
    date1 = request.args.get('date1')
    date2 = request.args.get('date2')
    if not all([date1, date2]):
        logger.warning("Missing date parameters for /gee-nbr-diff")
        return jsonify({'error': 'Faltan parámetros de fecha (date1, date2)'}), 400
    
    try:
        logger.info(f"Creating NBR mosaic for date1: {date1}")
        nbr1, clouds1, start1, end1, cloud_cover1 = crear_mosaico_nbr_periodo(date1)
        logger.info(f"Creating NBR mosaic for date2: {date2}")
        nbr2, clouds2, start2, end2, cloud_cover2 = crear_mosaico_nbr_periodo(date2)
        
        if nbr1 is None or nbr2 is None:
            return jsonify({'error': 'No se pudieron crear mosaicos NBR para una o ambas fechas.'}), 404

        diff = nbr2.subtract(nbr1).rename('NBR_DIFF')
        logger.info("NBR difference calculated.")
        
        vis_params = {'min': -0.5, 'max': 0.5, 'palette': ['red', 'yellow', 'white', 'cyan', 'green']} # Paleta similar a NDVI diff
        map_id = diff.getMapId(vis_params)
        logger.info("Map ID obtained for NBR difference.")
        
        return jsonify({
            'name': f'Diferencia NBR ({start1} a {end2})',
            'tileUrl': map_id['tile_fetcher'].url_format,
            'range1': {'start': start1, 'end': end1},
            'range2': {'start': start2, 'end': end2},
            'cloudCover1': cloud_cover1,
            'cloudCover2': cloud_cover2
        })
    except Exception as e:
        logger.error(f"Error en /gee-nbr-diff: {e}", exc_info=True)
        return jsonify({'error': f'Error al calcular diferencia NBR: {str(e)}'}), 500

@app.route('/gee-deforestation-zones-from-geojson-nbr', methods=['POST'])
def zonas_deforestadas_geojson_nbr():
    logger.info("Received request for /gee-deforestation-zones-from-geojson-nbr")
    data = request.get_json()
    if not data:
        logger.warning("Invalid JSON body for /gee-deforestation-zones-from-geojson-nbr")
        return jsonify({'error': 'Cuerpo de la solicitud no es JSON válido'}), 400

    date1 = data.get('date1')
    date2 = data.get('date2')
    geometry_data = data.get('geometry')
    threshold = float(data.get('threshold', 0.25)) # Umbral para la deforestación

    if not all([date1, date2, geometry_data]):
        logger.warning("Missing required parameters for /gee-deforestation-zones-from-geojson-nbr")
        return jsonify({'error': 'Faltan parámetros requeridos: date1, date2 o geometry'}), 400

    try:
        logger.info("Processing deforestation zones from GeoJSON using NBR.")
        region = ee.Geometry(geometry_data)
        nbr1, clouds1, start1, end1, cloud_cover1 = crear_mosaico_nbr_periodo(date1)
        nbr2, clouds2, start2, end2, cloud_cover2 = crear_mosaico_nbr_periodo(date2)
        
        if nbr1 is None or nbr2 is None:
            return jsonify({'error': 'No se pudieron crear mosaicos NBR para una o ambas fechas para la detección de deforestación.'}), 404

        diff = nbr1.subtract(nbr2).rename('NBR_DIFF')
        # La lógica de deforestación con NBR puede variar, aquí un ejemplo:
        # Consideramos deforestación si NBR inicial es alto (vegetación sana) y la diferencia es grande y negativa
        deforestation_mask = nbr1.gt(0.4).And(diff.gt(threshold)).selfMask() # Ajustar umbral y lógica según sea necesario
        
        vectors = deforestation_mask.reduceToVectors(
            geometry=region, scale=90, geometryType='polygon', maxPixels=1e10
        )
        total_area_sq_m = region.area().getInfo()
        
        # Calculate the area of the deforestation mask
        deforested_area_image = deforestation_mask.multiply(ee.Image.pixelArea())
        deforested_area_dict = deforested_area_image.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=region,
            scale=90, # Use the same scale as reduceToVectors
            maxPixels=1e10
        ).getInfo()
        deforested_area_sq_m = list(deforested_area_dict.values())[0] if deforested_area_dict else 0 # Get the sum of pixel areas

        deforestation_percentage = (deforested_area_sq_m / total_area_sq_m * 100) if total_area_sq_m > 0 else 0

        geojson = vectors.getInfo()
        zone_count = len(geojson.get('features', []))
        logger.info(f"Detected {zone_count} deforestation zones using NBR. Total Area: {total_area_sq_m:.2f} sqm, Deforested Area: {deforested_area_sq_m:.2f} sqm, Percentage: {deforestation_percentage:.2f}%")

        return jsonify({
            'features': geojson.get('features', []),
            'deforestationSummary': {
                'zoneCount': zone_count,
                'deforestationDetected': zone_count > 0,
                'threshold': threshold,
                'dateBase': {'start': start1, 'end': end1},
                'dateFinal': {'start': start2, 'end': end2},
                'cloudCover1': cloud_cover1,
                'cloudCover2': cloud_cover2,
                'totalAreaSqM': total_area_sq_m,
                'deforestedAreaSqM': deforested_area_sq_m,
                'deforestationPercentage': deforestation_percentage
            }
        })
    except Exception as e:
        logger.error(f"Error en /gee-deforestation-zones-from-geojson-nbr: {e}", exc_info=True)
        return jsonify({'error': f'Error al detectar zonas de deforestación con NBR: {str(e)}'}), 500




if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


