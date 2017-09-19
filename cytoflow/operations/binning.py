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

'''
cytoflow.operations.binning
---------------------------
'''

from traits.api import (HasStrictTraits, Str, CStr, provides, Constant, Int)
import numpy as np
import bottleneck as bn

from cytoflow.views import IView, HistogramView
import cytoflow.utility as util

from .i_operation import IOperation
from .base_op_views import Op1DView, AnnotatingView

@provides(IOperation)
class BinningOp(HasStrictTraits):
    """
    Bin data along an axis.
    
    This operation creates equally spaced bins (in linear or log space)
    along an axis and adds a condition assigning each event to a bin.  The
    value of the event's condition is the left end of the bin's interval in
    which the event is located.
    
    Attributes
    ----------
    name : Str
        The operation name.  Used to name the new metadata field in the
        experiment that's created by apply()
        
    channel : Str
        The name of the channel along which to bin.

    scale : {"linear", "log", "logicle"}
        Make the bins equidistant along what scale?
        
    num_bins : Int
        The number of bins to make.  Must set either :attr:`num_bins` or 
        :attr:`bin_width`. If both are defined, :attr:`num_bins` takes precedence.
        
    bin_width : Float
        The width of the bins.  Must set either :attr:`num_bins` or :attr:`bin_width`.  If
        :attr:`scale` is ``log``, :attr:`bin_width` is in log-10 units; if :attr:`scale` is
        ``logicle``, and error is thrown because the units are ill-defined.
        If both :attr:`num_bins` and :attr:`bin_width` are defined, :attr:`num_bins` takes 
        precedence. 
        
    bin_count_name : Str
        If :attr:`bin_count_name` is set, :meth:`apply` adds another column to 
        the resulting :class:`Experiment` that contains the number of events in 
        the bin that this event falls in.  Useful for filtering bins by number of events.
        
    Examples
    --------
    Create a small experiment:
    
    .. plot::
        :context: close-figs
    
        >>> import cytoflow as flow
        >>> import_op = flow.ImportOp()
        >>> import_op.tubes = [flow.Tube(file = "tasbe/rby.fcs")]
        >>> ex = import_op.apply()
    
    Create and parameterize the operation
    
    .. plot::
        :context: close-figs

        >>> bin_op = flow.BinningOp()
        >>> bin_op.name = "Bin"
        >>> bin_op.channel = "FITC-A"
        >>> bin_op.scale = "log"
        >>> bin_op.bin_width = 0.2
    
    Apply the operation to the experiment
    
    .. plot::
        :context: close-figs 
    
        >>> ex2 = bin_op.apply(ex)
    
    Plot the result
    
    .. plot::
        :context: close-figs

        >>> bin_op.default_view().plot(ex2)  

    """
    
    # traits
    id = Constant('edu.mit.synbio.cytoflow.operations.binning')
    friendly_id = Constant("Binning")
    
    name = CStr()
    bin_count_name = CStr()
    channel = Str()
    num_bins = util.PositiveInt(0, allow_zero = True)
    bin_width = util.PositiveFloat(0, allow_zero = True)
    scale = util.ScaleEnum
    
    _max_num_bins = Int(100)

    def apply(self, experiment):
        """
        Applies the binning to an experiment.
        
        Parameters
        ----------
        experiment : Experiment
            the old_experiment to which this op is applied
            
        Returns
        -------
        Experiment
            A new experiment with a condition column named :attr:`name`, which
            contains the location of the left-most edge of the bin that the
            event is in.  If :attr:`bin_count_name` is set, another column
            is added with that name as well, containing the number of events
            in the same bin as the event.

        """
        if experiment is None:
            raise util.CytoflowOpError('experiment', "no experiment specified")
        
        if not self.name:
            raise util.CytoflowOpError('name', "Name is not set")
        
        if self.name in experiment.data.columns:
            raise util.CytoflowOpError('name',
                                       "Name {} is in the experiment already"
                                       .format(self.name))
            
        if self.bin_count_name and self.bin_count_name in experiment.data.columns:
            raise util.CytoflowOpError('bin_count_name',
                                       "bin_count_name {} is in the experiment already"
                                       .format(self.bin_count_name))
        
        if not self.channel:
            raise util.CytoflowOpError('channel', "channel is not set")
        
        if self.channel not in experiment.data.columns:
            raise util.CytoflowOpError('channel', 
                                       "channel {} isn't in the experiment"
                                       .format(self.channel))
              
        if not self.num_bins and not self.bin_width:
            raise util.CytoflowOpError('num_bins',
                                       "must set either bin number or width")
        
        if self.bin_width \
           and not (self.scale == "linear" or self.scale == "log"):
            raise util.CytoflowOpError('scale',
                                       "Can only use bin_width with linear or log scale") 
        
        scale = util.scale_factory(self.scale, experiment, channel = self.channel)
        scaled_data = scale(experiment.data[self.channel])
            
        scaled_min = bn.nanmin(scaled_data)
        scaled_max = bn.nanmax(scaled_data)
        
        num_bins = self.num_bins if self.num_bins else \
                   (scaled_max - scaled_min) / self.bin_width
                   
        if num_bins > self._max_num_bins:
            raise util.CytoflowOpError(None,
                                       "Too many bins! To increase this limit, "
                                       "change _max_num_bins (currently {})"
                                       .format(self._max_num_bins))

        scaled_bins = np.linspace(start = scaled_min, 
                                  stop = scaled_max,
                                  num = num_bins)
        
        if len(scaled_bins) < 2:
            raise util.CytoflowOpError('num_bins', "Must have more than one bin")
        
        # put the data in bins
        bin_idx = np.digitize(scaled_data, scaled_bins[1:-1])
        
        # now, back into data space
        bins = scale.inverse(scaled_bins)
            
        new_experiment = experiment.clone()
        new_experiment.add_condition(self.name, "float", bins[bin_idx])
        
        # keep track of the bins we used, for prettier plotting later.
        new_experiment.metadata[self.name]["bin_scale"] = self.scale
        new_experiment.metadata[self.name]["bins"] = bins
        
        if self.bin_count_name:
            # TODO - this is a HUGE memory hog?!
            # TODO - fix this, then turn it on by default
            agg_count = new_experiment.data.groupby(self.name).count()
            agg_count = agg_count[agg_count.columns[0]]
            
            # have to make the condition a float64, because if we're in log
            # space there may be events that have NaN as the bin number.
            
            new_experiment.add_condition(
                self.bin_count_name,
                "float64",
                new_experiment[self.name].map(agg_count))
        
        new_experiment.history.append(self.clone_traits(transient = lambda _: True))
        return new_experiment
    
    def default_view(self, **kwargs):
        """
        Returns a diagnostic plot to check the binning.
        
        Returns
        -------
        IView
            An view instance, call :meth:`plot()` to plot the bins.
        """
        return BinningView(op = self, **kwargs)
    
@provides(IView)
class BinningView(Op1DView, AnnotatingView, HistogramView):
    """
    Plots a histogram of the current binning op.  By default, the different
    bins are shown in different colors.
    
    Attributes
    ----------
    
    """
     
    id = Constant('edu.mit.synbio.cytoflow.views.binning')
    friendly_id = Constant('Binning Setup')                                 
    
    def plot(self, experiment, **kwargs):
        """
        Plot the histogram.
        
        Parameters
        ----------
        
        """
        
        view, trait_name = self._strip_trait(self.op.name)
    
        super(BinningView, view).plot(experiment,
                                      annotation_facet = self.op.name,
                                      annotation_trait = trait_name,
                                      annotations = {},
                                      **kwargs)

util.expand_class_attributes(BinningView)
util.expand_method_parameters(BinningView, BinningView.plot)
