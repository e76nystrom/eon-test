from msaGlobal import GetMsa, SetModuleVersion
import wx
from wx.lib.dialogs import alertDialog
from msa import MSA
from util import floatOrEmpty, gstr, Ohms
from marker import Marker

SetModuleVersion("functionDialog",("1.30","EON","05/20/2014"))

#==============================================================================
# Base class for main dialog boxes.

class MainDialog(wx.Dialog):

    # Add a test-fixture settings box to the dialog. Returns its sizer.

    def FixtureBox(self, isSeriesFix=True, isShuntFix=False):
        p = self.frame.prefs
        c = wx.ALIGN_CENTER
        chb = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM
        self.R0 = p.fixtureR0
        titleBox = wx.StaticBox(self, -1, "Test Fixture")
        sizerHF = wx.StaticBoxSizer(titleBox, wx.HORIZONTAL)
        sizerVF1 = wx.BoxSizer(wx.VERTICAL)
        self.seriesRB = rb = wx.RadioButton(self, -1, "Series",
                                            style= wx.RB_GROUP)
        rb.Disable()
        rb.SetValue(isSeriesFix)
        sizerVF1.Add(rb, 0, wx.ALL, 2)
        self.shuntRB = rb = wx.RadioButton(self, -1, "Shunt")
        rb.Disable()
        rb.SetValue(isShuntFix)
        sizerVF1.Add(rb, 0, wx.ALL, 2)
        if GetMsa().mode == MSA.MODE_VNARefl:
            self.bridgeRB = rb = wx.RadioButton(self, -1, "Bridge")
            rb.Disable()
            rb.SetValue(not (isSeriesFix or isShuntFix))
            sizerVF1.Add(rb, 0, wx.ALL, 2)
        sizerHF.Add(sizerVF1, 0, c|wx.RIGHT, 10)
        sizerVG2 = wx.GridBagSizer()
        sizerVG2.Add(wx.StaticText(self, -1, "R0"), (0, 0), flag=chb)
        self.R0Box = tc = wx.TextCtrl(self, -1, gstr(self.R0), size=(40, -1))
        self.R0Box.Disable()
        sizerVG2.Add(tc, (1, 0), flag=c)
        sizerVG2.Add(wx.StaticText(self, -1, Ohms), (1, 1),
                flag=c|wx.LEFT, border=4)
        sizerHF.Add(sizerVG2, 0, c)
        return sizerHF

#==============================================================================
# Base class for Functions menu function dialog boxes.

class FunctionDialog(MainDialog):
    def __init__(self, frame, title, shortName):
        self.frame = frame
        self.title = title
        self.shortName = shortName
        p = frame.prefs
        self.pos = p.get(shortName+"WinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, title, self.pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        frame.StopScanAndWait()
        self.helpDlg = None
        self.R0 = p.fixtureR0

    #--------------------------------------------------------------------------
    # Common button events.

    def OnHelpBtn(self, event):
        self.helpDlg = dlg = FunctionHelpDialog(self)
        dlg.Show()

    def OnClose(self, event):
        p = self.frame.prefs
        self.frame.task = None
        msa = GetMsa()
        if msa.IsScanning():
            msa.StopScan()
            event.Skip()
        setattr(p, self.shortName+"WinPos", self.GetPosition().Get())
        p.R0 = self.R0
        helpDlg = self.helpDlg
        if helpDlg:
            setattr(p, self.shortName+"HelpWinPos", \
                                        helpDlg.GetPosition().Get())
            helpDlg.Close()
        self.Destroy()

    #--------------------------------------------------------------------------
    # Return the name of the primary "Mag" or "dB" trace.

    def MagTraceName(self):
        specP = self.frame.specP
        magNames = [x for x in specP.traces.keys() \
                if ("dB" in x) or ("Mag" in x)]
        if len(magNames) != 1:
            raise RuntimeError("No Magnitude trace found (or multiple)")
        return magNames[0]

    #--------------------------------------------------------------------------
    # Find peak frequency Fs, -3 dB (or dbDownBy) points, and Fp if fullSweep.
    # Sets self.Fs and self.Fp, and returns PeakS21DB, Fdb3A, Fdb3B.
    # If isPos is False, it finds only the notch Fp, which may be dbDownBy
    # dB up from the notch or taken as an absolute level if isAbs is True.

    def FindPoints(self, fullSweep=False, dbDownBy=3, isPos=True, isAbs=False):
        frame = self.frame
        p = frame.prefs
        specP = frame.specP
        markers = specP.markers
        specP.markersActive = True
        specP.dbDownBy = dbDownBy
        specP.isAbs = isAbs

        # place L, R, P+, P- markers on Mag trace and find peaks
        magName = self.MagTraceName()
        markers["L"]  = L =  Marker("L",  magName, p.fStart)
        markers["R"]  = R =  Marker("R",  magName, p.fStop)
        if isPos:
            markers["P+"] = Pres = Pp = Marker("P+", magName, p.fStart)
        if fullSweep or not isPos:
            markers["P-"] = Pres = Pm = Marker("P-", magName, p.fStart)
        frame.SetMarkers_PbyLR()
        wx.Yield()

        # place L and R at -3db points around P+ or P-
        (frame.SetMarkers_LRbyPm, frame.SetMarkers_LRbyPp)[isPos]()
        wx.Yield()

        # The main resonance is a peak if we have a crystal or a series RLC
        # in a series fixture, or parallel RLC in parallel fixture.
        Fres = Pres.mhz
        # For crystal we may also need to zoom in more closely around the
        # series peak to get a good read on Fs.

        if fullSweep:
            # we need to find Fp ourselves
            PeakS21DB = Pp.dbm
            self.Fs = Fs = Pp.mhz
            self.Fp = Fp = Pm.mhz
            if Fp > p.fStop - 0.00005:
                msg = "Sweep does not include enough of parallel resonance."
                raise RuntimeError(msg)
            if Fs >= Fp:
                msg = "Sweep does not show proper series resonance followed " \
                        "by parallel resonance."
                raise RuntimeError(msg)
        else:
            PeakS21DB = Pres.dbm
            self.Fres = Fres
            if isPos:
                self.Fs = Fres
            else:
                self.Fp = Fres

        if L.mhz < p.fStart or R.mhz > p.fStop:
            msg = "Sweep does not contain necessary -3 dB points."
            raise RuntimeError(msg)

        return PeakS21DB, L.mhz, R.mhz

    #--------------------------------------------------------------------------
    # Read R0 from text box.

    def GetR0FromBox(self):
        self.R0 = floatOrEmpty(self.R0Box.GetValue())
        if self.R0 < 0:
            self.R0 = 50
            alertDialog(self, "Invalid R0. 50 ohms used.", "Note")

#==============================================================================
# A Help dialog for a Function menu dialog.

class FunctionHelpDialog(wx.Dialog):
    def __init__(self, funcDlg):
        frame = funcDlg.frame
        p = frame.prefs
        pos = p.get(funcDlg.shortName+"HelpWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, funcDlg.title+" Help", pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        sizerV = wx.BoxSizer(wx.VERTICAL)
        self.SetBackgroundColour("WHITE")
        st = wx.StaticText(self, -1, funcDlg.helpText, pos=(10, 10))
        st.Wrap(600)
        sizerV.Add(st, 0, wx.ALL, 5)

        # OK button
        butSizer = wx.BoxSizer(wx.HORIZONTAL)
        butSizer.Add((0, 0), 0, wx.EXPAND)
        btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        butSizer.Add(btn, 0, wx.ALL, 5)
        sizerV.Add(butSizer, 0, wx.ALIGN_RIGHT)

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if pos == wx.DefaultPosition:
            self.Center()
