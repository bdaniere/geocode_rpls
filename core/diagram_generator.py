# -*- coding: utf-8 -*-
"""
Created on Tue Jun 19 19:00:00 2019

@author: bdaniere

"""

import logging
from math import pi

import pandas as pd
from bokeh.models import ColumnDataSource
from bokeh.palettes import Category20c
from bokeh.plotting import figure
from bokeh.tile_providers import get_provider, Vendors
from bokeh.transform import cumsum

"""
Globals variables 
"""
# lecture du json

logging.basicConfig(level=logging.INFO, format='%(asctime)s -- %(levelname)s -- %(message)s')

""" Classes / methods / functions """


class BokehChart:

    def __init__(self, title, data, y_label, index_name):
        self.title = title
        self.data = data
        self.y_label = y_label
        self.index_name = index_name

        self.chart = figure()

    def formatting_data(self):
        if type(self.data) in [dict, pd.core.series.Series]:
            self.data = pd.Series(self.data).reset_index(name='value').rename(columns={'index': self.index_name})

        else:
            logging.warning("Input data for chart generation isn't type dict or pd.Series")

        if self.data.count().max() < 45:
            self.data['color'] = Category20c[self.data.count().max()]
        else:
            self.data['color'] = "red"


class BokehPieChart(BokehChart):

    def __init__(self, title, data, y_label, index_name):
        BokehChart.__init__(self, title, data, y_label, index_name)

    def generate_chart(self):
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

    def __init__(self, title, data, y_label, index_name):
        BokehChart.__init__(self, title, data, y_label, index_name)

    def add_cumulative_value_line(self):
        self.data['cumulative_sum'] = self.data.value.cumsum()
        self.chart.line(self.data[self.index_name], self.data.cumulative_sum, line_width=1,
                        legend="valeur cumulée des indices")

    def generate_chart(self):
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

    def __init__(self, title, gdf):
        self.data = gdf
        self.data = self.data.to_crs(epsg='3857')
        self.chart = figure()
        self.title = title

    def gdf_geometry_to_xy(self):
        """
        Transform the self.data.geometry to x & y field
        Drop the initial geometry
        """

        def get_point_coords(row, geom, coord_type):
            """Calculates coordinates ('x' or 'y') of a Point geometry"""
            if coord_type == 'x':
                return row[geom].x
            elif coord_type == 'y':
                return row[geom].y

        self.data['x'] = self.data.apply(get_point_coords, geom='geometry', coord_type='x', axis=1)
        self.data['y'] = self.data.apply(get_point_coords, geom='geometry', coord_type='y', axis=1)
        self.data = self.data.drop('geometry', axis=1).copy()

    def create_map_bokeh_figure(self):
        """
        creation of the cartographic figure to welcome the data
        """

        TOOLTIPS = [
            ('Adresse', '@result_label'),
            ('Nombre adresse', "@nb"),
            ('Type geocodage', '@result_type'),
            ("Score de geocodage", "@result_score")
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

    def Add_layer_to_map(self, fill_color, line_color):
        """ Add data in self.chart"""
        bokeh_data = ColumnDataSource(self.data)
        self.chart.circle('x', 'y', source=bokeh_data, fill_color=fill_color, line_color=line_color, size=10)

    def run(self):
        self.gdf_geometry_to_xy()
        self.create_map_bokeh_figure()
