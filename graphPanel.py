from msaGlobal import GetFontSize, GetMsa, GetVersion, SetModuleVersion
import re, string, time, wx
import wx.lib.colourselect as csel
from numpy import array, clip, concatenate, floor, log10, nan_to_num
from vScale import VScale
from events import LogGUIEvent
from theme import red, blue
from msa import MSA
from marker import Marker
from util import MHz, ns, si, SI_NO,StdScale

SetModuleVersion("graphPanel",("1.04","JGH.d","03/17/2014"))

#==============================================================================
# A graph of a set of traces.

class GraphPanel(wx.Panel):
    def __init__(self, parent, frame):
        self.frame = frame
        self.prefs = p = frame.prefs
        self._gridBitmap = None
        self._haveDrawnGrid = False
        self._isReady = False

        # settable parameters
        self.marginPix = 32         # minimum margin around graph (pixels)
        self.rtMarginPix = 180      # additional margin on right (pixels)
        self.botMarginPix = 80      # additional margin on bottom (pixels)
        self.gridHSize = 50         # target grid horizontal spacing (pixels)
        self.gridVSize = 50         # target grid vertical spacing (pixels)
        self.printData = False      # set to print debug data
        self.dotSize = 4            # dot size for low-rez scans (pixels)
        self.isLogF = True          # set for log frequency scale mode
        self.hUnit = "MHz"          # default horizontal scale label
        self.h0 = 1.                # horizontal start (MHz)
        self.h1 = 0.                # horizontal end (MHz)
        self.dh = 1.                # horizontal delta (MHz)
        # list of vertical scales
        self.vScales = [VScale(0, 0, 1, 0, 0, ""), VScale(0, 0, 1, 0, 0, "")]
        self.traces = {}            # traces to graph, by name
        self.cursorStep = 0         # step location of cursor
        self.eraseOldTrace = False  # set to erase previous trace first
        self.markers = {}           # markers to graph, by name
        self.tcWithFocus = None     # TextCtrl box that has input focus
        self.results = None         # results text box, if any
        self.showCursor = False     # enable cursor (small box) drawing
        self.markersActive = False  # enable marker position update
        self.dbDownBy = 3           # dB down-by level to put L, R markers
        self.isAbs = False          # set if dbDownBy is an absolute level
        self.bind = False # EON Jan 12 2014

        wx.Panel.__init__(self, parent, -1)
        self.SetBackgroundColour(p.theme.backColor)
        ##self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)

    #--------------------------------------------------------------------------
    # Enable graph events and update.

    def Enable(self):
        # Start EON Jan 12 2014
        if not self.bind:
            self.bind = True
            global msa, fontSize
            msa = GetMsa()
            fontSize = GetFontSize()
            self.Bind(wx.EVT_PAINT,        self.OnPaint)
            self.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
            self.Bind(wx.EVT_KEY_DOWN,     self.OnKeyDown)
            self.Bind(wx.EVT_SIZE,         self.OnSizeChanged)
            self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
        # End EON Jan 12 2014
        self._isReady = True
        self.Refresh()

    #--------------------------------------------------------------------------
    # Force the grid and other parts to be redrawn on a resize of the frame.

    def FullRefresh(self):
        LogGUIEvent("FullRefresh hdg=%d" % self._haveDrawnGrid)
        self._haveDrawnGrid = False
        self.Refresh() # JGH: This a Panel class method
        smithDlg = self.frame.smithDlg
        if smithDlg:
            smithDlg.Refresh()

    #--------------------------------------------------------------------------
    # Handle a resize event.

    def OnSizeChanged(self, event):
        self.FullRefresh()
        event.Skip()   # (will continue handling event)

    #--------------------------------------------------------------------------
    # Repaint the waveform frame.
    # Do the actual drawing of the waveforms, including a grid and legend.

    def OnErase(self, event):
        pass

    def OnPaint(self, event):
        global msa, fontSize
        LogGUIEvent("OnPaint")
        ##assert wx.Thread_IsMain()

        # get current colors, pens, and brushes
        #frame = self.frame
        p = self.prefs
        self.vColors = vColors = p.theme.vColors
        foreColor = p.theme.foreColor
        backColor = p.theme.backColor
        gridColor = p.theme.gridColor
        hColor = p.theme.hColor
        linePen = wx.Pen(foreColor, 1, wx.SOLID)
        backPen = wx.Pen(backColor, 1, wx.SOLID)
        ##gridPen = wx.Pen(foreColor, 1, wx.DOT)
        gridPen = wx.Pen(gridColor, 1, wx.SOLID)
        grid0Pen = wx.Pen(foreColor, 2, wx.SOLID)
        noFillBrush = wx.Brush("BLACK", wx.TRANSPARENT)
        dyText = fontSize + 5
        clientWid, clientHt = self.GetSize()

        # exit if any traces outside of graph: they may have not caught up yet
        h0 = self.h0
        h1 = self.h1
        dh = self.dh
        for tr in self.traces.values():
            margin = 0.000001
            if tr.Fmhz[0] < h0 - margin or tr.Fmhz[-1] > h1 + margin:
                print ("trace %s outside: [%5.6f, %5.6f] in [%5.6f, %5.6f]" % \
                    (tr.name, tr.Fmhz[0], tr.Fmhz[-1], h0, h1))
                return

        # left and right vertical scales, and their corresponding units
        vs0 = self.vScales[0]
        vs1 = self.vScales[1]
        vaUnits = vs0.dataType.units
        vbUnits = vs1.dataType.units 
        vaLabel = ""
        vbLabel = ""
        aPrimary = False
        if vaUnits:
            vaLabel = re.sub("_.+", "", vs0.dataType.name) + " " + vs0.dataType.units
            if vaUnits in ("dB"):
                aPrimary = True
            else:
                if vbUnits:
                    if not (vbUnits in ("dB")):
                        aPrimary = True
        else:
            aPrimary = False
        if vbUnits:
            vbLabel = re.sub("_.+", "", vs1.dataType.name) + " " + vs1.dataType.units
        else:
            aPrimary = True

        # determine if axis traces are the prime traces, and which
        # trace belongs to which axis
        trA = trB = None
        axesArePrime = True
        if len(self.traces) == 2:
            # 2 traces: one axis for each
            trA, trB = self.traces.values()
            if trA.iScale != 0:
                # trace A not left axis: swap A and B
                trB, trA = self.traces.values()
                axesArePrime = trA.units == vs1.primeTraceUnits and \
                               trB.units == vs0.primeTraceUnits
            else:
                axesArePrime = trA.units == vs0.primeTraceUnits and \
                               trB.units == vs1.primeTraceUnits
        else:
            # 1 or more than 2 traces: see which axis each trace belongs to
            for tr in self.traces.values():
                if tr.units == vaUnits:
                    trA = tr
                    if trA.units != vs0.primeTraceUnits:
                        axesArePrime = False
                if tr.units == vbUnits:
                    trB = tr
                    if trB.units != vs1.primeTraceUnits:
                        axesArePrime = False

        # if log freq scale determine decade range if possible
        isLogF = p.isLogF
        if isLogF:
            try:
                lf0 = log10(h0)
                lf1 = log10(h1)
            except FloatingPointError:
                isLogF = False

        # draw the grid, axes, and legend if they're new or updated
        if not self._haveDrawnGrid:
            LogGUIEvent("OnPaint: redraw grid")
            # (GraphicsContext doesn't like AutoBufferedPaintDC, so we use:)
            if False:
##            if slowDisplay or self.IsDoubleBuffered():
                dc1 = wx.PaintDC(self)
            else:
                dc1 = wx.BufferedPaintDC(self)
                dc1.Clear()

            ##if clientWid != self.clientWid or clientHt != self.clientHt:
            ##self.clientWid = clientWid
            ##self.clientHt = clientHt
            self.graphWid = graphWid = clientWid - self.marginPix - \
                            self.rtMarginPix
            self.graphHt = graphHt = clientHt  - 2*self.marginPix - 20 - \
                            self.botMarginPix
            ##print ("OnPaint"

            # scale horz axis of graph to fit window
            hWid = h1 - h0
            dc1.SetFont(wx.Font(fontSize, wx.SWISS, wx.NORMAL,
                                p.theme.textWeight))
            wh0, hh0 = dc1.GetTextExtent(str(h0))
            wh1, hh1 = dc1.GetTextExtent(str(h1))
            gridHSize = max(self.gridHSize, 2*max(wh0, wh1)+10)
            if hWid == 0:
                isLogF = False
                dh = 0.     # h distance (in hUnits) between divisions
                hBase = h0  # h position of first div
                hFrac = 0.  # h distance from h0 to first div
                nXDiv = 2   # number of horizontal divisions
                xPixDiv = graphWid/2
                self.dx = dx = graphWid/2     # pixels/hUnit
                ##print ("dh=0"
            else:
                if isLogF:
                    self.dx = dx = graphWid / (lf1 - lf0)   # pixels/hUnit
                else:
                    dh, hBase, hFrac, nXDiv = \
                        StdScale(h0, h1, graphWid, gridHSize)

                    self.dx = dx = graphWid / (h1 - h0)   # pixels/hUnit
                xPixDiv = dx * dh
            self.dh = dh

            # scale vert axis of graph to fit window
            va1 = vs0.top
            va0 = vs0.bot
            vb1 = vs1.top
            vb0 = vs1.bot
            #if vaUnits:
            if aPrimary:
                v0, v1, = va0, va1
                vDiv = vs0.div
                units = vaUnits
            else:
                v0, v1 = vb0, vb1
                vDiv = vs1.Div
                units = vbUnits

            if vDiv == 0 and units != "Deg":
                dv, vBase, vFrac, nYDiv = \
                    StdScale(v0, v1, graphHt, self.gridVSize)
            else:
                if vDiv == 0:
                    vDiv = 10
                nYDiv = vDiv
                dv = (v1 - v0) / float(nYDiv)
                vBase = v0
                vFrac = 0

            # calculate graph boundaries
            den = max(v1 - v0, 1e-20)
            yPixDiv = graphHt * dv / den
            self.x0 = x0 = self.marginPix + 10
            self.y0 = y0 = self.marginPix + 10
            self.x1 = x1 = x0 + graphWid
            self.y1 = y1 = y0 + graphHt

            self.dy = dy = yPixDiv / dv      # pixels/vUnit
            self.dya = dya = dy
            self.dyb = dyb = dy
            vbBase = vBase
#            if vaUnits:
#                vaBase = vBase
#                if trB:
#                    den = max(va1 - va0, 1e-20)
#                    dvb = max(dv * (vb1 - vb0) / den,1e-20)
#                    self.dyb = dyb = yPixDiv / dvb
#                    vbBase = vb0 + vFrac

            if aPrimary:
                vbBase = vBase
                dva = dv
                if vaUnits:
                    vaBase = vBase
                    #if trB:
                    if vbUnits:
                        den = max(va1 - va0, 1e-20)
                        dvb = max(dv * (vb1 - vb0) / den,1e-20)
                        self.dyb = dyb = yPixDiv / dvb
                        vbBase = vb0 + vFrac
            else:
                vbBase = vBase
                dvb = dv
                if vbUnits:
                    vaBase = vBase
                    #if trB:
                    if vaUnits:
                        den = max(vb1 - vb0, 1e-20)
                        dva = max(dv * (va1 - va0) / den,1e-20)
                        self.dya = dya = yPixDiv / dva
                        vaBase = va0 + vFrac

            # create a bitmap to store the grid in
            self.dc = dc = wx.MemoryDC()
            self._gridBitmap = wx.EmptyBitmap(clientWid, clientHt)
            dc.SelectObject(self._gridBitmap)
            dc.SetBackground(wx.Brush(backColor, wx.SOLID))
            dc.SetTextForeground(hColor)
            dc.Clear()
            dc.SetFont(wx.Font(fontSize, wx.SWISS, wx.NORMAL,
                                p.theme.textWeight))

            # ------ GRID ------

            # draw legend
            #ntr = len(self.traces)
            y = y0 + 150
            x = x1 + 50
            for name, tr in sorted(self.traces.iteritems(), \
                                key=(lambda (k,v): v.name.upper())):
                if tr.displayed:
#                    print("p.theme.vColors:", len(p.theme.vColors), "tr.iColor=", tr.iColor)
                    vColor = vColors[tr.iColor]
                    ##dc.SetPen(wx.Pen(vColor, 1, wx.SOLID))
                    dc.SetPen(wx.Pen(vColor, 5, wx.SOLID))
                    dc.DrawLine(x, y, x + 20, y)
                    dc.SetTextForeground(vColor)
                    #unit = self.vScales[tr.iScale].dataType.units
                    ##text = "%s (%s)" % (name, unit)
                    text = name
                    (w, h) = dc.GetTextExtent(text)
                    dc.DrawText(text, x + 23, y - 6)
                    y += h + 4

            # draw graph axis labels
            vaColor = None
            if trA:
                vaColor = vColors[trA.iColor]
            vbColor = None
            if trB:
                vbColor = vColors[trB.iColor]
            if vaUnits:
                dc.SetTextForeground(vaColor)
                (w, h) = dc.GetTextExtent(vaLabel)
                dc.DrawText(vaLabel, x0 - w/2, y0 - 2*h)
#                dc.DrawText(vaUnits, x0 - w - 2, y0 - 2*h)
            if vbUnits:
                dc.SetTextForeground(vbColor)
                (w, h) = dc.GetTextExtent(vbLabel)
                dc.DrawText(vbLabel, x1 - w/2 , y0 - 2*h)
#                dc.DrawText(vbUnits, x1 - 2, y0 - 2*h)
            dc.SetTextForeground(hColor)
            hUnit = self.hUnit
            if isLogF:
                hUnit = hUnit[1:]
            else:
                hUnit = hUnit + " (%sHz/div)" % si(dh*MHz)
            (w, h) = dc.GetTextExtent(hUnit)
            dc.DrawText(hUnit, (x1 + x0 - w) / 2, y1 + 20)

            # draw grid vert axis lines
            yDiv0 = y1 - vFrac * dy
            for vDiv in range(0, nYDiv+1):
                y = yDiv0 - vDiv * yPixDiv
                if y < (y0 - 0.01):
                    break
                if vaUnits:
                    va = vaBase + vDiv * dva
                    vaText = si(va, 3)
                    (w, h) = dc.GetTextExtent(vaText)
                    dc.SetTextForeground(vaColor)
                    dc.DrawText(vaText, x0 - w - 3, y - h/2)
                if vbUnits:
                    vb = vbBase + vDiv * dvb
                    vbText = si(vb, 3)
                    (w, h) = dc.GetTextExtent(vbText)
                    dc.SetTextForeground(vbColor)
                    dc.DrawText(vbText, x1 + 3, y - h/2)

                dc.SetPen(gridPen)
                dc.DrawLine(x0, y, x1, y)

            # draw grid h lines
            dc.SetTextForeground(hColor)
            if isLogF:
                ##print ("h0=", h0, "h1=", h1
                hName = si(h0 * MHz)
                (tw, th) = dc.GetTextExtent(hName)
                dc.DrawText(hName, x0 - tw/2, y1 + 6)
                df = 10**floor(lf0)
                f = floor(h0 / df) * df + df
                lf = log10(f)
                hDiv = 0
                lf1 -= 0.001
                textFrac = min(dx/200, 0.85)
                ##print ("lf=", lf, "f=", f, "df=", df
                while lf < lf1:
                    lfFrac = lf - floor(lf+0.001)
                    if abs(lfFrac) < 0.01:
                        df *= 10.
                        hDiv = 0
                    x = x0 + (lf - lf0) * dx
                    if f > 950 or (lfFrac < textFrac and \
                         (hDiv % 2) == 0 and x > x0+30 and x < x1-30):
                        hName = si(f * MHz)
                        (tw, th) = dc.GetTextExtent(hName)
                        dc.DrawText(hName, x - tw/2, y1 + 6)
                    dc.SetPen(gridPen)
                    dc.DrawLine(x, y0, x, y1)
                    hDiv += 1
                    f += df
                    lf = log10(f)
                hName = si(h1 * MHz)
                (tw, th) = dc.GetTextExtent(hName)
                dc.DrawText(hName, x1 - tw/2, y1 + 6)
            else:
                xDiv0 = x0 + hFrac * dx
                for hDiv in range(0, nXDiv+1):
                    x = xDiv0 + hDiv * xPixDiv
                    if x > (x1 + 0.01):
                        break
                    if dh == 0:
                        x = (x1 + x0)/2
                    h = hBase + hDiv * dh
                    if (hDiv % 2) == 0:
                        hName = str(h)
                        if len(hName) > 2 and hName[-2:] == ".0":
                            hName = hName[:-2]
                        (w, h) = dc.GetTextExtent(hName)
                        dc.DrawText(hName, x - w/2, y1 + 6)
                    dc.SetPen(gridPen)
                    dc.DrawLine(x, y0, x, y1)

            # draw border
            dc.SetPen(grid0Pen)
            dc.SetBrush(noFillBrush)
            dc.DrawRectangle(x0, y0, x1-x0, y1-y0)

            # ------ INFO ------

            # draw title
            dc.SetTextForeground(hColor)
            dc.SetFont(wx.Font(fontSize*1.2, wx.SWISS, wx.NORMAL, wx.NORMAL))
            (w, h) = dc.GetTextExtent(self.title)
            dc.DrawText(self.title, (x1 + x0 - w)/2, y0 - 10 - h)

            # draw right info panel
            xinfo = x1 + 50
            yinfo = y0 - 10
            modeName = msa.modeNames[p.mode]
            (w, h) = dc.GetTextExtent(modeName)
            dc.DrawText(modeName, clientWid - 10 - w, 5)
            dc.SetFont(wx.Font(fontSize, wx.SWISS, wx.NORMAL, wx.NORMAL))
            if p.calLevel <= 2 and p.mode > MSA.MODE_SATG:
                calLevelName = ("None", "Base", "Band")[msa.calLevel]
                dc.SetTextForeground((red, blue, hColor)[p.calLevel])
                dc.DrawText("Cal=" + calLevelName, xinfo, yinfo + 0*dyText)
            dc.SetTextForeground(hColor)
            ##dc.DrawText("RBW=%sHz" % si(p.rbw * kHz), xinfo, yinfo + 1*dyText)
            ##dc.DrawText("RBW=%sHz" % (p.rbw * kHz), xinfo, yinfo + 1*dyText)
            dc.DrawText("RBW=%.1fkHz" % p.rbw, xinfo, yinfo + 1*dyText)
            dc.DrawText("Wait=%dms" % int(p.wait), xinfo, yinfo + 2*dyText)
            dc.DrawText("Steps=%d" % int(p.nSteps), xinfo, yinfo + 3*dyText)
            y = 4
            if not p.isLogF:
                df = (p.fStop - p.fStart) / p.nSteps
                dc.DrawText("%sHz/Step" % si(df * MHz), xinfo, yinfo+y*dyText)
                y += 1
            if p.mode >= MSA.MODE_VNATran and p.planeExt[0] > 0:
                for i, planeExt in enumerate(p.planeExt):
                    dc.DrawText("Exten%dG=%ss" % (i, si(planeExt * ns)), xinfo,
                            yinfo + y*dyText)
                    y += 1
            if p.mode == MSA.MODE_VNARefl:
                fixName = "Bridge"
                if p.isSeriesFix:
                    fixName = "Series"
                elif p.isShuntFix:
                    fixName = "Shunt"
                dc.DrawText("Fixture=%s" % fixName, xinfo, yinfo + y*dyText)
                y += 1
##            if p.cftest == True:
##                dc.DrawText("CFfilter test is ON", xinfo, yinfo + y*dyText)
##                y += 1
            dc.DrawText("Vers %s" % GetVersion(), xinfo, yinfo + y*dyText)
            y += 1
            

            # draw optional results text box
            if self.results:
                lnsep = 4
                border = 5
                dc.SetTextForeground(hColor)
                dc.SetFont(wx.Font(fontSize, wx.SWISS, wx.NORMAL, wx.NORMAL))
                resultList = self.results.split("\n")
                wres = 0
                for result in resultList:
                    wid, ht = dc.GetTextExtent(result)
                    wres = max(wres, wid)
                wres += 2*lnsep
                xres0 = clientWid - border - wres
                yres0 = clientHt - border - lnsep - \
                            (ht+lnsep) * len(resultList)
                hres = clientHt - border - yres0
                dc.SetPen(wx.Pen(foreColor, 2, wx.SOLID))
                dc.SetBrush(noFillBrush)
                dc.DrawRectangle(xres0, yres0, wres, hres)
                for result in resultList:
                    dc.DrawText(result, xres0+lnsep, yres0+lnsep)
                    yres0 += ht + lnsep

            dc.SelectObject(wx.NullBitmap)
            self._haveDrawnGrid = True
            dc = dc1
            ##print ("Graph DoDrawing\n"
            dc.DrawBitmap(self._gridBitmap, 0, 0)

            ##dc.DestroyClippingRegion()

        else:
            # already have drawn grid, just retrieve parameters
            x0 = self.x0; y0 = self.y0
            x1 = self.x1; y1 = self.y1
            h0 = self.h0; h1 = self.h1
            dx = self.dx; dh = self.dh
            dya = self.dya; dyb = self.dyb ;dy = self.dy;
            va0 = self.vScales[0].bot
            vb0 = self.vScales[1].bot

            # (GraphicsContext doesn't like AutoBufferedPaintDC, so we use:)
            if False:
##            if slowDisplay or self.IsDoubleBuffered():
                dc = wx.PaintDC(self)
            else:
                dc = wx.BufferedPaintDC(self)
                dc.Clear()

            dc.DrawBitmap(self._gridBitmap, 0, 0)

        ##LogGUIEvent("OnPaint: have grid")

        ##dc.SetClippingRegion(x0, y0, x1-x0, y1-y0)
        if isLogF:
            h0 = log10(h0)
            h1 = log10(h1)

        # ------ TRACES ------

        # draw each trace in a different color
        for name, tr in sorted(self.traces.iteritems(), \
                     key=(lambda (k,v): -v.iScale)):
            LogGUIEvent("OnPaint: compute trace %s" % name)
            if not tr.displayed:
                continue
            fullLen = len(tr.v)
            #isPhase = tr.units == "Deg"
            useFull = not tr.isMain or self.eraseOldTrace
            if useFull:
                nv = fullLen
            else:
                nv = min(self.cursorStep+1, fullLen)
            if nv < 2:
                break
            v = nan_to_num(tr.v[:nv])
            if isLogF:
                Fmhz = tr.LFmhz[:nv]
            else:
                Fmhz = tr.Fmhz[:nv]
            # jMin, jMax are limits of indices of v within the
            # displayed region, plus extra
            trh0 = Fmhz[0]
            trdh = Fmhz[1] - trh0    # hUnits/step
            if trdh == 0:
                jMin = 0
                jMax = nv-1
            else:
                jMin = max(min((int((h0 - trh0) / trdh) - 2), nv-2), 0)
                jMax = max(min((int((h1 - trh0) / trdh) + 2), nv-1), 1)
            jStep = max(int(1 / dx), 1)
            if self.printData:
                print (tr.name, "trh0=", trh0, "trdh=", trdh, "jMin/Max=", \
                        jMin, jMax, jStep, "nv=", nv)

            # h,v: coords of points to plot, in given units
            h = Fmhz[jMin:jMax+1]
            v = v[jMin:jMax+1]
            # x,y: window coords of those points
            if trdh == 0:
                # no span: draw straight line across
                x = array([x0, x1])
                v = v[0:2]
            else:
                ##print ("x0=", x0, "h=", h, "h0=", h0
                x = x0 + (h - h0) * dx
                if useFull:
                    x[-1] = x1
            if tr.iScale == 1:
                y = y1 - (v - vb0) * dyb
            else:
                y = y1 - (v - va0) * dya
            y = clip(y, y0+1, y1-1)
            if self.printData:
                print ("shape h=", h.shape, "shape v=", v.shape)
                print ("h[:5]=", h[:5])
                print ("v[:5]=", v[:5])
                print ("y[:5]=", y[:5])
                print ("x[:5]=", x[:5])
            # save coords for use by marker click searches
            self.xs = x.copy()
            tr.ys = y.copy()

            if True:
##            if not isWin:
                # GraphicsContext: faster and smoother (but broken in Windows?)
                gc = wx.GraphicsContext.Create(dc)
##                eraseWidth = 0
                if tr.isMain and self.eraseOldTrace and trdh > 0 and p.bGap == True:
                    # remove main line segs at the cursor to form a moving gap
                    eraseWidth = int(10./(trdh*dx)) + 1
                else:
                    eraseWidth = 0
                path = gc.CreatePath()
                path.MoveToPoint(x[0], y[0])
                for i in range(1, len(x)):
                    if tr.isMain and i > self.cursorStep and \
                                i <= self.cursorStep+eraseWidth:
                        path.MoveToPoint(x[i], y[i])
                    else:
                        path.AddLineToPoint(x[i], y[i])
                color = vColors[tr.iColor]
                gc.SetPen(wx.Pen(color, tr.dotSize, wx.SOLID))
                gc.StrokePath(path)

                if self.graphWid/fullLen > 20:
                    # draw larger dots at data points if X low-res
                    dsz = self.dotSize
                    path = gc.CreatePath()
                    for i in range(len(x)):
                        path.MoveToPoint(x[i], y[i])
                        path.AddLineToPoint(x[i], y[i])
                    gc.SetPen(wx.Pen(color, dsz, wx.SOLID))
                    gc.StrokePath(path)

            else:
                ##except NotImplementedError:
                # form an array of pairs of begin-end line coords tween points
                xy = concatenate((x.reshape(-1, 1), y.reshape(-1, 1)), axis=1)
                xpyp = concatenate(([[0,0]], xy[:-1]))
                lines = concatenate((xpyp, xy), axis=1)[1:]
                if tr.isMain and self.eraseOldTrace and trdh > 0 and p.bGap == True:
                    # remove main line segs at the cursor to form a moving gap
                    eraseWidth = int(10./(trdh*dx)) + 1
                else:
                    erasewidth = 0
                lines = concatenate((lines[:self.cursorStep],
                                         lines[self.cursorStep+eraseWidth:]))
##                if isPhase:
##                    # remove phase line segments that wrap or have feeble mag
##                    linesY = lines[:,1]
##                    linesYP = lines[:,3]
##                    lines = lines[(abs((linesY - linesYP) < (y1 - y0)/2) *
##                                            (linesY < y1) * (linesYP < y1))]
##                    lines = lines.tolist()
                LogGUIEvent("OnPaint: draw trace %s" % name)
                # draw that list of lines
                color = vColors[tr.iColor]
                dc.SetPen(wx.Pen(color, tr.dotSize, wx.SOLID))
                dc.DrawLineList(lines, None)
                if self.graphWid/fullLen > 20:
                    ##dotEdge = [[self.dotSize/2+1, 0]]
                    dotEdge = [[0, 0]]
                    dots = concatenate((xy-dotEdge, xy+dotEdge),
                                        axis=1).tolist()
                    dc.SetPen(wx.Pen(color, self.dotSize, wx.SOLID))
                    dc.DrawLineList(dots, None)

        # ------ MARKERS ------

        markers = self.markers
        dc.SetTextForeground(hColor)
        dc.SetFont(wx.Font(fontSize, wx.SWISS, wx.NORMAL, wx.NORMAL))
        xminfo = x0 - 20
        yminfo = y1 + 40
        needHeader = True
        dc.SetBrush(wx.Brush(backColor, wx.SOLID))

        for name, m in sorted(markers.iteritems(), key=(lambda (k,v): v.name)):
            tr = self.traces.get(m.traceName)
            if tr:
                if needHeader:
                    dc.DrawText("Mark", xminfo, yminfo)
                    dc.DrawText(" Freq (MHz)", xminfo+55, yminfo)
                    if trA:
                        dc.DrawText(trA.name, xminfo+130, yminfo)
                    if trB:
                        dc.DrawText(trB.name, xminfo+190, yminfo)
                    yminfo += dyText
                    needHeader = False

                if p.markerMode == Marker.MODE_PbyLR:
                    if self.markersActive and m.name[0] == "P":
                        # markers P+,P- bounded by L,R
                        isPos = m.name[1] == "+"
                        mLeft = markers.get("L")
                        mRight = markers.get("R")
                        if mLeft and mRight:
                            jL, trh0, trdh = tr.Index(mLeft.mhz, isLogF, True)
                            jR, trh0, trdh = tr.Index(mRight.mhz, isLogF, True)
                            ##print m.name, isPos, trdh, h0, jL, jR
                            m.FindPeak(tr.v[jL:jR], trdh, isLogF, isPos,
                                mLeft.mhz)
                elif p.markerMode > Marker.MODE_PbyLR:
                    if self.markersActive and m.name in ("L", "R"):
                        # markers L,R bounded by P+ or P-
                        isPos = (p.markerMode == Marker.MODE_LRbyPp)
                        mPeak = markers.get(("P-", "P+")[isPos])
                        if mPeak:
                            signP = (-1, 1)[isPos]
                            if self.isAbs:
                                # dbDownBy taken as an absolute level
                                mag3dB = self.dbDownBy
                            else:
                                # normally dbDownBy==3 for -3dB from the peak
                                # or +3dB up from the notch
                                mag3dB = mPeak.dbm - self.dbDownBy * signP
                            jP = tr.Index(mPeak.mhz, isLogF)
#                            print ("Marker", m.name, "finding", mPeak.name, \
#                                   "mag3dB=", mag3dB, "jP=", jP, "signP=", signP)
                            m.FindValue(tr, jP, isLogF, signP, m.name == "R", 
                                mag3dB, show=0)

                if self.markersActive:
                    m.SetFromTrace(tr, isLogF)

                # draw marker's freq, mag, phase values with decimals aligned
                name = "%4s" % m.name
                ##if trA and tr.name != trA.name:
                ##    name = "%s-%s" % (m.name, tr.name)
                dc.DrawText(name, xminfo, yminfo)
                text = "%11.6f" % m.mhz
                (tw, th) = dc.GetTextExtent(text[:-6])
                dc.DrawText(text, xminfo+70-tw, yminfo)

                # draw axis trace values, or marker's mag & deg if axis
                # traces are the prime traces
                a = b = None
                if axesArePrime:
                    a = "%8.3f" % m.dbm
                    if m.deg > -190:
                        b = "%7.2f" % m.deg
                else:
                    if trA:
                        flags = 0
                        if trA.units in ("dB", "Deg"):
                            flags += SI_NO
                        a = si(m.TraceValue(trA, isLogF), flags=flags)
                    if trB:
                        flags = 0
                        if trB.units in ("dB", "Deg"):
                            flags += SI_NO
                        b = si(m.TraceValue(trB, isLogF), flags=flags)

                if a:
                    places = min(a[::-1].find("."), 3)
                    (tw, th) = dc.GetTextExtent(a[:-places])
                    dc.DrawText(a, xminfo+150-tw, yminfo)

                if b:
                    places = min(b[::-1].find("."), 3)
                    (tw, th) = dc.GetTextExtent(b[:-places])
                    dc.DrawText(b, xminfo+210-tw, yminfo)

                # draw triangle at marker position
                if m.name != "X":
                    if h1 == h0:
                        x = -1
                        if m.mhz == h0:
                            # a zero span: put mark in center
                            x = (x1 + x0) / 2
                    else:
                        if isLogF:
                            x = x0 + (log10(max(m.mhz, 1e-6)) - lf0) * dx
                            ##print ("marker", m.name, "mhz=", m.mhz, \
                            ##"log(mhz)=", log10(m.mhz), "lf0=", lf0, "x=", x
                        else:
                            x = x0 + (m.mhz - h0) * dx
                    if x >= x0 and x <= x1:
                        if tr == trA:
                            scale = dya
                            bot = va0
                        else:
                            scale = dyb
                            bot = vb0
                        if tr.units == "Deg":
                            val = m.deg
                        else:
                            val = m.dbm
                        y = max(min(y1 - (val - bot) * scale, y1), y0)
                        q = 6
                        isPos = m.name != "P-"
                        ydir = 2*isPos - 1
                        yq =  ydir * q
                        dc.SetPen(linePen)
                        dc.DrawLine(x, y, x-q, y-yq)
                        dc.DrawLine(x-q, y-yq, x+q, y-yq)
                        dc.DrawLine(x+q, y-yq, x, y)
                        (tw, th) = dc.GetTextExtent(m.name)
                        tx = x-tw/2
                        ty = y-yq - (ydir+1)*(th+2)/2 + 1
                        dc.SetPen(backPen)
                        dc.DrawRectangle(tx, ty, tw, th)
                        dc.DrawText(m.name, tx, ty)

                # move to next info line
                yminfo += dyText
                if yminfo > clientHt - 20:
                    xminfo += 280
                    yminfo = y1 + 40
                    needHeader = True
            else:
                # marker missing its trace: remove it too
                markers.pop(name)

        # draw cursor, if present
        if self.showCursor:
            dc.SetPen(linePen)
            dc.SetBrush(noFillBrush)
            dc.DrawRectangle(self.cursorX-2, self.cursorY-2, 5, 5)

        LogGUIEvent("OnPaint: done")

    #--------------------------------------------------------------------------
    # Mouse event: holding mouse down in graph area puts a cursor on nearest
    # trace. Or a double-click adds the current marker.

    def OnMouse(self, event):
        frame = self.frame
        self.showCursor = False
        x, y = event.GetPosition()

        LogGUIEvent("OnMouse")
        if event.LeftDClick():
            if y > self.y0 and y < self.y1:
                ymid = (self.y1 + self.y0) / 2
                if x < self.x0:
                    # left vert axis double-click
                    self.vScales[0].Set(frame, (10, ymid - 50))
                elif x < self.x1:
                    # graph body double-click
                    self.SetMarker(x, y)
                elif x < self.x1 + 40:
                    # right vert axis double-click
                    xpos = min(self.x1+10, frame.screenWidth - 450)
                    self.vScales[1].Set(frame, (xpos, ymid - 50))
                else:
                    # right legend area
                    lgPos = wx.Point(self.x1+40, self.y0+100)
                    lgPos = self.ClientToScreen(lgPos)
                    LegendPopup(self, lgPos)

            elif x > self.x0 and x < self.x1:
                if y > self.y1 and y < self.y1 + 30:
                    # horiz axis double-click
                    frame.SetSweep()

        elif event.LeftDown() or event.Dragging():
            if x > self.x0 and x < self.x1 and y > self.y0 and y < self.y1:
                # in graph body:
                self.SetFocus()
                LogGUIEvent("OnMouse: SetFocus on graph")
                tr, mhz, y = self.FindNearestTrace(x, y)
                if tr:
                    # found nearest trace: will draw a small rectangle on it
                    self.showCursor = True
                    self.cursorX, self.cursorY = x, y
                    # and list a temporary 'X' marker there
                    mx = self.markers.get("X")
                    if mx:
                        mx.traceName = tr.name
                        mx.mhz = mhz
                    else:
                        self.markers["X"] = mx = Marker("X", tr.name, mhz)
                    mx.SetFromTrace(tr, self.isLogF)
                    self.cursorInfo = tr, mhz
                    self.markersActive = True
                    LogGUIEvent("OnMouse: cursor")
                    self.FullRefresh()

        if not self.showCursor and self.markers.has_key("X"):
            self.markers.pop("X")
            self.markersActive = True
            self.FullRefresh()
        LogGUIEvent("OnMouse: done")

    #--------------------------------------------------------------------------
    # Key pressed: if mouse is also down, add a marker at the cursor location.

    def OnKeyDown(self, event):
        ##print ("OnKeyDown"
        keycode = event.GetKeyCode()
        LogGUIEvent("OnKeyDown 0x%x cursor=%d" % (keycode, self.showCursor))
        if keycode >= 32 and keycode < 96:
            frame = self.frame
            p = self.prefs
            if self.showCursor:
                name = chr(keycode).upper()
                # when setting a marker currently auto-positioned, change mode
                if name in "+=":
                    name = "P+"
                    if p.markerMode == Marker.MODE_PbyLR:
                        frame.SetMarkers_Indep()
                elif name in "_-":
                    name = "P-"
                    if p.markerMode == Marker.MODE_PbyLR:
                        frame.SetMarkers_Indep()
                elif name in "LR":
                    if p.markerMode in (Marker.MODE_LRbyPp, Marker.MODE_LRbyPm):
                        frame.SetMarkers_Indep()
                elif not (name in "123456789"):
                    event.Skip()
                    return
                frame = self.frame
                tr, mhz = self.cursorInfo
                frame.markerCB.SetValue(name)
                m = Marker(name, tr.name, mhz)
                self.markers[name] = m
                m.SetFromTrace(tr, self.isLogF)
                frame.mhzT.ChangeValue(str(mhz))
                frame.markMHz = mhz
                self.markersActive = True
                self.FullRefresh()

    #--------------------------------------------------------------------------
    # Find the closest trace to given mouse coordintates.
    # Returns (trace, mhz, y), or 3 Nones if not found.

    def FindNearestTrace(self, x, y):
        traces = self.traces
        if len(traces) > 0:
            i = self.xs.searchsorted(x)
            if i >= 0 and i < len(self.xs):
                ysatx = [(abs(tr.ys[i] - y), name, tr) for name, tr in \
                         traces.items() if tr.ys != None]
                if len(ysatx) > 0:
                    ysatx.sort()
                    # found closest trace to click location
                    dist, traceName, tr = ysatx[0]
                    if dist < 200:
                        # interpolate between points to get freq at x
                        xi0, xi1 = self.xs[i-1:i+1]
                        hi0, hi1 = tr.Fmhz[i-1:i+1]
                        m = (x - xi0) / (xi1 - xi0)
                        mhz = round(hi0 + (hi1 - hi0)*m, 6)
                        y = 0
                        if tr.ys != None:
                            yi0, yi1 = tr.ys[i-1:i+1]
                            y = int(yi0 + (yi1 - yi0)*m)
                        return tr, mhz, y
        return None, None, None

    #--------------------------------------------------------------------------
    # Find the closest trace to given mouse coords and set a marker on it.

    def SetMarker(self, x, y):
        #traces = self.traces # JGH 2/10/14
        frame = self.frame
        tr, mhz, y = self.FindNearestTrace(x, y)
        if tr:
            # found closest trace to click location
            markName = frame.markerCB.GetValue()
            if markName == "None":
                markName = "L"
            frame.markerCB.SetValue(markName)
            m = Marker(markName, tr.name, mhz)
            self.markers[markName] = m
            m.SetFromTrace(tr, self.isLogF)
            frame.mhzT.ChangeValue(str(mhz))
            frame.markMHz = mhz
            self.FullRefresh()

    #--------------------------------------------------------------------------
    # Write graph data to a text file.

    def WriteGraph(self, fileName, p):
        traces = self.traces
        f = open(fileName, "w")
        f.write("!MSA, msapy %s\n" % GetVersion())
        f.write("!Date: %s\n" % time.ctime())
        f.write("!Graph Data\n")
        f.write("!Freq(MHz)  %s\n" % string.join(["%16s" % k \
                    for k in traces.keys()]))

        Fmhz = traces.values()[0].Fmhz
        for i in range(len(Fmhz)):
            f.write("%11.6f %s\n" % \
                (Fmhz[i],
                 string.join(["%16.8f" % tr.v[i] \
                                for tr in traces.values()])))
        f.close()

#==============================================================================
# A Line legend pop-up window for enabling graph lines.

class LegendPopup(wx.Dialog):
    def __init__(self, specP, pos):
        self.specP = specP
        frame = specP.frame
        self.prefs = frame.prefs
        wx.Dialog.__init__(self, specP, -1, "Lines", pos, (1, 1))
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizerGB = wx.GridBagSizer(2, 2)
        c = wx.ALIGN_CENTER
        cl = wx.ALIGN_LEFT
        self.traces = []

        # add an enabling checkbox for each possible trace line
        for name, tr in specP.traces.iteritems():
            print ("name=", name, "tr.name=", tr.name, "tr.i=", tr.iScale)
        for i, (name, tr) in enumerate(sorted(specP.traces.iteritems(), \
                        key=(lambda (k,v): v.name.upper()))): # JGH mod4P3
            self.traces.append(tr)
            chk = wx.CheckBox(self, -1, name)
            chk.SetValue(tr.displayed)
            self.Bind(wx.EVT_CHECKBOX, self.OnCheckBox, chk)
            sizerGB.Add(chk, (i, 0), flag=cl|wx.ALL, border=2)
            # trace color entry
            color = specP.vColors[tr.iColor]
            cs = csel.ColourSelect(self, -1, "", color, size=(35, -1))
            cs.trace = tr
            cs.Bind(csel.EVT_COLOURSELECT, self.OnSelectColor)
            sizerGB.Add(cs, (i, 1), flag=c)

        sizer.Add(sizerGB, 0, wx.ALL, 10)
        sizer.Add((1, 20), 0)
        sizer.Layout()
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Show()

    #--------------------------------------------------------------------------
    # Event handlers.

    def OnCheckBox(self, event):
        specP = self.specP
        chk = event.GetEventObject()
        name = chk.GetLabel()
        trace = specP.traces.get(name)
        ##print ("Check: name=", name, trace
        if trace:
            trace.displayed = chk.GetValue()
            self.specP.FullRefresh()

    def OnSelectColor(self, event):
        print ("OnSelectColor")
        specP = self.specP
        cs = event.GetEventObject()
        tr = cs.trace
        specP.prefs.theme.vColors[tr.iColor] = wx.Colour(*event.GetValue())
        specP.FullRefresh()
