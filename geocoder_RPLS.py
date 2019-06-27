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
import pandas as pd
from bokeh.layouts import layout
from bokeh.plotting import output_file, show

from core import diagram_generator
from core import import_building
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


class GeocodeHlm:

    def __init__(self, init_gdf_building):
        # variables for export bokeh
        self.dict_error = {}
        self.dict_count_entity = {}

        self.epsg = param["global"]["epsg"]
        self.output_gdf = gpd.GeoDataFrame()

        # Read RPLS csv file
        assert param["data"]["csv_hlm"].split('.')[-1] == "csv", "the value of the key 'csv_hlm' must be a csv file"
        self.df_hlm = pd.read_csv(param["data"]["csv_hlm"], sep=';')
        self.dict_count_entity["count init adress"] = self.df_hlm.count().max()

        # Read GeoDataFrame building
        self.gdf_building = init_gdf_building
        assert type(
            self.gdf_building) == gpd.geodataframe.GeoDataFrame, "the buildings must be in GeoDataFrame format"

    def correct_street_name_time_format(self):
        """
        Some lines in the input data present anomalies on the street number, which are in the format time -
        Detection and correction of this error
        """

        self.df_hlm.NUMVOIE = self.df_hlm.NUMVOIE.astype(str)
        num_street_time_index = self.df_hlm.index[self.df_hlm.NUMVOIE.str.contains('AM|AP') == True]
        self.dict_error["time format error"] = len(num_street_time_index)
        logging.info(' correct {} entity with time NUMVOIE '.format(len(num_street_time_index)))

        for time_street_number in num_street_time_index:
            if self.df_hlm.NUMVOIE.loc[time_street_number][-2:] == 'AM':
                self.df_hlm.NUMVOIE.loc[time_street_number] = self.df_hlm.NUMVOIE.loc[time_street_number].split(':')[0]
            if self.df_hlm.NUMVOIE.loc[time_street_number][-2:] == 'AP':
                self.df_hlm.NUMVOIE.loc[time_street_number] = int(
                    self.df_hlm.NUMVOIE.loc[time_street_number].split(':')[0]) + 12

    def correct_type_street_is_in_name_street(self):
        """
        Some lines of the entered data present anomalies on the type of street: the information is in duplicate
        Detection and correction of this error (drop the duplicate value)
        """

        type_street_error_count = 0
        cut_name_list = self.df_hlm.NOMVOIE.str.split(' ')

        for cut_name_index in cut_name_list.index:
            try:
                if cut_name_list[cut_name_index][0] == self.df_hlm.TYPVOIE[cut_name_index]:
                    self.df_hlm.NOMVOIE[cut_name_index] = ' '.join(cut_name_list[cut_name_index][1:])
                    type_street_error_count += 1
            except TypeError:
                # Error caused by nan value in cut_name_list
                pass
        self.dict_error["duplicate street name"] = type_street_error_count
        logging.info(' correct {} entity with duplicate street type '.format(type_street_error_count))

    def drop_duplicate_address(self):
        """
        The input file shows all the addresses corresponding to HLMs
        grouping addresses to avoid duplication / limit processing time thereafter
        recovery of number and address area by location
        """

        drop_col = ['NUMVOIE', 'INDREP', 'TYPVOIE', 'NOMVOIE', 'CODEPOSTAL', 'LIBCOM']
        df_hlm = self.df_hlm.copy()

        def count_duplicate_value_before_drop(df):
            """ Group by for recover sum of addresses & living space by location """

            df['nb'] = 1
            df['index'] = df.index

            df['temp_address'] = df.apply(
                lambda row: str(row.NUMVOIE) + ' ' + str(row.INDREP) + ' ' + str(row.TYPVOIE) + ' ' + str(
                    row.NOMVOIE) + ' ' + str(row.CODEPOSTAL) + ' ' + str(row.LIBCOM), axis=1)

            nb_group_by = df.groupby('temp_address')["nb"].apply(lambda x: x.astype(int).sum())
            surface_group_by = df.groupby('temp_address')["SURFHAB"].apply(lambda x: x.astype(int).sum())

            assert type(df) == pd.DataFrame
            return df, nb_group_by, surface_group_by

        def drop_duplicate(df):
            """ Drop duplicates address, based on drop_col list """
            count_address_before = df.count()[0]
            df = df.sort_values("NOMVOIE", ascending=False)
            df = df.drop_duplicates(drop_col, keep='first')

            drop_address_duplicate = count_address_before - df.count()[0]
            logging.info("Drop duplicate address : {} address delete".format(drop_address_duplicate))

            return df, drop_address_duplicate

        def update_nb_and_surface_column(df, nb_group_by, surface_group_by):
            df.index = df.temp_address
            df.update(pd.DataFrame(nb_group_by))
            df.update(surface_group_by)

            df.index = df['index']
            df = df.drop(columns=["temp_address", "index"])

            return df

        df_hlm, nb_unique_address, nb_unique_address_surface = count_duplicate_value_before_drop(df_hlm)
        df_hlm, drop_duplicate_count = drop_duplicate(df_hlm)
        self.df_hlm = update_nb_and_surface_column(df_hlm, nb_unique_address, nb_unique_address_surface)

        self.dict_error["duplicate adress (drop)"] = drop_duplicate_count
        self.dict_count_entity["drop duplicate adress"] = drop_duplicate_count

    def patch_before_export(self):
        """
        Additional / complementary correction before exporting data in csv
        """

        # Problem on some addresses in float type: deletion of these
        self.df_hlm.NUMVOIE = self.df_hlm.NUMVOIE.apply(lambda x: str(x).split('.')[0])
        self.df_hlm.NUMVOIE = self.df_hlm.NUMVOIE.apply(lambda x: str(x).split('/')[0])

        self.df_hlm.TYPVOIE.loc[self.df_hlm.TYPVOIE == self.df_hlm.NUMVOIE] = ''
        self.df_hlm = static_functions.drop_value_in_column(self.df_hlm, 'TYPVOIE', 'INCONNUE', '')

        # DROP str 'nan' in cols and change ? to E
        for geocoding_cols in ['NUMVOIE', 'INDREP', 'TYPVOIE', 'NOMVOIE', 'CODEPOSTAL', 'LIBCOM']:
            self.df_hlm = static_functions.drop_value_in_column(self.df_hlm, geocoding_cols, '?', 'E')
            if (geocoding_cols != 'NOMVOIE') or (geocoding_cols != 'LIBCOM'):
                self.df_hlm = static_functions.drop_value_in_column(self.df_hlm, geocoding_cols, 'nan', '')

    def correct_hlm_csv(self):
        """ grouping input data correction functions """

        logging.info("START csv HLM pretreatment")
        pd.options.mode.chained_assignment = None

        #
        # To avoid encoding errors with the API
        self.df_hlm = static_functions.drop_columns(self.df_hlm, {'LIBEPCI', 'EPCI', 'DPEDATE', 'CONV', 'NUMCONV',
                                                                  'FINANAUTRE', 'LIBSEGPATRIM', 'LIBREG', 'DROIT'})

        self.correct_street_name_time_format()
        self.correct_type_street_is_in_name_street()
        self.drop_duplicate_address()
        self.patch_before_export()

        self.df_hlm.to_csv(ch_output + 'RPLS_correct.csv', sep=';', index=False, encoding='utf-8')
        logging.info("END csv HLM pretreatment")

    @staticmethod
    def formatting_geocoding_result(gdf_hlm):
        """
        For the moment, just select columns to export

        :param gdf_hlm: geopandas.GeoDataFrame with geocode HLM
        :return: geopandas.GeoDataFrame with selected columns
        """

        logging.info("Formatting data after geocoding")
        try:
            gdf_hlm = static_functions.drop_columns(gdf_hlm,
                                                    {'REG', 'DEP', 'LIBDEP', 'DEPCOM', 'CODEPOSTAL', 'LIBCOM',
                                                     'NUMVOIE', 'NEWLOGT',
                                                     'INDREP', 'TYPVOIE', 'NOMVOIE', 'NUMAPPT', 'NUMBOITE', 'FINAN',
                                                     'DATCONV',
                                                     'ESC', 'COULOIR', 'ETAGE', 'COMPLIDENT', 'ENTREE', 'BAT', 'IMMEU',
                                                     'COMPLGEO',
                                                     'LIEUDIT', 'QPV', 'SRU_EXPIR', 'SRU_ALINEA'})
        except ValueError as error:
            print error

        return gdf_hlm

    def run(self):
        self.correct_hlm_csv()
        df_hlm = static_functions.geocode_with_api(ch_output, ch_dir)
        self.dict_count_entity["count result geocoding"] = df_hlm.count().max()

        gdf_hlm = static_functions.geocode_df(df_hlm, 'latitude', 'longitude', 4326)
        gdf_hlm = self.formatting_geocoding_result(gdf_hlm)

        static_functions.formatting_gdf_for_shp_export(gdf_hlm, ch_output + 'result_geocoding.shp')
        self.output_gdf = gdf_hlm


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


def find_nearest_point(building, hlm_point):
    pass


def generate_dashboard_indicator(obj_geocoder):
    logging.info('Generate dashboard indicator')
    output_file(ch_output + "layout_grid.html")

    # Creation of pie chart for result synthesis
    synthesis_chart = diagram_generator.BokehPieChart(u'Synthèse des résultats du géocodage', obj_geocoder.dict_count_entity, 'data',
                                                      'toto')
    synthesis_chart.run()

    # Creation of bar chart for correction synthesis
    correction_chart = diagram_generator.BokehBarChart(u'Syntèse du pré-traitement des données', obj_geocoder.dict_error,
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

    result_score_chart = diagram_generator.BokehBarChart(u"Répartition de l'indice de fiabilité du géocodage", result_score_serie,
                                                         u'Résultat du géocodage', "indice de fiabilité du résultat")
    result_score_chart.run()
    result_score_chart.add_cumulative_value_line()

    # Creation of Bokhe map with geocoding result
    synthesis_map = diagram_generator.BokehMap("Cartographie du géocodage", obj_geocoder.output_gdf)
    synthesis_map.run()
    synthesis_map.Add_layer_to_map("orange", "green")

    show(layout([[synthesis_chart.chart, correction_chart.chart, result_type_chart.chart], [result_score_chart.chart],
                 [synthesis_map.chart]], sizing_mode='stretch_width'))


"""
PROCESS
"""

main_building_process = init_building_gdf()

hlm = GeocodeHlm(main_building_process.gdf_building)
hlm.run()

generate_dashboard_indicator(hlm)

# def nearest(row, geom_union, df1, df2, geom1_col='geometry', geom2_col='geometry', src_column=None):
#     """Find the nearest point and return the corresponding value from specified column."""
#     # Find the geometry that is closest
#     nearest = df2[geom2_col] == nearest_points(row[geom1_col], geom_union)[1]
#     # Get the corresponding value from df2 (matching is based on the geometry)
#     value = df2[nearest][src_column].get_values()[0]
#     return value
