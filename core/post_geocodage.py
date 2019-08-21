# -*- coding: utf-8 -*-
"""
Created on Tue Jun 19 19:00:00 2019

@author: bdaniere

"""

import logging
import os

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString
from shapely.ops import nearest_points

from core import static_functions

"""
Globals variables 
"""
logging.basicConfig(level=logging.INFO, format='%(asctime)s -- %(levelname)s -- %(message)s')
ch_dir = os.getcwd().replace('\\', '/')
ch_output = ch_dir + "/output/"

""" Classes / methods / functions """


class PostGeocodeData:

    def __init__(self, gdf_hlm, gdf_building):
        """
        link the geocoding results to the nearest building (from the building inside centroid)

        :param gdf_hlm: gpd.GeoDataFrame (epsg : 4326) containing geocoding results retrieve upstream
        :param gdf_building: gpd.GeoDataFrame (epsg : 4326) containing buildings retrieve upstream
        """
        self.gdf_building = gdf_building.copy()
        self.gdf_building.id = range(0, len(self.gdf_building))
        # Read & filter result geocoding hlm
        self.gdf_hlm = gdf_hlm.copy()
        self.gdf_hlm = self.gdf_hlm[self.gdf_hlm.result_type == "housenumber"]
        self.gdf_hlm.id = range(0, len(self.gdf_hlm))
        logging.info(' -- only geocoding is taken into account with street number accuracy -- {} result will not be' \
                     'taken into account'.format(gdf_building.count().max() - self.gdf_hlm.count().max()))



        # Create empty GeoDataFrame
        self.gdf_surf_geom = gpd.GeoDataFrame()
        self.gdf_geom_point = gpd.GeoDataFrame()
        self.gdf_connexion_line = gpd.GeoDataFrame()
        self.init_result_geocoder = gpd.GeoDataFrame()

    @staticmethod
    def nearest(row, geom_union, df1, df2, geom1_col='geometry', geom2_col='geometry', src_column=None):
        """
        Find the nearest point and return the corresponding value from specified column. (use in a loop)
        source : https://automating-gis-processes.github.io/2017/lessons/L3/nearest-neighbour.html

        :param row: gpd.GeoDataFrame element
        :param geom_union: gpd.GeoDataFrame.geometry : unary_union of geometry of neighbors to reattach
        :param df1: ?????
        :param df2: gpd.GeoDataFrame containing the elements to be recovered (nearest neighbors)
        :param geom1_col: gpd.GeoDataFrame.geometry containing the geocoding result geometry
        :param geom2_col: gpd.GeoDataFrame.geometry containing the building geometry
        :param src_column: gpd.GeoDataFrame.id -- nearest neighbor identifier
        :return: nearest neighbor identifier
        """

        # Find the geometry that is closest
        nearest = df2[geom2_col] == nearest_points(row[geom1_col], geom_union)[1]
        # Get the corresponding value from df2 (matching is based on the geometry)
        value = df2[nearest][src_column].get_values()[0]
        return value

    def inside_centroid_building(self):
        """
        Creation of inside centroid centroid (conservation of the initial geometry
        :return: gpd.GeoDataFrame (epsg : 4326) containing buildings with inside centroid geometry
        """

        logging.info(" -- Transform building to centroid inside point")
        # Recover Inside centroid building geometry
        self.gdf_building["geom_point"] = self.gdf_building.geometry.representative_point()

        self.gdf_building["surf_geom"] = self.gdf_building.geometry
        self.gdf_building.geometry = self.gdf_building.geom_point
        self.gdf_building.index = self.gdf_building.id

    def finding_nearest_neighbour(self):
        """
        Attachment of the points resulting from the geocoding result to the nearest building
        :return: gpd.GeoDataFrame (epsg : 4326) containing geocoding results and the geometry of
                the nearest building (centroid and surface)
        """
        logging.info(" -- Find nearest neighbour")
        logging.info(' ---- This part is currently time-consuming')

        unary_union = self.gdf_building.unary_union
        self.gdf_hlm['nearest_id'] = self.gdf_hlm.apply(self.nearest, geom_union=unary_union, df1=self.gdf_hlm,
                                                        df2=self.gdf_building, geom1_col='geometry', src_column='id',
                                                        axis=1)

    def formatting_hlm_building_output(self):
        """
        Update self.gdf_hlm with nearest building geometry (inside centroid and area) & export the result
        """

        def formatting_and_export_building_result(gdf, new_geometry, output_name):
            gdf.geometry = gdf[new_geometry]
            gdf = gdf.drop(columns=["surf_geom", "geom_point"])
            static_functions.formatting_gdf_for_shp_export(gdf, ch_output + output_name)
            return gdf

        logging.info(" -- formatting output HLM building")
        # Create empty columns for recover building geometry
        self.gdf_hlm["surf_geom"] = ''
        self.gdf_hlm["geom_point"] = ''
        self.gdf_hlm.index = self.gdf_hlm.nearest_id

        # hlm_gdf recover nearest building geometries
        logging.info("Add information to output file ")
        self.init_result_geocoder = self.gdf_hlm.copy()
        self.gdf_hlm.update(self.gdf_building)

        # Create gpd.GeoDataFrame surf_geom (HLM building area)
        self.gdf_surf_geom = formatting_and_export_building_result(self.gdf_hlm, "surf_geom", "suf_geom.shp")
        self.gdf_geom_point = formatting_and_export_building_result(self.gdf_hlm, "geom_point", "geom_point.shp")

    def drop_duplicate_geometry(self):
        def count_duplicate_value_before_drop(gdf):
            """
            Group by for recover sum of addresses & living space by location

            :param gdf: gpd.GeoDataFrame()
            :return df : pd.DataFrame containing RPLS file information (after the two first corrections) &
                         "nb" field (each value = 1)
                         "geom_fictive" field with concatenated  complete address
            :return nb_group_by: pd.core.series.Series containing the number of identical addresses for each line
            :return surface_group_by: pd.core.series.Series containing the sum of surface for
                                      identical addresses for each line
            """

            gdf['index'] = gdf.index
            gdf['geom_fictive'] = gdf.geometry.astype(str)

            nb_group_by = gdf.groupby('geom_fictive')["nb"].apply(lambda x: x.astype(int).sum())
            surface_group_by = gdf.groupby('geom_fictive')["SURFHAB"].apply(lambda x: x.astype(int).sum())

            assert type(gdf) == gpd.GeoDataFrame
            return gdf, nb_group_by, surface_group_by

        def drop_duplicate(gdf):
            """
            Drop duplicates address, based on drop_col list

            :param gdf: gpd.GeoDataFrame - output of function "count_duplicate_value_before_drop"
            :return: pd.DataFrame containing RPLS file information without duplicates address
            """
            count_address_before = gdf.count().max()
            gdf = gdf.drop_duplicates('geom_fictive', keep='first')

            drop_address_duplicate = count_address_before - gdf.count()[0]

            return gdf, drop_address_duplicate

        def update_nb_and_surface_column(gdf, nb_group_by, surface_group_by):
            """
            Adding the number of unique addresses (removed during processing) and
            sum of the areas for an output address

            :param df: pd.DataFrame containing the unique address of the RPLS file
            :param nb_group_by: pd.core.series.Series containing the number of unique address
                                (having been deleted upstream)
            :param surface_group_by:pd.core.series.Series containing the sum of living space per address
            :return: pd.DataFrame containing the unique address of the RPLS file, with the sum of living space and
                     number of housing per unique adress
            """

            gdf.index = gdf.geom_fictive
            gdf.update(pd.DataFrame(nb_group_by))
            gdf.update(surface_group_by)

            gdf.index = gdf['index']
            df = gdf.drop(columns=["index", "geom_fictive"])

            return df

        gdf_building, nb_unique_geometry, nb_unique_surface = count_duplicate_value_before_drop(self.gdf_surf_geom)
        gdf_building, drop_duplicate_count = drop_duplicate(gdf_building)
        self.gdf_surf_geom = update_nb_and_surface_column(gdf_building, nb_unique_geometry, nb_unique_surface)

        gdf_building, nb_unique_geometry, nb_unique_surface = count_duplicate_value_before_drop(self.gdf_geom_point)
        gdf_building, drop_duplicate_count = drop_duplicate(gdf_building)
        self.gdf_geom_point = update_nb_and_surface_column(gdf_building, nb_unique_geometry, nb_unique_surface)

    @staticmethod
    def connect_result_point_to_line(gdf_street, gdf_building_point):
        """
        Method for create Line GeoDataFrame, connecting result point to API geocoding and corresponding building

        :param gdf_street: GeoDataFrame / result of geocoding (housenumber / street)
        :param gdf_building_point: GeoDataFrame / result of attachment to the building
        :return gdf_connexion_line: GeoDataFrame / Line connexion between the two gdf from above
        """

        logging.info(' -- Connect geocoding result and building centroid')

        # Drop duplicate based on nearest_id columns
        gdf_building_point = gdf_building_point.drop_duplicates(subset='nearest_id', keep='first', inplace=False)

        # Create & "formatting df_geometry_merge" for concatenate street point and building point
        df_geometry_merge = pd.DataFrame(columns=['id', 'geom_street', 'geom_building', 'geometry_sum'],
                                         index=gdf_street.index)
        df_geometry_merge.id = gdf_street.nearest_id
        df_geometry_merge.geom_street = gdf_street.geometry
        df_geometry_merge = df_geometry_merge.reset_index(drop=True)

        for street_index in df_geometry_merge.index:
            common_id = df_geometry_merge.id[street_index]
            df_geometry_merge.geom_building[street_index] = gdf_building_point.geometry[common_id]
            df_geometry_merge.geometry_sum[street_index] = [df_geometry_merge.geom_building[street_index],
                                                            df_geometry_merge.geom_street[street_index]]


        # Create gdf_connexion_line GeoDataFrame
        df_geometry_merge.id = df_geometry_merge.index

        gdf_connexion_line = gpd.GeoDataFrame(columns=['id', 'geometry'], index=df_geometry_merge.index)
        gdf_connexion_line.id = gdf_connexion_line.index
        gdf_connexion_line.geometry = df_geometry_merge.geometry_sum.apply(lambda x: LineString(x))
        gdf_connexion_line.crs = gdf_building_point.crs

        static_functions.formatting_gdf_for_shp_export(gdf_connexion_line, ch_output + "connexion_line_point.shp")

        return gdf_connexion_line

    def run(self):
        """ Execution of the different methods of the class """

        logging.info("formatting data for join")

        self.inside_centroid_building()
        self.finding_nearest_neighbour()
        self.formatting_hlm_building_output()
        self.drop_duplicate_geometry()
        self.gdf_connexion_line = self.connect_result_point_to_line(self.init_result_geocoder, self.gdf_geom_point)

