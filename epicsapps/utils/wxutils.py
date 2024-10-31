"""
wxPython utils
"""
import os
import wx

def get_icon(iconname):
    topdir, _s = os.path.split(__file__)
    topdir, _s = os.path.split(topdir)
    if not iconname.endswith('.ico'):
        iconname = "%s.ico" % iconname
    return os.path.abspath(os.path.join(topdir, 'icons', iconname))

def SelectWorkdir(parent,  message='Select Working Folder...'):
    "prompt for and change into a working directory "
    dlg = wx.DirDialog(parent, message,
                       style=wx.DD_DEFAULT_STYLE|wx.DD_CHANGE_DIR)

    path = os.path.abspath(os.curdir)
    dlg.SetPath(path)
    if  dlg.ShowModal() == wx.ID_CANCEL:
        return None
    path = os.path.abspath(dlg.GetPath())
    dlg.Destroy()
    os.chdir(path)
    return path

class GUIColors(object):
    def __init__(self):
        self.bg = wx.Colour(250,250,240)
        self.nb_active = wx.Colour(254,254,195)
        self.nb_area   = wx.Colour(250,250,245)
        self.nb_text = wx.Colour(10,10,180)
        self.nb_activetext = wx.Colour(80,10,10)
        self.title  = wx.Colour(80,10,10)
        self.pvname = wx.Colour(10,10,80)
