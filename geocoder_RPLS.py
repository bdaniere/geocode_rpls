# -*- coding: utf-8 -*-
"""
Created on Tue Jun 19 19:00:00 2019

@author: bdaniere

"""

import json
import logging
import os
import sys

from bokeh.layouts import layout
from bokeh.plotting import output_file, show

from core import diagram_generator
from core import geocode_hlm_core
from core import import_building
from core import post_geocodage

"""
Globals variables 
"""
# lecture du json
json_param = open("param.json")
param = json.load(json_param)

logging.basicConfig(level=logging.INFO, format='%(asctime)s -- %(levelname)s -- %(message)s')
ch_dir = os.getcwd().replace('\\', '/')
ch_output = ch_dir + "/output/"

""" Classes / methods / functions """


def init_building_gdf():
    """
    Creation of building GeoDataFrame :
    Read the user choice and import building data
         - read a building shapefile
         - import data from OSM
         - import data from PostGis Database

    :return: building GeoDataFrame (epsg : 4326)
    """
    # Process building with shp
    if param["data"]["osm_shp_postgis_building"] == "shp":
        logging.info("Start process with specified building shapefile")
        building_process = import_building.ShpBuilding()
        building_process.run()

    # Process building with OSM
    elif param["data"]["osm_shp_postgis_building"] == "osm":
        logging.info("Start process with osm building")
        building_process = import_building.OsmBuilding()
        building_process.run()

    # Process building with Postgis Table
    elif param["data"]["osm_shp_postgis_building"] == "postgis":
        logging.info("Start process with specified PostGis building Table")
        building_process = import_building.PostGisBuilding()
        building_process.run()

    # If input param is poorly defined
    else:
        logging.warning("the value of the key 'osm_shp_postgis_building' must be 'shp' or 'osm' or 'postgis'")
        sys.exit()

    return building_process


def generate_dashboard_indicator(obj_geocoder, obj_post_geocoder):
    """
    Generation of the dashboard is part of the dictionaries or information made upstream

    :param obj_geocoder: geocode_hlm_core.GeocodeHlm use upstream
    :return: bokeh.layout in ch_output + "layout_grid.html"
    """

    logging.info('Generate dashboard indicator')
    output_file(ch_output + "layout_grid.html")

    # Creation of pie chart for result synthesis
    synthesis_chart = diagram_generator.BokehPieChart(u'Synthèse des résultats du géocodage',
                                                      obj_geocoder.dict_count_entity, 'data',
                                                      'toto')
    synthesis_chart.run()

    # Creation of bar chart for correction synthesis
    correction_chart = diagram_generator.BokehBarChart(u'Syntèse du pré-traitement des données',
                                                       obj_geocoder.dict_error,
                                                       u"Nombre d'entité", "type d'erreur")
    correction_chart.run()

    # Creation od bar chart for reult_type value
    result_type_chart = diagram_generator.BokehBarChart(u'Type de précision du résultat du géocodage',
                                                        obj_geocoder.output_gdf.result_type.value_counts(),
                                                        u'Résultat du géocodage', "result_type")
    result_type_chart.run()

    # Creation od bar chart for result_score value
    result_score_serie = obj_geocoder.output_gdf.result_score.value_counts()
    result_score_serie = result_score_serie.sort_index(ascending=True)
    result_score_serie.index = (result_score_serie.index * 100).astype(int).astype(str)

    result_score_chart = diagram_generator.BokehBarChart(u"Répartition de l'indice de fiabilité du géocodage",
                                                         result_score_serie,
                                                         u'Résultat du géocodage', "indice de fiabilité du résultat")
    result_score_chart.run()
    result_score_chart.add_cumulative_value_line()

    # Creation of Bokhe map with geocoding result
    synthesis_map = diagram_generator.BokehMap("Cartographie du géocodage", obj_geocoder.output_gdf,
                                               u"résultat du géocodage")
    synthesis_map.init_map()
    synthesis_map.add_first_layer_to_map("orange", "green")

    show(layout([[synthesis_chart.chart, correction_chart.chart, result_type_chart.chart], [result_score_chart.chart],
                 [synthesis_map.chart]], sizing_mode='stretch_width'))


"""
PROCESS
"""

# Read / recover building
main_building_process = init_building_gdf()

# Read & geocode RLPS
hlm = geocode_hlm_core.GeocodeHlm(main_building_process.gdf_building)
hlm.run()

post_geocoding = post_geocodage.PostGeocodeData(hlm.output_gdf, main_building_process.gdf_building)
post_geocoding.run()

# Generate dashboard
generate_dashboard_indicator(hlm, post_geocoding)