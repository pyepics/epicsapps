try:
    from epicsscan import ScanDB
except:
    ScanDB = None

def setup_calibration(self, ponifile):
    """set up calibration from PONI file"""
    calib = read_poni(ponifile)
    # if self.image.rot90 in (1, 3):
    #     calib['rot3'] = np.pi/2.0
    self.calib = calib
    if HAS_PYFAI:
        self.integrator = AzimuthalIntegrator(**calib)
        self.show1d_btn.Enable()
    else:
        self.write('Warning: PyFAI is not installed')

    if self.scandb is not None:
        _, calname  = os.path.split(ponifile)
        self.scandb.set_detectorconfig(calname, json.dumps(calib))
        self.scandb.set_info('xrd_calibration', calname)
