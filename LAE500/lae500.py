#!/usr/bin/python
"""
Epics LAE-500 control
"""
import time
import numpy as np

import wx
from wx import (GROW, ALL, ALIGN_LEFT, ALIGN_CENTER, EXPAND)

from epics import get_pv
from epics.wx import (EpicsFunction, PVText)
from wxutils import (SimpleText, Button, pack)

from wxmplot.plotpanel import PlotPanel

LAE_PREFIX = '13LAE500:LAE500'
_pvnames = ('X', 'Z', 'Y_COEFF', 'Z_COEFF', 'Y_COEFF_RBV', 'Z_COEFF_RBV')


STY  = GROW|ALL
LSTY = ALIGN_LEFT|EXPAND|ALL
CSTY = ALIGN_CENTER

# https://scipython.com/blog/direct-linear-least-squares-fitting-of-an-ellipse/
def fit_ellipse(x, y):
    """
    Fit the coefficients a,b,c,d,e,f, representing an ellipse described by
    the formula F(x,y) = ax^2 + bxy + cy^2 + dx + ey + f = 0 to the provided
    arrays of data points x=[x1, x2, ..., xn] and y=[y1, y2, ..., yn].

    Based on the algorithm of Halir and Flusser, 'Numerically stable direct
    least squares fitting of ellipses'.
    """
    d1 = np.vstack([x**2, x*y, y**2]).T
    d2 = np.vstack([x, y, np.ones(len(x))]).T
    s1 = d1.T @ d1
    s2 = d1.T @ d2
    t = -np.linalg.inv(d2.T @ d2) @ s2.T
    m = s1 + s2 @ t
    c = np.array(((0, 0, 2), (0, -1, 0), (2, 0, 0)), dtype=float)
    m = np.linalg.inv(c) @ m
    _, eigvec = np.linalg.eig(m)
    con = 4 * eigvec[0]* eigvec[2] - eigvec[1]**2
    ak = eigvec[:, np.nonzero(con > 0)[0]]
    return np.concatenate((ak, t @ ak)).ravel()


def cart_to_pol(coeffs):
    """Convert the cartesian conic coefficients, (a, b, c, d, e, f), to the
    ellipse parameters, where F(x, y) = ax^2 + bxy + cy^2 + dx + ey + f = 0.
    The returned parameters are x0, y0, ap, bp, e, phi, where (x0, y0) is the
    ellipse centre; (ap, bp) are the semi-major and semi-minor axes,
    respectively; e is the eccentricity; and phi is the rotation of the semi-
    major axis from the x-axis.
    """
    # We use the formulas from https://mathworld.wolfram.com/Ellipse.html
    # which assumes a cartesian form ax^2 + 2bxy + cy^2 + 2dx + 2fy + g = 0.
    # Therefore, rename and scale b, d and f appropriately.
    a = coeffs[0]
    b = coeffs[1] / 2
    c = coeffs[2]
    d = coeffs[3] / 2
    f = coeffs[4] / 2
    g = coeffs[5]

    den = b**2 - a*c
    if den > 0:
        raise ValueError('coeffs do not represent an ellipse: b^2 - 4ac must'
                         ' be negative!')

    # The location of the ellipse centre.
    x0, y0 = (c*d - b*f) / den, (a*f - b*d) / den

    num = 2 * (a*f**2 + c*d**2 + g*b**2 - 2*b*d*f - a*c*g)
    fac = np.sqrt((a - c)**2 + 4*b**2)
    # The semi-major and semi-minor axis lengths (these are not sorted).
    ap = np.sqrt(num / den / (fac - a - c))
    bp = np.sqrt(num / den / (-fac - a - c))

    # Sort the semi-major and semi-minor axis lengths but keep track of
    # the original relative magnitudes of width and height.
    width_gt_height = True
    if ap < bp:
        width_gt_height = False
        ap, bp = bp, ap

    # The eccentricity.
    r = (bp/ap)**2
    if r > 1:
        r = 1/r
    e = np.sqrt(1 - r)

    # The angle of anticlockwise rotation of the major-axis from x-axis.
    if b == 0:
        phi = 0 if a < c else np.pi/2
    else:
        phi = np.arctan((2.*b) / (a - c)) / 2
        if a > c:
            phi += np.pi/2
    if not width_gt_height:
        # Ensure that phi is the angle to rotate to the semi-major axis.
        phi += np.pi/2
    phi = phi % np.pi
    return x0, y0, ap, bp, e, phi


def get_ellipse_pts(params, npts=500, tmin=0, tmax=2*np.pi):
    """
    Return npts points on the ellipse described by the params = x0, y0, ap,
    bp, e, phi for values of the parametric variable t between tmin and tmax.
    """
    x0, y0, ap, bp, _, phi = params
    # A grid of the parametric variable, t.
    t = np.linspace(tmin, tmax, npts)
    x = x0 + ap * np.cos(t) * np.cos(phi) - bp * np.sin(t) * np.sin(phi)
    y = y0 + ap * np.cos(t) * np.sin(phi) + bp * np.sin(t) * np.cos(phi)
    return x, y

class LAE500Frame(wx.Frame):
    about_msg =  """Epics LAE-500 Controller
Matt Newville <newville@cars.uchicago.edu>
"""

    def __init__(self, prefix=LAE_PREFIX):
        wx.Frame.__init__(self, None, -1, 'LAE 500', size=(750, 700),
                          style=wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL)

        self.pvs = {}
        for _pv in _pvnames:
            self.pvs[_pv] = get_pv(f'{prefix}_{_pv}')

        time.sleep(0.1)
        self.xvals = []
        self.zvals = []
        self.last_x = None
        self.last_z = None
        self.needs_refresh = False
        self.collecting = False
        self.has_plotdata = False

        sbar = self.CreateStatusBar(2, wx.CAPTION)
        sfont = sbar.GetFont()
        sfont.SetWeight(wx.BOLD)
        sfont.SetPointSize(10)
        sbar.SetFont(sfont)
        self.SetStatusWidths([-5, -2])
        self.SetStatusText('', 0)

        panel = wx.Panel(self)

        xlab = SimpleText(panel, ' X current:  ',   size=(75, -1), style=LSTY)
        zlab = SimpleText(panel, ' Z current:  ',   size=(75, -1), style=LSTY)
        xclab = SimpleText(panel, ' X center:',  size=(75, -1), style=LSTY)
        zclab = SimpleText(panel, ' Z center:',  size=(75, -1), style=LSTY)
        slab = SimpleText(panel, ' Status:  ',   size=(75, -1), style=LSTY)
        nlab = SimpleText(panel, ' N points:  ',   size=(75, -1), style=LSTY)

        self.status = SimpleText(panel, ' not collecting',  size=(100, -1), style=LSTY)
        self.nval = SimpleText(panel, ' -- ',  size=(100, -1), style=LSTY)

        self.xcen = SimpleText(panel, ' -- ',  size=(100, -1), style=LSTY)
        self.zcen = SimpleText(panel, ' -- ',  size=(100, -1), style=LSTY)

        elab = SimpleText(panel, ' Ellipse:  ',   size=(75, -1), style=LSTY)
        self.ellipse_text = SimpleText(panel, ' -- ',  size=(400, -1), style=LSTY)

        xval = PVText(panel, self.pvs['X'])
        zval = PVText(panel, self.pvs['Z'])
        # print(self.pvs['X'])

        bpanel = wx.Panel(panel)
        bsizer = wx.BoxSizer(wx.HORIZONTAL)
        bstart = Button(bpanel, label='Start',  size=(150, 30),
                        action=self.onStart)
        bstop  = Button(bpanel, label='Stop',  size=(150, 30),
                        action=self.onStop)
        berase = Button(bpanel, label='Erase',  size=(150, 30),
                        action=self.onErase)
        bfit  = Button(bpanel, label='Fit Ellipse',  size=(150, 30),
                       action=self.onFitEllipse)
        bsizer.Add(bstart, 0, wx.EXPAND|wx.ALL, 1)
        bsizer.Add(bstop,  0, wx.EXPAND|wx.ALL, 1)
        bsizer.Add(berase,  0, wx.EXPAND|wx.ALL, 1)
        bsizer.Add(bfit,   0, wx.EXPAND|wx.ALL, 1)

        pack(bpanel, bsizer)

        sizer = wx.GridBagSizer(3, 3)
        sizer.Add(xlab, (0, 0), (1, 1), LSTY|wx.EXPAND, 2)
        sizer.Add(xval, (0, 1), (1, 1), LSTY, 1)
        sizer.Add(zlab, (0, 2), (1, 1), LSTY|wx.EXPAND, 2)
        sizer.Add(zval, (0, 3), (1, 1), LSTY, 1)
        sizer.Add(slab, (0, 4), (1, 1), LSTY, 1)
        sizer.Add(self.status, (0, 5), (1, 1), LSTY, 1)

        sizer.Add(xclab,     (1, 0), (1, 1), LSTY|wx.EXPAND, 2)
        sizer.Add(self.xcen, (1, 1), (1, 1), LSTY, 1)
        sizer.Add(zclab,     (1, 2), (1, 1), LSTY|wx.EXPAND, 2)
        sizer.Add(self.zcen, (1, 3), (1, 1), LSTY, 1)
        sizer.Add(nlab,      (1, 4), (1, 1), LSTY|wx.EXPAND, 2)
        sizer.Add(self.nval, (1, 5), (1, 1), LSTY, 1)

        sizer.Add(elab,      (2, 0), (1, 1), LSTY|wx.EXPAND, 2)
        sizer.Add(self.ellipse_text, (2, 1), (1, 5), LSTY, 1)

        sizer.Add(bpanel, (3, 0), (1, 7), LSTY|wx.EXPAND, 2)

        pack(panel, sizer)

        self.plotpanel = PlotPanel(self)
        self.plotpanel.messenger = self.write_message

        tsizer = wx.BoxSizer(wx.VERTICAL)
        tsizer.Add(panel, 0, 1)
        tsizer.Add(self.plotpanel, 1, wx.EXPAND|wx.ALL)

        pack(self, tsizer)
        self.pvs['X'].add_callback(self.onXval)
        self.pvs['Z'].add_callback(self.onZval)

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onUpdatePlot, self.timer)
        self.timer.Start(100)


    def write_message(self, s, panel=0):
        """write a message to the Status Bar"""
        self.SetStatusText(s, panel)


    @EpicsFunction
    def onXval(self, pvname, value, **kws):
        if self.last_z is not None and self.collecting:
            self.zvals.append(self.last_z)
            self.xvals.append(value)
        self.last_x = value
        self.needs_refresh = True

    @EpicsFunction
    def onZval(self, pvname, value, **kws):
        if self.last_x is not None and self.collecting:
            self.xvals.append(self.last_x)
            self.zvals.append(value)
        self.last_z = value
        self.needs_refresh = True

    @EpicsFunction
    def onStart(self, name=None):
        self.collecting = True
        self.status.SetLabel('collecting')

    @EpicsFunction
    def onErase(self, name=None):
        self.xvals = []
        self.zvals = []
        self.xfit, self.zfit = None, None
        self.lastx = self.lastz = None
        self.collecting = False
        self.status.SetLabel('erased data')

    @EpicsFunction
    def onStop(self, name=None):
        self.collecting = False
        self.has_plotdata = False
        self.status.SetLabel('not collecting')


    @EpicsFunction
    def onFitEllipse(self, evt=None):
        print("fit ellipse ", len(self.xvals))
        coefs = fit_ellipse(np.array(self.xvals),
                            np.array(self.zvals))
        x0, y0, xh, yh, ex, phi = cart_to_pol(coefs)

        etext = f'center: [{x0:.2f}, {y0:.2f}], size: [{xh:.2f}, {yh:.2f}]'

        self.xfit, self.zfit = get_ellipse_pts((x0, y0, xh, yh, ex, phi))

        self.ellipse_text.SetLabel(etext)
        self.plotpanel.oplot(self.xfit, self.zfit,
                             linewidth=0.5,  markersize=0,
                             label='fit', delay_draw=False)

    def onUpdatePlot(self, event=None):
        if not self.collecting or not self.needs_refresh:
            return

        if (len(self.xvals) < 1 or len(self.zvals) < 1):
            return

        if self.has_plotdata:
            self.plotpanel.update_line(0, self.xvals, self.zvals,
                                       update_limits=True)

        else:
            self.plotpanel.plot(self.xvals, self.zvals,
                                linewidth=0, marker='o', markersize=2,
                                xlabel = 'X', ylabel = 'Z')
            self.has_plotdata = True


        self.plotpanel.canvas.draw()
        self.needs_refresh = False
        xc = (max(self.xvals) + min(self.xvals))/2.0
        zc = (max(self.zvals) + min(self.zvals))/2.0
        self.xcen.SetLabel("%.2f" % xc)
        self.zcen.SetLabel("%.2f" % zc)
        self.nval.SetLabel("%d" % len(self.xvals))



class LAE500App(wx.App):
    def __init__(self, prefix=LAE_PREFIX, debug=False, **kws):
        self.debug = debug
        self.prefix = prefix
        wx.App.__init__(self, **kws)

    def createApp(self):
        self.frame = LAE500Frame(prefix=self.prefix)
        self.frame.Show()
        self.SetTopWindow(self.frame)

    def OnInit(self):
        self.createApp()
        if self.debug:
            self.ShowInspectionTool()
        return True

LAE500App().MainLoop()
