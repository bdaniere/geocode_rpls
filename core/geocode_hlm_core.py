# -*- coding: utf-8 -*-
"""
Created on Tue Jun 19 19:00:00 2019

@author: bdaniere

"""

import json
import logging
import os

import geopandas as gpd
import pandas as pd

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
        """
        Constructor of GeocodeHlm class
        :param init_gdf_building: gpd.GeoDataFrame from core.import_building python file
        """

        # variables for export bokeh
        self.dict_error = {}
        self.dict_count_entity = {}

        self.epsg = param["global"]["epsg"]
        self.output_gdf = gpd.GeoDataFrame()

        # Read RPLS csv file
        assert param["data"]["csv_hlm"].split('.')[-1] == "csv", "the value of the key 'csv_hlm' must be a csv file"

        try:
            self.df_hlm = pd.read_csv(param["data"]["csv_hlm"], sep=';', encoding='utf-8')
        except UnicodeDecodeError:
            self.df_hlm = pd.read_csv(param["data"]["csv_hlm"], sep=';', encoding='latin-1')
            logging.error("Impossible to read csv with utf-8 encoding - Use Latin-1")

        self.df_hlm = self.df_hlm[self.df_hlm.DEPCOM.isin(param["data"]["list_cod_insee"])]
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
            """
            Group by for recover sum of addresses & living space by location

            :param df: pd.DataFrame containing RPLS fils information (after the two first corrections)
            :return df : pd.DataFrame containing RPLS file information (after the two first corrections) &
                         "nb" field (each value = 1)
                         "temp_address" field with concatenated  complete address
            :return nb_group_by: pd.core.series.Series containing the number of identical addresses for each line
            :return surface_group_by: pd.core.series.Series containing the sum of surface for
                                      identical addresses for each line
            """

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
            """
            Drop duplicates address, based on drop_col list

            :param df: pd.DataFrame - output of function "count_duplicate_value_before_drop"
            :return: pd.DataFrame containing RPLS file information without duplicates address
            """
            count_address_before = df.count()[0]
            df = df.sort_values("NOMVOIE", ascending=False)
            df = df.drop_duplicates(drop_col, keep='first')

            drop_address_duplicate = count_address_before - df.count()[0]
            logging.info("Drop duplicate address : {} address delete".format(drop_address_duplicate))

            return df, drop_address_duplicate

        def update_nb_and_surface_column(df, nb_group_by, surface_group_by):
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
        Select columns to export & drop geocoding error

        :param gdf_hlm: geopandas.GeoDataFrame with geocode HLM
        :return: geopandas.GeoDataFrame with selected columns without goecoding error
        """

        logging.info("Formatting data after geocoding")
        # Deleting results that are not in the list of common codes (geocoding error)
        gdf_hlm = gdf_hlm[gdf_hlm.result_citycode.isin(param["data"]["list_cod_insee"])]

        # Drop some columns for export
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
            print(error)

        return gdf_hlm

    def run(self):
        """
        Execution of the different methods of the class
        """

        self.correct_hlm_csv()
        df_hlm = static_functions.geocode_with_api(ch_output, ch_dir)
        self.dict_count_entity["count result geocoding"] = df_hlm.count().max()

        gdf_hlm = static_functions.geocode_df(df_hlm, 'latitude', 'longitude', 4326)
        gdf_hlm = self.formatting_geocoding_result(gdf_hlm)

        static_functions.formatting_gdf_for_shp_export(gdf_hlm, ch_output + 'result_geocoding.shp')
        self.output_gdf = gdf_hlm
