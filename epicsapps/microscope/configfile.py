#!/usr/bin/python

from ..utils import ConfigFile, load_yaml, get_default_configfile


_configtext = """
title: 'SampleStage'
workdir: /home/user
verify_move: true
verify_erase: true
verify_overwrite: true
center_with_fine_stages: false
image_folder: Sample_Images
zmq_push: true

camera_type: areadetector
camera_id:  1
ad_prefix: '13IDEPS1:'
ad_format: JPEG
web_url:  http://164.54.160.115/jpg/2/image.jpg

calibration:
   - ['default',  1.0, 1.0]

overlays:
   - ['scalebar', 100.0, 0.85, 0.97, 2.0, 255, 255, 128]
   - ['circle ',   10.0, 0.50, 0.50, 2.0, 0, 255, 0]

scandb_credentials: ESCAN_CREDENTIALS
instrument: SampleStage
xyzmotors: ['13XRM:m4.VAL', '13XRM:m5.VAL', '13XRM:m6.VAL']
offline_instrument:
offline_xyzmotors: []

stages:
   - ['13XRM:m4.VAL', 'Coarse Stages', x, -1, 4, 10.5, 1]
   - ['13XRM:m5.VAL', 'Coarse Stages', y, -1, 4, 10.5, 1]
   - ['13XRM:m6.VAL', 'Coarse Stages', z, -1, 4, 10.5, 1]
"""

CONFFILE = 'microscope.yaml'

class MicroscopeConfig(ConfigFile):
    def __init__(self, fname='microscope.yaml', default_config=None):
        if default_config is None:
            default_config = load_yaml(_configtext)
        ConfigFile.__init__(self, fname, default_config=default_config)
