#!/usr/bin/env python3.4
# coding: latin-1

# (c) Massachusetts Institute of Technology 2015-2017
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Bar Chart
---------

Plots a bar chart of a statistic.

Each variable in the statistic (ie, each variable chosen in the statistic
operation's **Group By**) must be set as **Variable** or as a facet.

.. object:: Statistic

    Which statistic to plot.
    
.. object:: Variable

    The statistic variable to use as the major bar groups.
    
.. object:: Scale

    How to scale the statistic plot.
    
.. object:: Horizontal Facet

    Make muliple plots, with each column representing a subset of the statistic
    with a different value for this variable.
        
.. object:: Vertical Facet

    Make multiple plots, with each row representing a subset of the statistic
    with a different value for this variable.
    
.. object:: Hue Facet

    Make multiple bars with different colors; each color represents a subset
    of the statistic with a different value for this variable.
    
.. object:: Error Statistic

    A statistic to use to make the error bars.  Must have the same variables
    as the statistic in **Statistic**.
    
.. object:: Subset

    Plot only a subset of the statistic.
    
.. plot::
        
    import cytoflow as flow
    import_op = flow.ImportOp()
    import_op.tubes = [flow.Tube(file = "Plate01/RFP_Well_A3.fcs",
                                 conditions = {'Dox' : 10.0}),
                       flow.Tube(file = "Plate01/CFP_Well_A4.fcs",
                                 conditions = {'Dox' : 1.0})]
    import_op.conditions = {'Dox' : 'float'}
    ex = import_op.apply()

    ex2 = flow.ThresholdOp(name = 'Threshold',
                           channel = 'Y2-A',
                           threshold = 2000).apply(ex)

    ex3 = flow.ChannelStatisticOp(name = "ByDox",
                                  channel = "Y2-A",
                                  by = ['Dox', 'Threshold'],
                                  function = len).apply(ex2) 
    
    flow.BarChartView(statistic = ("ByDox", "len"),
                      variable = "Dox",
                      huefacet = "Threshold").plot(ex3)
"""

from traits.api import provides, Callable, Property
from traitsui.api import View, Item, VGroup, Controller, EnumEditor
from envisage.api import Plugin, contributes_to
from pyface.api import ImageResource

import pandas as pd

from cytoflow import BarChartView

from cytoflowgui.subset import SubsetListEditor
from cytoflowgui.color_text_editor import ColorTextEditor
from cytoflowgui.ext_enum_editor import ExtendableEnumEditor
from cytoflowgui.view_plugins.i_view_plugin \
    import IViewPlugin, VIEW_PLUGIN_EXT, ViewHandlerMixin, PluginViewMixin, PluginHelpMixin
        
class BarChartHandler(ViewHandlerMixin, Controller):
    
    indices = Property(depends_on = "context.statistics, model.statistic, model.subset")
    levels = Property(depends_on = "context.statistics, model.statistic")

    def default_traits_view(self):
        return View(VGroup(
                    VGroup(Item('statistic',
                                editor=EnumEditor(name='handler.numeric_statistics_names'),
                                label = "Statistic"),
                           Item('variable',
                                editor=EnumEditor(name='handler.indices'),
                                label = "Variable"),
                           Item('yscale', label = "Scale"),
                           Item('xfacet',
                                editor=ExtendableEnumEditor(name='handler.indices',
                                                            extra_items = {"None" : ""}),
                                label = "Horizontal\nFacet"),
                           Item('yfacet',
                                editor=ExtendableEnumEditor(name='handler.indices',
                                                            extra_items = {"None" : ""}),
                                label = "Vertical\nFacet"),
                           Item('huefacet',
                                editor=ExtendableEnumEditor(name='handler.indices',
                                                            extra_items = {"None" : ""}),
                                label="Hue\nFacet"),
                           Item('error_statistic',
                                editor=ExtendableEnumEditor(name='handler.statistics_names',
                                                            extra_items = {"None" : ("", "")}),
                                label = "Error\nStatistic"),
                             label = "Bar Chart",
                             show_border = False),
                    VGroup(Item('subset_list',
                                show_label = False,
                                editor = SubsetListEditor(conditions = "handler.levels")),
                           label = "Subset",
                           show_border = False,
                           show_labels = False),
                    Item('context.view_warning',
                         resizable = True,
                         visible_when = 'context.view_warning',
                         editor = ColorTextEditor(foreground_color = "#000000",
                                                 background_color = "#ffff99")),
                    Item('context.view_error',
                         resizable = True,
                         visible_when = 'context.view_error',
                         editor = ColorTextEditor(foreground_color = "#000000",
                                                  background_color = "#ff9191"))))
        
    # MAGIC: gets the value for the property indices
    def _get_indices(self):
        if not (self.context and self.context.statistics 
                and self.model.statistic in self.context.statistics):
            return []
        
        stat = self.context.statistics[self.model.statistic]
        data = pd.DataFrame(index = stat.index)
        
        if self.model.subset:
            data = data.query(self.model.subset)
            
        if len(data) == 0:
            return []       
        
        names = list(data.index.names)
        for name in names:
            unique_values = data.index.get_level_values(name).unique()
            if len(unique_values) == 1:
                data.index = data.index.droplevel(name)
        
        return list(data.index.names)
    
    # MAGIC: gets the value for the property 'levels'
    # returns a Dict(Str, pd.Series)
    
    def _get_levels(self):        
        if not (self.context and self.context.statistics 
                and self.model.statistic in self.context.statistics):
            return []
        
        stat = self.context.statistics[self.model.statistic]
        index = stat.index
        
        names = list(index.names)
        for name in names:
            unique_values = index.get_level_values(name).unique()
            if len(unique_values) == 1:
                index = index.droplevel(name)

        names = list(index.names)
        ret = {}
        for name in names:
            ret[name] = pd.Series(index.get_level_values(name)).sort_values()
            ret[name] = pd.Series(ret[name].unique())
            
        return ret
    
class BarChartPluginView(PluginViewMixin, BarChartView):
    handler_factory = Callable(BarChartHandler)

@provides(IViewPlugin)
class BarChartPlugin(Plugin, PluginHelpMixin):

    id = 'edu.mit.synbio.cytoflowgui.view.barchart'
    view_id = 'edu.mit.synbio.cytoflow.view.barchart'
    short_name = "Bar Chart"
    
    def get_view(self):
        return BarChartPluginView()

    def get_icon(self):
        return ImageResource('bar_chart')

    @contributes_to(VIEW_PLUGIN_EXT)
    def get_plugin(self):
        return self