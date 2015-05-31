#!/usr/bin/python

from ConfigParser import  ConfigParser
from cStringIO import StringIO
from epics.wx.ordereddict import OrderedDict
import os
import time

STAGE_LEGEND = '# index =  Motor ||  name ||  description  ||   sign'
POS_LEGEND   = '# index = name   || imagefile     || fineX, fineY, theta, coarsex, coarsez, coarsey'

DEFAULT_CONF = """
## Sample Stage Configuration
#--------------------------#
[setup]
verify_move = 1
verify_erase = 1
verify_overwrite = 1
finex_dir = 1
finey_dir = 1
#--------------------------#
[camera]
type = areadetector
image_folder = Sample_Images
ad_prefix    = 13IDEPS1:
ad_format    = JPEG
web_url = http://164.54.160.115/jpg/4/image.jpg
#--------------------------#
[stages]
# index =  Motor ||  name ||  description   ||   sign
1   = 13XRM:m1   || fineX || Fine X         ||    1
2   = 13XRM:m2   || fineY || Fine Y         ||    1
3   = 13XRM:m3   || theta || Theta          ||    1
4   = 13XRM:m4   ||   X   || Stage X        ||    1
5   = 13XRM:m5   ||   Z   || Stage Z (focus)||    1
6   = 13XRM:m6   ||   Y   || Stage Y (vert) ||    1
#--------------------------#
[positions]
# index = xxxxname      || imagefile     || finex, finey, theta, coarsex, coarsez, coarsey
001 =   p1 || p1.jpg ||  0, 0, 0, 90, 70, 350
"""
conf_sects = {'setup':{'bools': ('verify_move','verify_erase', 'verify_overwrite'),
                       'ints': ('finex_dir', 'finey_dir')},
              'camera': {'ordered':False},
              'stages': {'ordered':True},
              'positions': {'ordered':True} }

conf_objs = OrderedDict( (('setup', ('verify_move', 'verify_erase', 'verify_overwrite',
                                      'finex_dir', 'finey_dir')),
                          ('camera', ('type', 'image_folder', 'ad_prefix', 'ad_format', 'web_url')),
                          ('stages', None),
                          ('positions', None)) )

conf_files = ('SampleStage_autosave.ini', 'SampleStage.ini',
              '//cars5/Data/xas_user/config/SampleStage.ini')

class StageConfig(object):
    def __init__(self, filename=None, text=None):
        self.config = {}
        self.cp = ConfigParser()
        self.nstages = 0
        conf_found = False
        if filename is None:
            for fname in conf_files:
                if os.path.exists(fname) and os.path.isfile(fname):
                    filename = fname
                    break

        if filename is not None:
            self.Read(fname=filename)
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
                val = get(sect,opt)
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
            skeys = list(self.config['stages'].keys())
            skeys.sort()
            for key in skeys:
                name, val = self.config['stages'][key]
                name = name.strip()
                label, desc, sign = val.split('||')
                out[name] = dict(label=label.strip(), desc=desc.strip(), sign=int(sign))
            self.config['stages'] = out
            self.nstages = len(out)

    def Save(self, fname=None):
        o = []
        cnf = self.config
        if fname is not None:
            self.filename = fname
        o.append('## Sample Stage Configuration (saved: %s)'  % (time.ctime()))
        for sect, optlist in conf_objs.items():
            o.append('#--------------------------#\n[%s]'%sect)
            if sect == 'positions':
                o.append(POS_LEGEND)
                fmt =  "%3.3i = %s || %s || %s"
                pfmt =  ', '.join(['%f' for i in range(self.nstages)])
                idx = 1
                for name, val in cnf['positions'].items():
                    img = val['image']
                    pos = pfmt % tuple(val['position'])
                    o.append(fmt % (idx, name, img, pos))
                    idx = idx + 1
            elif sect == 'stages':
                o.append(STAGE_LEGEND)
                fmt =  "%i = %s || %s || %s || %i"
                idx = 1
                for name, val in cnf['stages'].items():
                    label = val['label']
                    desc  = val['desc']
                    sign  = val['sign']
                    o.append(fmt % (idx, name, label, desc, sign))
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
