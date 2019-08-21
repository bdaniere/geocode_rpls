# -*- coding: utf-8 -*-
"""
Created on Tue Jun 19 19:00:00 2019

@author: bdaniere

"""

import logging
from math import pi

import geopandas as gpd
import pandas as pd
from bokeh.models import ColumnDataSource
from bokeh.palettes import Category20c
from bokeh.plotting import figure
from bokeh.tile_providers import get_provider, Vendors
from bokeh.transform import cumsum

"""
Globals variables activate bd
"""
# lecture du json

logging.basicConfig(level=logging.INFO, format='%(asctime)s -- %(levelname)s -- %(message)s')

""" Classes / methods / functions """


class BokehChart:
    """
    parent class for specific bokeh.plotting.figure generation
    also contains the method for formatting the input data
    """

    def __init__(self, title, data, y_label, index_name):
        self.title = title
        self.data = data
        self.y_label = y_label
        self.index_name = index_name

        self.chart = figure()

    def formatting_data(self):
        """
        a class method for formatting input data in dictionary or pd.core.series.Series format by renaming columns and adding output chart color information
        :return: pd.core.series.Series with formatted input data
        """

        if type(self.data) in [dict, pd.core.series.Series]:
            self.data = pd.Series(self.data).reset_index(name='value').rename(columns={'index': self.index_name})
        else:
            logging.warning("Input data for chart generation isn't type dict or pd.Series")

        try:
            if self.data.count().max() == 2:
                self.data['color'] = Category20c[3][:2]
            elif self.data.count().max() < 20:
                self.data['color'] = Category20c[self.data.count().max()]
            else:
                self.data['color'] = "red"

        except KeyError:
            logging.error("Unexpected error when setting chart color")
            raise


class BokehPieChart(BokehChart):
    """  Class inheriting from BokehChart allowing the generation of pie chart  """

    def __init__(self, title, data, y_label, index_name):
        BokehChart.__init__(self, title, data, y_label, index_name)

    def generate_chart(self):
        """
        Generation of the pie chart bokeh.plotting.figure and different display settings
        :return: Pie chart bokeh.plotting.figure
        """
        self.data['angle'] = self.data['value'] / self.data['value'].sum() * 2 * pi

        self.chart = figure(plot_height=400, title=self.title, toolbar_location=None,
                            tools="hover", tooltips="@{}: @value".format(self.index_name), x_range=(-0.5, 1.0))

        self.chart.wedge(x=0, y=1, radius=0.4,
                         start_angle=cumsum('angle', include_zero=True), end_angle=cumsum('angle'),
                         line_color="white", fill_color='color', legend=self.index_name, source=self.data)

        self.chart.axis.axis_label = None
        self.chart.axis.visible = False
        self.chart.grid.grid_line_color = None

        self.chart.title.align = "center"
        self.chart.title.text_font_style = "bold"
        self.chart.title.text_color = "olive"

    def run(self):
        self.formatting_data()
        self.generate_chart()


class BokehBarChart(BokehChart):
    """  Class inheriting from BokehChart allowing the generation of bar chart  """

    def __init__(self, title, data, y_label, index_name):
        BokehChart.__init__(self, title, data, y_label, index_name)

    def add_cumulative_value_line(self):
        """
        class method to add a curve on the bar chart to display the cumulative population size
        """
        self.data['cumulative_sum'] = self.data.value.cumsum()
        self.chart.line(self.data[self.index_name], self.data.cumulative_sum, line_width=1,
                        legend="valeur cumulée des indices")

    def generate_chart(self):
        """
        Generation of the bar chart bokeh.plotting.figure and different display settings
        differentiation of the output according to the class variable "index_name": if it contains "index",
        we will add an x_label, its size will be larger, and the scale will be based on 100

        :return: Bar chart bokeh.plotting.figure
        """

        self.data.value = self.data.value / self.data.value.sum()
        self.data.value = self.data.value.apply(lambda x: round(x, 2))

        tools = "pan,box_select,wheel_zoom,reset,save,hover"
        tooltips = [
            (self.index_name, "@x"),
            ("value", "@top %"),
        ]

        if "indice" in self.index_name:
            self.chart = figure(title_location="above", x_range=[str(i).zfill(2) for i in range(
                int(self.data[self.index_name].astype(int).min()), int(self.data[self.index_name].astype(int).max()))],
                                plot_width=1200, plot_height=400, title=self.title, tooltips=tooltips, tools=tools)
            self.chart.xaxis.axis_label = self.index_name
            self.chart.vbar(x=self.data[self.index_name], top=self.data.value, width=0.5, color=self.data.color,
                            legend="Part de l'indice")

        else:
            self.chart = figure(title_location="above", x_range=self.data[self.index_name], plot_width=1200,
                                plot_height=400, title=self.title, tooltips=tooltips, tools=tools)
            self.chart.vbar(x=self.data[self.index_name], top=self.data.value, width=0.5, color=self.data.color)

        self.chart.title.align = "center"
        self.chart.title.text_font_style = "bold"
        self.chart.title.text_color = "olive"

    def run(self):
        self.formatting_data()
        self.generate_chart()


class BokehMap:
    """
    class for creating a bokeh map figure
    :param gdf: Input GeoDataFrame (Point)
    """

    def __init__(self, title, gdf, data_name):
        self.data = gdf
        self.data = self.data.to_crs(epsg='3857')
        self.chart = figure()
        self.title = title
        self.data_name = data_name

    def create_map_bokeh_figure(self):
        """
        creation of the cartographic figure to welcome the data
        """

        TOOLTIPS = [
            ('Adresse', '@result_label'),
            ('Nombre adresse', "@nb"),
            ('Type geocodage', '@result_type'),
            ("Score de geocodage", "@result_score"),
            ("surface habitable (HLM)", "@SURFHAB")
        ]
        tile_provider = get_provider(Vendors.CARTODBPOSITRON)
        self.chart = figure(title=self.title, plot_width=800, plot_height=600, x_axis_type="mercator",
                            y_axis_type="mercator",
                            tooltips=TOOLTIPS)
        self.chart.add_tile(tile_provider)

        self.chart.title.align = "center"
        self.chart.title.text_font_style = "bold"
        self.chart.title.text_color = "olive"

        self.chart.outline_line_width = 7
        self.chart.outline_line_alpha = 0.3
        self.chart.outline_line_color = "navy"

    def add_first_layer_to_map(self, fill_color, line_color):
        """ Add data in self.chart"""
        bokeh_data = ColumnDataSource(self.data)
        self.chart.circle('x', 'y', source=bokeh_data, fill_color=fill_color, line_color=line_color, size=10,
                          legend=self.data_name)
        self.chart.legend.click_policy = "hide"

    def init_map(self):
        """ Execution of the different methods of the class """
        self.data = gdf_geometry_to_xy(self.data)
        self.create_map_bokeh_figure()


# Static function for Bokeh Map
def gdf_geometry_to_xy(data):
    """
    Transform the self.data.geometry to x & y field
    Drop the initial geometry

    :param data: input gpd.GeoDataFrame (Point) to display the Dashboard cartography box
    :return: data formatting for displaying in Dashboard cartography box
    """

    assert type(data) == gpd.geodataframe.GeoDataFrame, "input data for generation of" \
                                                        "Bokeh mapping is not GeoDataFrame type"

    data['x'] = data.apply(get_point_coords, geom='geometry', coord_type='x', axis=1)
    data['y'] = data.apply(get_point_coords, geom='geometry', coord_type='y', axis=1)
    data = data.drop('geometry', axis=1).copy()

    return data


def get_point_coords(row, geom, coord_type):
    """
    Calculates coordinates ('x' or 'y') of a Point geometry
    source : https://automating-gis-processes.github.io/2018/2017/lessons/L5/interactive-map-bokeh.html
    """
    if coord_type == 'x':
        return row[geom].x
    elif coord_type == 'y':
        return row[geom].y


def getLineCoords(row, geom, coord_type):
    """
    Returns a list of coordinates ('x' or 'y') of a LineString geometry
    source : https://automating-gis-processes.github.io/2018/2017/lessons/L5/interactive-map-bokeh.html
    """
    if coord_type == 'x':
        return list(row[geom].coords.xy[0])
    elif coord_type == 'y':
        return list(row[geom].coords.xy[1])


def getPolyCoords(row, geom, coord_type):
    """
    Returns the coordinates ('x' or 'y') of edges of a Polygon exterior
    source : https://automating-gis-processes.github.io/2018/2017/lessons/L5/interactive-map-bokeh.html
    """
    # ATTENTION, les coordonnées prise en compte sont uniquement les coordonnées extérieur
    # (donc pas les polygon a trous)

    # Parse the exterior of the coordinate
    exterior = row[geom].exterior

    if coord_type == 'x':
        # Get the x coordinates of the exterior
        return list(exterior.coords.xy[0])
    elif coord_type == 'y':
        # Get the y coordinates of the exterior
        return list(exterior.coords.xy[1])


def add_new_data_in_bokeh_map(obj_bokeh_map, gdf, data_name, fill_color, line_color):
    # check if input gdf is type gpd.GeoDataFrame and re project to epsg 3857
    assert type(gdf) == gpd.geodataframe.GeoDataFrame, "input data for generation of Bokeh mapping" \
                                                       "is not GeoDataFrame type"
    gdf = gdf.to_crs(epsg='3857')

    # specific treatment depending on the type of geometry
    if gdf.geom_type.max() == 'Point':
        gdf = gdf_geometry_to_xy(gdf)

        bokeh_data = ColumnDataSource(gdf)
        obj_bokeh_map.chart.circle('x', 'y', source=bokeh_data, fill_color=fill_color, line_color=line_color, size=10,
                                   legend=data_name)
        obj_bokeh_map.chart.legend.click_policy = "hide"

    elif gdf.geom_type.max() == 'LineString':
        # Keep only gdf geometry for geometry transformation
        temp_gdf = gpd.GeoDataFrame(gdf.geometry)

        gdf['x'] = temp_gdf.apply(getLineCoords, geom='geometry', coord_type='x', axis=1)
        gdf['y'] = temp_gdf.apply(getLineCoords, geom='geometry', coord_type='y', axis=1)
        gdf = gdf.drop('geometry', axis=1)

        bokeh_data = ColumnDataSource(gdf)
        obj_bokeh_map.chart.multi_line('x', 'y', source=bokeh_data, color='red', line_width=0.5, legend=data_name)
        obj_bokeh_map.chart.legend.click_policy = "hide"

    elif gdf.geom_type.max() == 'Polygon':
        gdf['x'] = gdf.apply(getPolyCoords, geom='geometry', coord_type='x', axis=1)
        gdf['y'] = gdf.apply(getPolyCoords, geom='geometry', coord_type='y', axis=1)
        gdf = gdf.drop('geometry', axis=1)

        bokeh_data = ColumnDataSource(gdf)
        obj_bokeh_map.chart.patches('x', 'y', source=bokeh_data, fill_color=fill_color, line_color=line_color,
                                    line_width=0.2, legend=data_name)
        obj_bokeh_map.chart.legend.click_policy = "hide"

    else:
        logging.warning(
            "Unable to load data '{}' on output map: geometry type is currently not supported ".format(data_name))
