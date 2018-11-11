#!/usr/bin/env python
import sys
from setuptools import setup

long_description = '''
Display and simplified control for Detcris Eiger
detectors using the Epics areaDetector interface
'''

install_reqs = [ 'numpy', 'matplotlib', 'pyepics', 'pyshortcuts',
                 'wxmplot', 'wxpython', 'wxutils']

setup(name='ad_eigerdisplay',
      version='1.0',
      author='Matthew Newville',
      author_email='newville@cars.uchicago.edu',
      url='http://github.com/pyepics/epicsapp',
      license = 'OSI Approved :: MIT License',
      python_requires='>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*',
      description='Display and simple control for Eiger Epics areaDetector',
      long_description=long_description,
      packages=['ad_eigerdisplay'],
      install_requires=install_reqs,
      classifiers=[
          'Intended Audience :: End Users/Desktop',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: MIT License',
          'Operating System :: MacOS :: MacOS X',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: POSIX',
          'Programming Language :: Python',
          ],
      package_data={'ad_eigerdisplay': ['icons/*']},
      entry_points={'console_scripts' : ['eiger_display = ad_eigerdisplay:run_adeiger']}
      )
