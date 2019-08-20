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

from core import static_functions

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

    def process_small_building(self):
        """
        Class method for merge small building (area < 30 m²) with the nearest adjoining building
        Else, remove isolated small buidling
        """

        logging.info("Merge & Drop small building ")

        def contiguous_small_building_contiguous(gdf):
            """
            Sub function allowing to isolate the small building (-30m²) and to determine those being
            contiguous or not to other building
            merge small building contiguously geometry with the geometry of the nearest building

            :param gdf: self.gdf_building -- type : gpd.GeoDataFrame
            :return small_building: gpd.GeoDataFrame containing only buildings of less than 30m²
            :return small_building_contiguously: gpd.GeoDataFrame containing only buildings of
                    less than 30m² contiguous to a larger building
            :return isolated_small_building_index: set containing only index buildings of
                    less than 30m² not adjacent to a building
            """

            logging.info(" -- Identification of small buildings")
            gdf["neighbors"] = None
            gdf["neighbors_geom"] = None
            gdf["small_fusion"] = 0
            small_building = gdf[gdf.area * 10000000000 < 30]
            temp_dict = {}

            # Find buildings neighbors for each building in small_building
            for index, row in gdf.iterrows():
                if index in set(small_building.index):
                    # find buildings neighbors
                    neighbors = gdf[gdf.geometry.touches(row['geometry'])].id.tolist()

                    # deletion of the current id if it is in the list (otherwise, exception handling)
                    if row.id in neighbors:
                        neighbors = neighbors.remove(row.id)

                    if len(neighbors) > 0:
                        # recover the max area of neighbors buildings
                        # biggest_neighbors = neighbors[max(enumerate([gdf.geometry[x].area for x in neighbors]))[0]]
                        biggest_neighbors = max([[x, gdf.geometry[x].area] for x in neighbors], key=(lambda y: y[1]))[0]

                        small_building.at[index, "neighbors"] = biggest_neighbors
                        small_building.at[index, "neighbors_geom"] = gdf.geometry[biggest_neighbors]

                        gdf.at[biggest_neighbors, "geometry"] = gdf.at[biggest_neighbors, "geometry"].union(
                            small_building.at[index, "geometry"])
                        gdf = gdf.drop([index])
                        gdf = gdf.dropna(subset=['geometry'])

                        # voir les cas ou le rattachement se fait su un small building ...
                        # Voir également pour les batiments qui vont se toucher mais devenir des multipolygon

            small_building_contiguously = small_building[small_building.neighbors.notnull()]
            isolated_small_building_index = set(small_building.index[small_building.neighbors.isnull()])

            return gdf, small_building, small_building_contiguously, isolated_small_building_index

        def drop_isolated_small_building(gdf, drop_index):
            """
            Drop row (building) with an area of ​​less than 30m² and not contiguous to another building

            :param gdf: self.gdf_building -- type : gpd.GeoDataFrame
            :param drop_index: set containing only index buildings of less than 30m² not adjacent to a building
            :return: self.gdf_building -- type : gpd.GeoDataFrame without -30m² buildings
            """

            logging.info(" -- Drop isolated small building")
            gdf = gdf[~gdf.id.isin(drop_index)]
            logging.info(" -- {} buildings have been removed".format(len(drop_index)))

            return gdf

        gdf, small_buildings, small_buildings_contiguously, isolated_index = contiguous_small_building_contiguous(
            self.gdf_building)
        self.gdf_building = drop_isolated_small_building(gdf, isolated_index)

        self.gdf_building = static_functions.clean_gdf_by_geometry(self.gdf_building)
        self.gdf_building = self.gdf_building[["id", "geometry"]]


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
        """ Execution of the different methods of the class """

        self.recover_osm_area()
        self.recover_osm_building()
        self.formatting_and_exporting_data()
        self.process_small_building()


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
            self.gdf_building.crs = {"init": "epsg:" + str(self.gdf_epsg)}
            self.gdf_building = self.gdf_building.to_crs({"init": "epsg:4326"})

        except IOError as ioe:
            logging.warning(ioe)
            sys.exit()

    def run(self):
        """ Execution of the different methods of the class """
        self.read_building_shp()
        self.formatting_and_exporting_data()
        self.process_small_building()


class PostGisBuilding(Building):

    def __init__(self):
        Building.__init__(self)

    def run(self):
        """ Execution of the different methods of the class """

        self.gdf_building = static_functions.import_table()
        self.formatting_and_exporting_data()
        self.process_small_building()
