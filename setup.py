#!/usr/bin/env python
"""
setup for pyepics/epicsapps
"""
from setuptools import setup, find_packages

install_requires = ('pyepics', 'numpy', 'matplotlib', 'xraydb', 'wxpython',
                    'wxmplot', 'sqliachemy', 'yaml')

packages = ['epicsapps']
for pname in find_packages('epicsapps'):
    packages.append('epicsapps.%s' % pname)

package_data = ['icons/*']

# list of top level scripts to add to Python's bin/
apps = ['epicsapps = epicsapps:run_epicsapps']

setup(name = 'epicsapps',
      version = '0.9',
      author = 'Matthew Newville',
      author_email = 'newville@cars.uchicago.edu',
      license = 'Epics Open License',
      description = 'PyEpics Applications',
      python_requires='>=3.6',
      install_requires=install_requires,
      packages=packages,
      package_data={'epicsapps': package_data},
      entry_points={'console_scripts' : apps},
      classifiers=['Intended Audience :: Science/Research',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python',
                   'License :: OSI Approved :: BSD License',
                   'Topic :: Scientific/Engineering'])
