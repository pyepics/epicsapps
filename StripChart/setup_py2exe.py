from distutils.core import setup
import py2exe

setup(name="Epics PV StripChart", 
      windows=[{'script': "pyepics_stripchart.py",
                'icon_resources': [(0, 'stripchart.ico')]}],
      options = dict(py2exe=dict(optimize=0,
                                 includes=['wx', 'epics', 'numpy', 'matplotlib'])))

