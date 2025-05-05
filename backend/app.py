import ee
import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

# Inicializa Earth Engine
ee.Initialize(project='ornate-shine-310021')

app = Flask(__name__)
CORS(app)

def buscar_ndvi_cercano(fecha, dias_rango=8):
    inicio = (datetime.datetime.strptime(fecha, "%Y%m%d") - datetime.timedelta(days=dias_rango)).strftime('%Y-%m-%d')
    fin = (datetime.datetime.strptime(fecha, "%Y%m%d") + datetime.timedelta(days=dias_rango)).strftime('%Y-%m-%d')
    coleccion = ee.ImageCollection('MODIS/061/MOD13A1').filterDate(inicio, fin)
    imagen = coleccion.first()
    if imagen is None:
        raise ValueError(f"No se encontró imagen MODIS entre {inicio} y {fin}")
    bandas = imagen.bandNames().getInfo()
    if 'NDVI' not in bandas:
        raise ValueError("La imagen no contiene la banda NDVI")
    return imagen.select('NDVI').multiply(0.0001)

@app.route('/gee-tile-url')
def get_tile_url():
    date = request.args.get('date')
    if not date:
        return jsonify({'error': 'Fecha no proporcionada'}), 400

    try:
        start = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        end = f"{date[:4]}-{date[4:6]}-{str(int(date[6:]) + 1).zfill(2)}"

        collection = ee.ImageCollection('MODIS/061/MOD13A1').filterDate(start, end)
        size = collection.size().getInfo()
        if size == 0:
            return jsonify({'error': 'No se encontraron imágenes NDVI para esa fecha'}), 404

        image = collection.first()

        bands = image.bandNames().getInfo()
        if 'NDVI' not in bands:
            return jsonify({'error': 'La imagen no contiene la banda NDVI'}), 400

        ndvi = image.select('NDVI').multiply(0.0001)
        vis_params = {
            'min': 0,
            'max': 1,
            'palette': ['#d73027', '#f46d43', '#fdae61', '#a6d96a', '#1a9850']
        }
        map_id_dict = ee.data.getMapId({'image': ndvi.visualize(**vis_params)})

        return jsonify({
            'name': f'NDVI MODIS ({start})',
            'tileUrl': map_id_dict['tile_fetcher'].url_format
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/gee-ndvi-diff')
def detectar_deforestacion():
    date1 = request.args.get('date1')
    date2 = request.args.get('date2')
    if not date1 or not date2:
        return jsonify({'error': 'Faltan fechas date1 o date2'}), 400

    try:
        ndvi1 = buscar_ndvi_cercano(date1)
        ndvi2 = buscar_ndvi_cercano(date2)
        diferencia = ndvi2.subtract(ndvi1)
        vis_params = {
            'min': -0.5,
            'max': 0.5,
            'palette': ['#2166ac', '#f7f7f7', '#b2182b']
        }
        map_id = ee.data.getMapId({'image': diferencia.visualize(**vis_params)})
        return jsonify({
            'name': f'Cambios NDVI ({date1[:4]}-{date1[4:6]}-{date1[6:]} → {date2[:4]}-{date2[4:6]}-{date2[6:]})',
            'tileUrl': map_id['tile_fetcher'].url_format
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/gee-deforestation-zones')
def zonas_deforestadas():
    date1 = request.args.get('date1')
    date2 = request.args.get('date2')
    threshold = float(request.args.get('threshold', 0.2))

    if not date1 or not date2:
        return jsonify({'error': 'Faltan fechas date1 o date2'}), 400

    try:
        ndvi1 = buscar_ndvi_cercano(date1)
        ndvi2 = buscar_ndvi_cercano(date2)

        diff = ndvi1.subtract(ndvi2)
        mask = diff.gte(threshold).selfMask()

        region = ee.Geometry.Polygon(
            [[[-82, -20], [-82, 10], [-66, 10], [-66, -20], [-82, -20]]]
        )

        vectorized = mask.reduceToVectors(
            geometry=region,
            geometryType='polygon',
            scale=2000,
            maxPixels=1e13,
            reducer=ee.Reducer.countEvery()
        ).filter(ee.Filter.gt('count', 10))

        return jsonify(vectorized.getInfo())

    except Exception as e:
        return jsonify({'error': f'Error al generar zonas deforestadas: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(port=8080)
