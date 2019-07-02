# -*- coding: utf-8 -*-
"""
Created on Tue Jun 19 19:00:00 2019

@author: bdaniere

"""

import json
import logging
import os
import sys

import geopandas as gpd
import osmnx as ox
import requests

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
    """
    Parent class for recovering and formatting building data
    This class mainly contains the method for formatting and exporting the data
    """

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
        if param["data"]["osm_shp_postgis_building"] == "osm":
            static_functions.formatting_gdf_for_shp_export(self.gdf_building, ch_output + 'building_osm.shp')


class OsmBuilding(Building):

    def __init__(self):
        """
        Constructor of the class
        Declaration of the empty GeoDataFrame and the location of the "study area"
        """

        Building.__init__(self)
        self.gdf_area = gpd.GeoDataFrame()
        self.place_name = str(param["data"]["if_osm"]["territory_name"].decode('utf-8-sig'))

    def recover_osm_area(self):
        """
        Recover area from OpenStreetMap, based of a name of locality
        :return: GeoDataFrame (epsg: 4326) : gdf_area
        """

        logging.info("data recovery from OSM")
        logging.info("-- recover territory")

        self.gdf_area = ox.gdf_from_place(self.place_name)
        assert self.gdf_area.count().max > 0, "No territory name {}".format(self.place_name)

    def recover_osm_building(self):
        """
         Recover building data from OpenStreetMap, based of a name of locality
         Or from self.gdf_area bbox if the data weight is too important
         :return: GeoDataFrame (epsg: 4326) : gdf_area
         """

        logging.info("-- recover building")
        try:
            self.gdf_building = ox.footprints.footprints_from_place(place=self.place_name)
        except ox.core.EmptyOverpassResponse():
            logging.error("-- EmptyOverpassResponse -- ")
            sys.exit()

        except requests.exceptions.ReadTimeout:
            logging.warning("The first recovery of buildings on the territory failed :" \
                            "the query to the OSM server has returned an TimeOut error")
            self.gdf_building = ox.footprints.osm_footprints_download(north=self.gdf_area.bbox_north[0],
                                                                      south=self.gdf_area.bbox_south[0],
                                                                      east=self.gdf_area.bbox_east[0],
                                                                      west=self.gdf_area.bbox_west[0],
                                                                      footprint_type='building', timeout=600)

    def run(self):
        """
         Execution of the different methods of the class
         """

        self.recover_osm_area()
        self.recover_osm_building()
        self.formatting_and_exporting_data()


class ShpBuilding(Building):

    def __init__(self):
        """
        Constructor of the class
        recovery of the path to the data and its EPSG code
        """

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
        """
         Execution of the different methods of the class
         """
        self.read_building_shp()
        self.formatting_and_exporting_data()


class PostGisBuilding(Building):

    def __init__(self):
        Building.__init__(self)

    def run(self):
        """
         Execution of the different methods of the class
         """

        self.gdf_building = static_functions.import_table()
        self.formatting_and_exporting_data()
