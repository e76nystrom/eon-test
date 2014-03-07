from msaGlobal import GetFontSize, SetModuleVersion
import sys, re, wx
from wx.lib.dialogs import alertDialog
from numpy import pi
from functionDialog import FunctionDialog
from crystal import CrystalParameters
from util import MHz, Ohms,  ParallelRLCFromScalarS21, pF, si, uH

SetModuleVersion(__name__,("1.0","3/6/2014"))

#==============================================================================
# The RLC Analysis dialog box.

class AnalyzeRLCDialog(FunctionDialog):
    def __init__(self, frame):
        FunctionDialog.__init__(self, frame, "RLC Analysis", "tranRLC")
        p = frame.prefs
        self.sizerV = sizerV = wx.BoxSizer(wx.VERTICAL)
        c = wx.ALIGN_CENTER

        self.helpText = \
        "RLC analysis will determine the R, L and C values for resistor, "\
        "inductor and capacitor combinations. The components may be in "\
        "series or in parallel, and either way they may be mounted in a "\
        "series or shunt fixture. The values of Q will also be determined."\
        "\n\nFor the shunt fixture, you may enter the time delay of the "\
        "connection between the actual fixture and the components; typically "\
        "on the order of 0.125 ns per inch.\n\n"\
        "You must enter the RLC Analysis function with a Transmission scan "\
        "already existing, showing the resonance peak (for series RLC in "\
        "series fixture, or parallel RLC in parallel fixture) or notch (for "\
        "series RLC in parallel fixture or parallel RLC in series fixture). "\
        "For resonance peaks, you should normally include the 3 dB points (3 "\
        "dB below a peak, or 3 dB above a dip). It is permissible, however, "\
        "to exclude one of those points. For resonant notches, you may "\
        "analyze the scan be using either the absolute -3 dB points (most "\
        "suitable for narrow notches) or the points 3 dB above the notch "\
        "bottom (most suitable for notches over 20 dB deep)."

        # description
        st = wx.StaticText(self, -1,"DETERMINATION OF COMBINED RLC PARAMETERS")
        sizerV.Add(st, 0, c|wx.TOP|wx.LEFT|wx.RIGHT, 10)
        st = wx.StaticText(self, -1, \
        "Determines individual components of an RLC combination from "\
        "resonance and 3 dB points. The scan must include the resonance and "\
        "at least one of the 3 dB points. High resolution improves "\
        "accuracy.")
        st.Wrap(600)
        sizerV.Add(st, 0, c|wx.TOP|wx.LEFT|wx.RIGHT, 10)

        # select series/parallel
        sizerG1 = wx.GridBagSizer(2, 2)
        self.parallelRLCRB = rb = wx.RadioButton(self, -1, \
            "The resistor, inductor and/or capacitor are in PARALLEL.", \
            style= wx.RB_GROUP)
        isSeriesRLC = p.get("isSeriesRLC", True)
        rb.SetValue(not isSeriesRLC)
        ##self.Bind(wx.EVT_RADIOBUTTON, self.UpdateFpBoxState, rb)
        sizerG1.Add(rb, (0, 0), (1, 6))
        self.SeriesRLCRB = rb = wx.RadioButton(self, -1, \
            "The resistor, inductor and/or capacitor are in SERIES.")
        rb.SetValue(isSeriesRLC)
        sizerG1.Add(rb, (1, 0), (1, 6))
        ##self.Bind(wx.EVT_RADIOBUTTON, self.UpdateFpBoxState, rb)
        sizerV.Add(sizerG1, 0, wx.ALL, 10)

        # test fixture
        isSeriesFix = p.get("isSeriesFix", True)
        st = self.FixtureBox(isSeriesFix, not isSeriesFix)
        sizerV.Add(st, 0, c|wx.ALL, 10)

        # select top/bottom 3dB points
        sizerG1 = wx.GridBagSizer(2, 2)
        self.useTopRB = rb = wx.RadioButton(self, -1, \
            "Use points at absolute -3 dB. (Best for narrow notches.)", \
            style= wx.RB_GROUP)
        isRLCUseTop = p.get("isRLCUseTop", True)
        rb.SetValue(not isRLCUseTop)
        self.Bind(wx.EVT_RADIOBUTTON, self.UpdateFpBoxState, rb)
        sizerG1.Add(rb, (0, 0), (1, 6))
        self.useBotRB = rb = wx.RadioButton(self, -1, \
            "Use points +3 dB from notch bottom. (Notch depth should exceed "\
            "20 dB.)")
        rb.SetValue(isRLCUseTop)
        sizerG1.Add(rb, (1, 0), (1, 6))
        self.Bind(wx.EVT_RADIOBUTTON, self.UpdateFpBoxState, rb)
        sizerV.Add(sizerG1, 0, wx.ALL, 10)

        # warning msg
        self.warnBox = st = wx.StaticText(self, -1, "")
        sizerV.Add(st, 0, c|wx.ALL, 10)
        fontSize = GetFontSize()
        st.SetFont(wx.Font(fontSize*1.3, wx.SWISS, wx.NORMAL, wx.BOLD))

        # text box for analysis results
        self.resultsBox = rb = wx.TextCtrl(self, -1, "", size=(400, -1))
        sizerV.Add(rb, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 20)

        #  bottom row buttons
        sizerH3 = wx.BoxSizer(wx.HORIZONTAL)
        sizerH3.Add((30, 0), 0, wx.EXPAND)
        self.analyzeBtn = btn = wx.Button(self, -1, "Analyze")
        btn.Bind(wx.EVT_BUTTON, self.OnAnalyze)
        btn.SetDefault()
        sizerH3.Add(btn, 0, c|wx.ALL, 5)
        sizerH3.Add((30, 0), 0, 0)
        self.helpBtn = btn = wx.Button(self, -1, "Help")
        btn.Bind(wx.EVT_BUTTON, self.OnHelpBtn)
        sizerH3.Add(btn, 0, c|wx.ALL, 5)
        self.okBtn = btn = wx.Button(self, wx.ID_OK)
        btn.Bind(wx.EVT_BUTTON, self.OnClose)
        sizerH3.Add(btn, 0, c|wx.ALIGN_RIGHT|wx.ALL, 5)
        sizerV.Add(sizerH3, 0, wx.ALIGN_RIGHT|wx.ALIGN_BOTTOM|wx.ALL, 10)

        self.UpdateFpBoxState()
        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if self.pos == wx.DefaultPosition:
            self.Center()
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Show()

    #--------------------------------------------------------------------------
    # Set the warning text based on top/bottom selection.

    def UpdateFpBoxState(self, event=None):
        self.useTop = useTop = self.useTopRB.GetValue()
        self.warnBox.SetLabel( \
        "Scan must show resonant notch and at least one point " +
        ("3 dB above notch bottom.", "at absolute -3 dB level.")[useTop])

    #--------------------------------------------------------------------------
    # Analyze the scan to extract RLC parameters.
    # We determine Q from resonant frequency and -3 dB bandwidth, and directly
    # measure Rs at resonance. From Q and Rs we can calculate L and C.

    def OnAnalyze(self, event):
        frame = self.frame
        specP = frame.specP
        #markers = specP.markers
        p = frame.prefs
        #isLogF = p.isLogF
        R0 = self.R0
        p.isSeriesRLC = isSeriesRLC = self.SeriesRLCRB.GetValue()
        p.isSeriesFix = isSeriesFix = self.seriesRB.GetValue()
        # a peak is formed if components in series and fixure is series
        isPos = not (isSeriesRLC ^ isSeriesFix)
        p.useTop = useTop = self.useTopRB.GetValue()

        try:
            Rser = 0
            isAbs = not isPos and useTop
            PeakS21DB, Fdb3A, Fdb3B = self.FindPoints(False, isPos=isPos, \
                                                      isAbs=isAbs)
            Fres = self.Fres

            if not isPos and not useTop:
                # analyze bottom of notch. Q determined from the 3 dB
                # bandwidth is assumed to be Qu
                S21 = 10**(-PeakS21DB/20)
                wp = 2*pi*Fres*MHz
                if isSeriesFix:
                    R = 2*R0 * (S21 - 1)
                else: # shunt fixture
                    R = (R0/2) / (S21 - 1)
                R = max(R, 0.001)
                BW = Fdb3B - Fdb3A
                # Qu at resonance. Accurate if notch is deep.
                Qu = Fres / BW
                if isSeriesRLC:
                    # series RLC in shunt fixture
                    Xres = R * Qu
                    QL = Xres / (R0/2)
                    Rser = R
                else:
                    # parallel RLC in shunt fixture
                    Xres = R / Qu
                    QL = Xres / (R0*2)
                    Rser = Xres / Qu

                L = Xres / wp
                C = 1 / (Xres * wp)

            else:
                # Analyze top of peak or notch
                if isSeriesRLC:
                    # For series RLC use crystal routine; Fp and Cp are bogus
                    R, C, L, Cp, Qu, QL = CrystalParameters(Fres, 1., \
                                    PeakS21DB, Fdb3A, Fdb3B, R0, isSeriesFix)
                else: # parallel RLC
                    R, C, L, Qu, QL, Rs = ParallelRLCFromScalarS21(Fres,
                                    PeakS21DB, Fdb3A, Fdb3B, R0, isSeriesFix)
                L *= uH
                C *= pF
            Fres *= MHz

        except RuntimeError:
            alertDialog(self, sys.exc_info()[1].message, "Analyze Error")
            return

        # compute and display filter info
        resText = ("F%s=%sHz, R=%s"+Ohms+", L=%sH, C=%sF, Qu=%s, QL=%s") % \
                ("ps"[isPos], si(Fres, 9), si(R, 4), si(L, 3), si(C, 3), \
                si(Qu, 3), si(QL, 3))
        if Rser > 0:
            resText += (", (Rser=%s)" % si(Rser, 3))
        self.resultsBox.SetValue(resText)

        BWdb3 = Fdb3B - Fdb3A
        info = re.sub(", ", "\n", resText) + "\n"
        info += ("BW(3dB)=%sHz" % si(BWdb3*MHz, 3))
        specP.results = info

        specP.FullRefresh()
        self.okBtn.SetDefault()

