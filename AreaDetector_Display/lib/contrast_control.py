import wx

class ContrastControl:
    """auto-contrast widgets"""
    def __init__(self, parent, default=1, callback=None):
        self.levels = ['None']
        for scale in (0.001, 0.01, 0.1, 1.0):
            for step in (1, 2, 5):
                self.levels.append(str(scale*step))

        self.callback = callback
        self.label = wx.StaticText(parent, label='Contrast Level (%):',
                                   size=(150, -1))
        self.choice = wx.Choice(parent, choices=self.levels, size=(100, -1))
        self.choice.Bind(wx.EVT_CHOICE, self.onChoice)
        self.choice.SetSelection(0)

    def set_level_str(self, choice=None):
        if choice not in self.levels:
            choice = self.levels[0]
        self.set_level_int(level=self.levels.index(choice))

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
