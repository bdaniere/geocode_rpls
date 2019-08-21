# -*- coding: utf-8 -*-
"""
Created on Tue Jun 19 19:00:00 2019

@author: bdaniere

"""

import json
import logging
import subprocess
import sys
import os

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point
from sqlalchemy import create_engine

"""
Globals variables 
"""
logging.basicConfig(level=logging.INFO, format='%(asctime)s -- %(levelname)s -- %(message)s')

# lecture du json
json_param = open("param.json")
param = json.load(json_param)

"""
Classes / methods / functions 
"""


def create_engine():
    """
    Create SqlAlchemy Engine with user parameters
    :return: SqlAlchemy Engine
    """
    db_name = param["data"]["if_postgis"]["db_name"]
    username = param["data"]["if_postgis"]["db_username"]
    password = param["data"]["if_postgis"]["db_password"]
    port = param["data"]["if_postgis"]["port"]
    host = param["data"]["if_postgis"]["host"]
    engine = create_engine('postgresql://{}:{}@{}:{}/{}'.format(username, password, host, port, host, db_name))
    return engine


def import_table():
    """ Read Postgis Table and return GeoDataFrame  """
    con = create_engine()
    gdf = gpd.GeoDataFrame.from_postgis("SELECT * FROM " + param["data"]["if_postgis"]["table_name"], con,
                                        geom_col='geom')
    gdf.crs = {'init': 'epsg:' + str(param["data"]["if_postgis"]["epsg"])}
    gdf = gdf.to_crs({"init": "epsg :4326"})

    if gdf.geometry.name == 'geom':
        gdf = gdf.rename(columns={"geom": "geometry"})

    assert type(gdf) == gpd.geodataframe.GeoDataFrame, "the output file in not a GeoDataFrame"
    return gdf


def formatting_gdf_for_shp_export(gdf, output_path_and_name):
    """ Formatting GeoDataFrame for export & export to shp

     :type gdf: GeoDataFrame
     :param output_path_and_name: path and name for the output shp
     """

    logging.info('formatting & export GeoDataFrame')

    gdf = gdf.dropna(axis=1, how='all')
    if {'id'}.issubset(gdf.columns) is False:
        gdf['id'] = gdf.index

    for gdf_column in gdf.columns:
        # Easy way : replace all accent
        if type(gdf[gdf_column].max()) in [str, unicode]:
            gdf[gdf_column] = gdf[gdf_column].str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode(
                'utf-8')

        # change type to str if
        if type(gdf[gdf_column][gdf.index.min()]) == np.bool_:
            gdf[gdf_column] = gdf[gdf_column].astype(str)
        if type(gdf[gdf_column][gdf.index.min()]) == pd._libs.tslib.Timestamp:
            gdf[gdf_column] = gdf[gdf_column].astype(str)

        # drop list column
        if type(gdf[gdf_column][gdf.index.min()]) == list:
            gdf = gdf.drop(columns=[gdf_column])
            continue

        # Truncate column name for export shp
        if len(gdf_column) > 10:
            gdf = gdf.rename(columns={gdf_column: gdf_column[:10]})

    gdf = gdf.to_crs({'init': 'epsg:' + str(param['global']['epsg'])})
    gdf.to_file(output_path_and_name)
    return gdf


def clean_gdf_by_geometry(gdf):
    """ Clean a GeoDataFrame : drop null / invalid / empty geometry """

    logging.info("drop null & invalid & duplicate geometry \n")

    # reset index for avoid geometry series
    if "id" not in gdf.columns:
        gdf = gdf.reset_index()

    # Check geometry validity
    invalid_geometry = gdf[gdf.geometry.is_valid == False].count().max()
    if invalid_geometry > 0:
        gdf = gdf[gdf.geometry.is_valid == True]
        logging.info("-- We found and drop {} invalid geometry".format(invalid_geometry))

    # check empty geometry
    null_geometry = gdf[gdf.geometry.is_valid == True].count().max()
    if null_geometry > 0:
        gdf = gdf[gdf.geometry.is_empty == False]

    # Check duplicates geometry
    unique_geometry = gdf.geometry.astype(str).nunique()
    number_duplicate_geometry = gdf.geometry.count() - unique_geometry

    if unique_geometry != gdf.geometry.count():
        wkb_geometry = gdf["geometry"].apply(lambda geom: geom.wkb)
        gdf = gdf.loc[wkb_geometry.drop_duplicates().index]

    logging.info("We found and drop {} duplicates geometry \n".format(number_duplicate_geometry))
    assert unique_geometry == gdf.geometry.count(), "Geometry problem in the input data: the deleted entity" \
                                                    "number is greater than the duplicate entity number"

    # re-initialization of the indexes in relation to the identifiers
    gdf.index = gdf.id
    return gdf


def geocode_with_api(ch_output, ch_dir):
    """
    Geocoding of HLMs from the corrected csv, by use of the api of the French government
    https://api-adresse.data.gouv.fr

    :return: pandas.DataFrame with latitude and longitude information
    """

    logging.info("START geocoding \n")

    geocode_rqt = "curl -X POST -F data=@{} -F columns=NUMVOIE -F columns=INDREP -F columns=TYPVOIE -F " \
                  "columns=NOMVOIE -F columns=CODEPOSTAL -F columns=LIBCOM " \
                  "https://api-adresse.data.gouv.fr/search/csv/".format(ch_output + "RPLS_correct.csv")

    # Execute request to API according to the user OS (MAC is not supported)
    if sys.platform == 'win32':
        result_geocoding = subprocess.check_output(geocode_rqt)
        result_geocoding = result_geocoding.decode('utf_8_sig')
        result_geocoding = result_geocoding.encode('utf_8_sig')

        with open('output/result_geocoding.csv', "w") as output_csv:
            output_csv.write(result_geocoding)

    elif sys.platform == 'linux':
        result_geocoding = os.system(geocode_rqt + " > output/result_geocoding.csv")
    else:
        raise OSError('Your OS is not supported')

    df_hlm = pd.read_csv(ch_dir + "/output/result_geocoding.csv", sep=';', encoding="utf-8")

    try:
        logging.info("END geocoding : {} result \n".format(df_hlm.REG.count()))
    except AttributeError:
        logging.warning('Erreur lors du géocaodage, le résultat ne contient aucun résultat')
        logging.warning(result_geocoding)
        sys.exit()

    return df_hlm


def geocode_df(df, latitude_field, longitude_field, epsg):
    """
    Transform a DataFrame to GeoDataFrame based on x, y field

    :type df: DataFrame
    :type latitude_field: Series
    :type longitude_field: Series
    :type epsg: integer
    :return: GeoDataFrame (epsg : epsg)
    """

    logging.info("Geocode Xls")

    geometry = [Point(xy) for xy in zip(df[longitude_field], df[latitude_field])]
    crs = {'init': 'epsg:' + str(epsg)}
    df = df.drop(columns=[longitude_field, latitude_field])

    gdf = gpd.GeoDataFrame(df, crs=crs, geometry=geometry)
    return gdf


def drop_value_in_column(gdf, col, drop_value, replace_value):
    gdf[col] = gdf[col].astype(str)
    gdf[col] = gdf[col].str.replace(drop_value, replace_value)
    return gdf


def drop_columns(gdf, drop_cols):
    gdf = gdf.drop(columns=drop_cols)
    return gdf
