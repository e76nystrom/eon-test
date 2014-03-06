from msaGlobal import GetFontSize, GetMsa, SetModuleVersion
import wx
import copy as dcopy
from math import sqrt
from numpy import Inf, pi
from functionDialog import FunctionDialog
from msa import MSA
from util import fF, floatOrEmpty, kOhm, mH, MHz, mOhm, nF, nH, Ohms, pF, pH, si, uF, uH
from util import SeriesJigImpedance, ShuntJigImpedance, EquivParallelImped

SetModuleVersion(__name__,("1.0","3/6/2014"))

#==============================================================================
# The Component Meter dialog box.

# pointNum values: index to frequency that component is being tested at
_100kHz, _210kHz, _450kHz, _950kHz, _2MHz, _4p2MHz, _8p9MHz, _18p9MHz, \
    _40MHz = range(9)

class ComponentDialog(FunctionDialog):
    def __init__(self, frame):
        global msa
        msa = GetMsa()
        FunctionDialog.__init__(self, frame, "Component Meter", "comp")
        self.sizerV = sizerV = wx.BoxSizer(wx.VERTICAL)
        c = wx.ALIGN_CENTER
        self.helpText = \
        "Component Meter is a simple way to measure the value of components "\
        "which are known to be relatively pure resistors, capacitors or "\
        "inductors. It determines the component value from the attenuation "\
        "caused by the component in the test fixture. You select the fixture "\
        "and component type, run a single calibration, then insert and "\
        "measure components.\n\n"\
        "When you click Measure, the MSA will determine the component value "\
        "at one of several possible frequencies and display the frequency of "\
        "the measurement. The possible frequencies are those that the MSA "\
        "automatically included in the calibration. You may "\
        "increase/decrease the frequency of the measurement with the +Freq "\
        "and -Freq buttons, after pushing Stop.\n\n"\
        "The test fixture is typically an attenuator, then the component, "\
        "then another attenuator. The component may be connected in Series "\
        "between the attenuators, or may be Shunt to ground, which accounts "\
        "for the two different fixture types. The component will see a "\
        "certain resistance R0 looking at the incoming signal and the "\
        "outgoing signal. You must specify that R0, usually 50 ohms.\n\n"\
        "The Series fixture is calibrated with a Short (the terminals "\
        "directly shorted) and can typically measure R from 5 ohms to 100K "\
        "ohms; L from 10 nH to 1 mH, and C from 1 pF to 0.2 uF.\n\n"\
        "The Shunt fixture is calibrated with an Open (no component "\
        "attached) and can typically measure R from 0.25 ohms to 1 kohm; L "\
        "from 100 nH to 100 uH, and C from 20 pF to 2 uF.\n\n"\
        "For inductors, the series resistance and Q will be displayed, but "\
        "if Q>30, both Q and series resistance may be unreliable."

        # instructions
        st = wx.StaticText(self, -1, \
        "To measure resistance, capacitance or inductance you must first "\
        "calibrate. Calibrate with series shorted and shunt open. Then "\
        "insert the component and click Measure. The video filter should be "\
        "set to NARROW. Other settings will be made automatically. You can "\
        "temporarily change the frequency with +Freq or -Freq.")
        st.Wrap(600)
        sizerV.Add(st, 0, wx.ALL, 10)

        # test fixture
        sizerH1 = wx.BoxSizer(wx.HORIZONTAL)
        sizerH1.Add((1, 1), 1, wx.EXPAND)
        if msa.mode == MSA.MODE_VNATran:
            sizerH1.Add(self.FixtureBox(isSeriesFix=True, isShuntFix=True), 0, wx.ALIGN_TOP)
            sizerH1.Add((1, 1), 1, wx.EXPAND)

        # component type
        choices = ["Resistor", "Capacitor", "Inductor", "All"]
        self.typeRB = rb = wx.RadioBox(self, -1, "Component Type",
                        choices=choices, style=wx.RA_VERTICAL)
        self.Bind(wx.EVT_RADIOBOX, self.UpdateBtns, rb)
        sizerH1.Add(rb, 0, wx.ALIGN_TOP)
        sizerH1.Add((1, 1), 1, wx.EXPAND)
        sizerV.Add(sizerH1, 0, wx.EXPAND|wx.TOP, 10)
        sizerV.Add((1, 20), 0)

        # value display (StaticBox contents filled in by Update)
        self.freq = 0.1
        sizerGV = wx.GridBagSizer(hgap=2, vgap=5)
        self.freqText = st = wx.StaticText(self, -1, "")
        sizerGV.Add(st, (0, 0), flag=c)
        sizerGV.Add((20, 1), (0, 1), flag=wx.EXPAND)
        self.decFreqBtn = btn = wx.Button(self, -1, "-Freq")
        btn.Bind(wx.EVT_BUTTON, self.OnDecFreqBtn)
        sizerGV.Add(btn, (0, 2), flag=c)
        self.incFreqBtn = btn = wx.Button(self, -1, "+Freq")
        btn.Bind(wx.EVT_BUTTON, self.OnIncFreqBtn)
        sizerGV.Add(btn, (0, 3), flag=c)
        sb = wx.StaticBox(self, -1, "")
        self.sizerBV = sizerBV = wx.StaticBoxSizer(sb, wx.HORIZONTAL)
        sizerGV.Add(sizerBV, (1, 0), (1, 4), flag=c)
        sizerV.Add(sizerGV, 0, c|wx.ALL, 15)

        self.seriesRText = st = wx.StaticText(self, -1, "")
        sizerV.Add(st, 0, c, 0)

        # main buttons
        butSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.debugCB = chk = wx.CheckBox(self, -1, "Debug")
        butSizer.Add(chk, 0, c)
        butSizer.Add((20, 0), 0, wx.EXPAND)
        self.calibBtn = btn = wx.Button(self, -1, "Calibrate")
        btn.Bind(wx.EVT_BUTTON, self.OnCalibrateBtn)
        butSizer.Add(btn, 0, wx.ALL, 5)
        self.measBtn = btn = wx.Button(self, -1, "Measure")
        btn.Enable(False)
        btn.Bind(wx.EVT_BUTTON, self.OnMeasureBtn)
        butSizer.Add(btn, 0, wx.ALL, 5)
        btn = wx.Button(self, -1, "Help")
        btn.Bind(wx.EVT_BUTTON, self.OnHelpBtn)
        butSizer.Add(btn, 0, wx.ALL, 5)
        self.okBtn = btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        btn.Bind(wx.EVT_BUTTON, self.OnClose)
        butSizer.Add(btn, 0, wx.ALL, 5)
        sizerV.Add(butSizer, 0, wx.ALIGN_RIGHT|wx.ALIGN_BOTTOM|wx.ALL, 10)

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if self.pos == wx.DefaultPosition:
            self.Center()
        self.calibrated = False
        self.inCal = False
        self.measuring = False
        self.oldCompType = -1
        self.pointNum = None
        self.pointNums = {}
        self.UpdateBtns()
        self.valueBoxes = {}
        self.Show()

    #--------------------------------------------------------------------------
    # Update the states of all buttons and format the value box.

    def UpdateBtns(self, event=None):
        self.freqText.SetLabel("Frequency= %sHz" % si(self.freq * MHz, 3))
        calibrated = self.calibrated
        inCal = self.inCal
        newCompType = self.typeRB.GetSelection()
        afterMeasure = calibrated and not self.measuring and \
                        self.pointNum != None and newCompType != 4
        self.calibBtn.Enable(not self.measuring)
        self.calibBtn.SetLabel(("Calibrate", "Abort")[inCal])
        self.measBtn.Enable(calibrated)
        self.decFreqBtn.Enable(afterMeasure)
        self.incFreqBtn.Enable(afterMeasure)
        self.okBtn.Enable(not inCal)

        if (newCompType == 3) != (self.oldCompType == 3) or \
                self.oldCompType < 0:
            if self.measuring:
                self.StopMeasuring()
                self.calibBtn.Enable(True)
            self.oldCompType = newCompType
            # delete any previous type-dependent controls
            sizerBV = self.sizerBV
            sizerBV.Clear(deleteWindows=True)
            # create new type's controls
            c = wx.ALIGN_CENTER
            # ch = wx.ALIGN_CENTER_HORIZONTAL
            bigFont = wx.Font(GetFontSize()*2.0, wx.SWISS, wx.NORMAL, wx.BOLD)
            self.valueBoxes = {}
            if newCompType == 3:
                # Display all values at once
                sizerG2 = wx.GridBagSizer(5, 5)
                for j in range(2):
                    st = wx.StaticText(self, -1, ("Series", "Shunt")[j])
                    sizerG2.Add(st, (0, j), flag=c)
                    for i in range(3):
                        tc = wx.StaticText(self, -1, "----", size=(180, -1))
                        self.valueBoxes[(i,1-j)] = tc
                        tc.SetFont(bigFont)
                        tc.SetForegroundColour("BLUE")
                        sizerG2.Add(tc, (i+1,j), flag=c)
                sizerBV.Add(sizerG2, 0, 0)
            else:
                # Display selected component's value only
                tc = wx.StaticText(self, -1, "----", size=(200, -1))
                self.valueBox = tc
                tc.SetFont(bigFont)
                tc.SetForegroundColour("BLUE")
                sizerBV.Add(tc, 0, 0)
            sizerBV.Layout()
            self.sizerV.Fit(self)

    #--------------------------------------------------------------------------
    # Frequency up-down buttons for manual selection.

    def OnIncFreqBtn(self, event):
        if self.pointNum != None and self.pointNum < _40MHz:
            self.pointNum += 1
            self.Measure()

    def OnDecFreqBtn(self, event):
        if self.pointNum != None and self.pointNum > _100kHz:
            self.pointNum -= 1
            self.Measure()

    #--------------------------------------------------------------------------
    # Run calibration.

    def OnCalibrateBtn(self, event):
        frame = self.frame
        p = self.frame.prefs
        frame.task = None
        if msa.IsScanning():
            msa.StopScan()
            self.inCal = False
        else:
            # set up and run a calibration scan
            self.inCal = True
            self.UpdateBtns()
            p.isLogF = 1
            p.sweepDir = 0
            p.fStart = 0.1
            p.fStop = 40
            p.nSteps = 8
            p.wait = 10
            if msa.mode == MSA.MODE_VNARefl:
                self.calibrated = frame.PerformCal()
            else:
                msa.calibrating = True
                savePlaneExt = p.planeExt
                frame.DoExactlyOneScan()
                frame.WaitForStop()
                msa.calibrating = False
                p.planeExt = savePlaneExt
                frame.SetBandCal(dcopy.deepcopy(frame.spectrum))
                frame.SetCalLevel(2)
            self.freq = 0.1
            self.inCal = False
            self.calibrated = True
            self.measuring = False
            frame.DoExactlyOneScan()
            frame.WaitForStop()

        self.UpdateBtns()

    #--------------------------------------------------------------------------
    # Start or stop measuring.

    def OnMeasureBtn(self, event):
        frame = self.frame
        if self.measuring:
            # was measuring: stop
            self.StopMeasuring()
        else:
            # else, continue scan if needed, and grab current spectrum
            self.measBtn.SetLabel("Stop")
            msa.WrapStep()
            msa.haltAtEnd = False
            msa.ContinueScan()
            self.measuring = True
            # set up OnTimer repeating measmts while allowing other commands
            frame.task = self
        self.UpdateBtns()

    def StopMeasuring(self):
        frame = self.frame
        frame.task = None
        frame.StopScanAndWait()
        self.measBtn.SetLabel("Measure")
        self.measuring = False

    #--------------------------------------------------------------------------
    # Take a measurement, with automatic adjustment of pointNum.

    def AutoMeasure(self):
        self.pointNum = None
        for i in range(3):
            for j in range(2):
                self.pointNums[(i,j)] = None
        try:
            self.Measure()
        except:
            # don't allow repeated errors
            self.frame.task = None
            raise

    #--------------------------------------------------------------------------
    # Measure selected or all types.

    def Measure(self):
        iCompType = self.typeRB.GetSelection()
        if iCompType == 3:
            if len(self.valueBoxes) == 0:
                return
            # All: measure and display all 6 component/jig-type values at once
            for i in range(3):
                for j in range(2):
                    valueText, color, LText = self.MeasureOne(i, j)
                    tc = self.valueBoxes[(i,j)]
                    tc.SetLabel(valueText)
                    tc.SetForegroundColour(color)
                    ##if i == 2:
                    ##    self.seriesRText.SetLabel(LText)
            self.seriesRText.SetLabel("")
        else:
            # measure just the selected type
            if msa.mode == MSA.MODE_VNATran:
                isSeries = self.seriesRB.GetValue()
            else:
                isSeries = False
            valueText, color, LText = self.MeasureOne(iCompType, isSeries)
            self.valueBox.SetLabel(valueText)
            self.valueBox.SetForegroundColour(color)
            self.seriesRText.SetLabel(LText)
        self.UpdateBtns()

    #--------------------------------------------------------------------------
    # Calculate component value at point specified by pointNum, but if it is
    # None find best frequency. Get the component value (ohms, F, or H)
    # and the point number at which we measured. For L and C, we also get
    # the series resistance, which is valid if we have phase.
    # It is possible to get a negative L or C value, which means the
    # self-resonance has interfered and the measurement is not valid.

    def MeasureOne(self, iCompType, isSeries):
        self.iCompType = iCompType
        self.isSeries = isSeries
        frame = self.frame
        debugM = self.debugCB.IsChecked()
        if debugM:
            self.debugCB.SetValue(False)
        ##debugM = False
        spectrum = frame.spectrum
        Sdb = spectrum.Sdb
        if debugM:
            print ("Fmhz=", spectrum.Fmhz)
            print ("Sdb=", Sdb)

        self.compType = compType = ("R", "C", "L")[iCompType]
        compUnits = (Ohms, "F", "H")[iCompType]
        if msa.mode == MSA.MODE_VNATran:
            self.R0 = floatOrEmpty(self.R0Box.GetValue())
        else:
            self.R0 = msa.fixtureR0
        if self.typeRB.GetSelection() == 3:
            pointNum = self.pointNums[(iCompType, isSeries)]
        else:
            pointNum = self.pointNum

        # Do an initial measurement
        if pointNum == None:
            # need to find the best one -- assume we need to iterate
            nTries = 3
            if compType == "R":
                # 950kHz: high enough where LO leakages are not an issue
                pointNum = _950kHz
                nTries = 0
            else:
                lowFreqDB = Sdb[0]
                highFreqDB = Sdb[8]
                if debugM:
                    print ("lowFreqDB=", lowFreqDB, "highFreqDB=", highFreqDB, \
                        "isSeries=", isSeries, "compType=", compType)
                if compType == "C":
                    # Low impedance at 100 kHz indicates a large capacitor.
                    # High impedance at 40 MHz indicates a small capacitor.
                    # Large cap may be past its self-resonance at low freq, but
                    # will still have low impedance. Small cap will not be
                    # significantly affected by self-resonance at 40 MHz.
                    # We have to assume here small lead lengths on capacitors.
                    pointNum = _450kHz
                    if isSeries:
                        # We can tell whether we have extreme values by
                        # looking at 100 kHz and 40 MHz
                        # thresholds approx. 0.1 uF and 20 pF
                        isLowZ = lowFreqDB > -0.1
                        isHighZ = (not isLowZ) and highFreqDB < -7
                    else:
                        # thresholds approx. 0.1 uF and 100 pF
                        isLowZ = lowFreqDB < -5.5
                        isHighZ = (not isLowZ) and highFreqDB > -1.4
                    if isLowZ:
                        # Stick with lowest frequency
                        pointNum = _100kHz
                        nTries = 0
                    if isHighZ:
                        # start with highest frequency; may turn out hiZ is due
                        # to inductance
                        pointNum = _40MHz
                    if debugM:
                        print ("C: isLowZ=", isLowZ, "isHighZ=", isHighZ, \
                            "pointNum=", pointNum)
                else:
                    # Inductors are trickier, because losses can confuse the
                    # situation when just looking at S21 dB. So we make a guess
                    # at a starting point, but always do iteration, which
                    # separates L and R. Low impedance at 40 MHz indicates a
                    # very small inductor, though a lossy small inductor
                    # may be missed. It could also be large inductor that
                    # turned to a capacitor, but the iteration will take care
                    # of that case.
                    # A non-low impedance at 100 kHz indicates a large or
                    # lossy inductor. We will start with 100 kHz and iterate
                    # from there. For non-extreme inductors, we will start at
                    # 4.2 MHz and iterate
                    pointNum = _4p2MHz
                    if isSeries:
                        # thresholds 100 uH and 100 nH
                        isHighZ = lowFreqDB < -1.8
                        isLowZ = (not isHighZ) and highFreqDB > -0.45
                    else:
                        # thresholds 100 uH and 100 nH
                        isHighZ = lowFreqDB > -0.9
                        isLowZ = (not isHighZ) and highFreqDB < -3.4
                    if isHighZ:
                        # Start with lowest frequency
                        pointNum = _100kHz
                    if isLowZ:
                        # Start with highest frequency for small inductors
                        pointNum = _40MHz

#            print ("nTries ", nTries)
            for i in range(nTries):
                value, serRes = self.GetComponentValue(pointNum, debugM)
#                print (i, pointNum, value)
                # See if we are at a reasonable frequency for this comp value
                if value < 0:
                    # The component measured negative, which may be a
                    # sign it is past self-resonance, so we need to go
                    # with a low frequency; but go high if we are
                    # already low
                    if pointNum == _100kHz:
                        pointNum = _40MHz
                    else:
                        pointNum = max(_100kHz, int(pointNum/2))
#                    print ("negative selected ", pointNum)
                else:
                    if compType == "C":
#                        print ("type c ", value)
                        if isSeries:
#                            print ("series", value)
                            # series wants high Z, meaning lower freq
                            if value >= 5*nF:
                                pointNum = _100kHz
                            elif value >= 50*pF:
                                pointNum = _950kHz
                            else:
                                pointNum = _40MHz
#                            table = [(0.,     _40MHz),
#                                    ( 50*pF, _950kHz),
#                                    (  5*nF, _100kHz)]
                        else:
#                            print ("shunt", value)
                            if value >= 500*nF:
                                pointNum = _100kHz
                            elif value >= 50*nF:
                                pointNum = _210kHz
                            elif value >= 1*nF:
                                pointNum = _950kHz
                            elif value >= 100*pF:
                                pointNum = _8p9MHz
                            else:
                                pointNum = _40MHz
                            # shunt C wants low Z, meaning higher freq
#                            table = [(0.,     _40MHz),
#                                    (100*pF, _8p9MHz),
#                                    (  1*nF, _950kHz),
#                                    ( 50*nF, _210kHz),
#                                    (500*nF, _100kHz)]
                    else: # "L"
                        # Note: Inductor measurement is much less accurate
                        # without phase info, due to inductor losses. These
                        # ranges are se assuming phase is available. A prime
                        # goal is then to avoid the lowest freqs, where LO
                        # leakage has significant effect.
                        if value >= 1*mH:
                            pointNum = _100kHz
                        elif value >= 100*uH:
                            pointNum = _210kHz
                        elif value >= 10*uH:
                            pointNum = _950kHz
                        elif value >= 300*nH:
                            pointNum = _8p9MHz
                        else:
                            pointNum = _40MHz
#                        table = [(0.,     _40MHz),
#                                (300*nH, _8p9MHz),
#                                ( 10*uH, _950kHz),
#                                (100*uH, _210kHz),
#                                (  1*mH, _100kHz)]

                    # look up value in table of ranges
#                    i = bisect_right(table, (value,)) - 1
#                    if debugM:
#                        print ("value=", value, "i=", i, "table=", table)
#                    pointNum = table[i][1]
                    if debugM:
                        print ("pointNum=", pointNum)

        # get final value and series resistance
        value, serRes = self.GetComponentValue(pointNum, debugM)
#        print ("final ", pointNum, value)

        # display value, in red if out of range
        if value < 0:
            valueText = "------"
            valueColor = "RED"
        else:
            if value < (0.001, 10*fF, 500*pH)[iCompType]:
                value = 0.
            valueText = si(value, 4) + compUnits
            valueColor = "BLUE"
        R0ratio = self.R0 / 50
        if isSeries:
            lowLimit = (      -2,   1*pF,  10*nH)[iCompType]
            hiLimit  = (100*kOhm, 200*nF,   1*mH)[iCompType]
        else:
            lowLimit = (100*mOhm,  20*pF, 100*nH)[iCompType]
            hiLimit  = (  1*kOhm,   2*uF, 100*uH)[iCompType]
        if value < lowLimit*R0ratio or value > hiLimit*R0ratio:
            valueColor = "RED"

        # display frequency at which we measured
        self.freq = spectrum.Fmhz[pointNum]

        # display series resistance and Q for inductors
        LText = ""
        if compType == "L":
            if value < 0:
                Qtext = "300+"
            else:
                serX = 2*pi*self.freq*MHz * value
                Q = serX / serRes
                if Q > 300:
                    Qtext = "300+"
                else:
                    Qtext = "%g" % Q
            LText = "Series R=%5.2f Q=%s" % (serRes, Qtext)

        self.pointNums[(iCompType, isSeries)] = self.pointNum = pointNum
        return valueText, valueColor, LText

    #--------------------------------------------------------------------------
    # Calculate value of specified component.
    #
    # self.R0 of the test fixture; ignored for reflection mode, where
    #       ReflectArray data already accounts for it.
    # self.isSeries is 1 if fixture is Series; 0 if fixture is Shunt; ignored
    #     for reflection mode, where ReflectArray data already accounts for it.
    # self.compType is "R", "L" or "C"
    # step is the step at which we are measuring.
    # Returns value (Ohms, F or H) and, for L and C, series res in serRes.

    def GetComponentValue(self, step, debugM=False):
        compType = self.compType
        isSeries = self.isSeries
        R0 = self.R0
        serRes = 0.
        serX = 0.
        frame = self.frame
        spectrum = frame.spectrum

        if msa.mode == MSA.MODE_VNARefl:
            specP = frame.specP
            magName = self.MagTraceName()
            trMag = specP.traces[magName]
            serRes = trMag.Zs[step].real
            if serRes < 0.001:
                serRes = 0
            elif serRes > 1e9:
                serRes = 1e9
            if compType == "R":
                serX = trMag.Zs[step].imag
                if serX > 0:
                    value = trMag.Zs[step].real
                else:
                    value = trMag.Zp[step].real
                return value, serRes
            elif compType == "C":
                value = -1 / (trMag.Zs[step].imag * trMag.w[step])
            else:
                value = trMag.Zs[step].imag / trMag.w[step]
            return min(value, 1.), serRes

        # trueFreq is frequency in Hz
        # db is S21 or S11 db of the component in the fixture
        # phase is S21 or S11 phase, unless we are in SATG mode
        trueFreq = spectrum.Fmhz[step] * MHz
        db = min(spectrum.Sdb[step], 0)
        phase = spectrum.Sdeg[step]
        if debugM:
            print ("GetCompValue: step=", step, "db=", db, "phase=", phase)

        if msa.mode == MSA.MODE_SATG:
            # Calculate impedance from magnitude alone, assuming ideal phase
            # Magnitude of measured S21
            mag = 10**(db/20)
            if compType == "R":
                serX = 0
                if isSeries:
                    if mag > 0.9999:
                        serRes = 0.
                    else:
                        serRes = 2*R0 * (1 - mag) / mag
                    if debugM:
                        print ("R: mag=", mag, "serRes=", serRes)
                else:
                    if mag > 0.9999:
                        serRes = Inf
                    else:
                        serRes = R0 * mag / (2*(1 - mag))
            else:
                # L and C -- calculate reactance and then component value
                if isSeries:
                    if mag < 0.000001:
                        serX = 0.
                    else:
                        serX = 2*R0 * sqrt(1 - mag**2) / mag
                else:
                    if mag > 0.9999:
                        serX = Inf
                    else:
                        serX = R0 * mag / (2*sqrt(1 - mag**2))
                # capacitors have negative reactance
                if compType == "C":
                    serX = -serX
        else:
            # MODE_VNATran: calculate impedance from jig
            if isSeries:
                serRes, serX = SeriesJigImpedance(R0, db, phase)
            else:
                # We use no delay here, so we just provide a frequency of 1
                # assumes zero connector delay
                serRes, serX = ShuntJigImpedance(R0, db, phase, 0, 1, debugM)

        # serRes and serX now have the series resistance and reactance
        if debugM:
            print ("GetComponentValue: serRes=", serRes, "serX=", serX)
        if serRes < 0.001:
            serRes = 0.

        # if reactance is inductive, assume small resistor with parasitic
        # inductance and return series resistance
        if compType == "R":
            if serX > 0:
                return serRes, 0.
            # Here we want to return parallel resistance, because we are a
            # large resistor in parallel with parasitic capacitance
            parRes, parX = EquivParallelImped(serRes, serX)
            return parRes, 0.

        # Here for L or C. Convert reactance to component value
        if compType == "C":
            if serX == 0:
                value = 1.
            else:
                # capacitance in farads
                value = -1 / (2*pi*serX*trueFreq)
        else:
            # inductance in henries
            value = serX / (2*pi*trueFreq)
        if debugM:
            print ("--> GetComponentValue: serRes=", serRes, "value=", value, \
                    "f=", trueFreq)
        return min(value, 1.), serRes
