# -*- coding: utf-8 -*-
# Copyright (C) Duncan Macleod (2013)
#
# This file is part of GWSumm.
#
# GWSumm is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GWSumm is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GWSumm.  If not, see <http://www.gnu.org/licenses/>.

"""Definitions for event trigger plots
"""

from __future__ import division

from itertools import (izip, cycle)

from numpy import isinf

from gwpy.detector import (Channel, ChannelList)
from gwpy.plotter import *
from gwpy.plotter.table import get_column_string
from gwpy.plotter.utils import (color_cycle, marker_cycle)
from gwpy.table.rate import (event_rate, binned_event_rates)
from gwpy.table.utils import get_table_column

from .. import (globalv, version)
from ..utils import re_cchar
from ..data import (get_channel, get_timeseries, add_timeseries)
from ..triggers import get_triggers
from .registry import (get_plot, register_plot)

__author__ = 'Duncan Macleod <duncan.macleod@ligo.org>'
__version__ = version.version

TimeSeriesDataPlot = get_plot('timeseries')


class TriggerPlotMixin(object):
    """Mixin to overwrite `channels` property for trigger plots

    We don't need to get channel data for trigger plots.
    """

    @property
    def channels(self):
        """List of channels for this plot

        :type: `~gwpy.detector.ChannelList`
        """
        return ChannelList(map(Channel, self._channels))

    @channels.setter
    def channels(self, channellist):
        self._channels = channellist

    @property
    def allchannels(self):
        """List of all unique channels for this plot
        """
        chans = [re.split('[#@]', str(c), 1)[0] for c in self._channels]
        return ChannelList(map(Channel, chans))


class TriggerDataPlot(TriggerPlotMixin, TimeSeriesDataPlot):
    """Standard event trigger plot
    """
    _threadsafe = False
    type = 'triggers'
    data = 'triggers'
    defaults = {'x': 'time',
                'y': 'snr',
                'color': None,
                'edgecolor': 'face',
                'facecolor': None,
                'marker': 'o',
                's': 20,
                'vmin': None,
                'vmax': None,
                'clim': None,
                'logcolor': False,
                'colorlabel': None,
                'cmap': 'jet',
                'size_by': None,
                'size_by_log': None,
                'size_range': None}

    def __init__(self, channels, start, end, state=None, outdir='.',
                 etg=None, **kwargs):
        super(TriggerDataPlot, self).__init__(channels, start, end,
                                              state=state, outdir=outdir,
                                              **kwargs)
        self.etg = etg
        self.columns = [self.pargs.pop(c) for c in ('x', 'y', 'color')]

    @property
    def pid(self):
        """Unique identifier for this `TriggerDataPlot`.

        Extends the standard `TimeSeriesDataPlot` pid with the ETG
        and each of the column names.
        """
        try:
            return self._pid
        except AttributeError:
            pid = super(TriggerDataPlot, self).pid
            self._pid += '_%s' % re_cchar.sub('_', self.etg)
            for column in self.columns:
                if column:
                    self._pid += '_%s' % re_cchar.sub('_', column)
            self._pid = self._pid.upper()
            return self.pid

    @pid.setter
    def pid(self, id_):
        self._pid = str(id_)

    def finalize(self, outputfile=None, close=True, **savekwargs):
        if isinstance(self.plot, TimeSeriesPlot):
            return super(TriggerDataPlot, self).finalize(
                       outputfile=outputfile, close=close, **savekwargs)
        else:
            return super(TimeSeriesDataPlot, self).finalize(
                       outputfile=outputfile, close=close, **savekwargs)

    def process(self):
        # get columns
        xcolumn, ycolumn, ccolumn = self.columns

        # initialise figure
        if 'time' in xcolumn:
            base = TimeSeriesPlot
        elif 'freq' in xcolumn:
            base = SpectrumPlot
        else:
            base = Plot
        plot = self.plot = EventTablePlot(figsize=[12, 6], base=base)
        ax = plot.gca()
        if isinstance(plot, TimeSeriesPlot):
            ax.set_epoch(float(self.start))
            ax.set_xlim(float(self.start), float(self.end))

        # work out labels
        labels = self.pargs.pop('labels', self.channels)
        if isinstance(labels, (unicode, str)):
            labels = labels.split(',')
        labels = map(lambda s: str(s).strip('\n '), labels)

        # get colouring params
        clim = self.pargs.pop('clim', self.pargs.pop('colorlim', None))
        clog = self.pargs.pop('logcolor', False)
        clabel = self.pargs.pop('colorlabel', None)

        # get plot arguments
        plotargs = []
        for i in range(len(self.channels)):
            plotargs.append(dict())
        # get plot arguments
        for key in ['vmin', 'vmax', 'edgecolor', 'facecolor', 'size_by',
                    'size_by_log', 'size_range', 'cmap', 's', 'marker']:
            val = self.pargs.pop(key)
            if key == 'facecolor' and len(self.channels) > 1 and val is None:
                val = color_cycle()
            if key == 'marker' and len(self.channels) > 1 and val is None:
                val = marker_cycle()
            elif (isinstance(val, (list, tuple, cycle)) and
                  key not in ['size_range']):
                val = cycle(val)
            else:
                val = cycle([val] * len(self.channels))
            for i in range(len(self.channels)):
                plotargs[i][key] = val.next()
        # fix size_range
        if (len(self.channels) == 1 and plotargs[0]['size_range'] is None and
                (plotargs[0]['size_by'] or plotargs[0]['size_by_log']) and
                clim is not None):
            plotargs[0]['size_range'] = clim

        # add data
        valid = SegmentList([self.span])
        if self.state and not self.all_data:
            valid &= self.state.active
        ntrigs = 0
        for channel, label, pargs in izip(self.channels, labels, plotargs):
            try:
                channel = get_channel(channel)
            except ValueError:
                pass
            if '#' in str(channel) or '@' in str(channel):
                key = '%s,%s' % (str(channel),
                                 self.state and str(self.state) or 'All')
            else:
                key = str(channel)
            table = get_triggers(key, self.etg, valid, query=False)
            ntrigs += len(table)
            # access channel parameters for limits
            for c, column in zip(('x', 'y', 'c'), (xcolumn, ycolumn, ccolumn)):
                if not column:
                    continue
                # hack for SnglBurst frequency nonsense
                if column in ['peak_frequency', 'central_freq']:
                    column = 'frequency'
                # set x and y in plotargs
                param = '%s_range' % column
                lim = '%slim' % c
                if hasattr(channel, param) and c in ('x', 'y'):
                    self.pargs.setdefault(lim, getattr(channel, param))
                # set clim separately
                elif hasattr(channel, param):
                    if not clim:
                        clim = getattr(channel, param)
                    if not pargs['size_range']:
                        pargs['size_range'] = getattr(channel, param)

            ax.plot_table(table, xcolumn, ycolumn, color=ccolumn,
                          label=label, **pargs)

        # customise plot
        legendargs = self.parse_legend_kwargs(markerscale=4)
        logx = self.pargs.pop('logx', self.pargs.pop('xscale', None) == 'log')
        logy = self.pargs.pop('logy', self.pargs.pop('yscale', None) == 'log')
        for key, val in self.pargs.iteritems():
            try:
                getattr(ax, 'set_%s' % key)(val)
            except AttributeError:
                setattr(ax, key, val)
        if logx:
            ax.set_xscale('log')
        if logy:
            ax.set_yscale('log')
        if 'title' not in self.pargs.keys() and len(self.channels) == 1:
            plot.title = '%s (%s)' % (self.channels[0].texname, self.etg)

        # correct log-scale empty axes
        if any(map(isinf, ax.get_ylim())):
            ax.set_ylim(0.1, 10)

        # add colorbar
        if ccolumn:
            if not ntrigs:
                ax.scatter([1], [1], c=[1], visible=False)
            plot.add_colorbar(ax=ax, clim=clim, log=clog, label=clabel)
        else:
            plot.add_colorbar(ax=ax, visible=False)

        if len(self.channels) == 1 and len(table):
            if ccolumn is None:
                ax.add_loudest(table, ycolumn, xcolumn, ycolumn)
            else:
                ax.add_loudest(table, ccolumn, xcolumn, ycolumn)

        if len(self.channels) > 1:
            plot.add_legend(ax=ax, **legendargs)

        # add state segments
        if isinstance(plot, TimeSeriesPlot) and self.state:
            self.add_state_segments(ax)


        # finalise
        return self.finalize()

register_plot(TriggerDataPlot)


class TriggerTimeSeriesDataPlot(TimeSeriesDataPlot):
    """Custom time-series plot to handle discontiguous `TimeSeries`.
    """
    type = 'trigger-timeseries'
    data = 'triggers'

    def process(self):
        """Read in all necessary data, and generate the figure.
        """
        (plot, axes) = self.init_plot()
        ax = axes[0]

        # work out labels
        labels = self.pargs.pop('labels', self.channels)
        if isinstance(labels, (unicode, str)):
            labels = labels.split(',')
        labels = map(lambda s: str(s).strip('\n '), labels)

        # add data
        for label, channel in zip(labels, self.channels):
            label = label.replace('_', r'\_')
            if self.state and not self.all_data:
                valid = self.state.active
            else:
                valid = SegmentList([self.span])
            data = get_timeseries(channel, valid, query=False)
            # handle no timeseries
            if not len(data):
                ax.plot([0], [0], visible=False, label=label)
                continue
            # plot time-series
            color = None
            for ts in data:
                # double-check log scales
                if self.pargs['logy']:
                    ts.value[ts.value == 0] = 1e-100
                if color is None:
                    line = ax.plot_timeseries(ts, label=label)[0]
                    color = line.get_color()
                else:
                    ax.plot_timeseries(ts, color=color, label=None)

            # allow channel data to set parameters
            if hasattr(data[0].channel, 'amplitude_range'):
                self.pargs.setdefault('ylim',
                                      data[0].channel.amplitude_range)

        # add horizontal lines to add
        for yval in self.pargs['hline']:
            try:
                yval = float(yval)
            except ValueError:
                continue
            else:
                ax.plot([self.start, self.end], [yval, yval],
                        linestyle='--', color='red')

        # customise plot
        legendargs = self.parse_legend_kwargs()
        for key, val in self.pargs.iteritems():
            try:
                getattr(ax, 'set_%s' % key)(val)
            except AttributeError:
                setattr(ax, key, val)
        if len(self.channels) > 1:
            plot.add_legend(ax=ax, **legendargs)

        # add extra axes and finalise
        if not plot.colorbars:
            plot.add_colorbar(ax=ax, visible=False)
        if self.state:
            self.add_state_segments(ax)
        return self.finalize()

register_plot(TriggerTimeSeriesDataPlot)


class TriggerHistogramPlot(TriggerPlotMixin, get_plot('histogram')):
    """HistogramPlot from a LIGO_LW Table
    """
    type = 'trigger-histogram'
    data = 'triggers'
    _threadsafe = False

    def __init__(self, *args, **kwargs):
        super(TriggerHistogramPlot, self).__init__(*args, **kwargs)
        self.etg = self.pargs.pop('etg')
        self.column = self.pargs.pop('column')

    @property
    def pid(self):
        try:
            return self._pid
        except AttributeError:
            etg = re_cchar.sub('_', self.etg).upper()
            self._pid = '%s_%s' % (etg, super(TriggerHistogramPlot, self).pid)
            if self.column:
                self._pid += '_%s' % re_cchar.sub('_', self.column).upper()
            return self.pid

    def init_plot(self, plot=HistogramPlot):
        """Initialise the Figure and Axes objects for this
        `TimeSeriesDataPlot`.
        """
        self.plot = plot(figsize=self.pargs.pop('figsize', [12, 6]))
        ax = self.plot.gca()
        ax.grid(True, which='both')
        return self.plot, ax

    def process(self):
        """Get data and generate the figure.
        """
        # get histogram parameters
        (plot, ax) = self.init_plot()

        # extract histogram arguments
        histargs = self.parse_plot_kwargs()
        legendargs = self.parse_legend_kwargs()

        # add data
        data = []
        livetime = []
        for channel in self.channels:
            try:
                channel = get_channel(channel)
            except ValueError:
                print(channel)
                pass
            if self.state and not self.all_data:
                valid = self.state.active
            else:
                valid = SegmentList([self.span])
            if '#' in str(channel) or '@' in str(channel):
                key = '%s,%s' % (str(channel),
                                 self.state and str(self.state) or 'All')
            else:
                key = str(channel)
            table_ = get_triggers(key, self.etg, valid, query=False)
            livetime.append(float(abs(table_.segments)))
            data.append(get_table_column(table_, self.column))
            # allow channel data to set parameters
            if hasattr(channel, 'amplitude_range'):
                self.pargs.setdefault('xlim', c.amplitude_range)

        # get range
        if not 'range' in histargs[0]:
            for kwset in histargs:
                kwset['range'] = ax.common_limits(data)

        # plot
        for arr, d, kwargs in zip(data, livetime, histargs):
            weights = kwargs.pop('weights', None)
            direction = kwargs.get('orientation', 'vertical')
            if weights is True:
                try:
                    weights = 1/d
                except ZeroDivisionError:
                    pass
                if direction == 'horizontal':
                    self.pargs.setdefault(
                        'xbound', 1/float(abs(self.span)) * .5)
                else:
                    self.pargs.setdefault(
                        'ybound', 1/float(abs(self.span)) * .5)
            kwargs.setdefault('bottom', self.pargs.get('ybound', None))
            label = kwargs.pop('label', None)
            if arr.size:
                ax.hist(arr, label=label, weights=weights, **kwargs)
            else:
                ax.plot([], label=label)

        # customise plot
        for key, val in self.pargs.iteritems():
            try:
                getattr(ax, 'set_%s' % key)(val)
            except AttributeError:
                setattr(ax, key, val)
        if len(self.channels) > 1:
            plot.add_legend(ax=ax, **legendargs)

        # add extra axes and finalise
        if not plot.colorbars:
            plot.add_colorbar(ax=ax, visible=False)
        return self.finalize()

register_plot(TriggerHistogramPlot)


class TriggerRateDataPlot(TimeSeriesDataPlot):
    """TimeSeriesDataPlot of trigger rate.
    """
    type = 'trigger-rate'
    data = 'triggers'
    _threadsafe = False
    defaults = TimeSeriesDataPlot.defaults.copy()
    defaults.update({'column': None,
                     'legend_bbox_to_anchor': (1.15, 1.1),
                     'legend_markerscale': 3,
                     'ylabel': 'Rate [Hz]'})

    def __init__(self, *args, **kwargs):
        if not 'stride' in kwargs:
            raise ValueError("'stride' must be configured for all rate plots.")
        if 'column' in kwargs and 'bins' not in kwargs:
            raise ValueError("'bins' must be configured for rate plots if "
                             "'column' is given.")
        super(TriggerRateDataPlot, self).__init__(*args, **kwargs)
        self.etg = self.pargs.pop('etg')
        self.column = self.pargs.pop('column')

    @property
    def pid(self):
        try:
            return self._pid
        except AttributeError:
            etg = re_cchar.sub('_', self.etg).upper()
            pid = '%s_%s' % (etg, super(TriggerRateDataPlot, self).pid)
            if self.column:
                self.pid += '_%s' % re_cchar.sub('_', self.column).upper()
            return pid

    @pid.setter
    def pid(self, id_):
        self._pid = str(id_)

    def process(self):
        """Read in all necessary data, and generate the figure.
        """

        # get rate arguments
        stride = self.pargs.pop('stride')
        if self.column:
            cname = get_column_string(self.column)
            bins = self.pargs.pop('bins')
            operator = self.pargs.pop('operator', '>=')
        else:
            bins = ['_']

        # work out labels
        labels = self.pargs.pop('labels', None)
        if isinstance(labels, (unicode, str)):
            labels = labels.split(',')
        elif labels is None and self.column and len(self.channels) > 1:
            labels = []
            for channel, bin in [(c, b) for c in self.channels for b in bins]:
                labels.append(r' '.join([channel, cname, '$%s$' % str(operator),
                                         str(b)]))
        elif labels is None and self.column:
            labels = [r' '.join([cname,'$%s$' % str(operator), str(b)])
                      for b in bins]
        elif labels is None:
            labels = self.channels
        self.pargs['labels'] = map(lambda s: str(s).strip('\n '), labels)

        # generate data
        keys = []
        for channel in self.channels:
            if self.state and not self.all_data:
                valid = self.state.active
            else:
                valid = SegmentList([self.span])
            if '#' in str(channel) or '@' in str(channel):
                key = '%s,%s' % (str(channel), state and str(state) or 'All')
            else:
                key = str(channel)
            table_ = get_triggers(key, self.etg, valid, query=False)
            if self.column:
                rates = binned_event_rates(
                    table_, stride, self.column, bins, operator, self.start,
                    self.end).values()
            else:
                rates = [event_rate(table_, stride, self.start, self.end)]
            for bin, rate in zip(bins, rates):
                rate.channel = channel
                keys.append('%s_%s_EVENT_RATE_%s_%s'
                            % (str(channel), str(self.etg),
                               str(self.column), bin))
                if keys[-1] not in globalv.DATA:
                    add_timeseries(rate, keys[-1])

        # reset channel lists and generate time-series plot
        channels = self.channels
        outputfile = self.outputfile
        self.channels = keys
        out = super(TriggerRateDataPlot, self).process(outputfile=outputfile)
        self.channels = channels
        return out

register_plot(TriggerRateDataPlot)