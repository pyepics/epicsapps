.. _GetEpicsApps.sh:   https://raw.githubusercontent.com/pyepics/epicsapps/master/installers/GetEpicsApps.sh
.. _GetEpicsApps.bat:   https://raw.githubusercontent.com/pyepics/epicsapps/master/installers/GetEpicsApps.bat


Installation
===============


Installing Epics Apps
---------------------------

The latest version of the `epicsapps` package is |release|. For
existing Python installations, this can be installed with::

     pip install epicsapps

or upgraded with::

     pip install --upgrade epicsapps


For installation into an existing Python environment,

This ``pip`` command will all the required packages needed on Windows
and macOS.

On Linux, however, the ``pip install`` command will not have a binary
package for wxPython, and may try to build wxPython from source.  This
requires a large number of development packages on Linux, and rarely
works without some effort.

There are conda packages for wxPython from the `conda-forge` channel.
Since using Anaconda Python provides many othed common scientific
pacakges, and is common at many facilities using Epics.  If using
Anaconda Python, you can first do::

    conda install -c conda-forge wxpython

and then::

    pip install epicsapps

This approach will work on all systems, and is recommended on Linux.

Installation Scripts
---------------------------


**Table of EpicsApps Install scripts**

  +---------------------+------------------------+
  | Operating System    | Installer Script       |
  +=====================+========================+
  | Windows             | `GetEpicsApps.bat`_    |
  +---------------------+------------------------+
  | macOS or Linux      | `GetEpicsApps.sh`_     |
  +---------------------+------------------------+


To install a full standalone installation of Python with EpicsApps,
download `GetEpicsApps.bat`_ for Windows or `GetEpicsApps.sh`_ for
Linux and MacOS and run that script.  This will install a full
Anaconda Python environment in a folder named
``C:\Users\<YourName>\epicsapps`` or
``C:\Users\<YourName>\AppData\Local\epicsapps`` on Windows or in a
folder called ``epicsapps`` in you Home Folder on Linux or macOS, and
will also put folder called ``Epics Apps`` on your desktop with links
to the GUI Applications.

.. _install_icons:

Creating Desktop Shortcuts
-----------------------------

Running::

    epicsapps -m

will create a folder called "Epics Apps" on your desktop with links to launch
the main GUI applications.  If you would like to call that folder a
different name, you can use::

    epicsapps -m MyAppsFolder

and if you want the folder to be placed in a Public desktop folder,
available to all users who log into that machine, you can use::


    epicsapps -p -m MyAppsFolder
