====================================
Area Detector Display
====================================

Epics Area Detector Display is a wxPython GUI application for viewing
images from an Epics Area Detector.  This application requires wxPython,
pyepics, numpy, and the Python Image Libary.


To run this application, simply run AD_Display.py at the command line::

    epicsapps adviewer

This will start with a file browser to search for an AreaDetector configuration file.

A few examples of configuration files are given at, with a sample lookng like this::

    name: IDA Beam Viewer
    prefix: '13IDAPG1:'
    title: AD Display /  IDA Beam Viewer
    camera_attributes: [Acquire, ArrayCounter, ArrayCounter_RBV, NumImages, NumImages_RBV,
      AcquireTime, AcquireTime_RBV, TriggerMode, TriggerMode_RBV]
    colormaps: [gray, magma, inferno, plasma, viridis, coolwarm, hot, jet]
    colormode: Mono
    default_rotation: 0
    enabled_plugins: [image1, Over1, Over2, Over3, Over4, ROI1, ROI2, JPEG1, TIFF1]
    epics_controls:
    - [Trigger Mode, 'cam1:TriggerMode', true, pvenum, _RBV, 150, 10]
    - [Image Mode, 'cam1:ImageMode', true, pvenum, _RBV, 150, 10]
    - ['# Images', 'cam1:NumImages', true, pvfloat, _RBV, 100, 10]
    - [Acquire Time, 'cam1:AcquireTime', true, pvfloat, _RBV, 100, 10]
    - [Acquire Period, 'cam1:AcquirePeriod', true, pvfloat, _RBV, 100, 10]
    - [TIFF File Path, 'TIFF1:FilePath', true, pvtctrl, false, 250, 10]
    - [Acquire Status, 'cam1:Acquire', true, pvtext, false, 250, 10]
    filesaver: 'TIFF1:'
    free_run_time: 0.2
    image_attributes: [ArrayData, UniqueId_RBV]
    show_thumbnail: true
    thumbnail_size: 100
    use_filesaver: true
    workdir: /home/user
    scandb_instrument: Pinhole Tank BPM


This describes how the `adviewer` application will connect to area detector, w
including which PVs to include for a very basic widget controls with a limited
set of Process Variables described such as those for starting and stopping the
acquisition.  This configuration file will generate an interface like this:


.. image:: images/AD_Display.png


Note that the `epics_controls` is a list of data for PVs to be displayed in the
upper left portion of the window.  Each item in this list has values of

   * display name, here "Trigger Mode"
   * Epics PV to use, here "cam1:TriggerMode"
   * whether to prepend the AD PV Prefix, here "13IDAPG1:" to the PV name, here "true".
   * what kind of PV it is -- enum, float, text, which will determine what type of widget is use, heree "pvenum".
   * what suffix (if any) to use for a "readback PV", here "_RBV", common for many AD PVs
   * the size of the widget in pixels, here 150
   * the font size for the widget, here 10.



The display will allow changing color table lookup using a few supplied
colortables (from matplotlib), and allowing reversing that color table.
Contrast levels can be set using a percentage value to clip the intensity
range. That is, a value of 1 will set the intensity range to be from the 1%% to
99%% intensity level of the entire image.  In addition, the display shows a
"thumbnail image" that can be recentered or have its size change dynamically.

Finally, if an Epics ScanDB data is setup with `Instruments` and a postgresql
database, saved positions from one or more instruments can be included in the
display, for example to move a camera or shutter into saved positions.
