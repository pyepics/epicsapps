#!/usr/bin/env python
"""
setup for pyepics/epicsapps
"""
from setuptools import setup, find_packages
import versioneer

install_requires = ('pyepics', 'numpy', 'matplotlib', 'xraydb', 'wxpython',
                    'wxmplot', 'wxutils', 'sqlalchemy', 'pyyaml', 'lmfit',
                    'pyshortcuts')

packages = ['epicsapps']
for pname in find_packages('epicsapps'):
    packages.append('epicsapps.%s' % pname)

package_data = ['icons/*']

# list of top level scripts to add to Python's bin/
apps = ['epicsapps = epicsapps:run_epicsapps']

setup(name = 'epicsapps',
      version = versioneer.get_version(),
      cmdclass = versioneer.get_cmdclass(),
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
