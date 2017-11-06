import wx
import wx.lib.mixins.inspection
import numpy as np
import sys
import time
import os
import shutil

from cStringIO import StringIO
from threading import Thread
from collections import OrderedDict
import base64
import json
import matplotlib
matplotlib.use('WXAgg')
from wxmplot import PlotFrame

from epics import caput, Motor
from epics.wx import EpicsFunction

from epics.wx.utils import (add_menu, pack, Closure, popup,
                            NumericCombo, SimpleText, FileSave, FileOpen,
                            SelectWorkdir, LTEXT, CEN, LCEN, RCEN, RIGHT)

from scipy.optimize import minimize
import skimage
import skimage.filters

from .configfile import StageConfig
from .icons import icons
from .controlpanel import ControlPanel
from .positionpanel import PositionPanel
from .overlayframe import OverlayFrame

from .imagepanel_fly2 import ImagePanel_Fly2, ConfPanel_Fly2
from .imagepanel_fly2 import ImagePanel_Fly2AD, ConfPanel_Fly2AD
from .imagepanel_epicsAD import ImagePanel_EpicsAD, ConfPanel_EpicsAD
from .imagepanel_weburl import ImagePanel_URL, ConfPanel_URL

ALL_EXP  = wx.ALL|wx.EXPAND|wx.GROW
CEN_ALL  = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL
LEFT_CEN = wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL
LEFT_TOP = wx.ALIGN_LEFT|wx.ALIGN_TOP
LEFT_BOT = wx.ALIGN_LEFT|wx.ALIGN_BOTTOM
CEN_TOP  = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_TOP
CEN_BOT  = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM


def image_blurriness(imgpanel, full=False):
    """ get image blurriness of central half of intensity"""
    img = imgpanel.GrabNumpyImage().astype(np.float32)
    if len(img.shape) == 3:
        img = img.sum(axis=2)

    w, h = img.shape
    w1, w2, h1, h2 = int(w/4.0), int(3*w/4.0), int(h/4.0), int(3*h/4.0)
    img = img[w1:w2, h1:h2]
    img[np.where(img<0.5)] = 0.5
    img = img/img.max()

    sobel = 50*skimage.filters.sobel(img).sum()/1000.0
    entropy = (img*np.log(img)).sum()/1000.0
    return (sobel, entropy)

class StageFrame(wx.Frame):
    htmllog  = 'SampleStage.html'
    html_header = """<html><head><title>Sample Stage Log</title></head>
<meta http-equiv='Pragma'  content='no-cache'>
<meta http-equiv='Refresh' content='300'>
<body>
    """

    def __init__(self, inifile='SampleStage.ini', size=(1600, 800),
                 ask_workdir=True, orientation='landscape'):
        super(StageFrame, self).__init__(None, wx.ID_ANY,
                                         style=wx.DEFAULT_FRAME_STYLE,
                                         size=size)

        self.SetFont(wx.Font(10, wx.SWISS, wx.NORMAL, wx.BOLD, False))
        self.read_config(configfile=inifile, get_dir=ask_workdir)
        self.overlay_frame = None
        self.last_pixel = None
        self.xhair_pixel = None
        self.create_frame(size=size, orientation=orientation)
        self.xplot = None
        self.yplot = None
        self.imgpanel.Start()

    def create_frame(self, size=(1600, 800), orientation='landscape'):
        "build main frame"
        self.statusbar = self.CreateStatusBar(2, wx.CAPTION)
        self.statusbar.SetStatusWidths([-4, -1])
        for index in range(2):
            self.statusbar.SetStatusText('', index)
        config = self.config

        opts = dict(writer=self.write_framerate,
                    leftdown_cb=self.onSelectPixel,
                    motion_cb=self.onPixelMotion,
                    xhair_cb=self.onShowCrosshair,
                    center_cb=self.onMoveToCenter,
                    autosave_file=self.autosave_file)

        autofocus_cb = self.onAutoFocus

        if self.cam_type.startswith('fly2'):
            opts['camera_id'] = int(self.cam_fly2id)
            opts['output_pv'] = config['camera'].get('output_pv', None)
            ImagePanel, ConfPanel = ImagePanel_Fly2, ConfPanel_Fly2
        elif self.cam_type.startswith('adfly'):
            opts['prefix'] = self.cam_adpref
            ImagePanel, ConfPanel = ImagePanel_Fly2AD, ConfPanel_Fly2AD
            autofocus_cb = None
        elif self.cam_type.startswith('area'):
            opts['prefix'] = self.cam_adpref
            ImagePanel, ConfPanel = ImagePanel_EpicsAD, ConfPanel_EpicsAD
        elif self.cam_type.startswith('webcam'):
            opts['url'] = self.cam_weburl
            ImagePanel, ConfPanel = ImagePanel_URL, ConfPanel_URL

        self.imgpanel  = ImagePanel(self, **opts)
        self.imgpanel.SetMinSize((285, 250))

        if orientation.lower().startswith('land'):
            size = (1600, 800)
            self.cpanel = wx.CollapsiblePane(self, label='Show Controls',
                                             style=wx.CP_DEFAULT_STYLE|wx.CP_NO_TLW_RESIZE)

            self.Bind(wx.EVT_COLLAPSIBLEPANE_CHANGED, self.OnPaneChanged, self.cpanel)

            ppanel = wx.Panel(self.cpanel.GetPane())

            self.pospanel  = PositionPanel(ppanel, self, config=config['scandb'])
            self.pospanel.SetMinSize((250, 700))

            self.ctrlpanel = ControlPanel(ppanel,
                                          groups=config['stage_groups'],
                                          config=config['stages'],
                                          autofocus=autofocus_cb)

            self.confpanel = ConfPanel(ppanel,
                                       image_panel=self.imgpanel, **opts)

            msizer = wx.GridBagSizer(2, 2)
            msizer.Add(self.ctrlpanel, (0, 0), (1, 1), ALL_EXP|LEFT_TOP, 1)
            msizer.Add(self.confpanel, (1, 0), (1, 1), ALL_EXP|LEFT_TOP, 1)
            msizer.Add(self.pospanel,  (0, 1), (2, 1), ALL_EXP|LEFT_TOP, 2)

            pack(ppanel, msizer)

            sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.AddMany([(self.imgpanel,  5, ALL_EXP|LEFT_CEN, 0),
                           (self.cpanel,    1, ALL_EXP|LEFT_CEN|wx.GROW, 1)])

            pack(self, sizer)
            self.cpanel.Collapse(False)
            self.cpanel.SetLabel('Hide Controls')

        else: # portrait mode
            size = (900, 1500)
            ppanel = wx.Panel(self)
            self.pospanel  = PositionPanel(ppanel, self, config=config['scandb'])
            self.pospanel.SetMinSize((250, 450))
            self.ctrlpanel = ControlPanel(ppanel,
                                          groups=config['stage_groups'],
                                          config=config['stages'],
                                          autofocus=autofocus_cb)

            self.confpanel = ConfPanel(ppanel,
                                       image_panel=self.imgpanel, **opts)

            msizer = wx.GridBagSizer(3, 3)
            msizer.Add(self.ctrlpanel, (0, 0), (1, 1), ALL_EXP|LEFT_TOP, 1)
            msizer.Add(self.pospanel,  (0, 1), (2, 1), ALL_EXP|LEFT_TOP, 2)
            msizer.Add(self.confpanel, (0, 2), (1, 1), ALL_EXP|LEFT_TOP, 1)

            pack(ppanel, msizer)

            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.AddMany([(self.imgpanel,  5, ALL_EXP|LEFT_CEN, 0),
                           (ppanel,    1, ALL_EXP|LEFT_CEN|wx.GROW, 1)])

            pack(self, sizer)

        self.imgpanel.confpanel = self.confpanel
        self.SetSize(size)
        if len(self.iconfile) > 0:
            self.SetIcon(wx.Icon(self.iconfile, wx.BITMAP_TYPE_ICO))

        ex  = [{'shape':'circle', 'color': (255, 0, 0),
                'width': 1.5, 'args': (0.5, 0.5, 0.007)},
               {'shape':'line', 'color': (200, 100, 0),
                'width': 2.0, 'args': (0.7, 0.97, 0.97, 0.97)}]

        self.create_menus()
        self.Bind(wx.EVT_CLOSE, self.onClose)
        self.init_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onInitTimer, self.init_timer)
        self.init_timer.Start(1000)

    def OnPaneChanged(self, evt=None):
        self.Layout()
        if self.cpanel.IsExpanded():
            self.cpanel.SetLabel('Hide Controls')
        else:
            self.cpanel.SetLabel('Show Controls')
        self.imgpanel.Refresh()


    def onInitTimer(self, event=None, **kws):
        if self.imgpanel.full_size is not None:
            if 'overlays' in self.config:
                olays = self.config['overlays']
                sbar = [float(x) for x in olays['scalebar'].split()]
                circ = [float(x) for x in olays['circle'].split()]

                img_x, img_y = self.imgpanel.full_size
                pix_x = float(self.config['camera']['calib_x'])
                iscale = 0.5/abs(pix_x * img_x)

                ssiz, sx, sy, swid, scolr, scolg, scolb = sbar
                csiz, cx, cy, cwid, ccolr, ccolg, ccolb = circ

                cargs = [cx, cy, csiz*iscale]
                sargs = [sx - ssiz*iscale, sy, sx + ssiz*iscale, sy]

                scol = wx.Colour(int(scolr), int(scolg), int(scolb))
                ccol = wx.Colour(int(ccolr), int(ccolg), int(ccolb))

                dobjs = [dict(shape='Line', width=swid,
                              style=wx.SOLID, color=scol, args=sargs),
                         dict(shape='Circle', width=cwid,
                              style=wx.SOLID, color=ccol, args=cargs)]

                if self.xhair_pixel is not None:
                    xwid, xcolr, xcolg, xcolb = swid, scolr, scolg, scolb
                    xcol = wx.Colour(int(xcolr), int(xcolg), int(xcolb))
                    xcol = wx.Colour(int(20), int(300), int(250))
                    hx = self.xhair_pixel['x']
                    hy = self.xhair_pixel['y']
                    xargs = [hx - ssiz*iscale, hy - ssiz*iscale, hx + ssiz*iscale, hy + ssiz*iscale]

                    dobjs.append(dict(shape='Line', width=2,
                                      style=wx.SOLID, color=xcol, args=xargs))
                    #print "Showing xhair: ", xargs
                # print 'Draw Objects ', dobjs
                self.imgpanel.draw_objects = dobjs
            self.init_timer.Stop()


    def onChangeCamera(self, evt=None):
        if not self.cam_type.startswith('area'):
            print 'How did that happen?'
            return

        name = self.cam_adpref
        prefix = None
        dlg = wx.TextEntryDialog(self, 'Enter PV for Area Detector',
                                 caption='Enter PV for Area Detector',
                                 defaultValue=name)
        dlg.Raise()
        if dlg.ShowModal() == wx.ID_OK:
            prefix = dlg.GetValue()
        dlg.Destroy()
        if prefix is not None:
            self.imgpanel.set_prefix(prefix)
            self.confpanel.set_prefix(prefix)
            self.cam_adpref = prefix


    def create_menus(self):
        "Create the menubar"
        mbar  = wx.MenuBar()
        fmenu = wx.Menu()
        pmenu = wx.Menu()
        omenu = wx.Menu()
        add_menu(self, fmenu, label="&Read Config", text="Read Configuration",
                 action = self.onReadConfig)

        add_menu(self, fmenu, label="&Save Config", text="Save Configuration",
                 action = self.onSaveConfig)

        add_menu(self, fmenu, label="Show Projections\tCtrl+G",
                 text="Start Projection Plots",
                 action = self.onStartProjections)

        add_menu(self, fmenu, label="Print Blurriness\tCtrl+B",
                 text="print blurriness",
                 action = self.onReportBlurry)

        add_menu(self, fmenu, label="Stop Projection\tCtrl+C",
                 text="Stop Projection Plots",
                 action = self.onStopProjections)

        add_menu(self, fmenu, label="Select &Working Directory\tCtrl+W",
                 text="change Working Folder",
                 action = self.onChangeWorkdir)

        if self.cam_type.startswith('area'):
            add_menu(self, fmenu, label="Change AreaDetector",
                     text="Change Camera to different AreaDetector",
                     action = self.onChangeCamera)

        fmenu.AppendSeparator()
        add_menu(self, fmenu, label="E&xit\tCtrl+x",  text="Quit Program",
                 action = self.onClose)

        add_menu(self, pmenu, label="Export Positions", text="Export Positions",
                 action = self.onExportPositions)
        add_menu(self, pmenu, label="Import Positions", text="Import Positions",
                 action = self.onImportPositions)
        add_menu(self, pmenu, label="Erase Many Positions\tCtrl+E",
                 text="Select Multiple Positions to Erase",
                 action = self.onEraseMany)


        add_menu(self, omenu, label="Image Overlays",
                 text="Setup Image Overlays",
                 action = self.onConfigOverlays)


        vmove  = wx.NewId()
        verase = wx.NewId()
        vreplace = wx.NewId()
        cenfine = wx.NewId()
        self.menu_opts = {vmove: 'v_move', verase: 'v_erase',
                          vreplace: 'v_replace',
                          cenfine: 'center_with_fine_stages'}

        mitem = omenu.Append(vmove, "Verify Go To ",
                             "Prompt to Verify Moving with 'Go To'",
                             wx.ITEM_CHECK)
        mitem.Check()
        self.Bind(wx.EVT_MENU, self.onMenuOption, mitem)

        mitem = omenu.Append(verase, "Verify Erase",
                     "Prompt to Verify Erasing Positions", wx.ITEM_CHECK)
        mitem.Check()
        self.Bind(wx.EVT_MENU, self.onMenuOption, mitem)

        mitem = omenu.Append(vreplace, "Verify Overwrite",
                     "Prompt to Verify Overwriting Positions",  wx.ITEM_CHECK)
        mitem.Check()
        self.Bind(wx.EVT_MENU, self.onMenuOption, mitem)

        mitem = omenu.Append(cenfine, "Center With Fine Stages",
                     "Bring to Center will move the Fine Stages", wx.ITEM_CHECK)
        mitem.Check(0)
        self.Bind(wx.EVT_MENU, self.onMenuOption, mitem)

        omenu.AppendSeparator()

        # print 'Create Menus ',      self.ctrlpanel.subpanels
        # for key, val in self.config['stages'].items():
        #     print key, val

        for name, panel in self.ctrlpanel.subpanels.items():
            show = 0
            label = 'Enable %s' % name
            mid = wx.NewId()
            self.menu_opts[mid] = label
            for mname, data in self.config['stages'].items():
                if data['group'] == name:
                    show = show + data['show']
            mitem = omenu.Append(mid, label, label, wx.ITEM_CHECK)
            if show > 0 :
                mitem.Check()
            self.Bind(wx.EVT_MENU, Closure(self.onShowHide, name=name, panel=panel), mitem)

        mbar.Append(fmenu, '&File')
        mbar.Append(omenu, '&Options')
        mbar.Append(pmenu, 'Positions')

        if len(self.config['scandb'].get('offline', '')):
            cmenu = wx.Menu()
            # add_menu(self, cmenu, label="Calibrate Microscope",
            #          text="Calibrate to Offline Microscope",
            #          action = self.pospanel.onMicroscopeCalibrate)
            add_menu(self, cmenu, label="Copy Positions from Offline Microscope",
                     text="Copy Positions from Offline Microscope",
                     action = self.pospanel.onMicroscopeTransfer)

            mbar.Append(cmenu, 'Offline Microscope')

        self.SetMenuBar(mbar)

    def onShowHide(self, event=None, panel=None, name='---'):
        showval = {True:1, False:0}[event.IsChecked()]
        if showval:
            panel.Enable()
        else:
            panel.Disable()

        for mname, data in self.config['stages'].items():
            if data['group'] == name:
                data['show'] = showval

    def onEraseMany(self, evt=None, **kws):
        self.pospanel.onEraseMany(event=evt)
        evt.Skip()

    def onConfigOverlays(self, evt=None, **kws):
        shown = False
        if self.overlay_frame is not None:
            try:
                self.overlay_frame.Raise()
                shown = True
            except:
                del self.overlay_frame
        if not shown:
            self.overlayframe = OverlayFrame(image_panel=self.imgpanel,
                                             config=self.config)

    def onMenuOption(self, evt=None):
        """events for options menu: move, erase, overwrite """
        setattr(self, self.menu_opts[evt.GetId()], evt.IsChecked())

    def read_config(self, configfile=None, get_dir=False):
        "open/read ini config file"
        if get_dir:
            ret = SelectWorkdir(self)
            if ret is None:
                self.Destroy()
            os.chdir(ret)
        self.cnf = StageConfig(configfile)
        self.config = self.cnf.config
        gui = self.config['gui']
        self.workdir_file  = gui.get('workdir_file', 'sampleviewer_workdir.txt')
        self.iconfile      = gui.get('icon_file', '')
        self.autosave_file = gui.get('autosave_file', 'SampleStage_autosave.ini')
        self.v_move    = gui.get('verify_move', True)
        self.v_erase   = gui.get('verify_erase', True)
        self.v_replace = gui.get('verify_overwrite', True)
        self.center_with_fine_stages = gui.get('center_with_fine_stages', False)
        self.SetTitle(gui.get('title', 'Microscope'))

        cam = self.config['camera']
        self.imgdir     = cam.get('image_folder', 'Sample_Images')
        self.cam_type   = cam.get('type', 'fly2').lower()
        self.cam_fly2id = cam.get('fly2_id', 0)
        self.cam_adpref = cam.get('ad_prefix', '')
        self.cam_adform = cam.get('ad_format', 'JPEG')
        self.cam_weburl = cam.get('web_url', 'http://164.54.160.115/jpg/2/image.jpg')
        self.get_cam_calib()
        try:
            pref = self.imgdir.split('_')[0]
        except:
            pref = 'Sample'
        self.htmllog = '%sStage.html' % pref
        if not os.path.exists(self.imgdir):
            os.makedirs(self.imgdir)
        if not os.path.exists(self.htmllog):
            self.begin_htmllog()

        self.config = self.cnf.config
        self.stages = OrderedDict()
        for mname, data in self.config.get('stages', {}).items():
            mot = Motor(name=mname)
            if data['prec'] is None:
                data['prec'] = mot.precision
            if data['desc'] is None:
                data['desc'] = mot.description
            if data['maxstep'] is None:
                data['maxstep'] = (mot.high_limit - mot.low_limit)/2.10
            self.stages[mname] = data

    def get_cam_calib(self):
        cam = self.config['camera']
        cx = self.cam_calibx = float(cam.get('calib_x', 0.001))
        cy = self.cam_caliby = float(cam.get('calib_y', 0.001))
        return cx, cy

    def begin_htmllog(self):
        "initialize log file"
        fout = open(self.htmllog, 'w')
        fout.write(self.html_header)
        fout.close()

    def save_image(self, fname):
        "save image to file"
        imgdata = self.imgpanel.SaveImage(fname)
        if imgdata is None:
            self.write_message('could not save image to %s' % fname)
        else:
            self.write_message('saved image to %s' % fname)
        return imgdata

    def autosave(self, positions=None):
        self.cnf.Save(self.autosave_file, positions=positions)

    def write_htmllog(self, name, thispos):
        stages  = self.config['stages']
        img_folder = self.config['camera']['image_folder']
        junk, img_file = os.path.split(thispos['image'])
        imgfile = os.path.join(img_folder, img_file)

        txt = []
        html_fmt ="""<hr>
    <table><tr><td><a href='%s'> <img src='%s' width=350></a></td>
    <td><table><tr><td>Position:</td><td>%s</td><td>%s</td></tr>
    <tr><td>Motor Name</td><td>PV Name</td><td>Value</td></tr>
    %s
    </table></td></tr></table>"""
        pos_fmt ="    <tr><td> %s </td><td> %s </td><td>   %f</td></tr>"
        for pvname, value in thispos['position'].items():
            txt.append(pos_fmt % (stages[pvname]['desc'], pvname, value))

        fout = open(self.htmllog, 'a')
        fout.write(html_fmt % (imgfile, imgfile, name,
                               thispos['timestamp'],  '\n'.join(txt)))
        fout.close()

    def write_message(self, msg='', index=0):
        "write to status bar"
        self.statusbar.SetStatusText(msg, index)

    def write_framerate(self, msg):
        "write to status bar"
        self.statusbar.SetStatusText(msg, 1)

    def onShowCrosshair(self, event=None, show=True, **kws):
        self.xhair_pixel = None
        if show:
            self.xhair_pixel = self.last_pixel
            # print "Set XHAIR ", self.xhair_pixel

    def onAFTimer(self, event=None, **kws):
        if self.af_done:
            self.af_thread.join()
            self.af_timer.Stop()
            if self.ctrlpanel.af_message is not None:
                self.ctrlpanel.af_message.SetLabel('')
            self.ctrlpanel.af_button.Enable()
            # print("AF Done: plot results")
            # x, y = self.af_data
            # plotf = PlotFrame(self)
            # plotf.plot(x, y, xlabel='focus', ylabel='focus score')
            # plotf.Show()

    def onAutoFocus(self, event=None, **kws):
        self.af_done = False
        self.ctrlpanel.af_button.Disable()
        self.af_thread = Thread(target=self.do_autofocus)
        self.af_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onAFTimer, self.af_timer)
        self.af_timer.Start(2000)
        self.af_thread.start()

    def do_autofocus(self):
        report = None
        if self.ctrlpanel.af_message is not None:
            report = self.ctrlpanel.af_message.SetLabel
        if report is not None:
            report('Auto-setting exposure')
        self.imgpanel.AutoSetExposureTime()
        report('Auto-focussing start')

        zstage = self.ctrlpanel.motors['z']._pvs['VAL']

        start_pos = zstage.get()
        min_pos = start_pos - 2.50
        max_pos = start_pos + 2.50

        step, min_step = 0.003*(81), 0.002
        # start trying both directions:

        def get_score():
            sobel, entropy = image_blurriness(self.imgpanel)
            return 0.5*entropy - sobel

        score_start = best_score = get_score()
        best_pos = start_pos

        zstage.put(start_pos+step/2.0, wait=True)
        time.sleep(0.15)
        score_plus = get_score()
        direction = -1
        if score_plus < score_start:
            direction = 1
            best_score = score_plus
            best_post = start_pos + step/2.0

        zstage.put(best_pos, wait=True)
        count = 0
        report('Auto-focussing finding focus')
        posvals = []
        scores  = []
        while step >= min_step and count < 32:
            self.imgpanel.Refresh()
            count += 1
            pos = zstage.get() + step * direction
            if pos < min_pos or pos > max_pos:
                break
            zstage.put(pos, wait=True, timeout=3.0)
            time.sleep(0.15)
            score = get_score() # image_blurriness(self.imgpanel)
            report('Auto-focussing step=%.3f' % step)
            # print 'Focus %2.2i: (%.3f, %.2f) best=(%.3f, %.2f) step=%.3f' % (
            #     count, pos, score, best_pos, best_score, step*direction)
            posvals.append(pos)
            scores.append(score)
            if score < best_score:
                best_score = score
                best_pos = pos
            else:
                # best_score = score
                step = step / 3.0
                if step < min_step:
                    break
                direction = -direction
                zstage.put(best_pos, wait=True, timeout=3.0)
                time.sleep(0.15)
            last_score = score
        zstage.put(best_pos)
        self.af_done = True
        self.af_data = (posvals, scores)
        report('Auto-focussing done.')




    def onMoveToCenter(self, event=None, **kws):
        "bring last pixel to image center"
        p = self.last_pixel
        if p is None:
            return

        cal_x, cal_y = self.get_cam_calib()
        dx = 0.001*cal_x*(p['x']-p['xmax']/2.0)
        dy = 0.001*cal_y*(p['y']-p['ymax']/2.0)

        mots = self.ctrlpanel.motors

        xmotor, ymotor = 'x', 'y'
        if self.center_with_fine_stages and 'finex' in mots:
            xmotor, ymotor = 'finex', 'finey'

        xscale, yscale = 1.0, 1.0
        for stage_info in self.stages.values():
            if stage_info['desc'].lower() == xmotor:
                xscale = stage_info['scale']
            if stage_info['desc'].lower() == ymotor:
                yscale = stage_info['scale']

        mots[xmotor].VAL += dx*xscale
        mots[ymotor].VAL += dy*yscale
        self.onSelectPixel(p['xmax']/2.0, p['ymax']/2.0,
                           xmax=p['xmax'], ymax=p['ymax'])

    def onSelectPixel(self, x, y, xmax=100, ymax=100):
        " select a pixel from image "
        self.last_pixel = dict(x=x, y=y, xmax=xmax, ymax=ymax)
        cal_x, cal_y = self.get_cam_calib()
        self.confpanel.on_selected_pixel(x, y, xmax, ymax,
                                         cam_calibx=cal_x,
                                         cam_caliby=cal_y)

    def onPixelMotion(self, x, y, xmax=100, ymax=100):
        " select a pixel from image "
        fmt  = """Pixel=(%i, %i) (%.1f, %.1f)um from center, (%.1f, %.1f)um from selected"""
        if x > 0 and x < xmax and y > 0 and y < ymax:
            dx = abs(self.cam_calibx*(x-xmax/2.0))
            dy = abs(self.cam_caliby*(y-ymax/2.0))
            ux, uy = 0, 0
            if self.last_pixel is not None:
                lastx = self.last_pixel['x']
                lasty = self.last_pixel['y']
                ux = abs(self.cam_calibx*(x-lastx))
                uy = abs(self.cam_caliby*(y-lasty))

            pix_msg = fmt % (x, y, dx, dy, ux, uy)
            self.write_message(pix_msg)

            if not self.confpanel.img_size_shown:
                self.confpanel.img_size.SetLabel("(%i, %i)" % (xmax, ymax))
                self.confpanel.img_size_shown = True

    def onClose(self, event=None):
        if wx.ID_YES == popup(self, "Really Quit?", "Exit Sample Stage?",
                              style=wx.YES_NO|wx.NO_DEFAULT|wx.ICON_QUESTION):

            fout = open(self.workdir_file, 'w')
            fout.write("%s\n" % os.path.abspath(os.curdir))
            fout.close()
            self.imgpanel.Stop()
            try:
                self.overlay_frame.Destroy()
            except:
                pass
            self.Destroy()

    def onExportPositions(self, event=None):
        curpath = os.getcwd()
        fname = FileSave(self, 'Export Positions File',
                         wildcard='Position Files (*.pos)|*.pos|All files (*.*)|*.*',
                         default_file='Save.pos')
        if fname is not None:
            self.pospanel.SavePositions(fname)

        self.write_message('Saved Positions File %s' % fname)
        os.chdir(curpath)

    def onImportPositions(self, event=None):
        curpath = os.getcwd()
        fname = FileOpen(self, 'Import Positions File',
                         wildcard='Position Files (*.pos)|*.pos|All files (*.*)|*.*',
                         default_file='Save.pos')
        if fname is not None:
            self.pospanel.LoadPositions(fname)

        self.write_message('Loaded Positions from File %s' % fname)
        os.chdir(curpath)


    def onChangeWorkdir(self, event=None):
        ret = SelectWorkdir(self)
        if ret is None:
            return
        os.chdir(ret)
        cam = self.config['camera']
        self.imgdir     = cam.get('image_folder', 'Sample_Images')
        if not os.path.exists(self.imgdir):
            os.makedirs(self.imgdir)
        if not os.path.exists(self.htmllog):
            self.begin_htmllog()


    def onReportBlurry(self, event=None):
        score = image_blurriness(self.imgpanel, full=True)
        tscore = -(5*score[0] - score[1])
        print(" blurriness: %.3f  %.3f -> %.3f " % (score[0], score[1], tscore))

    def onStartProjections(self, event=None):
        try:
            self.xplot.Raise()
        except:
            self.xplot = PlotFrame(parent=self)
        try:
            self.yplot.Raise()
        except:
            self.yplot = PlotFrame(parent=self)

        self.proj_start = True
        self.proj_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onShowProjections, self.proj_timer)
        self.proj_timer.Start(500)


    def onStopProjections(self, event=None):
        self.proj_timer.Stop()


    def onShowProjections(self, event=None):
        dat = self.imgpanel.grab_data()
        shape = dat.shape
        if len(shape) == 3:
            dat = dat.sum(axis=2)
        cx, cy = self.get_cam_calib()
        kws = dict(ylabel='intensity',
                   xlabel='distance ($\mu\mathrm{m}$)',
                   marker='+', markersize=4)

        _y = (np.arange(shape[0]) - shape[0]/2.0) *abs(cx)
        _x = (np.arange(shape[1]) - shape[1]/2.0) *abs(cy)
        _xi = dat.sum(axis=0)
        _yi = dat.sum(axis=1)
        ymin = min((min(_xi), min(_yi)))
        ymax = max((max(_xi), max(_yi)))

        if self.proj_start:
            self.xplot.plot(_x, _xi, title='X projection', **kws)
            self.yplot.plot(_y, _yi, title='Y projection', **kws)
            self.xplot.Show()
            self.yplot.Show()
            self.proj_start = False
        else:
            self.xplot.panel.update_line(0, _x, _xi, draw=True, update_limits=True)
            self.yplot.panel.update_line(0, _y, _yi, draw=True, update_limits=True)

            self.xplot.panel.axes.set_ylim((ymin, ymax), emit=True)
            self.yplot.panel.axes.set_ylim((ymin, ymax), emit=True)

            # print 'X lims: ', self.xplot.panel.conf.zoom_lims, xlims
            # self.xplot.panel.set_xylims(xlims)
            # self.yplot.panel.set_xylims(ylims)

    def onSaveConfig(self, event=None):
        fname = FileSave(self, 'Save Configuration File',
                         wildcard='INI (*.ini)|*.ini|All files (*.*)|*.*',
                         default_file='SampleStage.ini')
        if fname is not None:
            self.cnf.Save(fname)
        self.write_message('Saved Configuration File %s' % fname)


    def onReadConfig(self, event=None):
        curpath = os.getcwd()
        fname = FileOpen(self, 'Read Configuration File',
                         wildcard='INI (*.ini)|*.ini|All files (*.*)|*.*',
                         default_file='SampleStage.ini')
        if fname is not None:
            self.read_config(fname)
            self.connect_motors()
            self.pospanel.set_positions(self.config['positions'])
        self.write_message('Read Configuration File %s' % fname)
        os.chdir(curpath)

class ViewerApp(wx.App, wx.lib.mixins.inspection.InspectionMixin):
    def __init__(self, inifile=None, debug=False, ask_workdir=True,
                 orientation='landscape', **kws):
        self.inifile = inifile
        self.orientation = orientation
        self.debug = debug
        self.ask_workdir = ask_workdir
        wx.App.__init__(self, **kws)

    def createApp(self):
        frame = StageFrame(inifile=self.inifile,
                           orientation=self.orientation,
                           ask_workdir=self.ask_workdir)
        frame.Show()
        self.SetTopWindow(frame)

    def OnInit(self):
        self.createApp()
        if self.debug:
            self.ShowInspectionTool()
        return True

if __name__ == '__main__':
    app = ViewerApp(inifile=None, debug=True)
    app.MainLoop()

"""
        def residual(vals):
            zval = min(max_pos, max(min_pos, vals[0]))
            zstage.put(zval, wait=True)
            time.sleep(0.1)
            score = image_blurriness(self.imgpanel)
            print 'Value: ', vals, zval, score
            return score

        minimize(residual, [zstage.get()], options={'xtol':0.002,
                                                    'maxfev':25})

"""
