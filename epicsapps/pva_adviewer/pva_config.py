#!/usr/bin/env python
"""
PVA Viewer YAML configuration.
"""

from epicsapps.utils import ConfigFile, load_yaml

__all__ = ["PVAConfig", "CONFFILE", "RECENT_PREFIXES_FILE", "RECENT_CONFIGS_FILE"]

# epics_controls entry format (width and fontsize are optional, fall back to defaults):
#   [label, pvname, use_prefix, type]
#   [label, pvname, use_prefix, type, readback_suffix]
#   [label, pvname, use_prefix, type, readback_suffix, width]
#   [label, pvname, use_prefix, type, readback_suffix, width, fontsize]
# types: pvfloat, pvenum, pvenumbuttons, pvtctrl, pvtext
# readback_suffix: '_RBV' string or false
_configtext = """
prefix: ''
pva_suffix: 'Pva1:Image'
title: 'PVA Viewer'
pixel_size: 1.0
colormap: grays
poni_file: null
show_integration_plot: true
show_pv_controls: true
control_width: 140
control_fontsize: 12
control_columns: 1
epics_controls: []
"""

CONFFILE = 'pvaviewer.yaml'
RECENT_PREFIXES_FILE = 'pvaviewer_prefixes.txt'
RECENT_CONFIGS_FILE = 'pvaviewer_configs.txt'


class PVAConfig(ConfigFile):
    def __init__(self, fname=CONFFILE, default_config=None):
        if default_config is None:
            default_config = load_yaml(_configtext)
        super().__init__(fname, default_config=default_config)

