
import json
import numpy as np

try:
    from pyFAI.azimuthalIntegrator import AzimuthalIntegrator
    HAS_PYFAI = True
except ImportError:
    HAS_PYFAI = False


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


class XRD_Integrator():
    def __init__(self, ponifile=None, calibration_callback=None):
        self.calib = None
        self.azint = None
        self.calibration_callback = calibration_callback
        self.read_ponifile(ponifile)

    def read_ponifile(self, ponifile):
        self.ponifile = ponifile
        if self.ponifile is not None:
            self.calib = read_poni(self.ponifile)
            if HAS_PYFAI:
                self.azint = AzimuthalIntegrator(**self.calib)
                if callable(self.calibration_callback):
                    self.calibration_callback(calib=self.calib)

    @property
    def enabled(self):
        return self.azint is not None

    def integrate1d(self, image, npts=2048, polarization_factor=0.999):
        if self.enabled:
            opts = dict(polarization_factor=polarization_factor,
                        unit='q_A^-1', correctSolidAngle=True)
            return self.azint.integrate1d(image, npts, **opts)
