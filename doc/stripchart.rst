====================================
Strip Chart Display
====================================

StripChart is a wxPython GUI application for viewing time traces of PVs as
a strip chart.   This is inspired by the classic Epics Stripchart
application written with X/Motif.    

Dependencies, Installation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This application needs pyepics, numpy, matplotlib, and wxPython. 

It also the wxmplot plotting library, which can be found at
`http://pypi.python.org/pypi/wxmplot/
<http://pypi.python.org/pypi/wxmplot/>`_, with development versions at
`http://github.com/newville/wxmplot/
<http://github.com/newville/wxmplot/>`_ and may be installed wth::

   easy_install -U wxmplot


Installation of the striphart can be done with::

   python setup.py install


Running  Stripchart
~~~~~~~~~~~~~~~~~~~~~~

To run this application, simply run stripchart.py at the command line::

    python pyepics_stripchart.py


and enter the base name of the PVs to follow.  A sample display would look
like this:

.. image:: images/StripChart_Basic.png


Usage
~~~~~~~~~~~~~~~~~~~~~~


Plot details such as line colors, thicknesses, labels, etc can be adjusted
from the configuration screen, available from the Menu.

.. image:: images/StripChart_Config.png



