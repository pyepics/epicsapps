import os
import sys
import json
import numpy as np

import wx
from wxutils import (GridPanel, Button, FloatCtrl, SimpleText, LCEN)


def read_poni(fname):
    conf = dict(dist=None, wavelength=None, pixel1=None, pixel2=None,
                poni1=None, poni2=None, rot1=None, rot2=None, rot3=None)
    with open(fname, 'r') as fh:
        for line in fh.readlines():
            line = line[:-1].strip()
            if line.startswith('#'):
                continue
            key, val = [a.strip() for a in line.split(':', 1)]
            key = key.lower()
            if key == 'detector_config':
                confdict = json.loads(val)
                for k, v in confdict.items():
                    k = k.lower()
                    if k in conf:
                        conf[k] = float(v)

            else:
                if key == 'distance':
                    key='dist'
                elif key == 'pixelsize1':
                    key='pixel1'
                elif key == 'pixelsize2':
                    key='pixel2'
                if key in conf:
                    conf[key] = float(val)
    missing = []
    for key, val in conf.items():
        if val is None:
            missing.append(key)
    if len(missing)>0:
        msg = "'%s' is not a valid PONI file: missing '%s'"
        raise ValueError(msg % (fname, ', '.join(missing)))
    return conf


class CalibrationDialog(wx.Dialog):
    """dialog for calibrating energy"""
    conv = {'wavelength': (1e10, 'Ang'),
            'pixel1': (1e6, 'microns'),
            'pixel2': (1e6, 'microns'),
            'poni1': (1e3, 'mm'),
            'poni2': (1e3, 'mm'),
            'dist': (1e3, 'mm'),
            'rot1': (180/np.pi, 'deg'),
            'rot2': (180/np.pi, 'deg'),
            'rot3': (180/np.pi, 'deg')}

    def __init__(self, parent, calfile, **kws):

        self.parent = parent
        self.scandb = parent.scandb
        self.calfile = calfile
        poni = read_poni(calfile)

        wx.Dialog.__init__(self, parent, wx.ID_ANY, size=(600, 525),
                           title="Read Calibration File")


        panel = GridPanel(self, ncols=3, nrows=4, pad=2, itemstyle=LCEN)

        self.wids = wids = {}

        wids['filename'] = SimpleText(panel, calfile)

        _p, fname = os.path.split(calfile)
        wids['calname']  = wx.TextCtrl(panel, value=fname, size=(350, -1))

        wids['ok'] = Button(panel, 'OK', size=(150, -1), action=self.on_apply)

        def add_text(text, dcol=1, newrow=True):
            panel.Add(SimpleText(panel, text), dcol=dcol, newrow=newrow)

        add_text('  Calibration file: ',  newrow=False)
        panel.Add(wids['filename'], dcol=3)
        add_text('  Save as : ')
        panel.Add(wids['calname'], dcol=3)

        opts  = dict(size=(90, -1), digits=5)
        for wname in ('wavelength', 'dist', 'pixel1', 'pixel2',
                      'poni1', 'poni2', 'rot1', 'rot2', 'rot3'):
            scale, units = self.conv[wname]
            val = scale*float(poni[wname])
            if wname == 'wavelength':
                energy = 12398.4193/val
                units = '%s,  Energy=%.2f' % (units, energy)

            wids[wname] = FloatCtrl(panel, value=val, size=(100, -1), precision=4)
            wids[wname+'_units'] = SimpleText(panel, units)
            add_text('  %s:' % wname.title() )
            panel.Add(wids[wname])
            panel.Add(wids[wname+'_units'])

        panel.Add((5, 5))
        panel.Add(wids['ok'], dcol=2, newrow=True)
        panel.pack()

    def onDone(self, event=None):
        self.Destroy()

    def on_apply(self, event=None):
        calname = self.wids['calname'].GetValue()

        calib = {}
        for wname in ('wavelength', 'dist', 'pixel1', 'pixel2',
                      'poni1', 'poni2', 'rot1', 'rot2', 'rot3'):
            scale, units = self.conv[wname]
            calib[wname] = self.wids[wname].GetValue()/scale

        if self.scandb is not None:
            self.scandb.set_detectorconfig(calname, json.dumps(calib))
            self.scandb.set_info('xrd_calibration', calname)
        self.parent.setup_calibration(calib)
        self.Destroy()
