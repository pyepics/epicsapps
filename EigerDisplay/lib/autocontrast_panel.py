import wx
from epics.wx.utils import pack

from collections import OrderedDict

class ContrastPanel(wx.Panel):
    """auto-contrast panel"""
    def __init__(self, parent, default=0, callback=None,
                 title='Auto Contrast', **kws):

        self.callback = callback
        self.levels = ['None']
        for scale in (0.01, 0.1, 1.0):
            for step in (1, 2, 5):
                self.levels.append(str(scale*step))

        wx.Panel.__init__(self, parent, -1,  **kws)

        opts = dict(size=(125, -1))
        title = wx.StaticText(self, label='Auto-Contrast (%):', **opts)
        self.choice = wx.Choice(self, choices=self.levels, **opts)
        self.choice.Bind(wx.EVT_CHOICE, self.onChoice)
        self.choice.SetSelection(default)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(title,       0, wx.ALIGN_LEFT|wx.TOP|wx.EXPAND, 2)
        sizer.Add(self.choice, 1, wx.ALIGN_LEFT|wx.TOP|wx.EXPAND, 2)
        pack(self, sizer)

    def set_level_str(self, choice=None):
        if choice not in self.levels:
            choice = self.levels[0]
        self.set_level_int(levl=self.levels.index(choice))

    def set_level_int(self, level=0):
        if level < 0 or level > len(self.levels)-1:
            level = 0
        self.choice.SetSelection(level)
        if callable(self.callback):
            self.run_callback(level)

    def onChoice(self, event=None):
        if callable(self.callback):
            self.run_callback(event.GetSelection())

    def run_callback(self, level):
        clevel = self.levels[level]
        if clevel == 'None':
            flevel = 0
        else:
            flevel = float(clevel)
        self.callback(contrast_level=flevel)

    def advance(self):
        self.set_level(self.choice.GetSelection() + 1)

    def retreat(self):
        self.set_level(self.choice.GetSelection() - 1)
