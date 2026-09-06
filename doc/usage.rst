Usage
==================

Installing the epicsapps package will install a command-line script `epicsapps`
that can be used to launch the main epicsapps GUI applications.  This works
as::

   epicsapps [options] appname  [filename]


where `options` can be

* `-h`, `--help`:      show this help message and exit
* `-m`, `--makeicons`  create desktop and start menu icons
* `-p`, `--prompt`     prompt for configuration on startup
* `-n`, `--no-prompt`  suppress prompt, use default configuration
* `-c`, `--cli`        run as a command-line program.

and `appname` can be one of

* `stripchart`              PV Stripchart
* `pvaviewer`               PVA Image Viewer {new!)
* `adviewer`     [filename] Area Detector Viewer
* `instruments`  [filename] Epics Instruments
* `pvlogger`     [filename] PV Logger data collection
* `pvlogview`               PV Logger data Viewer
* `microscope`   [filename] Sample Microscope Viewer


and `filename` is an optional configuration YAML file.

See :ref:`install_icons` for details on making desktop icons.
