#!/usr/bin/python

from ..utils import ConfigFile, load_yaml, get_default_configfile

# default camera configuration
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
int1d_trimx: 0
int1d_trimy: 0
int1d_flipx: false
int1d_flipy: true
show_thumbnail: true
thumbnail_size: 100

enabled_plugins: [image1, Over1, Over2, Over3, Over4, ROI1, ROI2, JPEG1, TIFF1]
image_attributes: [ArrayData, UniqueId_RBV]

camera_attributes:
- Acquire
- DetectorState_RBV
- ArrayCounter
- ArrayCounter_RBV
- NumImages
- NumImages_RBV
- AcquireTime
- AcquireTime_RBV
- TriggerMode
- TriggerMode_RBV


colormaps: [gray, magma, inferno, plasma, viridis, coolwarm, hot]
scandb_instrument: None

epics_controls:
 - ['Trigger Mode',   'cam1:TriggerMode', true, pvenum, _RBV,  150,  10]
 - ['Num Images',     'cam1:NumImages', true, pvfloat, _RBV, 100, 10]
 - ['Acquire Period', 'cam1:AcquirePeriod', true,pvfloat, _RBV, 100, 10]
 - ['Acquire Time',   'cam1:AcquireTime', true, pvfloat, _RBV, 100, 10]
 - ['Acquire Status', 'cam1:Acquire', true, pvtext, false, 250, 10]
 - ['Acquire Busy',   'cam1:AcquireBusy', true, pvtext, false, 250, 10]
 - ['Acquire Message', 'cam1:StatusMessage_RBV', true, pvtext, false, 250, 10]

"""

CONFFILE = 'areadetector.yaml'

class ADConfig(ConfigFile):
    def __init__(self, fname='areadetector.yaml', default_config=None):
        if default_config is None:
            default_config = load_yaml(_configtext)

        ConfigFile.__init__(self, fname, default_config=default_config)
