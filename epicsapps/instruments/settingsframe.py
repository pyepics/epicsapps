import sys
import time

import wx
import wx.lib.scrolledpanel as scrolled

from wxutils import (NumericCombo, pack, SimpleText, FileSave,
                     FileOpen, SelectWorkdir, Button)

from .utils import GUIColors, set_font_with_children

class SettingsFrame(wx.Frame) :
    """ GUI Configure Frame"""
    def __init__(self, parent=None, pos=(-1, -1), db=None):

        self.parent = parent
        self.db = db

        style    = wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL
        labstyle  = wx.ALIGN_LEFT|wx.ALL
        rlabstyle = wx.ALIGN_RIGHT|wx.ALL
        tstyle    = wx.ALIGN_LEFT

        wx.Frame.__init__(self, None, -1, 'Epics Instruments:  Settings')

        font = parent.GetFont()

        titlefont  = self.GetFont()
        titlefont.PointSize += 2
        titlefont.SetWeight(wx.BOLD)

        sizer = wx.GridBagSizer(4, 4)
        panel = wx.Panel(self)
        self.colors = GUIColors()

        title = SimpleText(panel, 'Positions Settings:',    font=titlefont,
                           minsize=(130, -1),
                           colour=self.colors.title, style=tstyle)

        self.v_move   = wx.CheckBox(panel, -1, 'Verify Move')# , style=wx.ALIGN_RIGHT)
        self.v_erase  = wx.CheckBox(panel, -1, 'Verify Erase ')# style=wx.ALIGN_RIGHT)
        self.v_owrite = wx.CheckBox(panel, -1, 'Verify Overwrie')#, style=wx.ALIGN_RIGHT)

        self.v_move.SetValue(1==int(self.db.get_info('verify_move')))
        self.v_erase.SetValue(1==int(self.db.get_info('verify_erase')))
        self.v_owrite.SetValue(1==int(self.db.get_info('verify_overwrite')))

        sizer.Add(title,        (0, 0), (1, 3), labstyle|wx.ALL, 5)
        sizer.Add(self.v_move,  (1, 0), (1, 1), labstyle,  5)
        sizer.Add(self.v_erase, (1, 1), (1, 1), labstyle,  5)
        sizer.Add(self.v_owrite,(1, 2), (1, 1), labstyle,  5)

        sizer.Add(wx.StaticLine(panel, size=(400, 2), style=wx.LI_HORIZONTAL),
                  (2, 0), (1, 5), 3)

        title = SimpleText(panel, 'Epics Database Connection:',
                           font=titlefont,
                           colour=self.colors.title, style=tstyle)

        label = SimpleText(panel, 'DB Prefix:')
        self.epics_prefix = wx.TextCtrl(panel, -1, value='', size=(160, -1))
        self.epics_use    = wx.CheckBox(panel, -1, 'Use Epics Db')

        self.epics_use.SetValue(1==int(self.db.get_info('epics_use', default=0)))
        self.epics_prefix.SetValue(self.db.get_info('epics_prefix', default=''))

        sizer.Add(title,             (3, 0), (1, 3), labstyle|wx.GROW|wx.ALL, 5)
        sizer.Add(self.epics_use,    (4, 0), (1, 1), labstyle|wx.GROW|wx.ALL, 5)
        sizer.Add(label,             (5, 0), (1, 1), labstyle|wx.ALL, 5)
        sizer.Add(self.epics_prefix, (5, 1), (1, 2), labstyle|wx.GROW|wx.ALL, 5)

        sizer.Add(wx.StaticLine(panel, size=(400, 2), style=wx.LI_HORIZONTAL),
                  (6, 0), (1, 5), 3)

        btn_ok     = Button(panel, 'OK',     size=(70, -1), action=self.OnOK)
        btn_cancel = Button(panel, 'Cancel', size=(70, -1), action=self.OnCancel)

        sizer.Add(btn_ok,     (7, 0), (1, 1), labstyle|wx.ALL,  5)
        sizer.Add(btn_cancel, (7, 1), (1, 1), labstyle|wx.ALL,  5)

        set_font_with_children(self, font)

        pack(panel, sizer)

        mainsizer = wx.BoxSizer(wx.VERTICAL)
        mainsizer.Add(panel, 1, wx.GROW|wx.ALL, 1)
        pack(self, mainsizer)
        self.Show()
        self.Raise()

    def OnOK(self, event=None):
        yesno = {True: 1, False: 0}
        self.db.set_info('verify_move',      yesno[self.v_move.IsChecked()])
        self.db.set_info('verify_erase',     yesno[self.v_erase.IsChecked()])
        self.db.set_info('verify_overwrite', yesno[self.v_owrite.IsChecked()])
        self.db.set_info('epics_use',        yesno[self.epics_use.IsChecked()])

        epics_prefix = str(self.epics_prefix.GetValue()).strip()
        if self.epics_use.IsChecked() and epics_prefix is not None:
            self.db.set_info('epics_prefix',    epics_prefix)
            self.db.set_info('epics_use',    1)
            self.parent.enable_epics_server()
        elif not self.epics_use.IsChecked():
            if self.parent.server_timer is not None:
                self.parent.server_timer.Stop()
        self.Destroy()

    def OnCancel(self, event=None):
        self.Destroy()


class InstSelectionFrame(wx.Frame) :
    """ GUI Configure Frame"""
    def __init__(self, parent=None, pos=(-1, -1), db=None):

        self.parent = parent
        self.db = db

        style    = wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL
        labstyle  = wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL|wx.ALL
        rlabstyle = wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL|wx.ALL
        tstyle    = wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL

        wx.Frame.__init__(self, None, -1,
                          'Epics Instruments:  Select Instruments to Display')

        font = parent.GetFont()

        titlefont  = self.GetFont()
        titlefont.PointSize += 2
        titlefont.SetWeight(wx.BOLD)

        sizer = wx.GridBagSizer(5, 5)
        panel = scrolled.ScrolledPanel(self, size=(700, 750),
                                       style=wx.GROW|wx.TAB_TRAVERSAL)
        # title row
        self.colors = GUIColors()
        title = SimpleText(panel, 'Show Instruments:',
                           font=titlefont,
                           colour=self.colors.title, style=tstyle)
        irow = 0
        sizer.Add(title, (irow, 0), (1, 4), labstyle|wx.ALL, 3)
        self.hideframes = {}
        strlen = 24
        for inst in self.db.get_all_instruments():
            strlen = max(strlen, len(inst.name))

        icol = 0
        irow = 1
        for inst in self.db.get_all_instruments():
            isshown = inst.name in self.get_page_map()
            iname = (inst.name + ' '*strlen)[:strlen]
            cb = wx.CheckBox(panel, -1, iname)#, style=wx.ALIGN_RIGHT)
            cb.SetValue(isshown)
            self.hideframes[inst.name] = cb
            sizer.Add(cb, (irow, icol), (1, 1), labstyle,  5)
            icol += 1
            if icol == 3:
                icol = 0
                irow += 1

        irow += 1
        sizer.Add(wx.StaticLine(panel, size=(200, -1), style=wx.LI_HORIZONTAL),
                  (irow, 0), (1, 5), wx.ALIGN_CENTER|wx.GROW|wx.ALL, 5)

        btn_ok     = Button(panel, 'OK',     size=(70, -1), action=self.OnOK)
        btn_cancel = Button(panel, 'Cancel', size=(70, -1), action=self.OnCancel)

        irow += 1
        sizer.Add(btn_ok,     (irow, 0), (1, 1), labstyle|wx.ALL,  5)
        sizer.Add(btn_cancel, (irow, 1), (1, 1), labstyle|wx.ALL,  5)

        set_font_with_children(self, font)

        pack(panel, sizer)
        panel.SetupScrolling()
        mainsizer = wx.BoxSizer(wx.VERTICAL)
        mainsizer.Add(panel, 1, wx.GROW|wx.ALL, 1)

        self.SetMinSize((750, 450))
        pack(self, mainsizer)
        self.Show()
        self.Raise()

    def get_page_map(self):
        out = {}
        for i in range(self.parent.nb.GetPageCount()):
            out[self.parent.nb.GetPageText(i)] = i
        return out

    def OnOK(self, event=None):
        yesno = {True: 1, False: 0}

        pagemap = self.get_page_map()
        for pagename, cb in self.hideframes.items():
            checked = cb.IsChecked()
            if not checked and pagename in pagemap:
                self.parent.nb.DeletePage(pagemap[pagename])
                pagemap = self.get_page_map()

            elif checked and pagename not in pagemap:
                inst = self.db.get_instrument(pagename)
                self.parent.add_instrument_page(inst.name)
                pagemap = self.get_page_map()
        self.Destroy()

    def OnCancel(self, event=None):
        self.Destroy()
