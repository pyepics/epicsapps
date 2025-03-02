#!/usr/bin/python
"""
PlotFrame
"""

import os
import numpy as np
from functools import partial

import wx
import wx.dataview as dv

from matplotlib import dates

from wxutils import (get_cwd, MenuItem, LEFT, pack, HLine,
                     GridPanel, SimpleText, Button, DARK_THEME)
from wxmplot import PlotPanel
from pyshortcuts import fix_filename, gformat


N_EVENTS = 7

class DatePlotPanel(PlotPanel):
    """subclass PlotPanel to force date formatting"""
    def __init__(self, parent, **kws):
        PlotPanel.__init__(self, parent, **kws)

    def xformatter(self, x, pos):
        " x-axis formatter "
        return self.__date_format(x)

    def __date_format(self, x):
        """ formatter for date x-data. primitive, and probably needs
        improvement, following matplotlib's date methods.
        """
        if x < 1: x = 1
        span = self.axes.xaxis.get_view_interval()
        tmin = max(1.0, span[0])
        tmax = max(2.0, span[1])
        tmin = dates.num2date(tmin, tz=self.dates_tzinfo).timestamp()
        tmax = dates.num2date(tmax, tz=self.dates_tzinfo).timestamp()
        nsec = (tmax - tmin)
        fmt = "%H:%M\n%S"
        frac = None
        if nsec < 0.1:
            frac = "%.6f"
            fmt = "%H:%M:%S\n"
        elif nsec <  25:
            frac = "%.3f"
            fmt = "%H:%M\n%S"
        elif nsec < 600:
            fmt = "%H:%M\n%S sec"
        elif nsec < 5*3600:
            fmt = "%m/%d\n%H:%M"
        elif nsec < 24*7*3600:
            fmt = "%m/%d\n%H:%M"
        else:
            fmt = "%m/%d"

        dtval = dates.num2date(x, tz=self.dates_tzinfo)
        try:
            out = dtval.strftime(fmt)
        except ValueError:
            out = dtval.strftime("%H:%M\n%S")
        if frac is not None:
            try:
                fval = frac % (1.e-6*dtval.microsecond)
                out = out + fval[1:]
            except:
                pass
        return out


class PlotFrame(wx.Frame):
    """
    PVLogger PlotFrame
    """
    help_msg =  """
Left-Click:   to display X,Y coordinates
Left-Drag:    to zoom in on plot region
Right-Click:  display popup menu with choices:
           Zoom out 1 level
           Zoom all the way out
           Configure
           Save Image

With a Plot Legend displayed, click on each label to toggle the display of that trace.

Key bindings (use 'Apple' for 'Ctrl' on MacOSX):

Ctrl-S:     Save plot image to PNG file
Ctrl-C:     Copy plot image to system clipboard
Ctrl-P:     Print plot image

Ctrl-D:     Export data to plain text file

Ctrl-L:     Toggle Display of Plot Legend
Ctrl-G:     Toggle Display of Grid

Ctrl-K:     Show Plot Configure Frame

Ctrl-Q:     Quit
"""

    about_msg =  """PVLogger
Matt Newville <newville@cars.uchicago.edu>"""


    def __init__(self, parent=None, panel=None, title='', size=None,
                 exit_callback=None, user_menus=None, panelkws=None,
                 axisbg=None, output_title='Plot', dpi=150,
                 with_data_process=True, theme=None, **kws):
        if size is None:
            size = (850, 650)
        kws['style'] = wx.DEFAULT_FRAME_STYLE
        kws['size']  = size
        wx.Frame.__init__(self, parent, -1, title, **kws)

        self.SetMinSize((600, 500))
        self.output_title = output_title
        self.exit_callback = exit_callback
        self.parent = parent
        self.panel  = panel
        self.dpi    = dpi
        self.user_menus = user_menus
        self.with_data_process = with_data_process
        self.size = size
        self.events = []
        self.event_lines = []
        self.panelkws = {'dpi': dpi}
        if panelkws is not None:
            self.panelkw.update(panelkws)

        if theme is None or theme.lower().startwith('<auto'):
            theme = 'dark' if DARK_THEME else 'white-background'
        self.theme = theme

        if axisbg is not None:
            self.panelkws['axisbg'] = axisbg
        self.BuildFrame()

    def write_message(self, txt, panel=0):
        """write a message to the Status Bar"""
        self.SetStatusText(txt, panel)

    def set_xylims(self, limits, axes=None):
        """overwrite data for trace t """
        if self.panel is not None:
            self.panel.set_xylims(limits, axes=axes)

    def clear(self):
        """clear plot """
        if self.panel is not None:
            self.panel.clear()

    def unzoom_all(self, event=None):
        """zoom out full data range """
        if self.panel is not None:
            self.panel.unzoom_all(event=event)

    def unzoom(self, event=None):
        """zoom out 1 level, or to full data range """
        if self.panel is not None: self.panel.unzoom(event=event)

    def set_title(self, s):
        "set plot title"
        if self.panel is not None:
            self.panel.set_title(s)

    def set_xlabel(self, s):
        "set plot xlabel"
        if self.panel is not None: self.panel.set_xlabel(s)
        self.panel.canvas.draw()

    def set_ylabel(self, s):
        "set plot xlabel"
        if self.panel is not None: self.panel.set_ylabel(s)
        self.panel.canvas.draw()

    def save_figure(self,event=None, transparent=False, dpi=600):
        """ save figure image to file"""
        if self.panel is not None:
            self.panel.save_figure(event=event,
                                   transparent=transparent, dpi=dpi)

    def configure(self,event=None):
        if self.panel is not None: self.panel.configure(event=event)

    ####
    ## create GUI
    ####
    def BuildFrame(self):
        sbar_widths = [-1, -1, -1]
        sbar = self.CreateStatusBar(len(sbar_widths), wx.CAPTION)
        sfont = sbar.GetFont()
        sfont.SetWeight(wx.BOLD)
        sfont.SetPointSize(10)
        sbar.SetFont(sfont)
        self.SetStatusWidths(sbar_widths)

        panelkws = self.panelkws
        if self.size is not None:
            w, h = self.size
            h = int(0.8*h)
            panelkws.update({'size': (w, h)})

        panelkws.update({'output_title': self.output_title,
                         'with_data_process': self.with_data_process,
                         'theme': self.theme})

        splitter = wx.SplitterWindow(self, style=wx.SP_3DSASH|wx.SP_LIVE_UPDATE)
        splitter.SetMinimumPaneSize(25)

        top = wx.Panel(splitter)
        bot = wx.Panel(splitter)
        top.SetMinSize((500, 500))
        bot.SetMinSize((500, 100))

        self.panel = DatePlotPanel(top, **panelkws)
        self.panel.messenger = self.write_message
        self.panel.nstatusbar = sbar.GetFieldsCount()
        self.panel.cursor_callback = self.onCursor

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.panel, 1, LEFT|wx.GROW|wx.ALL|wx.EXPAND)
        pack(top, sizer)

        bpanel = GridPanel(bot, ncols=4, nrows=10, pad=1, itemstyle=LEFT)

        wids = self.wids = {}
        def txt(label, wid):
            return SimpleText(bpanel, label, size=(wid, -1), style=LEFT)

        clear_btn = Button(bpanel, 'Clear Events', size=(175, -1),
                           action=self.clear_events)

        bpanel.Add(txt(' Events: ', 400), dcol=2, newrow=True)
        bpanel.Add(clear_btn, dcol=1)
        bpanel.Add((5, 5))
        bpanel.Add(txt(' PV Description', 180), newrow=True)
        bpanel.Add(txt(' PV Name ', 200))
        bpanel.Add(txt(' Date/Time ', 180))
        bpanel.Add(txt( ' Value ', 350))
        bpanel.Add((5, 5))
        bpanel.Add(HLine(bpanel, size=(850, 3)), dcol=4, newrow=True)
        bpanel.Add((5, 5))
        for i in range(N_EVENTS):
            wids[f'lab_{i}']  = txt(' - ', 180)
            wids[f'pv_{i}']  = txt(' - ', 200)
            wids[f'dt_{i}']  = txt(' - ', 180)
            wids[f'val_{i}'] = txt(' - ', 350)
            bpanel.Add(wids[f'lab_{i}'], newrow=True)
            bpanel.Add(wids[f'pv_{i}'])
            bpanel.Add(wids[f'dt_{i}'])
            bpanel.Add(wids[f'val_{i}'])
        bpanel.Add((5, 5))
        bpanel.Add(HLine(bpanel, size=(850, 3)), dcol=4, newrow=True)
        bpanel.pack()

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(bpanel, 1, LEFT|wx.GROW|wx.ALL|wx.EXPAND)
        pack(bot, sizer)

        self.BuildMenu()

        splitter.SplitHorizontally(top, bot, 1)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(splitter, 1, wx.GROW|wx.ALL, 5)
        pack(self, sizer)
        self.SetAutoLayout(True)
        self.SetSizer(sizer)
        w0, h0 = self.GetSize()
        self.SetSize((w0+5, h0+10))
        self.Show()


    def add_event(self, evdat):
        h = (evdat['desc'], evdat['name'], evdat['mpldate'], evdat['value'])
        if h not in self.events:
            self.events.append(h)
            xline = self.panel.add_vline(evdat['mpldate'],
                                         color=evdat['color'],
                                         report_data=evdat)
            self.event_lines.append(xline)

    def clear_events(self, event=None):
        for i in range(N_EVENTS):
            for a in ('lab', 'pv', 'dt', 'val'):
                self.wids[f'{a}_{i}'].SetLabel('-')
        for lx in self.event_lines:
            try:
                lx.remove()
            except:
                pass
        self.event_lines = []
        self.events = []
        self.panel.conf.marker_report_data = []
        self.panel.canvas.draw()

    def reshow_events(self, event=None):
        events = self.events[:]
        self.events = []
        for evdat in events:
            self.add_event(evdat)

    def onCursor(self, x=None, y=None, message='', marker_data=None, **kws):
        if marker_data is not None:
            wids = self.wids
            for mdata in marker_data:
                x, y, label, edata = mdata
                # push old events
                for i in reversed(range(1, N_EVENTS)):
                    for a in ('lab', 'pv', 'dt', 'val'):
                        wids[f'{a}_{i}'].SetLabel(wids[f'{a}_{i-1}'].GetLabel())
                wids['lab_0'].SetLabel(edata['desc'])
                wids['pv_0'].SetLabel(edata['name'])
                wids['dt_0'].SetLabel(edata['datetime'])
                wids['val_0'].SetLabel(edata['value'])


    def Build_FileMenu(self, extras=None):
        mfile = wx.Menu()
        MenuItem(self, mfile, "&Save Image\tCtrl+S",
                 "Save Image of Plot (PNG, SVG, JPG)",
                 action=self.save_figure)
        MenuItem(self, mfile, "&Copy\tCtrl+C",
                 "Copy Plot Image to Clipboard",
                 self.Copy_to_Clipboard)
        MenuItem(self, mfile, "Export Data\tCtrl+D",
                 "Export Data to Text File",
                 self.onExport)

        if extras is not None:
            for text, helptext, callback in extras:
                MenuItem(self, mfile, text, helptext, callback)

        mfile.AppendSeparator()
        MenuItem(self, mfile, 'Page Setup...', 'Printer Setup',
                 self.PrintSetup)

        MenuItem(self, mfile, 'Print Preview...', 'Print Preview',
                 self.PrintPreview)

        MenuItem(self, mfile, "&Print\tCtrl+P", "Print Plot",
                 self.Print)

        mfile.AppendSeparator()
        MenuItem(self, mfile, "E&xit\tCtrl+Q", "Exit", self.onExit)
        return mfile

    def Copy_to_Clipboard(self, event=None):
        self.panel.canvas.Copy_to_Clipboard(event=event)

    def PrintSetup(self, event=None):
        self.panel.PrintSetup(event=event)

    def PrintPreview(self, event=None):
        self.panel.PrintPreview(event=event)

    def Print(self, event=None):
        self.panel.Print(event=event)

    def onZoomStyle(self, event=None, style='both x and y'):
        self.panel.conf.zoom_style = style

    def BuildMenu(self):
        mfile = self.Build_FileMenu()
        mopts = wx.Menu()
        MenuItem(self, mopts, "Configure Plot\tCtrl+K",
                 "Configure Plot styles, colors, labels, etc",
                 self.panel.configure)

        MenuItem(self, mopts, "Toggle Legend\tCtrl+L",
                 "Toggle Legend Display",
                 self.panel.toggle_legend)
        MenuItem(self, mopts, "Toggle Grid\tCtrl+G",
                 "Toggle Grid Display",
                 self.panel.toggle_grid)

        mopts.AppendSeparator()

        MenuItem(self, mopts, "Zoom X and Y\tCtrl+W",
                 "Zoom on both X and Y",
                 partial(self.onZoomStyle, style='both x and y'),
                 kind=wx.ITEM_RADIO, checked=True)
        MenuItem(self, mopts, "Zoom X Only\tCtrl+X",
                 "Zoom X only",
                 partial(self.onZoomStyle, style='x only'),
                 kind=wx.ITEM_RADIO)

        MenuItem(self, mopts, "Zoom Y Only\tCtrl+Y",
                 "Zoom Y only",
                 partial(self.onZoomStyle, style='y only'),
                 kind=wx.ITEM_RADIO)

        MenuItem(self, mopts, "Undo Zoom/Pan\tCtrl+Z",
                 "Zoom out / Pan out to previous view",
                 self.panel.unzoom)
        MenuItem(self, mopts, "Zoom all the way out",
                 "Zoom out to full data range",
                 self.panel.unzoom_all)

        mopts.AppendSeparator()

        logmenu = wx.Menu()
        for label in self.panel.conf.log_choices:
            xword, yword = label.split(' / ')
            xscale = xword.replace('x', '').strip()
            yscale = yword.replace('y', '').strip()
            MenuItem(self, logmenu, label, label,
                     partial(self.panel.set_logscale, xscale=xscale, yscale=yscale),
                     kind=wx.ITEM_RADIO)

        mopts.AppendSubMenu(logmenu, "Linear/Log Scale ")

        transmenu = None
        if self.panel.conf.with_data_process:
            transmenu = wx.Menu()
            MenuItem(self, transmenu, "Toggle Derivative", "Toggle Derivative",
                     self.panel.toggle_deriv, kind=wx.ITEM_CHECK)

            for expr in self.panel.conf.data_expressions:
                label = expr
                if label is None:
                    label = 'original Y(X)'
                MenuItem(self, transmenu, label, label,
                         partial(self.panel.process_data, expr=expr),
                         kind=wx.ITEM_RADIO)

        if transmenu is not None:
            mopts.AppendSubMenu(transmenu, "Transform Y(X)")

        mhelp = wx.Menu()
        MenuItem(self, mhelp, "Quick Reference",
                     "Quick Reference for PlotFrame", self.onHelp)

        mbar = wx.MenuBar()
        mbar.Append(mfile, 'File')
        mbar.Append(mopts, '&Options')
        if self.user_menus is not None:
            for title, menu in self.user_menus:
                mbar.Append(menu, title)

        mbar.Append(mhelp, '&Help')

        self.SetMenuBar(mbar)
        self.Bind(wx.EVT_CLOSE, self.onExit)

    def BindMenuToPanel(self, panel=None):
        pass

    def onAbout(self, event=None):
        dlg = wx.MessageDialog(self, self.about_msg, "About WXMPlot",
                               wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def onExport(self, event=None):
        if (self.panel is None or
            not callable(getattr(self, 'ExportTextFile', None))):
            return

        try:
            title = self.panel.conf.title
        except AttributeError:
            title = None

        if title is None:
            title = self.output_title
        if title is None:
            title = self.GetTitle()

        title = title.strip()
        if title in (None, '', 'None'):
            title = 'wxmplot'

        fname = fix_filename(title + '.dat')

        origdir = get_cwd()
        file_choices = "DAT (*.dat)|*.dat|ALL FILES (*.*)|*.*"
        dlg = wx.FileDialog(self, message='Export Data to Text File',
                            defaultDir=origdir,
                            defaultFile=fname,
                            wildcard=file_choices,
                            style=wx.FD_SAVE|wx.FD_CHANGE_DIR)

        if dlg.ShowModal() == wx.ID_OK:
            self.ExportTextFile(dlg.GetPath(), title=title)
        os.chdir(origdir)

    def onHelp(self, event=None):
        dlg = wx.MessageDialog(self, self.help_msg, "WXMPlot Quick Reference",
                               wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def onExit(self, event=None):
        try:
            if callable(self.exit_callback):
                self.exit_callback()
        except:
            pass
        try:
            if self.panel is not None:
                self.panel.win_config.Close(True)
            if self.panel is not None:
                self.panel.win_config.Destroy()
        except:
            pass

        try:
            self.Destroy()
        except:
            pass

    def get_figure(self):
        """return MPL plot figure"""
        return self.panel.fig

    def add_text(self, text, x, y, **kws):
        """add text to plot"""
        self.panel.add_text(text, x, y, **kws)

    def add_arrow(self, x1, y1, x2, y2, **kws):
        """add arrow to plot"""
        self.panel.add_arrow(x1, y1, x2, y2, **kws)

    def plot(self, x, y, **kw):
        """plot after clearing current plot """
        self.panel.plot(x, y, **kw)
        self._adjust_framesize(side=kw.get('side', None))

    def oplot(self, x, y, **kw):
        """generic plotting method, overplotting any existing plot """
        self.panel.oplot(x, y, **kw)
        self._adjust_framesize(side=kw.get('side', None))

    def _adjust_framesize(self, side=None):
        if side is not None and side.startswith('right'):
            fsize = self.GetSize()
            if side == 'right':
                fsize[0] = int(fsize[0]*1.05)
            else:
                fsize[0] = int(fsize[0]*1.10)
            self.SetSize(fsize)


    def plot_many(self, datalist, **kws):
        self.panel.plot_many(datalist, **kws)

    def scatterplot(self, x, y, **kw):
        """plot after clearing current plot """
        self.panel.scatterplot(x, y, **kw)

    def draw(self):
        "explicit draw of underlying canvas"
        self.panel.canvas.draw()

    def clear(self):
        "clear plot"
        self.panel.clear()

    def reset_config(self):
        self.panel.reset_config()

    def update_line(self, t, x, y, **kw):
        """overwrite data for trace t """
        self.panel.update_line(t, x, y, **kw)

    def ExportTextFile(self, fname, title='unknown plot'):
        "save plot data to external file"

        buff = ["# Plot Data for %s" % title,
                "#---------------------------------"]

        out = []
        labels = []
        itrace = 0
        for ax in self.panel.fig.get_axes():
            for line in ax.lines:
                itrace += 1
                x = line.get_xdata()
                y = line.get_ydata()
                ylab = line.get_label()

                if len(ylab) < 1:
                    ylab = 'Y%i' % itrace
                for c in ' .:";|/\\(){}[]\'&^%*$+=-?!@#':
                    ylab = ylab.replace(c, '_')
                xlab = (' X%d' % itrace + ' '*3)[:4]
                ylab = ' '*(18-len(ylab)) + ylab + '  '
                out.extend([x, y])
                labels.extend([xlab, ylab])

        if itrace == 0:
            return

        buff.append('# %s' % (' '.join(labels)))

        npts = [len(a) for a in out]
        for i in range(max(npts)):
            oline = []
            for a in out:
                d = np.nan
                if i < len(a):
                    d = a[i]
                oline.append(gformat(d, 12))
            buff.append(' '.join(oline))

        buff.append('')
        with open(fname, 'w') as fout:
            fout.write("\n".join(buff))
        fout.close()
        self.write_message("Exported data to '%s'" % fname, panel=0)

    def onSelectEvent(self, evt=None):
        if self.event_table is None:
            return
        if not self.event_table.HasSelection():
            return
        item = self.event_table.GetSelectedRow()
        en = self.events[item]

        if self.highlight_events is not None:
            self.highlight_events.remove()

        print("would hightlight event ", item)
        self.draw()
