from msaGlobal import GetFontSize, isLinux, SetModuleVersion
import wx
from math import atan2
from numpy import arange, angle, interp, log10, nan_to_num, pi, sqrt, tan
from util import si
from events import LogGUIEvent

SetModuleVersion("smithPanel",("1.30","EON","05/20/2014"))

debug = False

#==============================================================================
# A Smith chart window for Reflectance mode.

class SmithDialog(wx.Dialog):
    def __init__(self, frame):
        self.frame = frame
        specP = frame.specP
        self.prefs = p = frame.prefs
        framePos = frame.GetPosition()
        frameSize = frame.GetSize()
        self.pos = p.get("smithWinPos", (framePos.x + frameSize.x - 400,
                                framePos.y))
        self.size = p.get("smithWinSize", (400, 500))
        wx.Dialog.__init__(self, frame, -1, "Smith Chart", self.pos,
                        self.size, wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER)
        self.SetBackgroundColour(p.theme.backColor)
        sizer = wx.GridBagSizer(5, 5)
        c = wx.ALIGN_CENTER
        #chb = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM

        sizer.AddGrowableCol(0)
        sizer.AddGrowableRow(1)
        sizerV1 = wx.BoxSizer(wx.VERTICAL)
        st = wx.StaticText(self, -1, specP.title)
        ##st.SetBackgroundColour("YELLOW")
        sizerV1.Add(st, 0, c)
        self.chart = chart = SmithPanel(self, frame)
        sizer.Add(chart, (1, 0), flag=c|wx.EXPAND)
        sizer.Add(sizerV1, (0, 0), flag=c|wx.EXPAND|wx.ALL, border=10)
        self.msgText = st = wx.StaticText(self, -1, "")
        ##st.SetBackgroundColour("GREEN")
        sizer.Add(st, (2, 0), flag=c|wx.EXPAND|wx.ALL, border=10)

        self.SetSizer(sizer)
        self.Show()

    def Close(self, event=None):
        self.prefs.smithWinPos = self.GetPosition().Get()
        self.prefs.smithWinSize = self.GetSize().Get()
        self.Destroy()

#==============================================================================
# A Smith chart panel.

class SmithPanel(wx.Panel):
    def __init__(self, parent, frame):
        global fontSize
        fontSize = GetFontSize()
        self.frame = frame
        self.prefs = p = frame.prefs

        wx.Panel.__init__(self, parent, -1)
        self.SetBackgroundColour(p.theme.backColor)
        ##self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        self.Bind(wx.EVT_PAINT,        self.OnPaint)
        self.Bind(wx.EVT_SIZE,         self.OnSizeChanged)

    #--------------------------------------------------------------------------
    # Force the grid and other parts to be redrawn on a resize.

    def FullRefresh(self):
        if debug:
            print ("Smith.FullRefresh")
        self.Refresh()

    def OnSizeChanged(self, event):
        self.FullRefresh()
        event.Skip()   # (will continue handling event)

    #--------------------------------------------------------------------------
    # Repaint the Smith chart.

    def OnPaint(self, event):
        LogGUIEvent("Smith.OnPaint")
        frame = self.frame
        specP = frame.specP
        p = self.prefs
        self.vColors = vColors = p.theme.vColors
        foreColor = p.theme.foreColor
        backColor = p.theme.backColor
        gridColor = p.theme.gridColor
        forePen = wx.Pen(foreColor, 1, wx.SOLID)
        #backPen = wx.Pen(backColor, 1, wx.SOLID)
        gridPen = wx.Pen(gridColor, 1, wx.SOLID)
        fontSizeGC = fontSize * (1, 1.5)[isLinux]
        normalFont = wx.Font(fontSizeGC, wx.SWISS, wx.NORMAL, wx.NORMAL)
        backBrush = wx.Brush(backColor, wx.SOLID)
        clientWid, clientHt = self.GetSize()

        # ------ GRID ------

        # (GraphicsContext doesn't like AutoBufferedPaintDC, so we use:)
        if self.IsDoubleBuffered():
            dc = wx.PaintDC(self)
        else:
            dc = wx.BufferedPaintDC(self)
            dc.Clear()

        gc = wx.GraphicsContext.Create(dc)
        gc.Translate(clientWid/2, clientHt/2)
        foreFont = gc.CreateFont(normalFont, foreColor)
        gridFont = gc.CreateFont(normalFont, gridColor)

        # pure resistance line across center
        gc.SetFont(gridFont)
        text = "0"
        tw, th = gc.GetTextExtent(text)
        smRad = min(clientWid, clientHt)/2 - th - 5
        path = gc.CreatePath()
        path.MoveToPoint(-smRad, 0)
        path.AddLineToPoint(smRad, 0)
        gc.SetPen(gridPen)
        gc.StrokePath(path)
        gc.DrawText(text, -smRad-tw-2, -th/2)

        R0 = p.get("graphR",50)
        for R in (0.2, 0.5, 1., 2., 4.):
            # resistance arcs
            s11r = (R-1) / (R+1)
            xcent = (s11r + 1) / 2
            radius = 1 - xcent
            path = gc.CreatePath()
            path.MoveToPoint(smRad, 0)
            path.AddCircle(xcent*smRad, 0, radius*smRad)
            gc.StrokePath(path)
            text = si(R*R0)
            tw, th = gc.GetTextExtent(text)
            tx = s11r*smRad+tw/2-2
            ty = -th-1
            path = gc.CreatePath()
            path.AddRectangle(tx, ty, tw, th)
            gc.SetBrush(backBrush)
            gc.FillPath(path)
            gc.DrawText(text, tx, ty)

            # reactance arcs
            s11 = (1j*R-1) / (1j*R+1)
            theta = angle(s11)
            ycent = tan(theta/2)
            theta2 = atan2(s11.imag-ycent, s11.real-1)
            ycent *= smRad
            path = gc.CreatePath()
            path.MoveToPoint(smRad, 0)
            path.AddArc((smRad, -ycent), ycent, pi/2, -theta2)
            path.MoveToPoint(s11.real*smRad, s11.imag*smRad)
            path.AddArc((smRad,  ycent), ycent, theta2, -pi/2)
            gc.StrokePath(path)
            txrad = smRad + sqrt(tw**2 + th**2)/2 + 1
            gc.DrawText(text, s11.real*txrad-tw/2, -s11.imag*txrad-th/2)
            text = si(-R*R0)
            tw, th = gc.GetTextExtent(text)
            gc.DrawText(text, s11.real*txrad-tw/2,  s11.imag*txrad-th/2)

        # unity circle
        path = gc.CreatePath()
        path.AddCircle(0, 0, smRad)
        gc.SetPen(wx.Pen(gridColor, 2, wx.SOLID))
        gc.StrokePath(path)

        # ------ TRACES ------

        f0 = specP.h0   # start freq (MHz)
        f1 = specP.h1   # stop freq (MHz)
        if p.isLogF:
            f0 = log10(f0)
            f1 = log10(f1)

        # draw each trace in a different color
        for name, tr in sorted(specP.traces.iteritems(), \
                     key=(lambda (k,v): -v.iScale)):
            if not tr.displayed or tr.units != "dB":
                continue
            fullLen = len(tr.S11)
            if specP.eraseOldTrace:
                nv = fullLen
            else:
                nv = min(specP.cursorStep+1, fullLen)
            f = (tr.Fmhz, tr.LFmhz)[p.isLogF][:nv]
            # jMin, jMax are limits of indices of Fmhz within the
            # displayed region
            trf0 = f[0]
            if len(f) > 1:
                trdf = f[1] - trf0
            else:
                trdf = 0
            if trdf == 0:
                jMin = 0
                jMax = nv-1
            else:
                jMin = max(min((int((f0 - trf0) / trdf) - 2), nv-2), 0)
                jMax = max(min((int((f1 - trf0) / trdf) + 2), nv-1), 1)
            ##print ("j=", jMin, jMax, "f0=", f0, "trf0=", trf0, "trdf=", trdf

            # S11.real,S11.imag: coords of points to plot
            S11 = nan_to_num(tr.S11[jMin:jMax+1])
            # x,y: window coords of those points
            x =  S11.real * smRad
            y = -S11.imag * smRad

            ##if specP.eraseOldTrace and trdf > 0:
            ##    # remove main line segs at the cursor to form a moving gap
            ##    eraseWidth = int(10/(trdf*dx)) + 1
            eraseWidth = 0 # EON Jan 29, 2014
            path = gc.CreatePath()
            path.MoveToPoint(x[0], y[0])
            for i in range(1, len(x)):
                if 0 and i > specP.cursorStep and \
                        i <= specP.cursorStep+eraseWidth:
                    path.MoveToPoint(x[i], y[i])
                else:
                    path.AddLineToPoint(x[i], y[i])
            color = vColors[tr.iColor]
            gc.SetPen(wx.Pen(color, tr.dotSize, wx.SOLID))
            gc.StrokePath(path)

            # draw dots, either on all points if few, or just the startpoint
            n = len(x)
            if specP._haveDrawnGrid and specP.graphWid/fullLen > 20:
                step = 1
            else:
                step = n
            dsz = specP.dotSize
            path = gc.CreatePath()
            for i in range(0, n, step):
                path.MoveToPoint(x[i], y[i])
                path.AddLineToPoint(x[i], y[i])
            gc.SetPen(wx.Pen(color, dsz, wx.SOLID))
            gc.StrokePath(path)

        # ------ MARKERS ------

        gc.SetFont(foreFont)

        for name, m in specP.markers.iteritems():
            tr = specP.traces.get(m.traceName)
            if tr:
                # marker frequency determines array index j
                nv = len(tr.Fmhz)
                f = (tr.Fmhz, tr.LFmhz)[p.isLogF][:nv]
                trf0 = f[0]
                if len(f) > 1:
                    trdf = f[1] - trf0
                else:
                    trdf = 0
                if trdf == 0:
                    j = 0
                else:
                    mf = (m.mhz, log10(max(m.mhz, 1e-6)))[p.isLogF]
                    j = max(min((mf - trf0) / trdf, nv), 0)

                # S11.real,S11.imag: coords of points to plot
                js = arange(len(tr.S11))
                x =  smRad * interp(j, js, tr.S11.real)
                y = -smRad * interp(j, js, tr.S11.imag)

                if m.name == "X":
                    # draw cursor, if present
                    path = gc.CreatePath()
                    path.AddRectangle(x-2.5, y-2.5, 5, 5)
                    gc.SetPen(forePen)
                    gc.StrokePath(path)
                else:
                    # draw triangle at marker position
                    q = 6
                    isPos = m.name != "P-"
                    ydir = 2*isPos - 1
                    yq =  ydir * q
                    path = gc.CreatePath()
                    path.MoveToPoint(x, y)
                    path.AddLineToPoint(x-q, y-yq)
                    path.AddLineToPoint(x+q, y-yq)
                    path.AddLineToPoint(x, y)
                    gc.SetPen(forePen)
                    gc.StrokePath(path)
                    (tw, th) = gc.GetTextExtent(m.name)
                    tx = x-tw/2
                    ty = y-yq - (ydir+1)*(th+2)/2 + 1
                    path = gc.CreatePath()
                    path.AddRectangle(tx, ty, tw, th)
                    gc.SetBrush(backBrush)
                    gc.FillPath(path)
                    gc.DrawText(m.name, tx, ty)
