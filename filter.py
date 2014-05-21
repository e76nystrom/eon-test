#import msaGlobal
from msaGlobal import SetModuleVersion
import wx
from functionDialog import FunctionDialog
from numpy import arange, diff, interp
from util import floatOrEmpty, MHz, si
from marker import Marker

SetModuleVersion("filter",("1.30","EON","05/20/2014"))

#==============================================================================
# The Analyze Filter dialog box.

class FilterAnalDialog(FunctionDialog):
    def __init__(self, frame):
        FunctionDialog.__init__(self, frame, "Analyze Filter", "filtAn")
        # JGH 2/10/14 Next 3 lines: vars not used
##        p = frame.prefs
##        markers = frame.specP.markers
##        self.sizerV = sizerV = wx.BoxSizer(wx.VERTICAL)
        c = wx.ALIGN_CENTER
        chb = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM

        # enabler and instructions
        sizerV = wx.BoxSizer(wx.VERTICAL)
        label = "Analyze filter spectrum for bandwidth, Q and shape factor."
        self.enableCB = chk = wx.CheckBox(self, -1, label)
        chk.SetValue(True)
        sizerV.Add(chk, 0, wx.ALL, 10)
        sizerV.Add(wx.StaticText(self, -1, \
            "Ref Marker is considered the peak. X1DB (typically 3 dB)"\
            "and X2DB (perhaps 30 dB,\nor 0 dB to ignore) are the dB"\
            "levels to evaluate."), 0, c|wx.ALL, 10)

        # ref marker and DB Down selection
        sizerG = wx.GridBagSizer(hgap=20, vgap=0)
        self.mNames = mNames = ("P+", "P-")
        sizerG.Add(wx.StaticText(self, -1, "Ref Marker"), (0, 0), flag=chb)
        self.peakMarkCB = cbox = wx.ComboBox(self, -1, "P+", \
                    (0, 0), (80, -1), mNames)
        sizerG.Add(cbox, (1, 0), flag=c)
        sizerG.Add(wx.StaticText(self, -1, "X1DB Down"), (0, 1), flag=chb)
        self.x1dbBox = tc = wx.TextCtrl(self, -1, "3", size=(60, -1))
        sizerG.Add(tc, (1, 1), flag=c)
        sizerG.Add(wx.StaticText(self, -1, "X2DB Down"), (0, 2), flag=chb)
        self.x2dbBox = tc = wx.TextCtrl(self, -1, "0", size=(60, -1))
        sizerG.Add(tc, (1, 2), flag=c)
        sizerV.Add(sizerG, 0, c|wx.ALL, 10)

        # Cancel and OK buttons
        butSizer = wx.BoxSizer(wx.HORIZONTAL)
        butSizer.Add((0, 0), 0, wx.EXPAND)
        btn = wx.Button(self, wx.ID_CANCEL)
        btn.Bind(wx.EVT_BUTTON, self.OnClose)
        butSizer.Add(btn, 0, wx.ALL, 5)
        btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        btn.Bind(wx.EVT_BUTTON, self.OnOK)
        butSizer.Add(btn, 0, wx.ALL, 5)
        sizerV.Add(butSizer, 0, wx.ALIGN_RIGHT|wx.ALIGN_BOTTOM|wx.ALL, 10)

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if self.pos == wx.DefaultPosition:
            self.Center()
        self.Show()

    #--------------------------------------------------------------------------
    # OK pressed- if enabled, analyze peak data and show in results box.

    def OnOK(self, event):
        frame = self.frame
        specP = frame.specP
        markers = specP.markers
        p = frame.prefs
        isLogF = p.isLogF

        if self.enableCB.IsChecked():
            # enabled: set up markers for analysis
            peakName = self.peakMarkCB.GetValue()
            # print ("Analyzing filter -- peak is", peakName)
            # get the db values for the x1 and x2 analysis points and
            # force them positive
            x1db = abs(floatOrEmpty(self.x1dbBox.GetValue()))
            x2db = abs(floatOrEmpty(self.x2dbBox.GetValue()))

            # add P+/P- reference marker if necessary
            magName = self.MagTraceName()
            mPeak =  markers.get(peakName)
            if not mPeak:
                mPeak = markers[peakName] = Marker(peakName, magName, p.fStart)

            # find N-db-down points and set markers
            isPos = peakName == "P+"
            show = False
            if x2db and x2db != 3:
                PeakS21DB, Fx2dbA, Fx2dbB = self.FindPoints(False, x2db, isPos)
                if show:
                    print ("X2: PeakS21DB=", PeakS21DB, "Fx2dbA=", Fx2dbA, \
                        "Fx2dbB=", Fx2dbB)
                if x1db:
                    if x1db != 3:
                        markers["3"] = Marker("3", magName, Fx2dbA)
                        markers["4"] = Marker("4", magName, Fx2dbB)
                    else:
                        markers["1"] = Marker("1", magName, Fx2dbA)
                        markers["2"] = Marker("2", magName, Fx2dbB)
            if x1db and x1db != 3:
                PeakS21DB, Fx1dbA, Fx1dbB = self.FindPoints(False, x1db, isPos)
                markers["1"] = Marker("1", magName, Fx1dbA)
                markers["2"] = Marker("2", magName, Fx1dbB)
                if show:
                    print ("X1: PeakS21DB=", PeakS21DB, "Fx1dbA=", Fx1dbA, \
                        "Fx1dbB=", Fx1dbB)
            PeakS21DB, Fdb3A, Fdb3B = self.FindPoints(False, 3, isPos)
            if show:
                print ("3dB: PeakS21DB=", PeakS21DB, "Fdb3A=", Fdb3A, \
                    "Fdb3B=", Fdb3B)
            if x1db == 3:
                Fx1dbA, Fx1dbB = Fdb3A, Fdb3B
            if x2db == 3:
                Fx2dbA, Fx2dbB = Fdb3A, Fdb3B

            # find amount of ripple
            # This is the max extent of the data values between the peak and
            # the last minor peak before reaching the target level.
            # To find that last peak, we take the derivative of the span
            # and find the last zero crossing. Then we can use argmin, argmax
            # on the remainder of the span.
            mPeak = markers[peakName]
            trM = specP.traces[magName]
            v = trM.v
            jP = trM.Index(mPeak.mhz, isLogF)
            jEnds = []
            for i in range(2):
                mE = markers["LR"[i]]
                dirE = 2*i - 1
                jE = trM.Index(mE.mhz, isLogF)
                if abs(jP - jE) > 1:
                    de = diff(v[jE:jP:-dirE])
                    jEnds.append(jE - dirE*interp(0, -de, arange(len(de))))
                else:
                    jEnds = None
            if jEnds != None:
                span = v[jEnds[0]:jEnds[1]]
                ripple = span[span.argmax()] - span[span.argmin()]
            else:
                ripple = 0

            # compute and display filter info
            BWdb3 = Fdb3B - Fdb3A
            info = "BW(3dB)=%sHz\n" % si(BWdb3*MHz, 3)
            if x1db and x1db != 3:
                info += "BW(%gdB)=%sHz\n" % (x1db, si((Fx1dbB - Fx1dbA)*MHz,3))
            if x2db and x2db != 3:
                info += "BW(%gdB)=%sHz\n" % (x2db, si((Fx2dbB - Fx2dbA)*MHz,3))
            Q = mPeak.mhz / BWdb3
            info += "Q=%4g\n" % Q
            if x1db and x2db:
                shape = (Fx2dbB - Fx2dbA) / (Fx1dbB - Fx1dbA)
                info += "SF(%gdB)/%gdB)=%4.2f\n" % (x1db, x2db, shape)
            info += "IL=%6.3f\nRipple=%4g" % (-PeakS21DB, ripple)
            specP.results = info

        else:
            # analysis disabled: remove results box
            specP.results = None

        specP.FullRefresh()
        self.OnClose(event)

