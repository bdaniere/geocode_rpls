# -*- coding: utf-8 -*-
"""
Created on Tue Jun 19 19:00:00 2019

@author: bdaniere

"""

import logging
import sys
import json
import os

import geopandas as gpd
import osmnx as ox
import static_functions

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


class Building:

    def __init__(self):
        self.gdf_building = gpd.GeoDataFrame()

    def formatting_and_exporting_data(self):
        """
        Filter building by territory (gdf_area) & drop 'source' field
        Export to shp & formatting the 3 GeoDataFrame
        """
        logging.info("start formatting building data")
        assert type(gpd.GeoDataFrame()) == gpd.geodataframe.GeoDataFrame

        # Re-projection to epsg 4326
        logging.info("-- re-project building data")
        if self.gdf_building.crs != {"init": "epsg:4326"}:
            self.gdf_building = self.gdf_building.to_crs({"init": "epsg:4326"})

        # Add id field
        if {'id'}.issubset(self.gdf_building.columns) is False:
            self.gdf_building['id'] = self.gdf_building.index

        # Clean geometry & filter columns
        self.gdf_building = static_functions.clean_gdf_by_geometry(self.gdf_building)
        self.gdf_building = self.gdf_building[['id', 'geometry']]

        # export data to shp
        # - Pertinant dans tout les cas ??
        # static_functions.formatting_gdf_for_shp_export(self.gdf_building, ch_output + 'building_osm.shp')

        # Drop small building
        logging.info("-- drop small building (area < 30 m²)")
        self.gdf_building = self.gdf_building[self.gdf_building.area > 30]


class OsmBuilding(Building):

    def __init__(self):
        Building.__init__(self)
        self.gdf_area = gpd.GeoDataFrame()
        self.place_name = str(param["data"]["if_osm"]["territory_name"].decode('utf-8-sig'))

    def recover_osm_building(self):
        """
        Recover area, building & road from OpenStreetMap, based of a name of locality
        :return: 2 GeoDataFrame (epsg: 4326) : gdf_area, gdf_building
        """

        logging.info("data recovery from OSM")

        logging.info("-- recover territory")
        self.gdf_area = ox.gdf_from_place(self.place_name)
        assert self.gdf_area.count().max > 0, "No territory name {}".format(self.place_name)

        logging.info("-- recover building")
        try:
            self.gdf_building = ox.footprints.footprints_from_place(place=self.place_name)
        except ox.core.EmptyOverpassResponse():
            logging.error("-- EmptyOverpassResponse -- ")
            sys.exit()

    def run(self):
        self.recover_osm_building()
        self.formatting_and_exporting_data()


class ShpBuilding(Building):

    def __init__(self):
        Building.__init__(self)
        self.gdf_path = param["data"]["if_shp"]["shp_building"]
        self.gdf_epsg = param["data"]["if_shp"]["shp_building_epsg"]

    def read_building_shp(self):
        """
        Read shapefile and transform to GeoDataFrame
        :return: Building GeoDataFrame (epsg: 4326)
        """
        logging.info("-- Read shp : " + self.gdf_path.split('/')[-1])
        assert self.gdf_path.split('.')[-1] == 'shp', "the value of the key 'shp_building' must be a shapeflie"

        try:
            self.gdf_building = gpd.read_file(self.gdf_path)
            self.gdf_building.crs = {"init": "epsg :" + str(self.gdf_epsg)}
            self.gdf_building = self.gdf_building.to_crs({"init": "epsg :4326"})

        except IOError as ioe:
            logging.warning(ioe)
            sys.exit()

    def run(self):
        self.read_building_shp()
        self.formatting_and_exporting_data()


class PostGisBuilding(Building):

    def __init__(self):
        Building.__init__(self)

    def run(self):
        self.gdf_building = static_functions.import_table()
        self.formatting_and_exporting_data()