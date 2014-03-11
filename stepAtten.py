from msaGlobal import GetCb, GetMsa, SetModuleVersion
import wx
from functionDialog import FunctionDialog
from msa import MSA
from util import floatOrEmpty
from ref import Ref

SetModuleVersion("stepAtten",("1.02","EON","03/11/2014"))

#=============================================================================
# The Step Attenuator dialog box.

class StepAttenDialog(FunctionDialog):
    def __init__(self, frame):
        global msa, cb
        msa = GetMsa()
        cb = GetCb()
        FunctionDialog.__init__(self, frame, "Step Attenuator", "stepAtten")
        p = frame.prefs
        self.sizerV = sizerV = wx.BoxSizer(wx.VERTICAL)
        c = wx.ALIGN_CENTER

        frame.StopScanAndWait()

        # instructions
        st = wx.StaticText(self, -1, \
        "With one or two digital step attenuator modules attached, a series "\
        "of sweeps may be made. set the number of steps and the step increment, "\
        "keeping the total within the range of the attenuator(s), and the "\
        "number of steps less than 10. Then click Run Steps. Any existing "\
        "Ref Lines will be replaced with the series. "\
        "An example: a pair of SKY12347 64-step "\
        "attenuators with 0.5dB per step could make a series of 7 in 10 dB "\
        "steps. Remember to account for attenuator insertion loss.")
        st.Wrap(600)
        sizerV.Add(st, 0, wx.ALL, 10)

        # steps range entry
        sizerH1 = wx.BoxSizer(wx.HORIZONTAL)
        self.nStepsLabel = st = wx.StaticText(self, -1, "# steps:")
        sizerH1.Add(st, 0, c|wx.RIGHT, 5)
        n = str(p.get("stepAttenN", 5))
        self.nStepsBox = tc = wx.TextCtrl(self, -1, n, size=(40, -1))
        tc.SetInsertionPoint(2)
        sizerH1.Add(tc, 0, c)
        sizerH1.Add((50, 0), 0, wx.EXPAND)
        sizerH1.Add(wx.StaticText(self, -1, "Start:"), 0, c|wx.RIGHT, 5)
        start = str(p.get("stepAttenStart", 0))
        self.stepsStartBox = tc = wx.TextCtrl(self, -1, start, size=(40, -1))
        tc.SetInsertionPoint(2)
        sizerH1.Add(tc, 0, c)
        sizerH1.Add(wx.StaticText(self, -1, "dB"), 0, c|wx.LEFT, 5)
        sizerH1.Add((50, 0), 0, wx.EXPAND)
        step = str(p.get("stepAttenStep", 5))
        sizerH1.Add(wx.StaticText(self, -1, "Step:"), 0, c|wx.RIGHT, 5)
        self.stepsStepBox = tc = wx.TextCtrl(self, -1, step, size=(40, -1))
        tc.SetInsertionPoint(2)
        sizerH1.Add(tc, 0, c)
        sizerH1.Add(wx.StaticText(self, -1, "dB"), 0, c|wx.LEFT, 5)
        sizerH1.Add((50, 0), 0, wx.EXPAND)
        sizerV.Add(sizerH1, 0, c|wx.ALL, 10)

        #  bottom row buttons
        sizerH3 = wx.BoxSizer(wx.HORIZONTAL)
        self.analyzeBtn = btn = wx.Button(self, -1, "Run Steps")
        btn.Bind(wx.EVT_BUTTON, self.OnRun)
        sizerH3.Add(btn, 0, c|wx.ALL, 5)
        self.okBtn = btn = wx.Button(self, wx.ID_OK)
        btn.Bind(wx.EVT_BUTTON, self.OnClose)
        sizerH3.Add(btn, 0, c|wx.ALIGN_RIGHT|wx.ALL, 5)
        sizerV.Add(sizerH3, 0, c|wx.ALL, 10)

        frame.ClearMarks() # extra Markers just cause visual confusion
        self.id = 1

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if self.pos == wx.DefaultPosition:
            self.Center()
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.haveAnalyzed = False
        self.resultsWin = None
        self.Show()

    def OnClose(self, event):
        self.frame.task = None
        if msa.IsScanning():
            self.done = True
            msa.StopScan()
        else:
            self.Destroy()

    #--------------------------------------------------------------------------
    # Run a series of scans of a range of attenuations.

    def OnRun(self, event):
        frame = self.frame
        p = frame.prefs
        n = int(self.nStepsBox.GetValue())
        if n < 1:
            n = 1
        p.stepAttenN = n
        stepAttenDB = floatOrEmpty(self.stepsStartBox.GetValue())
        p.stepAttenStart = p.stepAttenDB
        p.stepAttenStep = step = floatOrEmpty(self.stepsStepBox.GetValue())

        # loop for each attenuator value
        self.done = False;
        for refNum in range(1, n+1):
            SetStepAttenuator(stepAttenDB)
            frame.DoExactlyOneScan()
            frame.WaitForStop()
            if self.done:
                self.Destroy()
                break

            # create a new ref from current data
            spec = frame.spectrum
            vScales = frame.specP.vScales
            # get the units from both vertical scales
            bothU = [vs.dataType.units for vs in vScales]
            ##print ("bothU=", bothU
            for i in range(2):
                vScale = vScales[i]
                # create a ref for each axis, unless the axes are
                # (db, Deg), in which case we create one ref with both
                if i == 1 and (msa.mode < MSA.MODE_VNATran or \
                         ("dB" in bothU and \
                         ("Deg" in bothU or "CDeg" in bothU))):
                    continue
                ref = Ref.FromSpectrum(refNum, spec, vScale)
                # assign trace width(s) and name
                ref.aWidth = 1
                if msa.mode >= MSA.MODE_VNATran:
                    # ref for axis 0 may be both mag and phase traces
                    ref.bWidth = 1
                ref.name = "%04.1fdB" % stepAttenDB
                frame.refs[refNum] = ref
            frame.DrawTraces()
            frame.specP.FullRefresh()

            stepAttenDB += step

def SetStepAttenuator(value):
    global msa, cb
    msa = GetMsa()
    cb = GetCb()
    band = msa._GHzBand
    msa._SetFreqBand(band)
    # each attenuator value is 0-31 in 0.5-dB increments
    value = int(value * 2)
    if 1:
        # dual attenuators
        if value > 0x3f:
            value = (0x3f << 6) | (value - 0x3f)   # (bitwise OR)
        for i in range(12):
            bit = ((value >> 11) & 1) ^ 1
            value <<= 1
            msa._SetFreqBand(band, (bit << cb.P4_AttenDataBit))
            msa._SetFreqBand(band, (bit << cb.P4_AttenDataBit) | cb.P4_AttenClk)
            msa._SetFreqBand(band, (bit << cb.P4_AttenDataBit))
    else:
        if 0:
            # clock scope loop
            while 1:
                msa._SetFreqBand(band, 0)
                msa._SetFreqBand(band, cb.P4_AttenClk)

        # single attenuator
        for i in range(6):
            bit = ((value >> 5) & 1) ^ 1
            value <<= 1
            msa._SetFreqBand(band, (bit << cb.P4_AttenDataBit))
            msa._SetFreqBand(band, (bit << cb.P4_AttenDataBit) | cb.P4_AttenClk)
            msa._SetFreqBand(band, (bit << cb.P4_AttenDataBit))
    # latch attenuator value and give relays time to settle
    msa._SetFreqBand(band, cb.P4_AttenLE)
    msa._SetFreqBand(band)
    cb.msWait(100)
