====================================
Installation and Getting Started
====================================


The latest version of the `epicsapps` package is |release|,  which can be installed with::

     pip install epicsapps


Many Epics Applications are available as GUI Applications, using wxPython.  For
Windows and macOS X, all dependencies can be reliably installed with either
`pip` and the PyPI packaging system or using Anaconda Python and `conda` and
the `conda-forge` channel.

PyPI does not currently have a binary package for wxPython for Linux, and
wxPython is somewhat challenging to automatically build from source on Linux.
There are conda packages for wxPython, especially from the `conda-forge`
channel.

Using Anaconda Python is recommended and likely to be in used for many folks
using Epics anyway.  In that case, you can first do::

    conda install -c conda-forge wxpython


and then do::

    pip install epicsapps


This approach will work on all systems, and is recommended on Linux.


Getting Started
~~~~~~~~~~~~~~~~~~

Installing the epicsapps package will install a command-line script `epicsapps`
that can be used to launch the main epicsapps GUI applications.  This works
as::


   epicsapps [options] appname  [filename]


where `options` can be

* `-h`, `--help`:       show this help message and exit
* `-m`, `--makeicons`  create desktop and start menu icons
* `-p`, `--prompt`     prompt for configuration on startup
* `-n`, `--no-prompt`  suppress prompt, use default configuration

and `appname` can be one of

* `adviewer`     [filename] Area Detector Viewer
* `instruments`  [filename] Epics Instruments
* `microscope`   [filename] Sample Microscope Viewer
* `stripchart`              Epics PV Stripchart


and `filename` is an optional configuration YAML file.

Note that running::

    epicsapps -m

will create a folder called "Epics Apps" on your desktop with links to launch
the main GUI applications.
