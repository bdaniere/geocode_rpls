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
from shapely.ops import nearest_points

from core import diagram_generator
from core import geocode_hlm_core
from core import import_building

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


def generate_dashboard_indicator(obj_geocoder):
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
    synthesis_map.run()
    synthesis_map.Add_layer_to_map("orange", "green")

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

# Generate dashboard
generate_dashboard_indicator(hlm)


def join_building_and_geocoding_result(gdf_hlm, gdf_building):
    """
    Function to link the geocoding results to the nearest building (from the building inside centroid)

    :param gdf_hlm: gpd.GeoDataFrame (epsg : 4326) containing geocoding results retrieve upstream
    :param gdf_building: gpd.GeoDataFrame (epsg : 4326) containing buildings retrieve upstream
    :return:  TO DO
    """

    def nearest(row, geom_union, df1, df2, geom1_col='geometry', geom2_col='geometry', src_column=None):
        """Find the nearest point and return the corresponding value from specified column."""
        # Find the geometry that is closest
        nearest = df2[geom2_col] == nearest_points(row[geom1_col], geom_union)[1]
        # Get the corresponding value from df2 (matching is based on the geometry)
        value = df2[nearest][src_column].get_values()[0]
        return value

    def inside_centroid_building(building_gdf):
        """
        Creation of inside centroid centroid (conservation of the initial geometry

        :param building_gdf: gpd.GeoDataFrame (epsg : 4326) containing buildings retrieve upstream
        :return: gpd.GeoDataFrame (epsg : 4326) containing buildings with inside centroid geometry
        """

        logging.info(" -- Transform building to centroid inside point")

        building_gdf["geom_point"] = gdf_building.geometry.representative_point()

        centroid_building = gdf_building.copy()
        centroid_building["surf_geom"] = centroid_building.geometry
        centroid_building.geometry = centroid_building.geom_point
        centroid_building.index = centroid_building.id

        return building_centroid

    def finding_nearest_neighbour(centroid_building, hlm_gdf):
        """
        Attachment of the points resulting from the geocoding result to the nearest building

        :param centroid_building: gpd.GeoDataFrame (epsg : 4326) containing buildings with inside centroid geometry
        :param hlm_gdf: gpd.GeoDataFrame (epsg : 4326) containing geocoding results retrieve upstream
        :return: gpd.GeoDataFrame (epsg : 4326) containing geocoding results and the geometry of
                the nearest building (centroid and surface)
        """
        logging.info("Find nearest neighbour")
        logging.info(' -- This part is currently time-consuming')

        unary_union = centroid_building.unary_union
        hlm_gdf['nearest_id'] = hlm_gdf.apply(nearest, geom_union=unary_union, df1=hlm_gdf,
                                              df2=centroid_building, geom1_col='geometry', src_column='id',
                                              axis=1)
        return gdf_hlm

    def formatting_hlm_building_output(hlm_gdf, centroid_building):
        # Create empty columns for recover building geometry
        hlm_gdf["surf_geom"] = ''
        hlm_gdf["geom_point"] = ''
        hlm_gdf.index = hlm_gdf.nearest_id

        # hlm_gdf recover nearest building geometries
        logging.info("Add information to output file ")
        hlm_gdf.update(centroid_building)

        # Create gpd.GeoDataFrame surf_geom (HLM building area)
        gdf_surf_geom = hlm_gdf.copy()
        gdf_surf_geom.geometry = gdf_surf_geom.surf_geom

        # Create gpd.GeoDataFrame geom_point (HLM building inside centroid)
        gdf_geom_point = hlm_gdf.copy()
        gdf_geom_point.geometry = gdf_geom_point.geom_point




    logging.info("formatting data for join")

    building_centroid = inside_centroid_building(gdf_building)
    gdf_hlm = finding_nearest_neighbour(building_centroid, gdf_hlm)
    formatting_hlm_building_output(gdf_hlm, building_centroid)

    return gdf_hlm


toto = join_building_and_geocoding_result(hlm.output_gdf, main_building_process.gdf_building)

import pdb

pdb.set_trace()
