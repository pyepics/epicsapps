#!/usr/bin/python
##
## MPlot BasePanel: a Basic Panel for 2D line and image plotting
##

import sys
import time
import os
import wx
import matplotlib
from utils import Printer

class BasePanel(wx.Panel):
    """
    wx.Panel component shared by PlotPanel and ImagePanel.

    provides:
         Basic support Zooming / Unzooming
         support for Printing
         popup menu
         bindings for keyboard short-cuts
    """
    def __init__(self, parent, messenger=None,
                 show_config_popup=True, **kw):



    ####
    ## GUI events
    ####


    ####
    ## private methods
    ####
