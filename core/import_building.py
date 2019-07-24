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

            :param gdf: self.gdf_building -- type : gpd.GeoDataFrame
            :return small_building: gpd.GeoDataFrame containing only buildings of less than 30m²
            :return small_building_contiguously: gpd.GeoDataFrame containing only buildings of
                    less than 30m² contiguous to a larger building
            :return isolated_small_building_index: set containing only index buildings of
                    less than 30m² not adjacent to a building
            """

            logging.info(" -- Identification of small buildings")
            small_building = gdf[gdf.area * 10000000000 < 30]
            small_building_contiguously = gpd.GeoDataFrame(columns=small_building.columns)
            small_building_contiguously["joiner"] = 0
            gdf["neighbors "] = None

            # import pdb
            # pdb.set_trace()

            for index, row in gdf.iterrows():
                neighbors = gdf[gdf.geometry.touches(row['geometry'])].id.tolist()
                neighbors = neighbors.remove(row.id)
                gdf.at[index, "neighbors"] = ", ".join(neighbors)

            import pdb
            pdb.set_trace()

            for small_index_building in small_building.index:
                unitary_small_building = small_building.geometry[small_index_building]
                max_contiguous_area = 0

                for building_index in self.gdf_building.index:
                    unitary_building = self.gdf_building.geometry[building_index]

                    if small_index_building != building_index and unitary_small_building.touches(unitary_building):
                        if unitary_building.area > max_contiguous_area:
                            max_contiguous_area = unitary_building.area
                            small_building_contiguously.loc[small_index_building] = small_building.loc[
                                small_index_building]
                            small_building_contiguously.loc[small_index_building, "joiner"] = int(building_index)

            isolated_small_building_index = set(small_building_contiguously.index).symmetric_difference(
                small_building.index)

            return small_building, small_building_contiguously, isolated_small_building_index

        def merge_small_building(gdf, small_building_contiguously):
            """
            Sub function allowing to merge small building contiguously geometry with the geometry
            of the nearest building (determined upstream)

            :param gdf: self.gdf_building -- type : gpd.GeoDataFrame without -30m² buildings
            :param small_building_contiguously: gpd.GeoDataFrame containing only buildings of
                   less than 30m² contiguous to a larger building
            :return:
            """

            logging.info(" -- Merge small building contiguously with the nearest building ")

            for small_building_index in small_building_contiguously.index:
                try:
                    add_index_geometry = small_building_contiguously.joiner[small_building_index]
                    gdf.loc[small_building_index, "geometry"] = small_building_contiguously.geometry[
                        small_building_index].union(gdf.geometry[add_index_geometry])
                    if add_index_geometry in small_building_contiguously.index:
                        small_building_contiguously.drop([add_index_geometry])

                except (ValueError, KeyError, AttributeError) as union_error:
                    # Avoid error if need to join two small buildings
                    pass

            gdf = gdf.dropna(subset=['geometry'])
            return gdf

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

        small_buildings, small_buildings_contiguously, isolated_index = contiguous_small_building_contiguous(
            self.gdf_building)
        self.gdf_building = merge_small_building(self.gdf_building, small_buildings_contiguously)
        self.gdf_building = drop_isolated_small_building(self.gdf_building, isolated_index)

        self.gdf_building = static_functions.clean_gdf_by_geometry(self.gdf_building)
        import pdb
        pdb.set_trace()


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
            self.gdf_building.crs = {"init": "epsg :" + str(self.gdf_epsg)}
            self.gdf_building = self.gdf_building.to_crs({"init": "epsg :4326"})

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
