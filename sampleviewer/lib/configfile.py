#!/usr/bin/python

from ConfigParser import  ConfigParser
from cStringIO import StringIO
from epics.wx.ordereddict import OrderedDict
import os
import time

from .utils import normalize_pvname


STAGE_LEGEND = '# index =  moto  || group      ||desc || scale || prec || maxstep'
POS_LEGEND   = '# index = name   || imagefile || position '

DEFAULT_CONF = """
## Sample Stage Configuration
#--------------------------#
[gui]
workdir_file = /tmp/workdir.dat
autosave_file = /tmp/micro_live.jpg
icon_file =
title = Microscope
verify_move = 1
verify_erase = 1
verify_overwrite = 1
center_with_fine_stages = 1
#--------------------------#
[camera]
type       = areadetector
fly2_id    = 0
ad_prefix  = 13IDEPS1:
ad_format  = JPEG
web_url    = http://164.54.160.115/jpg/2/image.jpg
image_folder = Sample_Images
calib_x    = 0.001
calib_y    = 0.001
#--------------------------#
[overlays]
scalebar  = 100.0 0.85 0.97 2.0 255 128 0
circle    = 7.0   0.50 0.50 2.0 0 255 0
#------------------------------#
[scandb]
instrument = microscope
server = sqlite3
dbname = microscope.db
host =
user =
password =
port =
offline =
#--------------------------#
[stages]
# index =  motor || group   ||desc || scale || prec || maxstep || show
1 = 13IDE:m1 || XY Stages   ||     ||  1    || 3    ||
2 = 13IDE:m2 || XY Stages   ||     || -1    || 3    ||
3 = 13IDE:m3 || Focus       ||     ||       || 3    || 7.1
#--------------------------#
[positions]
# index = name  || position || imagefile
001 =   p1 || 0, 0, 0, 90, 70, 350 ||
"""
conf_sects = {'gui': {'bools': ('verify_move','verify_erase', 'verify_overwrite',
                                'center_with_fine_stages')},
              'camera': {'ordered':False},
              'stages': {'ordered':True},
              'overlays': {'ordered':True},
              'scandb': {'ordered':True},
              'positions': {'ordered':True} }

conf_objs = OrderedDict( (('gui', ('title', 'workdir_file', 'icon_file',
                                   'autosave_file', 'verify_move',
                                   'verify_erase', 'verify_overwrite',
                                   'center_with_fine_stages')),
                          ('camera', ('type', 'image_folder', 'fly2_id',
                                      'ad_prefix', 'ad_format', 'web_url',
                                      'calib_x', 'calib_y')),
                          ('scandb', ('instrument', 'dbname', 'server',
                                      'host', 'user', 'password', 'port',
                                      'offline')),
                          ('overlays', ('circle', 'scalebar')),
                          ('stages', None),
                          ('positions', None)) )

conf_files = ('SampleStage.ini',
              'SampleStage_autosave.ini',
              '//cars5/Data/xas_user/config/13ide/SampleStage.ini')

class StageConfig(object):
    def __init__(self, filename=None, text=None):
        self.config = {}
        self.cp = ConfigParser()
        self.nstages = 0
        fname = None
        if filename is not None and os.path.exists(filename):
            fname = filename
        if fname is None:
            for filename in conf_files:
                if os.path.exists(filename) and os.path.isfile(filename):
                    fname = filename
                    break

        if fname is not None:
            self.Read(fname=fname)
        else:
            self.cp.readfp(StringIO(DEFAULT_CONF))
            self._process_data()

    def Read(self,fname=None):
        if fname is not None:
            ret = self.cp.read(fname)
            if len(ret)==0:
                time.sleep(0.5)
                ret = self.cp.read(fname)
            self.filename = fname
            self._process_data()

            stage_names = self.config['stages']
            image_folder = self.config['camera']['image_folder']
            pos = OrderedDict()
            if 'positions' not in self.config:
                self.config['positions'] = {}
            for key, dat in self.config['positions'].items():
                img_fname = dat['image']
                image = {'type': 'filename',
                         'data': os.path.join(image_folder, img_fname)}

                poslist = dat['position']
                posdict = {}
                for name, val in zip(stage_names, poslist):
                    posdict[name] = val
                pos[key] = dict(image=image, position=posdict)
            self.config['positions'] = pos

    def _process_data(self):
        for sect, opts in conf_sects.items():
            if not self.cp.has_section(sect):
                # print 'skipping section ' ,sect
                continue
            bools = opts.get('bools',[])
            floats= opts.get('floats',[])
            ints  = opts.get('ints',[])
            thissect = {}
            is_ordered = False
            if 'ordered' in opts:
                is_ordered = True

            for opt in self.cp.options(sect):
                get = self.cp.get
                if opt in bools:
                    get = self.cp.getboolean
                elif opt in floats:
                    get = self.cp.getfloat
                elif opt in ints:
                    get = self.cp.getint
                try:
                    val = get(sect, opt)
                except ValueError:
                    val = ''
                if is_ordered and '||' in val:
                    nam, val = val.split('||', 1)
                    opt = opt.strip()
                    val = nam, val.strip()
                thissect[opt] = val
            self.config[sect] = thissect

        if 'positions' in self.config:
            out = OrderedDict()
            poskeys = list(self.config['positions'].keys())
            poskeys.sort()
            for key in poskeys:
                name, val = self.config['positions'][key]
                name = name.strip()
                img, posval = val.strip().split('||')
                pos = [float(i) for i in posval.split(',')]
                out[name] = dict(image=img.strip(), position= pos)
            self.config['positions'] = out

        if 'stages' in self.config:
            out = OrderedDict()
            groups = []

            skeys = list(self.config['stages'].keys())
            skeys.sort()
            for key in skeys:
                name, val = self.config['stages'][key]
                name = normalize_pvname(name.strip())
                val = val.replace('||', ' | ')
                words = [w.strip() for w in val.split('|')]
                group = words[0]
                desc  = words[1]
                if len(desc) == 0:
                    desc = None

                scale = 1.0
                if len(words) > 1 and len(words[2]) > 0:
                    scale = float(words[2])

                prec = None
                if len(words) > 2 and len(words[3]) > 0:
                    prec = int(words[3])

                maxstep = None
                if len(words) > 4 and len(words[4]) > 0:
                    maxstep = float(words[4])

                show = 1
                if len(words) > 5 and len(words[5]) > 0:
                    show = int(words[5])

                out[name] = dict(label=name, group=group, desc=desc, scale=scale,
                                 prec=prec, maxstep=maxstep, show=show)
                if group not in groups:
                    groups.append(group)
            self.config['stages'] = out
            self.config['stage_groups'] = groups
            self.nstages = len(out)

    def Save(self, fname=None, positions=None):
        o = []
        # print 'Save CONFIG FILE:', fname, os.getcwd()
        # print positions.keys()
        cnf = self.config

        if fname is not None:
            self.filename = fname
        o.append('## Sample Stage Configuration (saved: %s)'  % (time.ctime()))

        if positions is None:
            positions = cnf['positions']
        for sect, optlist in conf_objs.items():
            o.append('#--------------------------#\n[%s]'%sect)
            if sect == 'positions' and positions is not None:
                o.append(POS_LEGEND)
                fmt =  "%3.3i = %s || %s || %s "
                pfmt =  ', '.join(['%f' for i in range(self.nstages)])
                idx = 1
                for name, val in positions.items():
                    pos = []
                    for pvname in cnf['stages']:
                        try:
                            pos.append(float(val['position'][pvname]))
                        except:
                            pass
                    pfmt =  ', '.join(['%f' for i in range(len(pos))])
                    pos = pfmt % tuple(pos)
                    try:
                        tmpdir, imgfile = os.path.split(val['image'])
                    except:
                        tmpdir, imgfile = '', ''

                    o.append(fmt % (idx, name, imgfile, pos))
                    idx = idx + 1
            elif sect == 'stages':
                o.append(STAGE_LEGEND)
                fmt =  "%i = %s || %s || %s || %s || %s || %s || %s"
                idx = 1
                for name, dat in cnf['stages'].items():
                    # print 'Save STAGE ', name, dat
                    # index =  motor || group   ||desc || scale || prec || maxstep || show
                    group = dat['group']
                    desc  = dat['desc']
                    show  = str(dat['show'])
                    scale  = str(dat['scale'])
                    prec   = str(dat['prec'])
                    maxstep  = "%.3f" % (dat['maxstep'])
                    o.append(fmt % (idx, name, group, desc, scale, prec, maxstep, show))
                    idx = idx + 1
            if optlist is not None:
                for opt in optlist:
                    try:
                        val = cnf[sect].get(opt,' ')
                        if not isinstance(val,(str,unicode)): val = str(val)
                        o.append("%s = %s" % (opt,val))
                    except:
                        pass
        o.append('#------------------#\n')
        # print 'Conf autosave ', fname
        # print os.path.abspath(fname)
        f = open(fname,'w')
        f.write('\n'.join(o))
        f.close()

    def sections(self):
        return self.config.keys()

    def section(self,section):
        return self.config[section]

    def get(self,section,value=None):
        if value is None:
            return self.config[section]
        else:
            return self.config[section][value]
