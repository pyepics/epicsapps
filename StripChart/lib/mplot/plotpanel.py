#!/usr/bin/python
##
## MPlot PlotPanel: a wx.Panel for 2D line plotting, using matplotlib
##

import sys
import time
import os
import wx

import matplotlib
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas

from config import PlotConfig
from configframe import PlotConfigFrame
from utils import Printer

class PlotPanel(wx.Panel):
    """
    MatPlotlib 2D plot as a wx.Panel, suitable for embedding
    in any wx.Frame.   This does provide a right-click popup
    menu for configuration, zooming, saving an image of the
    figure, and Ctrl-C for copy-image-to-clipboard.

    For more features, see PlotFrame, which embeds a PlotPanel
    and also provides, a Menu, StatusBar, and Printing support.
    """
    def __init__(self, parent, messenger=None,
                 size=(5.5, 3.40), dpi=100,
                 trace_color_callback=None, **kwds):

        self.is_macosx = False
        if os.name == 'posix':
            if os.uname()[0] == 'Darwin':
                self.is_macosx = True

        self.messenger = messenger
        self.trace_color_callback = trace_color_callback
        if messenger is None:
            self.messenger = self.__def_messenger

        self.cursor_mode = 'cursor'
        self.cursor_save = 'cursor'
        self._yfmt = '%.4f'
        self._y2fmt = '%.4f'
        self._xfmt = '%.4f'
        self.use_dates = False
        self.show_config_popup = True
        self.launch_dir  = os.getcwd()

        self.mouse_uptime = time.time()
        self.zoom_lims = []           # store x, y coords zoom levels
        self.zoom_ini  = (-1, -1, -1, -1)  # store init axes, x, y coords for zoom-box
        self.rbbox = None
        self.parent = parent
        self.printer = Printer(self)


        matplotlib.rc('axes', axisbelow=True)
        matplotlib.rc('lines', linewidth=2)
        matplotlib.rc('xtick',  labelsize=11, color='k')
        matplotlib.rc('ytick',  labelsize=11, color='k')
        matplotlib.rc('grid',  linewidth=0.5, linestyle='-')

        self.conf = PlotConfig() # trace_color_callback=self.trace_color_callback)
        self.data_range = {}
        self.win_config = None
        self.cursor_callback = None
        self.parent    = parent
        self.figsize = size
        self.dpi     = dpi

    def plot(self, xdata, ydata, side='left', label=None, dy=None,
             color=None,  style =None, linewidth=None,
             marker=None,   markersize=None,   drawstyle=None,
             use_dates=False, ylog_scale=False, grid=None, xylims=None,
             title=None,  xlabel=None, ylabel=None, y2label=None, **kw):
        """
        plot (that is, create a new plot: clear, then oplot)
        """

        allaxes = self.fig.get_axes()
        if len(allaxes) > 1:
            for ax in allaxes[1:]:
                self.fig.delaxes(ax)

        axes = self.axes
        if side == 'right':
            axes = self.create_right_axes()
        axes.cla()
        self.conf.ntrace  = 0
        self.data_range[axes] = ( (min(xdata), max(xdata)),
                                  (min(ydata), max(ydata)) )
        if xlabel is not None:
            self.set_xlabel(xlabel)
        if ylabel is not None:
            self.set_ylabel(ylabel)
        if y2label is not None:
            self.set_y2label(y2label)
        if title  is not None:
            self.set_title(title)
        if use_dates is not None:
            self.use_dates  = use_dates

        if grid:
            self.conf.show_grid = grid

        return self.oplot(xdata, ydata, side=side, label=label,
                          color=color, style=style, ylog_scale=ylog_scale,
                          drawstyle=drawstyle,
                          linewidth=linewidth, dy=dy, xylims=None,
                          marker=marker, markersize=markersize,  **kw)

    def oplot(self, xdata, ydata, side='left', label=None, color=None,
              style=None, ylog_scale=False,
              linewidth=None, marker=None, markersize=None,
              drawstyle=None, dy=None, xylims=None,
              autoscale=True, refresh=True, yaxis='left', **kw):
        """ basic plot method, overplotting any existing plot """
        # set y scale to log/linear
        yscale = 'linear'
        if ylog_scale and min(ydata) > 0:
            yscale = 'log'

        axes = self.axes
        if side == 'right':
            axes = self.create_right_axes()

        axes.set_yscale(yscale, basey=10)

        if dy is None:
            _lines = axes.plot(xdata, ydata, drawstyle=drawstyle)
        else:
            _lines = axes.errorbar(xdata, ydata, yerr=dy)

        if axes not in self.data_range:
            self.data_range[axes] = ((min(xdata), max(xdata)),
                                     (min(ydata), max(ydata)))

        dr = self.data_range[axes]
        self.data_range[axes]    = ( (min(dr[0][0], min(xdata)),
                                      max(dr[0][1], max(xdata))),
                                     (min(dr[1][0], min(ydata)),
                                      max(dr[1][1], max(ydata))))

        cnf  = self.conf
        n    = cnf.ntrace

        if label == None:
            label = 'trace %i' % (n+1)
        cnf.set_trace_label(label)
        cnf.lines[n] = _lines

        if color:
            cnf.set_trace_color(color)
        if style:
            cnf.set_trace_style(style)
        if marker:
            cnf.set_trace_marker(marker)
        if linewidth is not None:
            cnf.set_trace_linewidth(linewidth)
        if markersize is not None:
            cnf.set_trace_markersize(markersize)

        if axes == self.axes:
            axes.yaxis.set_major_formatter(FuncFormatter(self.yformatter))
        else:
            axes.yaxis.set_major_formatter(FuncFormatter(self.y2formatter))

        axes.xaxis.set_major_formatter(FuncFormatter(self.xformatter))

        if refresh:
            cnf.refresh_trace(n)
            cnf.relabel()

        if xylims is not None:
            self.set_xylims(xylims, autoscale=False)
        elif autoscale:
            axes.autoscale_view()
            self.unzoom_all()
        if self.conf.show_grid and axes == self.axes:
            # I'm sure there's a better way...
            for i in axes.get_xgridlines()+axes.get_ygridlines():
                i.set_color(self.conf.grid_color)
            axes.grid(True)
        else:
            axes.grid(False)

        self.canvas.draw()
        self.canvas.Refresh()
        cnf.ntrace = cnf.ntrace + 1
        return _lines

    def set_xylims(self, lims, axes=None, side=None, autoscale=True):
        """ update xy limits of a plot, as used with .update_line() """

        if axes is None:
            axes = self.axes
        if side == 'right' and len(self.fig.get_axes()) == 2:
            axes = self.fig.get_axes()[1]

        if autoscale:
            (xmin, xmax), (ymin, ymax) = self.data_range[axes]
        else:
            (xmin, xmax), (ymin, ymax) = lims

        axes.set_xbound(axes.xaxis.get_major_locator().view_limits(xmin, xmax))
        axes.set_ybound(axes.yaxis.get_major_locator().view_limits(ymin, ymax))
        axes.set_xlim((xmin, xmax), emit=True)
        axes.set_ylim((ymin, ymax), emit=True)
        # axes.update_datalim(((xmin, ymin), (xmax, ymax)))


    def clear(self):
        """ clear plot """
        for ax in self.fig.get_axes():
            ax.cla()

        self.conf.ntrace = 0
        self.conf.xlabel = ''
        self.conf.ylabel = ''
        self.conf.y2label = ''
        self.conf.title  = ''

    def unzoom_all(self, event=None):
        """ zoom out full data range """
        if len(self.zoom_lims) > 0:
            self.zoom_lims = [self.zoom_lims[0]]
        self.unzoom(event)

    def unzoom(self, event=None):
        """ zoom out 1 level, or to full data range """
        if len(self.zoom_lims) < 1:
            return

        for ax, lims in self.zoom_lims.pop().items():
            self.set_xylims(lims=lims, axes=ax, autoscale=False)

        self.write_message('zoom level %i' % (len(self.zoom_lims)))
        self.canvas.draw()

    def configure(self, event=None):
        try:
            self.win_config.Raise()
        except:
            self.win_config = PlotConfigFrame(self.conf,
                                              trace_color_callback=self.trace_color_callback)


    ####
    ## create GUI
    ####
    def BuildPanel(self, **kwds):
        """ builds basic GUI panel and popup menu"""

        wx.Panel.__init__(self, self.parent, -1, **kwds)

        self.fig   = Figure(self.figsize, dpi=self.dpi)

        self.axes  = self.fig.add_axes([0.12, 0.12, 0.76, 0.76],
                                       axisbg='#FEFFFE')

        self.canvas = FigureCanvas(self, -1, self.fig)
        self.printer.canvas = self.canvas
        self.set_bg()
        self.conf.canvas = self.canvas
        self.canvas.SetCursor(wx.StockCursor(wx.CURSOR_CROSS))

        # overwrite ScalarFormatter from ticker.py here:
        self.axes.xaxis.set_major_formatter(FuncFormatter(self.xformatter))
        self.axes.yaxis.set_major_formatter(FuncFormatter(self.yformatter))

        # This way of adding to sizer allows resizing
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.canvas, 2, wx.LEFT|wx.TOP|wx.BOTTOM|wx.EXPAND, 0)
        self.SetAutoLayout(True)
        self.SetSizer(sizer)
        self.Fit()

        self.addCanvasEvents()

    def addCanvasEvents(self):
        # use matplotlib events
        self.canvas.mpl_connect("motion_notify_event",
                                self.__onMouseMotionEvent)
        self.canvas.mpl_connect("button_press_event",
                                self.__onMouseButtonEvent)
        self.canvas.mpl_connect("button_release_event",
                                self.__onMouseButtonEvent)
        self.canvas.mpl_connect("key_press_event",
                                self.__onKeyEvent)

        self.rbbox = None
        self.zdc = None
        # build pop-up menu for right-click display
        self.popup_unzoom_all = wx.NewId()
        self.popup_unzoom_one = wx.NewId()
        self.popup_config     = wx.NewId()
        self.popup_save   = wx.NewId()
        self.popup_menu = wx.Menu()
        self.popup_menu.Append(self.popup_unzoom_one, 'Unzoom')
        self.popup_menu.Append(self.popup_unzoom_all, 'Zoom all the way out')
        self.popup_menu.AppendSeparator()
        if self.show_config_popup:
            self.popup_menu.Append(self.popup_config,'Configure')

        self.popup_menu.Append(self.popup_save,  'Save Image')
        self.Bind(wx.EVT_MENU, self.unzoom,       id=self.popup_unzoom_one)
        self.Bind(wx.EVT_MENU, self.unzoom_all,   id=self.popup_unzoom_all)
        self.Bind(wx.EVT_MENU, self.save_figure,  id=self.popup_save)
        self.Bind(wx.EVT_MENU, self.configure,    id=self.popup_config)


    def update_line(self, trace,  xdata, ydata, side='left'):
        """ update a single trace, for faster redraw """
        x = self.conf.get_mpl_line(trace)
        x.set_data(xdata, ydata)
        axes = self.axes
        if side == 'right':
            axes = self.create_right_axes()
        dr = self.data_range[axes]
        self.data_range[axes] = ( (min(dr[0][0], xdata.min()),
                                   max(dr[0][1], xdata.max())),
                                  (min(dr[1][0], ydata.min()),
                                   max(dr[1][1], ydata.max())) )
        # this defeats zooming, which gets ugly in this fast-mode anyway.
        self.cursor_mode = 'cursor'
        #self.canvas.draw()

    ####
    ## GUI events
    ####
    def reportLeftDown(self, event=None):
        if event is None:
            return
        ex, ey = event.x, event.y
        msg = ''
        try:
            x, y = self.axes.transData.inverted().transform((ex, ey))
        except:
            x, y = event.xdata, event.ydata

        msg = ("X,Y= %s, %s" % (self._xfmt, self._yfmt)) % (x, y)

        if len(self.fig.get_axes()) > 1:
            ax2 = self.fig.get_axes()[1]
            try:
                x2, y2 = ax2.transData.inverted().transform((ex, ey))
                msg = "X,Y,Y2= %s, %s, %s" % (self._xfmt, self._yfmt, self._y2fmt) % (x, y, y2)
            except:
                pass
        self.write_message(msg,  panel=0)
        if hasattr(self.cursor_callback , '__call__'):
            self.cursor_callback(x=event.xdata, y=event.ydata)


    def onLeftDown(self, event=None):
        """ left button down: save and report x,y coords"""
        if event == None:
            return
        if event.inaxes not in self.fig.get_axes():
            return

        self.zoom_ini = (event.x, event.y, event.xdata, event.ydata)
        if event.inaxes is not None:
            self.reportLeftDown(event=event)

        self.cursor_mode = 'zoom'
        self.ForwardEvent(event=event.guiEvent)

    def onLeftUp(self, event=None):
        """ left button up: zoom in on selected region"""
        if event is None:
            return

        ini_x, ini_y, ini_xd, ini_yd = self.zoom_ini
        try:
            dx = abs(ini_x - event.x)
            dy = abs(ini_y - event.y)
        except:
            dx, dy = 0, 0
        t0 = time.time()

        if ((dx > 4) and (dy > 4) and (t0-self.mouse_uptime)>0.1 and
            self.cursor_mode == 'zoom'):
            self.mouse_uptime = t0
            olims = {}
            nlims = {}
            for ax in self.fig.get_axes():
                olims[ax] = ax.get_xlim(), ax.get_ylim()
            self.zoom_lims.append(olims)
            msg = 'zoom level %i ' % (len(self.zoom_lims))
            # for multiple axes, we first collect all the new limits, and only
            # then apply them
            for ax in self.fig.get_axes():
                try:
                    x1, y1 = ax.transData.inverted().transform((event.x, event.y))
                except:
                    x1, y1 =  event.xdata, event.ydata
                try:
                    x0, y0 = ax.transData.inverted().transform((ini_x, ini_y))
                except:
                    x0, y0 =  ini_xd, ini_yd
                    print 'could not invert event data (ini)'
                    print ini_x, ini_y, event.xdata, event.ydata

                nlims[ax] = ((min(x0, x1), max(x0, x1)),
                             (min(y0, y1), max(y0, y1)))

                                        
            # now appply limits:
            for ax in nlims:
                self.set_xylims(lims=nlims[ax], axes=ax, autoscale=False)

            self.write_message(msg, panel=1)

        self.rbbox = None
        self.cursor_mode = 'cursor'
        self.canvas.draw()
        self.ForwardEvent(event=event.guiEvent)

    def ForwardEvent(self, event=None):
        """finish wx event, forward it to other wx objects"""
        if event is not None:
            event.Skip()
            if os.name == 'posix' or  self.HasCapture():
                try:
                    self.ReleaseMouse()
                except:
                    pass

    def onRightDown(self, event=None):
        """ right button down: show pop-up"""
        if event is None:
            return
        self.cursor_mode = 'cursor'
        # note that the matplotlib event location have to be converted
        if event.inaxes is not None:
            pos = event.guiEvent.GetPosition()
            wx.CallAfter(self.PopupMenu, self.popup_menu, pos)
        self.ForwardEvent(event=event.guiEvent)

    def onRightUp(self, event=None):
        """ right button up: put back to cursor mode"""
        if event is None:
            return
        self.cursor_mode = 'cursor'
        self.ForwardEvent(event=event.guiEvent)


    def __def_messenger(self, s, panel=0):
        """ default, generic messenger: write to stdout"""
        sys.stdout.write(s)

    def __date_format(self, x):
        """ formatter for date x-data. primitive, and probably needs
        improvement, following matplotlib's date methods.
        """
        interval = self.axes.xaxis.get_view_interval()
        ticks = self.axes.xaxis.get_major_locator()()
        span = max(interval) - min(interval)
        fmt = "%m/%d"
        if span < 1800:
            fmt = "%I%p \n%M:%S"
        elif span < 86400*5:
            fmt = "%m/%d \n%H:%M"
        elif span < 86400*20:
            fmt = "%m/%d"

        s = time.strftime(fmt, time.localtime(x))
        return s

    def xformatter(self, x, pos):
        " x-axis formatter "
        if self.use_dates:
            return self.__date_format(x)
        else:
            return self.__format(x, type='x')

    def yformatter(self, y, pos):
        " y-axis formatter "
        return self.__format(y, type='y')

    def y2formatter(self, y, pos):
        " y-axis formatter "
        return self.__format(y, type='y2')

    def __format(self, x, type='x'):
        """ home built tick formatter to use with FuncFormatter():
        x     value to be formatted
        type  'x' or 'y' or 'y2' to set which list of ticks to get

        also sets self._yfmt/self._xfmt for statusbar
        """
        fmt, v = '%1.5g','%1.5g'
        if type == 'y':
            ax = self.axes.yaxis
        elif type == 'y2' and len(self.fig.get_axes()) > 1:
            ax =  self.fig.get_axes()[1].yaxis
        else:
            ax = self.axes.xaxis

        try:
            dtick = 0.1 * ax.get_view_interval().span()
        except:
            dtick = 0.2
        try:
            ticks = ax.get_major_locator()()
            dtick = abs(ticks[1] - ticks[0])
        except:
            pass
        if   dtick > 99999:
            fmt, v = ('%1.6e', '%1.7g')
        elif dtick > 0.99:
            fmt, v = ('%1.0f', '%1.2f')
        elif dtick > 0.099:
            fmt, v = ('%1.1f', '%1.3f')
        elif dtick > 0.0099:
            fmt, v = ('%1.2f', '%1.4f')
        elif dtick > 0.00099:
            fmt, v = ('%1.3f', '%1.5f')
        elif dtick > 0.000099:
            fmt, v = ('%1.4f', '%1.6e')
        elif dtick > 0.0000099:
            fmt, v = ('%1.5f', '%1.6e')

        s =  fmt % x
        s.strip()
        s = s.replace('+', '')
        while s.find('e0')>0:
            s = s.replace('e0','e')
        while s.find('-0')>0:
            s = s.replace('-0','-')
        if type == 'y':
            self._yfmt = v
        if type == 'y2':
            self._y2fmt = v
        if type == 'x':
            self._xfmt = v
        return s

    def __onKeyEvent(self, event=None):
        """ handles key events on canvas
        """
        if event is None:
            return
        key = event.guiEvent.GetKeyCode()
        if (key < wx.WXK_SPACE or  key > 255):
            return
        ckey = chr(key)
        mod  = event.guiEvent.ControlDown()
        if self.is_macosx:
            mod = event.guiEvent.MetaDown()
        if mod:
            if ckey == 'C':
                self.canvas.Copy_to_Clipboard(event)
            elif ckey == 'S':
                self.save_figure(event)
            elif ckey == 'K':
                self.configure(event)
            elif ckey == 'Z':
                self.unzoom_all(event)
            elif ckey == 'P':
                self.canvas.printer.Print(event)

    def __onMouseButtonEvent(self, event=None):
        """ general mouse press/release events. Here, event is
        a MplEvent from matplotlib.  This routine just dispatches
        to the appropriate onLeftDown, onLeftUp, onRightDown, onRightUp....
        methods.
        """
        if event is None:
            return
        # print 'MouseButtonEvent ', event, event.button
        button = event.button or 1
        handlers = {(1, 'button_press_event'):   self.onLeftDown,
                    (1, 'button_release_event'): self.onLeftUp,
                    (3, 'button_press_event'):   self.onRightDown,
                    }
        # (3,'button_release_event'): self.onRightUp}

        handle_event = handlers.get((button, event.name), None)
        if hasattr(handle_event, '__call__'):
            handle_event(event)

    def __onMouseMotionEvent(self, event=None):
        """Draw a cursor over the axes"""
        if event is None:
            return

        ax = event.inaxes
        if self.cursor_mode == 'cursor':
            if ax is not None:
                self.reportMotion(event=event)
            return
        try:
            x, y  = event.x, event.y
        except:
            self.cursor_mode == 'cursor'
            return

        ini_x, ini_y, ini_xd, ini_yd = self.zoom_ini
        x0     = min(x, ini_x)
        ymax   = max(y, ini_y)
        width  = abs(x -ini_x)
        height = abs(y -ini_y)
        y0     = self.canvas.figure.bbox.height - ymax

        zdc = wx.ClientDC(self.canvas)
        zdc.SetLogicalFunction(wx.XOR)
        zdc.SetBrush(wx.TRANSPARENT_BRUSH)
        zdc.SetPen(wx.Pen('White', 2, wx.SOLID))
        zdc.ResetBoundingBox()
        zdc.BeginDrawing()

        # erase previous box
        if self.rbbox is not None:
            zdc.DrawRectangle(*self.rbbox)

        self.rbbox = (x0, y0, width, height)
        zdc.DrawRectangle(*self.rbbox)
        zdc.EndDrawing()


    def reportMotion(self, event=None):
        fmt = "X,Y= %s, %s" % (self._xfmt, self._yfmt)
        y  = event.ydata
        if len(self.fig.get_axes()) > 1:
            try:
                x, y = self.axes.transData.inverted().transform((event.x, event.y))
            except:
                pass
        self.write_message(fmt % (event.xdata, y), panel=1)

    def Print(self, event=None, **kw):
        self.printer.Print(event=event, **kw)

    def PrintPreview(self, event=None, **kw):
        self.printer.Preview(event=event, **kw)

    def PrintSetup(self, event=None, **kw):
        self.printer.Setup(event=event, **kw)

    def create_right_axes(self):
        "create right-hand y axes"
        if len(self.fig.get_axes()) < 2:
            ax = self.axes.twinx()

        return self.fig.get_axes()[1]

    def get_xylims(self, side='left'):
        axes = self.axes
        if side == 'right':
            axes = self.create_right_axes()

        return  axes.get_xlim(), axes.get_ylim()

    def set_title(self, s):
        "set plot title"
        self.conf.relabel(title=s)

    def set_ylabel(self, s):
        "set plot ylabel"
        self.conf.relabel(ylabel=s)

    def set_y2label(self, s):
        "set plot ylabel"
        self.conf.relabel(y2label=s)

    def set_xlabel(self, s):
        "set plot xlabel"
        self.conf.relabel(xlabel=s)

    def set_bg(self, color= None):
        if color is None:
            color = '#FEFFEE'
        self.fig.set_facecolor(color)

    def save_figure(self, event=None):
        """ save figure image to file"""
        file_choices = "PNG (*.png)|*.png"
        ofile = self.conf.title.strip()
        if len(ofile) > 64:
            ofile = ofile[:63].strip()
        if len(ofile) < 1:
            ofile = 'plot'

        for c in ' :";|/\\': # "
            ofile = ofile.replace(c, '_')

        ofile = ofile + '.png'

        dlg = wx.FileDialog(self, message='Save Plot Figure as...',
                            defaultDir = os.getcwd(),
                            defaultFile=ofile,
                            wildcard=file_choices,
                            style=wx.SAVE|wx.CHANGE_DIR)

        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            self.canvas.print_figure(path, dpi=600)
            if (path.find(self.launch_dir) ==  0):
                path = path[len(self.launch_dir)+1:]
            self.write_message('Saved plot to %s' % path)

    def write_message(self, s, panel=0):
        """ write message to message handler
        (possibly going to GUI statusbar)"""
        self.messenger(s, panel=panel)
