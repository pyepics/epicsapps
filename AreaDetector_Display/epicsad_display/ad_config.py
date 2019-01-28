import sys
import yaml

# default camera configuration
#
_def_ = {'general': {'prefix': None,
                     'name': 'areaDetector',
                     'title': 'Epics areaDetector Display',
                     'filesaver': 'TIFF1:',
                     'use_filesaver': True,
                     'default_rotation': 0,
                     'show_free_run': False,
                     'free_run_time': 0.5,
                     'show_1dintegration': False,
                     'iconfile': None,
                     'colormode': 'Mono'},

         'enabled_plugins': ['image1', 'Over1', 'Over2', 'Over3', 'Over4',
                             'ROI1', 'ROI2', 'JPEG1', 'TIFF1'],
         'controls': [],
         'img_attributes': ['ArrayData', 'UniqueId_RBV'],
         'cam_attributes': ['Acquire', 'DetectorState_RBV',
                            'ArrayCounter', 'ArrayCounter_RBV',
                            'NumImages', 'NumImages_RBV',
                            'AcquireTime', 'AcquireTime_RBV',
                            'TriggerMode', 'TriggerMode_RBV'],
         'colormaps':  ['gray', 'magma', 'inferno', 'plasma',
                        'viridis', 'coolwarm', 'hot', 'jet'],
         }

def read_adconfig(fname):
    """read configuration from YAML file"""
    conf = {}
    conf.update(_def_)
    text = open(fname, 'r').read()
    data = yaml.load(text)
    for key, val in data.items():
        key = key.lower()
        if key == 'general':
            conf['general'].update(val)
        elif key in ('enabled_plugins', 'colormaps',
                     'cam_attributes', 'img_attributes'):
            for p in val:
                if p not in conf[key]:
                    conf[key].append(p)
        else:
            conf[key] = val

    prefix = conf['general'].get('prefix', None)
    if prefix is None:
        raise ValueError('prefix required in config file')
    if prefix.endswith(':'):
        prefix = prefix[:-1]
    if prefix.endswith(':image1'):
        prefix = prefix[:-7]
    if prefix.endswith(':cam1'):
        prefix = prefix[:-5]

    conf['general']['prefix'] = prefix + ':'

    fsaver = conf['general'].get('filesaver', 'TIFF1:')
    if fsaver.endswith(':'):
        fsaver = fsaver[:-1]
    if fsaver.startswith(':'):
        fsaver = fsaver[1:]
    conf['general']['filesaver'] = fsaver + ':'
    return conf
