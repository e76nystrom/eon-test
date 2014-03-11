from msaGlobal import GetMsa, SetModuleVersion
import wx
from numpy import mod
from msa import MSA

SetModuleVersion("pdmCal",("1.02","EON","03/11/2014"))

#==============================================================================
# The PDM Calibration dialog box.

class PDMCalDialog(wx.Dialog):
    def __init__(self, frame):
        self.frame = frame
        p = frame.prefs
        msa = GetMsa()
        if msa.IsScanning():
            msa.StopScan()
        pos = p.get("pdmCalWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, "PDM Calibration", pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        c = wx.ALIGN_CENTER
        sizerV = wx.BoxSizer(wx.VERTICAL)
        st = wx.StaticText(self, -1, \
        "The actual phase shift caused by PDM inversion will differ from "\
        "the theoretical 180 degrees. A one-time calibration is required to "\
        "determine the actual phase shift. This value will be used "\
        "internally, and you will not directly need to know or use the "\
        "value. To perform this calibration you first need to do the "\
        "following, which will require that you close this window and return "\
        "to the Graph Window:\n\n"\
        "    * Set Video Filter to NARROW bandwidth.\n"\
        "    * Connect Tracking Generator output to MSA input with 1-2 foot "\
                "cable.\n"\
        "    * In menu Operating Cal->Transmission, set Transmission "\
                "Reference to No Reference.\n"\
        "    * Sweeping 0-200 MHz, find a frequency with a phase shift near "\
                "90 or 270 deg.\n"\
        "    * Center the sweep at that frequency, with zero sweep width.\n"\
        "    * Return to this window and click the PDM Inversion Cal button.")
        st.Wrap(600)
        sizerV.Add(st, 0, c|wx.ALL, 10)

        btn = wx.Button(self, -1, "Set Up")
        btn.Bind(wx.EVT_BUTTON, self.OnCalSetup)
        sizerV.Add(btn, 0, c|wx.ALL, 5)
        btn = wx.Button(self, -1, "PDM Inversion Cal")
        btn.Bind(wx.EVT_BUTTON, self.OnPDMInversionCal)
        sizerV.Add(btn, 0, c|wx.ALL, 5)
        self.invDeg = p.invDeg
        self.invBox =tb = wx.StaticText(self, -1,
                                "Current Inversion= %g deg" % self.invDeg)
        sizerV.Add(tb, 0, c)

        # Cancel and OK buttons
        butSizer = wx.BoxSizer(wx.HORIZONTAL)
        butSizer.Add((0, 0), 0, wx.EXPAND)
        btn = wx.Button(self, wx.ID_CANCEL)
        butSizer.Add(btn, 0, wx.ALL, 5)
        btn = wx.Button(self, wx.ID_OK)
        butSizer.Add(btn, 0, wx.ALL, 5)
        sizerV.Add(butSizer, 0, wx.ALIGN_RIGHT|wx.ALIGN_BOTTOM|wx.ALL, 10)

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if pos == wx.DefaultPosition:
            self.Center()

    #--------------------------------------------------------------------------
    # Set up for a PDM calibration.

    def OnCalSetup(self, event):
        frame = self.frame
        p = frame.prefs
        if frame.sweepDlg:
            frame.sweepDlg.OnClose()
        p.fStart = 0.
        p.fStop = 200.
        p.nSteps = 100
        p.planeExt = 3*[0.]
        p.isLogF = False
        frame.SetCalLevel(0)
        frame.SetMode(MSA.MODE_VNATran)
        frame.ScanPrecheck(True)

    #--------------------------------------------------------------------------
    # Find the amount of phase shift when the PDM state is inverted.
    # invDeg is a calibration value used in CaptureOneStep(),
    # (phase of inverted PDM) - (invDeg) = real phase of PDM.
    # The VNA must be in "0" sweepwidth, freq close to the transition point.

    def OnPDMInversionCal(self, event):
        frame = self.frame
        p = frame.prefs
        print ("Calibrating PDM Inversion")
        msa = GetMsa()
        msa.wait = 250
        msa.invDeg = 192.
        msa.invPhase = 0
        msa.WrapStep()
        freq, adc, Sdb, phase0 = \
            msa.CaptureOneStep(post=False, useCal=False, bypassPDM=True)
        print ("phase0= %8.3f freq= %8.6f adc=%5d" % (phase0, freq, msa._phasedata))
        msa.invPhase = 1
        msa.WrapStep()
        freq, adc, Sdb, phase1 = \
            msa.CaptureOneStep(post=False, useCal=False, bypassPDM=True)
        print ("phase0= %8.3f freq= %8.6f adc=%5d" % (phase1, freq, msa._phasedata))
        msa.wait = p.wait
        self.invDeg = round(mod(phase1 - phase0, 360), 2)
        self.invBox.SetLabel("Current Inversion= %g deg" % self.invDeg)
