import sys
import os
import yaml

from ..utils import get_configfile, normalize_pvname

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

# default camera configuration
#
_configtext = """
prefix: None
name: areaDetector
title: 'Epics areaDetector Display'
workdir: ''
filesaver: 'TIFF1:'
use_filesaver: true
default_rotation: 0
show_free_run: false
free_run_time: 0.5
show_1dintegration: false
iconfile: None
colormode: Mono
int1d_trimx': 0
int1d_trimy': 0
int1d_flipx': false
int1d_flipy': true
show_thumbnail: true
thumbnail_size: 100

enabled_plugins: ['image1', 'Over1', 'Over2', 'Over3', 'Over4', 'ROI1', 'ROI2', 'JPEG1', 'TIFF1']
image_attributes: ['ArrayData', 'UniqueId_RBV']

camera_attributes:
- 'Acquire'
- 'DetectorState_RBV'
- 'ArrayCounter'
- 'ArrayCounter_RBV'
- 'NumImages'
- 'NumImages_RBV'
- 'AcquireTime'
- 'AcquireTime_RBV'
- 'TriggerMode'
- 'TriggerMode_RBV'
colormaps: ['gray', 'magma', 'inferno', 'plasma', 'viridis', 'coolwarm', 'hot', 'jet']

epics_controls: []
scandb_instrument: None
"""

CONFFILE = 'areadetector.yaml'
class ADConfig(object):
    def __init__(self, name=None):
        if name is None:
            name = CONFFILE
        self.config = yaml.load(_configtext, Loader=yaml.Loader)
        self.read(name)

    def read(self, fname):
        self.config_file = get_configfile(fname)
        if os.path.exists(self.config_file):
            text = None
            with open(self.config_file, 'r') as fh:
                text = fh.read()
            try:
                self.config.update(yaml.load(text, Loader=Loader))
            except:
                pass

    def write(self, fname=None, config=None, defaultfile=False):
        if fname is None:
            fname = self.config_file
            if defaultfile:
                fname = get_configfile(CONFFILE)
        if config is None:
            config = self.config
        with open(fname, 'w') as fh:
            fh.write(yaml.dump(config))
        return fname
