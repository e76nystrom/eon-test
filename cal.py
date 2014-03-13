from msaGlobal import GetMsa, GetVersion, SetModuleVersion
import cmath, os, re, time, wx
import copy as dcopy
from numpy import array, cos, interp, pi, sin, tan, zeros
from util import constMaxValue, DegreesPerRad, floatOrEmpty, floatSI, message, \
    polarDbDeg, RadsPerDegree, uSafeLog10
from msa import MSA
from functionDialog import MainDialog
from spectrum import Spectrum

SetModuleVersion("cal",("1.03","EON","03/13/2014"))

calWait = 50 # sweep wait during calibration # EON Jan 29, 2014

# Return base 10 log of aVal; special rule for small and non-positive arguments

def uNormalizeDegrees(deg):
    while deg <= -180:
        deg += 360
    while deg > 180:
        deg -= 360
    return deg

def cpx(Z):
    val = "(%10.3e,%10.3e)" % (Z.real, Z.imag)
    return val

def pol(X):
    val = "(m %10.3e,p %10.3e)" % (X[0], X[1])
    return val

#==============================================================================
# The Perform Calibration dialog box.

class PerformCalDialog(MainDialog):
    def __init__(self, frame):
        global msa
        msa = GetMsa()
        self.frame = frame
        p = frame.prefs
        pos = p.get("perfCalWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, "Perform Calibration", pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        self.sizerV = sizerV = wx.BoxSizer(wx.VERTICAL)
        c = wx.ALIGN_CENTER

        # text box, filled in by Update()
        self.textBox = wx.StaticText(self, -1, "")
        sizerV.Add(self.textBox, 0, wx.TOP|wx.LEFT|wx.RIGHT, 10)

        # optional thru delay
        self.calThruBox = None
        # DISABLED- expected to be set up beforehand in Sweep dialog
        if msa.mode == MSA.MODE_VNATran: # EON Jan 10 2014
            sizerH = wx.BoxSizer(wx.HORIZONTAL)
            st = wx.StaticText(self, -1,
                    "Delay of Calibration Through Connection:")
            sizerH.Add(st, 0, c|wx.RIGHT, 8)
            delText = "%g" % p.get("calThruDelay", 0)
            tc = wx.TextCtrl(self, -1, delText, size=(40, -1))
            self.calThruBox = tc
            tc.SetInsertionPoint(len(delText))
            sizerH.Add(tc, 0, c)
            sizerH.Add(wx.StaticText(self, -1, "ns"), 0, c|wx.LEFT, 5)
            sizerV.Add(sizerH, 0, wx.LEFT, 20)

        if 0 and msa.mode == MSA.MODE_VNARefl: #EON add 0 to disable 12/24/2013
            # test fixture
            sizerH1 = wx.BoxSizer(wx.HORIZONTAL)
            sizerH1.Add((1, 1), 1, wx.EXPAND)
            series = p.get("isSeriesFix", True)
            shunt = p.get("isShuntFix", False)
            sizerH1.Add(self.FixtureBox(series, shunt), 0, wx.ALIGN_TOP)
            sizerH1.Add((1, 1), 1, wx.EXPAND)
            sizerV.Add(sizerH1, 0, c)

        #  buttons
        sizerG1 = wx.GridBagSizer(10, 10)
        self.perfBandCalBtn = btn = wx.Button(self, -1, "Perform Band Cal")
        # Start EON Jan 10 2014
        if msa.mode == MSA.MODE_VNATran:
            btn.Bind(wx.EVT_BUTTON, self.OnPerformBandCal)
        else:
            btn.Bind(wx.EVT_BUTTON, self.ReflBandCalDialog)
        # End EON Jan 10 2014
        sizerG1.Add(btn, (0, 0), flag=c)
        self.saveAsBaseBtn = btn = wx.Button(self, -1, "Save As Base")
        btn.Bind(wx.EVT_BUTTON, self.OnSaveAsBase)
        sizerG1.Add(btn, (1, 0), flag=c)
        self.clearBandBtn = btn = wx.Button(self, -1, "Clear Band Cal")
        btn.Bind(wx.EVT_BUTTON, self.OnClearBandCal)
        sizerG1.Add(btn, (0, 1), flag=c)
        self.clearBaseBtn =  btn = wx.Button(self, -1, "Clear Base Cal")
        btn.Bind(wx.EVT_BUTTON, self.OnClearBaseCal)
        sizerG1.Add(btn, (1, 1), flag=c)
        self.helpBtn = btn = wx.Button(self, -1, "Help")
        btn.Bind(wx.EVT_BUTTON, self.OnHelp)
        sizerG1.Add(btn, (0, 3)) # EON Jan 22, 2014
        self.okBtn = btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        sizerG1.Add(btn, (1, 3)) # EON Jan 22, 2014
        sizerV.Add(sizerG1, 0, wx.EXPAND|wx.ALL, 10)
        sizerG1.AddGrowableCol(2) # EON Jan 22, 2014

        self.SetSizer(sizerV)
        self.Update()
        if pos == wx.DefaultPosition:
            self.Center()
        self.Bind(wx.EVT_CLOSE, self.OnClose)

    #--------------------------------------------------------------------------
    # Update help and info text and button enables after a change.

    def Update(self):
        frame = self.frame
        p = frame.prefs
        msg = "Connect TG output and MSA input to test fixture and attach "\
                "proper cal standards."
        if msa.mode == MSA.MODE_VNATran:
            msg = "TG output must have THROUGH connection to MSA input."
        bandCalInfo = "(none)"
        spec = msa.bandCal
        # Start EON Jan 10 2014
        if spec:
            bandCalInfo = "Performed %s" % spec.desc
        baseCalInfo = "(none)"
        spec = msa.baseCal
        if spec:
            baseCalInfo = "Performed %s" % spec.desc
        # End EON Jan 10 2014
        self.textBox.SetLabel( \
        "            The MSA is currently in Path %d.\n\n"\
        "MSA calibrations are not saved separately for different paths. If "\
        "the current path is not the one for which the calibration will be "\
        "used, close this window and change the path selection. VIDEO FILTER "\
        "should be set to NARROW bandwidth for maximum smoothing. %s\n\n"\
        "Band Sweep calibration is run at the same frequency points at which "\
        "it will be used.\n\n"\
        "   Band: %s\n\n"\
        "You may save the current Band calibration as a Base calibration, to "\
        "be used as a coarse reference when the Band calibration is not "\
        "current.\n\n"\
        "   Base: %s \n\n"\
        % (p.indexRBWSel + 1, msg, bandCalInfo, baseCalInfo))
        self.textBox.Wrap(600)

        self.sizerV.Fit(self)
        frame.RefreshAllParms()

    #--------------------------------------------------------------------------
    # Perform Band Cal pressed- do a scan in calibration mode.

    def OnPerformBandCal(self, event):
        frame = self.frame
        p = frame.prefs
        if msa.IsScanning():
            msa.StopScan()
        else:
## Start EON Jan 10 2014
##            if msa.mode == MSA.MODE_VNARefl:
##                spec = frame.spectrum
##                p.isSeriesFix = self.seriesRB.GetValue()
##                p.isShuntFix = self.shuntRB.GetValue()
##                if spec:
##                    spec.isSeriesFix = p.isSeriesFix
##                    spec.isShuntFix = p.isShuntFix
## End EON Jan 10 2014
            msa.calibrating = True
            ##savePlaneExt = p.planeExt
            if self.calThruBox:
                p.calThruDelay = floatOrEmpty(self.calThruBox.GetValue())
                p.planeExt = 3*[p.calThruDelay]
            self.perfBandCalBtn.SetLabel("Cancel")
            self.EnableButtons(False)
            frame.DoExactlyOneScan()
            frame.WaitForStop()
            self.perfBandCalBtn.SetLabel("Perform Band Cal")
            self.EnableButtons(True)
            msa.calibrating = False
            ##p.planeExt = savePlaneExt
            frame.SetBandCal(dcopy.deepcopy(frame.spectrum))
            frame.SetCalLevel(2)
            self.Update()

    # Start EON Jan 10 2014
    #--------------------------------------------------------------------------
    # Reflection Band Cal

    def ReflBandCalDialog(self, event):
        p = self.frame.prefs
        dlg = PerformReflCalDialog(self.frame, self)
        if dlg.ShowModal() == wx.ID_OK:
            p.perfReflCalpWinPos = dlg.GetPosition().Get()
    # End EON Jan 10 2014

    #--------------------------------------------------------------------------
    # Save As Base pressed- copy band cal data to base.

    def OnSaveAsBase(self, event):
        self.frame.CopyBandToBase()
        self.Update()

    #--------------------------------------------------------------------------
    # Clear Band or Clear Base Cal pressed- clear corresponding data.

    def OnClearBandCal(self, event):
        frame = self.frame
        if msa.bandCal:
            frame.SetBandCal(None)
            if msa.baseCal:
                frame.SetCalLevel(1)
            else:
                frame.SetCalLevel(0)
            self.Update()

    def OnClearBaseCal(self, event):
        frame = self.frame
        if msa.baseCal:
            msa.baseCal = None
            # Start EON Jan 10 2014
            try:
                os.unlink(frame.baseCalFileName)
            except:
                pass
            # End EON Jan 10 2014
            if not msa.bandCal:
                frame.SetCalLevel(0)
            self.Update()

    #--------------------------------------------------------------------------
    # Help pressed- bring up help.

    def OnHelp(self, event):
        p = self.frame.prefs
        dlg = OperCalHelpDialog(self.frame)
        if dlg.ShowModal() == wx.ID_OK:
            p.operCalHelpWinPos = dlg.GetPosition().Get()

    #--------------------------------------------------------------------------
    # Disable buttons while running calibration.

    def EnableButtons(self, enable):
        self.saveAsBaseBtn.Enable(enable)
        self.clearBandBtn.Enable(enable)
        self.clearBaseBtn.Enable(enable)
        self.okBtn.Enable(enable)

    #--------------------------------------------------------------------------
    # Close- quit any running calibration.

    def OnClose(self, event):
        if msa.IsScanning():
            msa.StopScan()
            event.Skip()

#==============================================================================
# A Help dialog for Operating Cal dialog.

class OperCalHelpDialog(wx.Dialog):
    def __init__(self, frame):
        p = frame.prefs
        pos = p.get("operCalHelpWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, "Perform Calibration Help", pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        sizerV = wx.BoxSizer(wx.VERTICAL)
        self.SetBackgroundColour("WHITE")
        st = wx.StaticText(self, -1, "Band calibration is performed at the "\
        "frequency points of immediate interest and is used only as long as "\
        "the sweep matches those points. Base calibration is performed over "\
        "a broad frequency range, to be interpolated to the current sweep "\
        "frequencies when there is no current band calibration. To create a "\
        "Base calibration you perform a Band calibration and save it as a "\
        "Base calibration. It is intended as a convenient coarse reference, "\
        "especially when phase precision is not required. In Transmission "\
        "Mode, Base calibrations are saved in a file for use in future "\
        "sessions. In Transmision Mode you also specify the time delay of "\
        "the calibration Through connection, which is ideally zero but may "\
        "be greater if you need to use an adapter.", pos=(10, 10))
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

#==============================================================================
# The Perform Calibration Update dialog box.

class PerformCalUpdDialog(wx.Dialog): # EON Jan 29, 2014
    def __init__(self, frame):
        global msa
        msa = GetMsa()
        self.frame = frame
        p = frame.prefs
        self.error = False # EON Jan 29, 2014
        if msa.calLevel != 2:
            message("Calibration Level must be Reference to Band to update.") # EON Jan 29, 2014
            self.error = True # EON Jan 29, 2014
            return
        mode = p.mode
        if mode == MSA.MODE_VNARefl:
            oslCal = msa.oslCal
            if oslCal != None:
                stdType = msa.oslCal.OSLBandRefType
            else:
                message("No OSL Calibration.") # EON Jan 29, 2014
                self.error = True # EON Jan 29, 2014
                return
        else:
            stdType = "Through connection"

        self.btnList = []
        pos = p.get("perfCalUpdWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, "Calibration Update", pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        self.sizerV = sizerV = wx.BoxSizer(wx.VERTICAL)
        c = wx.ALIGN_CENTER

        text = "To update the currently band calibration, attach the " + stdType +\
                " and click Perform Update. This will update the currently installed "\
                "reference to partially adjust for drift occurring since the full "\
                "calibration was performed."
        st = wx.StaticText(self, -1, text, pos=(10, 10))
        st.Wrap(500)
        sizerV.Add(st, 0, wx.ALL|wx.EXPAND, 5)

        if mode == MSA.MODE_VNATran:
            sizerH0 = wx.BoxSizer(wx.HORIZONTAL)
            text = "Delay of Calibration Through Connection (ns):"
            txt = wx.StaticText(self, -1, text)
            sizerH0.Add(txt, 0, wx.EXPAND|wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
            delText = "%g" % p.get("calThruDelay", 0)
            self.calThruBox = tc = wx.TextCtrl(self, -1, delText, size=(40, -1))
            self.btnList.append(tc)
            sizerH0.Add(tc, 0, wx.EXPAND|wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
            sizerV.Add(sizerH0, 0, c|wx.ALL, 10)

##        text = ("Apply update to " + # EON Jan 29, 2014
##                ("Reflection","Transmission")[mode == MSA.MODE_VNARefl] +
##                " Cal as well.")
##        self.updateBoth = chk = wx.CheckBox(self, -1, text)
##        self.btnList.append(chk)
##        sizerV.Add(chk, 0, c|wx.ALL, 10)

        sizerH1 = wx.BoxSizer(wx.HORIZONTAL)
        self.calBtn = btn = wx.Button(self, -1, "Perform " + stdType)
        btn.Bind(wx.EVT_BUTTON, self.onCal)
        sizerH1.Add(btn, 0, c|wx.ALL, 5)

        self.doneBtn = btn = wx.Button(self, -1, "Done")
        self.btnList.append(btn)
        btn.Bind(wx.EVT_BUTTON, self.onDone)
        sizerH1.Add(btn, 0, c|wx.ALL, 5)
        sizerV.Add(sizerH1, 0, c|wx.ALL, 5)

        self.SetSizer(sizerV)
        sizerV.Fit(self)

#        self.Update()
        if pos == wx.DefaultPosition:
            self.Center()
#        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def EnableButtons(self, enable):
        for btn in self.btnList:
            btn.Enable(enable)

    def CalScan(self):
        frame = self.frame
        p = frame.prefs
        spectrum = frame.spectrum
        if spectrum:
            spectrum.isSeriesFix = p.isSeriesFix
            spectrum.isShuntFix = p.isShuntFix
        msa.calibrating = True
        wait = p.wait
        p.wait = calWait # EON Jan 29, 2014
        self.calBtn
        self.doneBtn
        frame.DoExactlyOneScan()
        frame.WaitForStop()
        p.wait = wait
        msa.calibrating = False
        ##p.planeExt = savePlaneExt
        return spectrum

    def onCal(self, wxEvent):
        if msa.IsScanning():
            msa.StopScan()
        else:
            self.EnableButtons(False)
            calBtn = self.calBtn
            label = calBtn.GetLabel()
            calBtn.SetLabel("Abort Cal")
            spectrum = self.CalScan()
            oslCal = msa.oslCal
            calBtn.SetLabel(label)
            self.EnableButtons(True)
            if msa.mode == MSA.MODE_VNARefl:
                for i in range (0, oslCal._nSteps):
                    Mdb = spectrum.Mdb[i]
                    Mdeg = spectrum.Mdeg[i]
                    #(db, deg) = oslCal.bandRef[i]
                    oslCal.bandRef[i] = (Mdb, Mdeg)
            else:
                cal = msa.bandCal # EON Jan 29, 2014
                if cal != None:
                    cal.Mdb = dcopy.copy(spectrum.Mdb)
                    cal.deg = dcopy.copy(spectrum.Mdeg)

    def onDone(self, wxEvent):
        self.Destroy()

class PerformReflCalDialog(wx.Dialog):
    def __init__(self, frame, calDialog):
        self.frame = frame
        self.readSpectrum = False
        self.saveSpectrum = False
        self.calDialog = calDialog
        p = frame.prefs
        self.prefs = p
        pos = p.get("perfReflCalWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, "Reflection Calibration", pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        self.sizerH = sizerH = wx.BoxSizer(wx.HORIZONTAL)
        c = wx.ALIGN_CENTER

        self.isSeriesFix = p.get("isSeriesFix", False)
        self.isShuntFix = p.get("isShuntFix", False)
        self.isReflBridge = (not self.isSeriesFix) and (not self.isShuntFix)
        self.isRefCal = p.get("isRefCal", True)
        self.isOslCal = not self.isRefCal
        self.oslCal = None
        self.btnList = []
        p.get("openSpec", "RLC[S,C0,D0]")
        p.get("shortSpec", "RLC[P,R0,L0,D0]")
        p.get("loadSpec", "RLC[P,R50,C0]")

        self.sizerV1 = sizerV = wx.BoxSizer(wx.VERTICAL)
        txt = "Specify the fixture used. For a\n"\
              "Shunt fixture, you may specify a\n"\
              "a delay time."
        self.textBox1 = wx.StaticText(self, -1, txt)
        sizerV.Add(self.textBox1, 0, wx.TOP|wx.LEFT|wx.RIGHT, 10)

        btn = wx.Button(self, -1, "Help")
        self.btnList.append(btn)
        btn.Bind(wx.EVT_BUTTON, self.onReflFixHelp)
        sizerV.Add(btn, 0, c|wx.ALL, 5)

        sizerH0 = wx.BoxSizer(wx.HORIZONTAL)
        txt = wx.StaticText(self, -1, "Fixture R0 (ohms)")
        sizerH0.Add(txt, 0, wx.EXPAND|wx.ALL|wx.ALIGN_CENTER_VERTICAL, 10)
        self.fixtureR0Box = tc = wx.TextCtrl(self, -1, str(p.fixtureR0), size=(40, -1))
        sizerH0.Add(tc, 0, wx.EXPAND|wx.ALL|wx.ALIGN_CENTER_VERTICAL, 10)
        sizerV.Add(sizerH0, 0, c|wx.ALL, 5)

        fixTypeTitle = wx.StaticBox(self, -1, "Fixture Type")
        self.fixTypeSizer = wx.StaticBoxSizer(fixTypeTitle, wx.VERTICAL)
        fixTypeBoxSizer = wx.BoxSizer(wx.VERTICAL)

        self.bridgeRb = rb = wx.RadioButton(self, -1, "Reflection Bridge", style=wx.RB_SINGLE)
        self.btnList.append(rb)
        rb.Bind(wx.EVT_RADIOBUTTON, self.BridgeUpd)
        fixTypeBoxSizer.Add(rb, 0, wx.ALL, 2)

        self.seriesRb = rb = wx.RadioButton(self, -1, "Series", style=wx.RB_SINGLE)
        self.btnList.append(rb)
        rb.Bind(wx.EVT_RADIOBUTTON, self.SeriesUpd)
        fixTypeBoxSizer.Add(rb, 0, wx.ALL, 2)

        self.shuntRb = rb = wx.RadioButton(self, -1, "Shunt", style=wx.RB_SINGLE)
        self.btnList.append(rb)
        rb.Bind(wx.EVT_RADIOBUTTON, self.ShuntUpd)
        fixTypeBoxSizer.Add(rb, 0, wx.ALL, 2)

        self.conDelayText = txt = wx.StaticText(self, -1, "Connect Delay (ns)")
        fixTypeBoxSizer.Add(txt, 0, c|wx.ALL, 2)
        self.conDelay = tc = wx.TextCtrl(self, -1, p.get("shuntConDelay", "0"), size=(60, -1))
        fixTypeBoxSizer.Add(tc, 0, c|wx.ALL, 2)

        self.fixTypeSizer.Add(fixTypeBoxSizer, 0, c|wx.ALL, 5)
        sizerV.Add(self.fixTypeSizer, 0, c|wx.ALL, 5)

        sizerH1 = wx.BoxSizer(wx.HORIZONTAL)

        self.doneBtn = btn = wx.Button(self, -1, "Done")
        self.btnList.append(btn)
        btn.Bind(wx.EVT_BUTTON, self.onDone)
        sizerH1.Add(btn, 0, c|wx.ALL, 5)

        self.cancelBtn = btn = wx.Button(self, -1, "Cancel")
        self.btnList.append(btn)
        btn.Bind(wx.EVT_BUTTON, self.OnClose)
        sizerH1.Add(btn, 0, c|wx.ALL, 5)

        sizerV.Add(sizerH1, 0, c|wx.ALL, 5)

        sizerH.Add(sizerV, 0, wx.EXPAND|wx.ALL, 10)

        self.sizerV2 = sizerV = wx.BoxSizer(wx.VERTICAL)
        txt = "Specify the desired calibration.\n"\
              "For OSL, specify characteristics\n"\
               "of the standards."
        self.textBox2 = wx.StaticText(self, -1, txt)
        sizerV.Add(self.textBox2, 0, wx.TOP|wx.LEFT|wx.RIGHT, 10)
        btn = wx.Button(self, -1, "Help")
        self.btnList.append(btn)
        btn.Bind(wx.EVT_BUTTON, self.onReflCalHelp)
        sizerV.Add(btn, 0, c|wx.ALL, 5)

        sizerV.AddSpacer(10)
        self.OslCalRb = rb = wx.RadioButton(self, -1, "Full OSL")
        self.btnList.append(rb)
        rb.Bind(wx.EVT_RADIOBUTTON, self.OslUpd)
        sizerV.Add(rb, 0, wx.ALL, 2)

        self.RefCalRb = rb = wx.RadioButton(self, -1, "Reference Cal")
        self.btnList.append(rb)
        rb.Bind(wx.EVT_RADIOBUTTON, self.RefUpd)
        sizerV.Add(rb, 0, wx.ALL, 2)
        sizerV.AddSpacer(10)

        c = wx.ALIGN_CENTER_VERTICAL
        sizerGb = wx.GridBagSizer(20, 10)
        doneSize = (30,-1)
        self.openDone = txt = wx.StaticText(self, -1, "", size=doneSize)
        sizerGb.Add(txt, (0, 0), flag=c)
        self.openBtn = btn = wx.Button(self, -1, "Perform Open")
        self.btnList.append(btn)
        btn.Bind(wx.EVT_BUTTON, self.OnOpen)
        sizerGb.Add(btn, (0, 1))
        self.openSpecTxt = txt = wx.TextCtrl(self, -1, "")
        txt.SetEditable(True)
        txt.Enable()
        txt.SetBackgroundColour(wx.WHITE)
        sizerGb.Add(txt, (0, 2))

        self.shortDone = txt = wx.StaticText(self, -1, "", size=doneSize)
        sizerGb.Add(txt, (1, 0), flag=c)
        self.shortBtn = btn = wx.Button(self, -1, "Perform Short")
        self.btnList.append(btn)
        btn.Bind(wx.EVT_BUTTON, self.OnShort)
        sizerGb.Add(btn, (1, 1))
        self.shortSpecTxt = txt = wx.TextCtrl(self, -1, "")
        txt.SetEditable(False)
        txt.Disable()
        txt.SetBackgroundColour(wx.WHITE)
        sizerGb.Add(txt, (1, 2))

        self.loadDone = txt = wx.StaticText(self, -1, "", size=doneSize)
        sizerGb.Add(txt, (2, 0), flag=c)
        self.loadBtn = btn = wx.Button(self, -1, "Perform Load")
        self.btnList.append(btn)
        btn.Bind(wx.EVT_BUTTON, self.OnLoad)
        sizerGb.Add(btn, (2, 1))
        self.loadSpecTxt = txt = wx.TextCtrl(self, -1, "")
        txt.SetEditable(True)
        txt.Disable()
        txt.SetBackgroundColour(wx.WHITE)
        sizerGb.Add(txt, (2, 2))
        sizerV.Add(sizerGb, 0, wx.ALL, 2)

        st = wx.StaticText(self, -1, "Calibrations Standards")
        sizerV.Add(st, 0, wx.ALL|wx.ALIGN_CENTER, 5)
        self.sizerV1 = sizerV

        loads = ['Ideal 50 ohms','Custom']
        self.loadBox = cb = wx.ComboBox(self, -1, choices=loads, style=wx.CB_READONLY)
        cb.Bind(wx.EVT_COMBOBOX, self.OnLoadBox)
        calStd = p.get("calStandard", 0)
        cb.SetSelection(calStd)
        if calStd != 0:
            self.openSpecTxt.SetValue(p.get("openSpec", ""))
            self.shortSpecTxt.SetValue(p.get("shortSpec", ""))
            self.loadSpecTxt.SetValue(p.get("loadSpec", ""))
        cb.SetBackgroundColour(wx.WHITE)
        sizerV.Add(cb, 0, wx.ALL|wx.ALIGN_CENTER, 5)

        txt = "50 ohms, good for cal plane\n"\
              "on back of SMA connectors."
        st = wx.StaticText(self, -1, txt)
        sizerV.Add(st, 0, wx.ALL|wx.ALIGN_CENTER, 5)

        sizerH.Add(sizerV, 0, wx.EXPAND|wx.ALL, 10)

        self.SetSizer(sizerH)
        self.Update()
        if pos == wx.DefaultPosition:
            self.Center()
        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def OnLoadBox(self,event):
        self.Update()

    def BridgeUpd(self, event):
        if self.bridgeRb.GetValue():
            self.isReflBridge = True
            self.isSeriesFix = False
            self.isShuntFix = False
        self.Update()

    def SeriesUpd(self, event):
        if self.seriesRb.GetValue():
            self.isSeriesFix = True
            self.isShuntFix = False
            self.isReflBridge = False
        self.Update()

    def ShuntUpd(self, event):
        if self.shuntRb.GetValue():
            self.isShuntFix = True
            self.isReflBridge = False
            self.isSeriesFix = False
        self.Update()

    def OslUpd(self, event):
        if self.OslCalRb.GetValue():
            self.isOslCal = True
            self.isRefCal = False
        self.Update()

    def RefUpd(self, event):
        if self.RefCalRb.GetValue():
            self.isRefCal = True
            self.isOslCal = False
        self.Update()

    def OslCal(self, spectrum):
        oslCal = self.oslCal
        isLogF = self.frame.prefs.isLogF
        msa = self.frame.msa
        upd = False
        if oslCal == None:
            oslCal = OslCal(self.frame.specP.title, msa.indexRBWSel + 1, isLogF,
                            msa._fStart, msa._fStop, msa._nSteps, msa._freqs)
            upd = True
        else:
            if oslCal.Changed(isLogF, msa._fStart, msa._fStop, msa._nSteps):
                oslCal = OslCal(self.frame.specP.title, msa.indexRBWSel + 1, isLogF,
                                msa._fStart, msa._fStop, msa._nSteps, msa._freqs)
                upd = True
        if upd:
            self.oslCal = oslCal
            msa.oslCal = oslCal
        return oslCal

    def CalScan(self):
        frame = self.frame
        p = self.prefs
        spectrum = frame.spectrum
        if spectrum:
            spectrum.isSeriesFix = p.isSeriesFix
            spectrum.isShuntFix = p.isShuntFix
        msa = frame.msa
        msa.calibrating = True
        wait = p.wait
        p.wait = calWait # EON Jan 29, 2014
        frame.DoExactlyOneScan()
        frame.WaitForStop()
        p.wait = wait
        msa.calibrating = False
        ##p.planeExt = savePlaneExt
        return frame.spectrum

    def ReadSpectrum(self, fileName):
        frame = self.frame
        p = self.prefs
        frame.spectrum = spectrum = Spectrum.FromS1PFile(fileName + ".s1p")
        specP = frame.specP
        specP.h0 = p.fStart = spectrum.Fmhz[0]
        specP.h1 = p.fStop  = spectrum.Fmhz[-1]
        p.nSteps = spectrum.nSteps
        frame.RefreshAllParms()
        frame.DrawTraces()
        f = open(fileName + ".txt", "r")
        f.readline()
        f.readline()
        for line in f:
            line = line.strip()
            (i, Fmhz, Sdb, magdata, tmp, Sdeg, phasedata) = re.split(" +", line)
            i = int(i)
            spectrum.magdata[i] = int(magdata)
            spectrum.phasedata[i] = int(phasedata)
#            spectrum.Fmhz[i] = float(Fmhz)
#            spectrum.Mdb[i] = float(Mdb)
#            spectrum.Mdeg[i] = float(Mdeg)
        f.close()
        return spectrum

    def OnOpen(self, event):
        msa = self.frame.msa
        if msa.IsScanning():
            msa.StopScan()
        else:
            self.EnableButtons(False)
            self.openBtn.SetLabel("Abort Cal")
            self.openBtn.Enable(True)
            if self.readSpectrum:
                spectrum = self.ReadSpectrum('open')
            else:
                spectrum = self.CalScan()
            oslCal = self.OslCal(spectrum)
            if self.saveSpectrum:
                spectrum.WriteInput("open.txt",self.prefs)
                spectrum.WriteS1P("open.s1p",self.prefs)
            for i in range (0, spectrum.nSteps + 1):
                oslCal.OSLcalOpen[i] = (spectrum.Sdb[i], spectrum.Sdeg[i])
            oslCal.OSLdoneO = True
            self.openBtn.SetLabel("Perform Open")
            self.openDone.SetLabel("Done");
            self.EnableButtons(True)
            self.Update()
            if self.isRefCal:
                self.onDone(event)

    def OnShort(self, event):
        msa = self.frame.msa
        if msa.IsScanning():
            msa.StopScan()
        else:
            self.EnableButtons(False)
            self.shortBtn.SetLabel("Abort Cal")
            self.shortBtn.Enable(True)
            msa.calibrating = True
            if self.readSpectrum:
                spectrum = self.ReadSpectrum('short')
            else:
                spectrum = self.CalScan()
            oslCal = self.OslCal(spectrum)
            if self.saveSpectrum:
                spectrum.WriteInput("short.txt",self.prefs)
                spectrum.WriteS1P("short.s1p",self.prefs)
            for i in range (0, spectrum.nSteps + 1):
                oslCal.OSLcalShort[i] = (spectrum.Mdb[i], spectrum.Mdeg[i])
            oslCal.OSLdoneS = True
            self.shortBtn.SetLabel("Perform Short")
            self.shortDone.SetLabel("Done");
            self.EnableButtons(True)
            self.Update()
            if self.isRefCal:
                self.onDone(event)

    def OnLoad(self, event):
        msa = self.frame.msa
        if msa.IsScanning():
            msa.StopScan()
        else:
            self.EnableButtons(False)
            self.loadBtn.SetLabel("Abort Cal")
            self.loadBtn.Enable(True)
            if self.readSpectrum:
                spectrum = self.ReadSpectrum('load')
            else:
                spectrum = self.CalScan()
            oslCal = self.OslCal(spectrum)
            if self.saveSpectrum:
                spectrum.WriteInput("load.txt",self.prefs)
                spectrum.WriteS1P("load.s1p",self.prefs)
            for i in range (0, spectrum.nSteps + 1):
                oslCal.OSLcalLoad[i] = (spectrum.Mdb[i], spectrum.Mdeg[i])
            oslCal.OSLdoneL = True
            self.loadBtn.SetLabel("Perform Load")
            self.loadDone.SetLabel("Done");
            self.EnableButtons(True)
            self.Update()

    def onDone(self, event):
        # User has performed the desired calibrations.  The caller must now
        # calculate/set up the calibration data.  But either the Open or
        # Short must have been performed.  We know what was done based on
        # OSLdoneO, OSLdoneS and OSdoneL
        # Retrieve test fixture info

#     #OSLcal.Full, "value? OSLFullval$"  'ver116-4k
        OSLFull = self.OslCalRb.GetValue()
# if doing full OSL, we treat all fixtures as bridges
#     if OSLFullval$="set" then #OSLcal.Bridge, "set" : #OSLcal.Series, "reset" : #OSLcal.Shunt, "reset"

        oslCal = self.oslCal
        if oslCal == None:
            message ("No Calibration Done") # EON Jan 29, 2014
            return

        if OSLFull:
            self.bridgeRb.SetValue(True)
            self.seriesRb.SetValue(False)
            self.shuntRb.SetValue(False)

#     #OSLcal.Bridge, "value? bridgeVal$"
#     isBridge=0
#     isSeries=0
#     if bridgeVal$="set" then
#         isBridge=1
#         S11JigType$="Reflect"   'bridge
#     else    'must be series or shunt
#         #OSLcal.Series, "value? attachVal$"
#         if attachVal$="set" then
#             S21JigAttach$="Series"
#             isSeries=1
#         else
#             S21JigAttach$="Shunt"
#             #OSLcal.ShuntDelay, "!contents? delayVal$"  'connector delay (ns)
#             S21JigShuntDelay=val(uCompact$(delayVal$))
#         end if
#         S11JigType$="Trans"
#     end if

        isBridge = False
        isSeries = False
        if self.bridgeRb.GetValue():
            isBridge = True
            oslCal.S11JigType = "Reflect"
        else:
            if self.seriesRb.GetValue():
                isSeries = True
                oslCal.S21JigAttach = "Series"
            else:
                oslCal.S21JigAttach = "Shunt"
                oslCal.ShuntDelay = self.conDelay.GetValue()
            oslCal.S11JigType = "Trans"

#     #OSLcal.R0, "!contents? R0$"
#     S11BridgeR0=uValWithMult(R0$) : if S11BridgeR0<=0 then S11BridgeR0=50 : notice "Invalid R0. 50 ohms used."
#         'We now set both S11BridgeR0 and S21JigR0 to the same value. When doing full OSL, the user does not choose the
#         'fixture type so we wouldn't know which one to set if we didn't set both. Certain routines refer to one or the other,
#         'depending on fixture type, but they will get the same value either way. ver116-4j
#     S21JigR0=S11BridgeR0

        S11BridgeR0 = self.frame.msa.fixtureR0
        if S11BridgeR0 <= 0:
            S11BridgeR0 = 50
            message("Invalid R0. 50 ohms used") # EON Jan 29, 2014
        oslCal.S11BridgeR0 = S11BridgeR0
        oslCal.S21JigR0 = S11BridgeR0

#
#     'Note S11GraphR0 is set in the sweep parameters window
#     OSLcalSum=OSLdoneO+OSLdoneL+OSLdoneS

        calSum = 0
        self.OSLError = False
        if oslCal.OSLdoneO:
            calSum += 1
        if oslCal.OSLdoneS:
            calSum += 1
        if oslCal.OSLdoneL:
            calSum += 1
#
#     'If full OSL, we require all 3 cals to be done. If reference, we quit as soon as one is done. This means
#     'we never leave with 2 cals done.
#     if OSLFullval$="set" then   'set means full OSL. Note if not full we quit as soon as one is done.
#         if OSLcalSum<>3 then notice "You are missing one of the necessary calibrations for full OSL." : wait
#     else
#         if isBridge then    'Be sure reference cal was done
#             didRef=(OSLdoneO or OSLdoneS)
#         else
#             if isSeries then didRef=OSLdoneS else didRef=OSLdoneO
#         end if
#         if didRef=0 then notice "You have not performed the necessary calibration" : wait
#     end if

        didRef = False
        if self.OslCalRb.GetValue():
            if calSum != 3:
                message("For full OSL all references must be scanned.") # EON Jan 29, 2014
                return # EON Jan 29, 2014
        else:
            if isBridge:
                didRef = oslCal.OSLdoneO or oslCal.OSLdoneS
            else:
                if isSeries:
                    didRef = oslCal.OSLdoneS
                else:
                    didRef = oslCal.OSLdoneO
                if not didRef:
                    message("You have not performed the necessary calibration.") # EON Jan 29, 2014
                    return # EON Jan 29, 2014

#         'ver115-3f moved the disables to here, after a possible wait occurs
#     call SetOSLCalCheckboxStatus "disable"    'So nothing gets clicked before dialog closes ver115-3a
#     call SetOSLCalButtonStatus "!disable"
#
#     #OSLcal.stdSet, "selectionindex? OSLLastSelectedCalSet"
#     #OSLcal.OpenSpecs, "!contents? OSLOpenSpec$"
#     #OSLcal.ShortSpecs, "!contents? OSLShortSpec$"
#     #OSLcal.LoadSpecs, "!contents? OSLLoadSpec$"

        oslCal.OslOpenSpec = self.openSpecTxt.GetValue()
        oslCal.OslShortSpec = self.shortSpecTxt.GetValue()
        oslCal.OslLoadSpec = self.loadSpecTxt.GetValue()

#
#     if OSLError then OSLBandNumSteps=-1 'Invalid cal data if math error occurred 'ver116-4b
#     call SignalNoCalInstalled   'ver116-4b 'So new cal will get installed on Restart
#     desiredCalLevel=2   'desire Band Sweep since we just did it
#     call RequireRestart 'So cal gets installed before user proceeds, but we don't install it here
#          'In earlier versions this line was put here.
#         'because we sometimes returned to a strange place. Doesn't seem to happen now.
#     cursor hourglass    'ver116-4b
#     gosub [ProcessOSLBandCal]   'ver115-1g

# [ProcessOSLBandCal]   'Process already gathered band cal data
#     call ProcessOSLCal
#     desiredCalLevel=2   'opt for using band cal since we just did it

        oslCal.ProcessOSLCal()

#     if OSLError then BandSweepCalDone=0 : OSLBandNumSteps=-1 : return    'If error, nullify the cal and return
#                 'Save the conditions under which the cal was done
#     OSLBandStartFreq=startfreq
#     OSLBandEndFreq=endfreq
#     OSLBandNumSteps=steps
#     OSLBandLinear=gGetXIsLinear()
#     OSLBandPath$=path$
#     OSLBandS11JigType$=S11JigType$
#     OSLBandS21JigAttach$=S21JigAttach$
#     OSLBandS11BridgeR0=S11BridgeR0
#     OSLBandS21JigR0=S21JigR0
#     OSLBandTimeStamp$=date$("mm/dd/yy"); "; ";time$()
#     BandSweepCalDone=1
#     return

#     cursor normal   'ver116-4b
#     close #OSLcal
#     'ver115-5b moved update of band cal display to the routines for the basic cal window
#     return 'we will be back in the basic cal window, or whoever called us

        frame = self.frame
        frame.SetBandCal(self.oslCal)
        frame.SetCalLevel(2)
        self.calDialog.Update()
        frame.RefreshAllParms()
        self.Destroy()

    def EnableButtons(self, enable):
        for btn in self.btnList:
            btn.Enable(enable)

    #--------------------------------------------------------------------------
    # Close or Cancel - quit any running calibration.

    def OnClose(self, event):
        msa = self.frame.msa
        if msa.IsScanning():
            msa.StopScan()
            event.Skip()
        self.Destroy()

    #--------------------------------------------------------------------------
    # Update button enables after a change.

    def Update(self):
        frame = self.frame
        p = self.prefs
        p.isSeriesFix = self.isSeriesFix
        p.isShuntFix = self.isShuntFix
        p.isRefCal = self.isRefCal
        frame.msa.fixtureR0 = p.fixtureR0 = float(self.fixtureR0Box.GetValue())
        p.shuntConDelay = self.conDelay.GetValue()

        spectrum = frame.spectrum
        if spectrum:
            spectrum.isSeriesFix = self.isSeriesFix
            spectrum.isShuntFix = self.isShuntFix

        self.bridgeRb.SetValue(self.isReflBridge)
        self.seriesRb.SetValue(self.isSeriesFix)
        self.shuntRb.SetValue(self.isShuntFix)

        self.RefCalRb.SetValue(self.isRefCal)
        self.OslCalRb.SetValue(self.isOslCal)

        self.fixTypeSizer.ShowItems(self.isRefCal)

        self.conDelayText.Show(self.isShuntFix)
        self.conDelay.Show(self.isShuntFix)

        show = self.isOslCal or (self.isRefCal and (self.isReflBridge or self.isShuntFix))
        self.openBtn.Show(show)
        self.openSpecTxt.Show(show)

        show = self.isOslCal or (self.isRefCal and (self.isReflBridge or self.isSeriesFix))
        self.shortBtn.Show(show)
        self.shortSpecTxt.Show(show)

        self.loadBtn.Show(self.isOslCal)
        self.loadSpecTxt.Show(self.isOslCal)

        calStd = self.loadBox.GetCurrentSelection()
        p.calStandard = calStd
        if calStd == 0:
            self.openSpecTxt.Disable()
            self.shortSpecTxt.Disable()
            self.loadSpecTxt.Disable()
            self.openSpecTxt.SetValue("RLC[S,C0,D0]")
            self.shortSpecTxt.SetValue("RLC[P,R0,L0,D0]")
            self.loadSpecTxt.SetValue("RLC[P,R50,C0]")
        else:
            self.openSpecTxt.Enable()
            self.shortSpecTxt.Enable()
            self.loadSpecTxt.Enable()
            p.openSpec = self.openSpecTxt.GetValue()
            p.shortSpec = self.shortSpecTxt.GetValue()
            p.loadSpec = self.loadSpecTxt.GetValue()

        frame.RefreshAllParms()
        self.sizerV1.Fit(self)
        self.sizerH.Fit(self)

    def onReflFixHelp(self, event):
        dlg = ReflFixHelpDialog(self.frame)
        if dlg.ShowModal() == wx.ID_OK:
            self.p.ReflFixHelpWinPos = dlg.GetPosition().Get()

    def onReflCalHelp(self, event):
        dlg = ReflCalHelpDialog(self.frame)
        if dlg.ShowModal() == wx.ID_OK:
            self.p.ReflCalHelpWinPos = dlg.GetPosition().Get()

#==============================================================================
# Help dialog for Reflection Fixtures.

class ReflFixHelpDialog(wx.Dialog):
    def __init__(self, frame):
        p = frame.prefs
        pos = p.get("ReflFixHelpWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, "Reflection Fixture Help", pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        sizerV = wx.BoxSizer(wx.VERTICAL)
        self.SetBackgroundColour("WHITE")
        txt = "Reflection measurements use one of several types of test fixtures "\
              "to which the device under test (DUT) is attached. Many fixtures "\
              "are Reflection Bridges, which make an attempt to make their "\
              "output signal correspond closely to the actual reflection from "\
              "the DUT. Such fixtures can use Reference Calibration with either "\
              "the Open or Short, or for better accuracy can use full OSL "\
              "calibration.\n\n"\
              "Other fixtures produce an output which does not directly "\
              "correspond to the DUT reflection, but can be mathematically "\
              "transformed into a reflection measurement. These test fixtures "\
              "typically consist of an attenuator, then the component, then "\
              "another attenuator. The component may be connected in Series "\
              "between the attenuators, or may be Shunt to ground, which "\
              "accounts for the two different fixture types. The component will "\
              "see a certain resistance R0 looking at the incoming signal and "\
              "the outgoing signal. You must specify that R0, usually 50 "\
              "ohms. The Series fixture is calibrated with just the Short or "\
              "with full OSL. The Shunt fixture is calibrated with just the Open "\
              "or with full OSL.\n\n"\
              "If you specify the Shunt Fixture, then you may also specify the "\
              "one-way connection delay time, which is used for compensation "\
              "when you do not use full OSL. A delay of 0.115 ns is typical. "\
              "For low frequencies a delay of 0 ns may be adequate."
        st = wx.StaticText(self, -1, txt, pos=(10, 10))
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

#==============================================================================
# Help dialog for Reflection Calibration.

class ReflCalHelpDialog(wx.Dialog):
    def __init__(self, frame):
        p = frame.prefs
        pos = p.get("ReflCalHelpWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, "Reflection Calibration Help", pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        sizerV = wx.BoxSizer(wx.VERTICAL)
        self.SetBackgroundColour("WHITE")
        txt = "All measurements in Reflection mode require some form of "\
              "calibration. The simplest calibration is Reference Calibration, which "\
              "uses either an Open or a Short calibration standard, which essentially "\
              "allows the MSA to adjust to set a reference signal level. This works "\
              "well for precise fixtures at relatively low frequencies. OSL "\
              "Calibration involves more steps but is more accurate. OSL involves "\
              "sequentially measuring Open, Short and Load calibration standards, in "\
              "any order.  For OSL Calibration, you generally specify the electrical "\
              "characteristics of each of the standards.  At low frequencies it may "\
              "work well just to treat them as Ideal."
        st = wx.StaticText(self, -1, txt, pos=(10, 10))
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

class OslCal:
    def __init__(self, when, pathNo, isLogF, fStart, fStop, nSteps, Fmhz):
        self.desc = "%s, Path %d, %d %s steps, %g to %g MHz." % \
            (when, pathNo, nSteps, ("linear", "log")[isLogF], fStart, fStop)
        self.oslDbg = False
        self.when = when
        self.path = pathNo
        self.oslCal = True
        self.isLogF = isLogF
        self._fStart = fStart
        self._fStop = fStop
        self.nSteps = nSteps
        self._nSteps = self.nSteps + 1
        n = self._nSteps
        self.Fmhz = dcopy.copy(Fmhz)
        self.OSLcalOpen = [None] * n
        self.OSLcalShort = [None] * n
        self.OSLcalLoad = [None] * n
        self.OSLstdOpen = zeros(n, dtype=complex)
        self.OSLstdShort = zeros(n, dtype=complex)
        self.OSLstdLoad = zeros(n, dtype=complex)
        self.comboResp = [None] * n
        self.OSLdoneO = False
        self.OSLdoneS = False
        self.OSLdoneL = False
        self.OSLError = False
        self.OSLShortSpec = ""
        self.OSLOpenSpec = ""
        self.OSLLoadSpec = ""
        self.S11JigType = ""
        self.S11BridgeR0 = 0
        self.S11FixR0 = 0
        self.S21JigAttach = ""
        self.S21JigShuntDelay = 0
        self.OSLBandRefType = ""
        self.OSLBandRef = [None] * n
        self.OSLBandA = zeros(n, dtype=complex)
        self.OSLBandB = zeros(n, dtype=complex)
        self.OSLBandC = zeros(n, dtype=complex)
        self.bandFmhz = []
        self.bandRef = []
        self.bandA = []
        self.bandB = []
        self.bandC = []

    # OSLCal[i] returns the tuple (Sdb, Sdeg) for step i

    def __getitem__(self, i):
        return self.bandRef[i]

    def Changed(self, isLogF, fStart, fStop, nSteps):
        if round(self._fStart - fStart, 8) != 0 or round(self._fStop - fStop, 8) != 0:
            return True
        if self.nSteps != nSteps:
            return True
        if self.isLogF != isLogF:
            return True
        return False

    def installBandCal(self):
        self.bandFmhz = self.Fmhz
        self.bandRef = self.OSLBandRef
        self.bandA = self.OSLBandA
        self.bandB = self.OSLBandB
        self.bandC = self.OSLBandC

    def interpolateCal(self, fMhz):
        nSteps = len(fMhz)
        self.bandRef = [(None, None)] * nSteps
        self.bandA = zeros(nSteps, dtype=complex)
        self.bandB = zeros(nSteps, dtype=complex)
        self.bandC = zeros(nSteps, dtype=complex)

        db = zeros(self._nSteps)
        deg = zeros(self._nSteps)
        for i in range(self._nSteps):
            (db[i], deg[i]) = self.OSLBandRef[i]

        i = 0
        for freq in fMhz:
            self.bandRef[i] = (interp(freq, self.Fmhz, db),
                               interp(freq, self.Fmhz, deg))
            i += 1

        dst = zeros(nSteps)
        src = self.OSLBandA.real
        i = 0
        for freq in fMhz:
            dst[i] = interp(freq, self.Fmhz, src)
            i += 1
        self.bandA.real = dcopy.copy(dst)
        src = self.OSLBandA.imag
        i = 0
        for freq in fMhz:
            dst[i] = interp(freq, self.Fmhz, src)
            i += 1
        self.bandA.imag = dcopy.copy(dst)

        src = self.OSLBandB.real
        i = 0
        for freq in fMhz:
            dst[i] = interp(freq, self.Fmhz, src)
            i += 1
        self.bandB.real = dcopy.copy(dst)
        src = self.OSLBandB.imag
        i = 0
        for freq in fMhz:
            dst[i] = interp(freq, self.Fmhz, src)
            i += 1
        self.bandB.imag = dcopy.copy(dst)

        src = self.OSLBandC.real
        i = 0
        for freq in fMhz:
            dst[i] = interp(freq, self.Fmhz, src)
            i += 1
        self.bandC.real = dcopy.copy(dst)
        src = self.OSLBandC.imag
        i = 0
        for freq in fMhz:
            dst[i] = interp(freq, self.Fmhz, src)
            i += 1
        self.bandC.imag = dcopy.copy(dst)

    def WriteS1P(self, fileName, p, contPhase=False):
        f = open(fileName, "w") # EON Jan 29, 2014
        f.write("!MSA, msapy %s\n" % GetVersion)
        f.write("!Date: %s\n" % time.ctime())
        f.write("!%s Sweep Path %d S11Jig=%s; S11BridgeR0=%d; S21Jig=%s; S21JigR0=%s\n" % \
                (("Linear", "Log")[p.isLogF], p.indexRBWSel+1, self.S11JigType, self.S11BridgeR0, "", ""))
        f.write("!  MHz         A_real          A_imag          B_real          B_imag          C_Real          C_Imag         RefDB     RefDeg\n")
        for freq, bandA, bandB, bandC, bandRef in zip(self.Fmhz, self.OSLBandA, self.OSLBandB, self.OSLBandC, self.OSLBandRef):
            f.write("%11.6f %15.8e %15.8e %15.8e %15.8e %15.8e %15.8e %10.5f %7.2f\n" % \
                    (freq, bandA.real, bandA.imag, bandB.real, bandB.imag, bandC.real, bandC.imag, bandRef[0], bandRef[1]))
        f.close()

    #--------------------------------------------------------------------------
    # Read OSL Calbration from file.

    @classmethod
    def FromS1PFile(cls, fileName):
        a = []
        b = []
        c = []
        Fmhz = []
        bandRef = []
        when = "**UNKNOWN DATE**"
        pathNo = 1
        isLogF = False
        S11Jig = "Bridge"
        S11BridgeR0 = 50
        f = open(fileName, "r")

        i = 0
        for line in f.readlines():
            line = line.strip()
            if len(line) > 1:
                if line[0] != "!":
                    val = re.split(" +",line)
                    if len(val) == 9:
                        Fmhz.append(float(val[0]))
                        a.append(complex(float(val[1]), float(val[2])))
                        b.append(complex(float(val[3]), float(val[4])))
                        c.append(complex(float(val[5]), float(val[6])))
                        bandRef.append((float(val[7]), float(val[8])))
                        i += 1
                    else:
                        pass
                else:
                    m = re.match("!Date: (.+)", line)
                    if m != None:
                        when = m.group(1)
                    else:
                        m = re.match("!(.+?) *Sweep *Path *(.+?) *S11Jig=(.*?);* *S11BridgeR0=(.*?);* *S21Jig=(.*?);* *S21JigR0=(.*?)", line)
                        if m != None:
                            isLogF = m.group(1) == "Log"
                            pathNo = int(m.group(2))
                            S11Jig = m.group(3)
                            S11BridgeR0 = m.group(4)
        f.close()

        n = len(Fmhz)
        if n == 0:
            raise ValueError("S1P file: no data found")

##        print ("Read %d steps." % (n-1), "Start=", Fmhz[0], "Stop=", Fmhz[-1]) # EON Jan 29, 2014
        this = cls(when, pathNo, isLogF, Fmhz[0], Fmhz[-1], n - 1, array(Fmhz))
        this.OSLBandA = array(a)
        this.OSLBandB = array(b) # EON Jan 29, 2014
        this.OSLBandC = array(c) # EON Jan 29, 2014
        this.OSLBandRef = bandRef
        this.S11JigType = S11Jig
        this.S11BridgeR0 = S11BridgeR0
        return this

# sub ConvertRawDataToReflection currStep

# For the current step in reflection mode, calculate S11, referenced to S11GraphR0

    def ConvertRawDataToReflection(self, i, Sdb, Sdeg):

# Calculate reflection in db, angle format and puts results in
# ReflectArray, which already contains the raw data.  Also calculates
# the various items in ReflectArray() from the final reflection value.
# We need to adjust the data for calibration
#
#       Reference calibration
#
# The simplest reflection calibration is to use the Open or Short as a
# reference. In that case, we still calculate OSL coefficients as though
# we did full OSL, using Ideal results for the missing data.
#
#     Full OSL
#
# More extensive calibration would include the Open, Short and Load,
# from which we calculated the a, b, c OSL coefficients during
# calibration. If we have full OSL coefficients, we apply them here.  We
# identify the type of jig used with S11JigType$, which the user sets
# during calibration.  S11JigType$ is always set to "Reflect" when doing
# full OSL, since we don't even know the nature of the actual jig.  In
# addition, S21JigR0 is set to S11BridgeR0.
#
# Note that S21 or S11 are now referenced to the S21JigR0 or
# S11BridgeR0, not the graph R0. We do the conversion here. But we also
# save S11 as an intermediate value before applying the R0 coversion or
# plane extension (but after applying cal) to make recalculations
# easier. It is saved with constIntermedS11DB and constIntermedS11Ang.
#
# First get the raw reflection data. This is the measured data, adjusted
# by subtracting the reference.  planeadj has not been applied; it is
# applied after applying calibration S21JigShuntDelay has not yet been
# applied. It will be applied here via the OSL coefficients.

#
#     trueFreq=ReflectArray(currStep,0)*1000000
#     db=ReflectArray(currStep,constGraphS11DB) : ang=ReflectArray(currStep,constGraphS11Ang)
#     if calInProgress then   'If calibrating we don't adjust anything here, or calculate anything other than S11
#         ReflectArray(currStep, constIntermedS11DB)=db  'ver115-2d
#         ReflectArray(currStep, constIntermedS11Ang)=ang  'ver115-2d
#         exit sub
#     end if
#
#     rho=uTenPower(db/20)    'mag made linear

# db, rho, and ang (degrees) now have the raw reflection data If
# necessary, we apply full OSL to the reflection data, whether it was
# derived from a reflection bridge or a transmission jig.  If doing OSL
# cal, then we don't want to apply whatever coefficients we happen to
# have now.  If doSpecialGraph<>0 we don't want to mess with the
# internally generated data

#     if doSpecialGraph=0 and applyCalLevel<>0 then   'ver115-5f
#         rads=ang*uRadsPerDegree()   'angle in radians
#         mR=rho*cos(rads) : mI=rho*sin(rads)     'measured S11, real and imaginary
#         aR=OSLa(currStep,0) : aI=OSLa(currStep,1)   'coefficient a, real and imaginary
#         bR=OSLb(currStep,0) : bI=OSLb(currStep,1)   'coefficient b, real and imaginary
#         cR=OSLc(currStep,0) : cI=OSLc(currStep,1)   'coefficient c, real and imaginary

        if True:
            M = cmath.rect(10 ** (Sdb / 20), Sdeg * RadsPerDegree)
            a = self.bandA[i]
            b = self.bandB[i]
            c = self.bandC[i]

#
#         'calculate adjusted db, ang via OSL. Note OSL must be referenced to S11BridgeR0
#         calcMethod=1    'For debugging, we have two different methods
#         if calcMethod=1 then
#                 'The first method uses  the following formula, and corresponds to CalcOSLCoeff
#                 '       S = (M - b) / (a - c*M)
#                 'where S is the actual reflection coefficient and M is the measured reflection coefficient.
#                 'S and M are in rectangular form in this equation.
#             RealCM=cR*mR-cI*mI : ImagCM=cR*mI+cI*mR     'c*M, real and imaginary
#             call cxDivide mR-bR, mI-bI, aR-RealCM,aI-ImagCM,refR, refI   'Divide M-b by a-c*M
#         else
#                 'The second method uses  the following formula, and corresponds to CalcOSLCoeff1
#                 '       S = (a - cM)/(bM - 1)
#                 'where S is the actual reflection coefficient and M is the measured reflection coefficient.
#                 'S and M are in rectangular form in this equation.
#
#             RealCM=cR*mR-cI*mI : ImagCM=cR*mI+cI*mR     'c*M, real and imaginary
#             RealBM=bR*mR-bI*mI : ImagBM=bR*mI+bI*mR     'b*M, real and imaginary
#             numR=aR-RealCM : numI=aI-ImagCM             'numerator, real and imaginary
#             denR=RealBM-1 :denI=ImagBM                  'denominator, real and imaginary
#             call cxDivide numR, numI, denR, denI, refR, refI     'Divide numerator by denominator; result is reflection coeff.
#         end if

            if True:
                # The first method uses the following formula, and corresponds to
                # CalcOSLCoeff
                #       S = (M - b) / (a - c * M)
                # where S is the actual reflection coefficient and M is the measured
                # reflection coefficient.  S and M are in rectangular form in this
                # equation.

                S = (M - b) / (a - c * M)
            else:
                # The second method uses the following formula, and corresponds to
                # CalcOSLCoeff1
                #        S = (a - cM)/(bM - 1)
                # where S is the actual reflection coefficient and M is the measured
                # reflection coefficient.  S and M are in rectangular form in this
                # equation.

                S = (a - c * M) / (b * M - 1)

#         'ver116-4k separated the following common calculations from the above if...else block
#         magSquared=refR^2+refI^2        'mag of S, squared
#         db=10*uSafeLog10(magSquared)    'S mag in db; multiply by 10 not 20 because mag is squared
#         if db>0 then db=0   'Shouldn't happen
#         ang=uATan2(refR, refI)      'angle of S in degrees
#             'db, ang (degrees) now have S11 data produced by applying OSL calibration.

        (db, deg) = polarDbDeg(S)
        if db > 0:
            db = 0

#     end if
#
#     'Save the angle prior to applying plane extension or Z0 transform, to make it easier to recalculate with a new values
#     ReflectArray(currStep, constIntermedS11DB)=db  'ver115-2d
#     ReflectArray(currStep, constIntermedS11Ang)=ang  'ver115-2d
#         'Note we do apply plane extension even when doSpecialGraph<>0
#     if planeadj<>0 or S11BridgeR0<>S11GraphR0 then call ApplyExtensionAndTransformR0 ReflectArray(currStep,0), db, ang 'ver115-2d
#
#         'Note we do not put the reflection data in datatable, which retains the original raw data
#     ReflectArray(currStep,constGraphS11DB)=db   'Save final S11 in db, angle format (in Graph R0, after plane ext)
#     while ang>180 : ang=ang-360 : wend
#     while ang<=-180 : ang=ang+360 : wend
#     ReflectArray(currStep,constGraphS11Ang)=ang
#     'We now compute the various items in ReflectArray() from S11, but if we are doing calibration we don't need this
#     'other data, and it probably doesn't make sense anyway.
#     if calInProgress=0 then call CalcReflectDerivedData currStep  'Calc other ReflectArray() data from S11.

        return db, deg

# end sub

# sub ProcessOSLCal     'Calc coefficients and reference data from raw OSL scan data

    def ProcessOSLCal(self):

#
# Calc coefficients and reference data from raw OSL scan data
#
# OSLdoneO, OSLdoneS and OSLdoneL indicate which of Open, Short, and
# Load were performed.  The relevant calibration data is in
# OSLcalOpen(), OSLcalShort() and OSLcalLoad() Calibration data will be
# the raw S11 for reflection bridge, and raw S21 for the transmission
# jigs.  In the latter case we must convert to S11 before calculating
# OSL coefficients.
#
# The measured cal data is in OSLcalOpen(), etc., as dB/angle. It is
# reflection data for the reflection bridge, For S11JigType$="Reflect",
# the data in OSLcalOpen(), etc., will be reflection per the bridge w/o
# OSL adjustment, and without being adjusted for planeadj (which we
# force to 0 in cal).  For S11JigType$="Trans", the data in
# OSLcalOpen(), etc., is "S21" of the fixture (unadjusted for any
# reference) which we are treating as the tentative estimate of
# reflection, even though it is far from true reflection.
#
# When raw data is collected in future scans, it will be adjusted by a
# reference installed into the line cal array. The reference will be
# the calibration data from the Open, except for the series jig it is
# the calibration data from the Short. In the case of a Reflection
# Bridge if we don't have the relevant Open data, we compute it from
# the Short. We assume Ideal values for the non-reference data in order
# to calc coefficients.
#
# We put the OSL coefficients into OSLBandA(), OSLBandB() and OSLBandC()
#

# 'DEBUG
# '    for i=0 to globalSteps
# '        OSLcalOpen(i,0)=0 : OSLcalOpen(i,1)=0
# '        OSLcalShort(i,0)=42.638 : OSLcalShort(i,1)=-93.4375
# '        OSLcalLoad(i,0)=39.166 : OSLcalLoad(i,1)=-92.76
# '    next i
#     calSum=OSLdoneO+OSLdoneS+OSLdoneL   'number of cals done. Will be 1 or 3
#     if calSum=0 then notice "No calibration performed" : OSLError=1 : exit sub
#     if calSum=2 then notice "Incomplete calibration performed" : OSLError=1 : exit sub   'Our OSL procedure actually never allows this to happen
#     if calSum=1 and OSLdoneL then notice "Incomplete calibration performed" : OSLError=1  : exit sub   'Our OSL procedure actually never allows this to happen
#
        calSum = 0
        self.OSLError = False
        if self.OSLdoneO:
            calSum += 1
        if self.OSLdoneS:
            calSum += 1
        if self.OSLdoneL:
            calSum += 1
        if calSum == 0:
            message("No Reference scanned.\nCalibration not performed.") # EON Jan 29, 2014
            self.OSLError = True
            return
        if calSum == 2:
            message("Incomplete calibration performed") # EON Jan 29, 2014
            self.OSLError = True
            return
        if calSum == 1 and self.OSLdoneL:
            message("Incomplete calibration performed") # EON Jan 29, 2014
            self.OSLError = True
            return

#     call CalcOSLStandards   'ver116-4k

        # Calc cal standard data for computing coefficients. For reference cal,
        # we don't need all of them, but there is no harm in calculating them.

        self.CalcOSLStandards()

        # If we have just one standard it will be reference cal with Open
        # (bridge or shunt) or Short(bridge or series), but may not be ideal
        # standard. We make up data for the missing standards so we can do
        # regular OSL.

        if self.oslDbg:
            f = open("OSLCal1.txt","w")

        if calSum == 1:

#         if OSLdoneO then OSLBandRefType$="Open" else OSLBandRefType$="Short"
#         for i=0 to globalSteps 'modver116-4n
#             if OSLdoneO then
# Note the measured values are the raw measurements of the data, which
# are the fixture transmission values but are not adjusted to any
# reference.
#                 S11R=OSLstdOpen(i,0) : S11I=OSLstdOpen(i,1)  'Actual standard S11, real/imag
#                 measDB=OSLcalOpen(i,0) : measDeg=OSLcalOpen(i,1)    'measured standard
#             else 'short
#                 S11R=OSLstdShort(i,0) : S11I=OSLstdShort(i,1) 'Actual standard S11, real/imag
#                 measDB=OSLcalShort(i,0) : measDeg=OSLcalShort(i,1)    'measured standard
#             end if
#             S11Mag=sqr(S11R^2+S11I^2) : S11dB=20*uSafeLog10(S11Mag) : S11Deg=uATan2(S11R, S11I) 'The calibration standard S11 spec in dB/angle format

            # Either the Open or Short was used as the reference. Even though the
            # cal standard may not be ideal, we use this as the (line cal)
            # reference, because it is easy to repeat when doing Update Cal. We also
            # need to create the two missing standards.  They will be created as
            # ideal, so we must also be sure that the description of the standard is
            # ideal, so we may override CalcOSLStandards that was just performed. We
            # need to find how the used standard would have performed if ideal, in
            # order to create the missing standards.

            if self.OSLdoneO:
                self.OSLBandRefType = "Open"
            else:
                self.OSLBandRefType = "Short"

            for i in range(self._nSteps):
                freq = self.Fmhz[i] * 1e6
                if self.OSLdoneO:
                    # Note the measured values are the raw measurements of the data, which
                    # are the fixture transmission values but are not adjusted to any
                    # reference.
                    S11 = self.OSLstdOpen[i]
                    (measDB, measDeg) = self.OSLcalOpen[i]
                else:
                    S11 = self.OSLstdShort[i]
                    (measDB, measDeg) = self.OSLcalShort[i]

                (S11dB, S11Deg) = polarDbDeg(S11)
                if self.oslDbg:
                    f.write("%2d, measDB %10.3e, measDeg %10.3e," % (i, measDB, measDeg))
                    f.write(" S11dB %10.3e, S11Deg %9.2e\n" % (S11dB, S11Deg))

#
#             if S11JigType$="Reflect" then
# Using bridge with reference cal. Reference may be Open or Short
#                 if S11dB<-40 then notice "Reference calibration standard is too close to "; S11BridgeR0; " ohms." : OSLError=1 : exit sub
#                 if OSLdoneO then
#                     OSLcalOpen(i,0)=0 : OSLcalOpen(i,1)=0  'Open adjusted by itself as reference
#                     OSLstdShort(i,0)=-1 : OSLstdShort(i,1)=0   'Force spec of Short to be ideal  (real/imag)
#                     OSLcalShort(i,0)=0-S11dB : OSLcalShort(i,1)=uNormalizeDegrees(-180-S11Deg)  'Pretend we measured the ideal Short and subtracted Open as reference (dB/ang form)
#                 else    'short is the reference
#                     OSLcalShort(i,0)=0 : OSLcalShort(i,1)=0  'Adjust short with itself as reference, resulting in 0 (dB/ang form)
#                     OSLstdOpen(i,0)=1 : OSLstdOpen(i,1)=0   'Force spec of Open to be ideal  (real/imag)
#                     OSLcalOpen(i,0)=0-S11dB : OSLcalOpen(i,1)=uNormalizeDegrees(0-S11Deg) 'Pretend we measured the ideal Open and subtracted Short as reference (dB/ang form)
#                 end if
#                 OSLstdLoad(i,0)=0 : OSLstdLoad(i,1)=0  'Force spec of load to be ideal (real/imag)
#                 OSLcalLoad(i,0)=-99-S11dB : OSLcalLoad(i,1)=0  'Pretend we measured the ideal load (dB/ang form); don't worry about angle
#             else

                if self.S11JigType == "Reflect":
                    # Using bridge with reference cal. Reference may be Open or Short
                    if S11dB < -40:
                        message("Reference calibration standard is too close to " + self.S11BridgeR0 + " ohms.") # EON Jan 29, 2014
                        self.OSLError = True
                        return

                    if self.OSLdoneO:
                        # Open adjusted by itself as reference
                        self.OSLcalOpen[i] = (0, 0)
                        # Force spec of Short to be ideal (real/imag)
                        self.OSLstdShort[i] = complex(-1, 0)
                        # Pretend we measured the ideal Short and subtracted Open as reference (dB/ang form)
                        self.OSLcalShort[i] = (-S11dB, uNormalizeDegrees(-180-S11Deg))
                    else:    # short is the reference
                        # Adjust short with itself as reference, resulting in 0 (dB/ang form)
                        self.OSLcalShort[i] = (0, 0)
                        # Force spec of Open to be ideal (real/imag)
                        self.OSLstdOpen[i] = complex(1, 0)
                        # Pretend we measured the ideal Open and subtracted Short as reference (dB/ang form)
                        self.OSLcalOpen[i] = (-S11dB, uNormalizeDegrees(-S11Deg))

                    # Force spec of load to be ideal (real/imag)
                    self.OSLstdLoad[i] = complex(0, 0)
                    # Pretend we measured the ideal load (dB/ang form); don't worry about angle
                    self.OSLcalLoad[i] = (-99 - S11dB, 0)
                else:

#                 if S21JigAttach$="Shunt" then   'calc S21 that this refco would produce
#                     phaseDelay=ReflectArray(i,0)*0.36*S21JigShuntDelay   'one way delay in degrees
#                     call uS11DBToImpedance S21JigR0, S11dB, S11Deg, impR, impX       'calc impedance
#                     call uPhaseShiftImpedance 50, phaseDelay, impR, impX    'Calculate effective impedance of Open with 50-ohm delay
#                     call uImpedanceToRefco S21JigR0, impR, impX, S11Mag, S11Deg   'calc actual Open S11 re S21JigR0 taking into account the delay
#                     call uRefcoToShuntS21DB S11Mag, S11Deg, S21dB, S21Deg   'calc S21 from the refco of the effective impedance
#                     if S11dB>-0.25 and (S11Deg<-165 or S11Deg>165) then _
#                         notice "Reference calibration standard is too close to a Short." : OSLError=1 : exit sub
#
#                     impR=0 : impX=0 'impedance of ideal Short
#                     call uPhaseShiftImpedance 50, phaseDelay, impR, impX    'Calculate effective impedance of ideal Short
#                     call uImpedanceToRefco S21JigR0, impR, impX, idealShortS11Mag, idealShortS11Deg   'calc ideal Short response taking into account the delay
#                     call uRefcoToShuntS21DB idealShortS11Mag, idealShortS11Deg, idealShortS21dB, idealShortS21Deg   'calc S21 from the refco of the effective impedance
# Adjust by the measured Open reading
#                     idealShortS21dB=idealShortS21dB - S21dB : idealShortS21Deg=uNormalizeDegrees(idealShortS21Deg - S21Deg)
#
#                     impR=S21JigR0 : impX=0  'impedance of ideal Load
#                     call uPhaseShiftImpedance 50, phaseDelay, impR, impX    'Calculate effective impedance of ideal Load
#                     call uImpedanceToRefco S21JigR0, impR, impX, idealLoadS11Mag, idealLoadS11Deg   'calc ideal Load response taking into account the delay
#                     call uRefcoToShuntS21DB idealLoadS11Mag, idealLoadS11Deg, idealLoadS21dB, idealLoadS21Deg   'calc S21 from the refco of the effective impedance
# Adjust by the same amount that the measured Open was high
#                     idealLoadS21dB=idealLoadS21dB - S21dB : idealLoadS21Deg=uNormalizeDegrees(idealLoadS21Deg  - S21Deg)
#
#                     OSLcalOpen(i,0)=0 : OSLcalOpen(i,1)=0  'Adjust open with itself as reference, resulting in 0 (dB/ang form)
#                     OSLstdShort(i,0)=-1 : OSLstdShort(i,1)=0   'Force spec of short to be ideal (real/imag)
#                     OSLcalShort(i,0)=idealShortS21dB : OSLcalShort(i,1)=idealShortS21Deg  'Pretend we measured the ideal short
#                     OSLstdLoad(i,0)=0 : OSLstdLoad(i,1)=0   'Force spec of load to be ideal (real/imag)
#                     OSLcalLoad(i,0)=idealLoadS21dB : OSLcalLoad(i,1)=idealLoadS21Deg  'Pretend we measured the ideal load

                    (S11Mag, S11Rad) = cmath.polar(S11)
                    S11Deg = S11Rad * DegreesPerRad
                    if self.S21JigAttach == "Shunt":   # calc S21 that this refco would produce

                        # For shunt fixture with no delay and a perfect Open, the ideal Load
                        # response would be 3.52 dB below the Open response and the ideal Short
                        # response would be zero. A non-zero delay or imperfect Open require us
                        # to calculate how the response of the actual Open, the ideal Load and
                        # the ideal Short would be transformed by the delay. We will use the
                        # measured Open as the reference for future measurements (i.e. it will
                        # be subtracted from the raw data the same as line cal). Therefore,
                        # whatever S21 we calculate for the actual Open, ideal Short or ideal
                        # Load, would produce reference-adjusted readings equal to that S21
                        # minus that opens calculated S21. That is, use of the measured open
                        # as a reference makes its net reading zero, and the ideal Load and
                        # Short need to be similarly adjusted The delay is assumed to be in a
                        # line of 50-ohms, not S21JigR0.

                        # one way delay in degrees
                        phaseDelay = freq * 0.36 * self.S21JigShuntDelay

                        # calc impedance
                        imp = self.uS11DBToImpedance(self.S21JigR0, S11dB, S11Deg)

                        # Calculate effective impedance of Open with 50-ohm delay
                        imp = self.uPhaseShiftImpedance(50, phaseDelay, imp)

                        # calc actual Open S11 re S21JigR0 taking into account the delay
                        (S11Mag, S11Deg) = self.uImpedanceToRefco(self.S21JigR0, imp)

                        # calc S21 from the refco of the effective impedance
                        (S21dB, S21Deg) = self.uRefcoToShuntS21DB(S11Mag, S11Deg)

                        if S11dB > -0.25 and S11Deg < -165 or S11Deg > 165:
                            message("Reference calibration standard is too close to a Short.") # EON Jan 29, 2014
                            self.OSLError = True
                            return

                        if self.oslDbg:
                            f.write("%2d S21 %s\n" % (i, pol((S21dB, S21Deg))))

                        # impedance of ideal Short
                        imp = complex(0, 0)

                        # Calculate effective impedance of ideal Short
                        imp = self.uPhaseShiftImpedance(50, phaseDelay, imp)

                        # calc ideal Short response taking into account the delay
                        (idealShortS11Mag, idealShortS11Deg) = self.uImpedanceToRefco(self.S21JigR0, imp)

                        # calc S21 from the refco of the effective impedance
                        (idealShortS21dB, idealShortS21Deg) = self.uRefcoToShuntS21DB(idealShortS11Mag, idealShortS11Deg)

                        if self.oslDbg:
                            f.write("%2d idealShortS21 %s\n" % (i, pol((idealShortS21dB, idealShortS21Deg))))

                        # Adjust by the measured Open reading
                        idealShortS21dB = idealShortS21dB - S21dB
                        idealShortS21Deg = uNormalizeDegrees(idealShortS21Deg - S21Deg)

                        # impedance of ideal Load
                        imp = complex(self.S21JigR0, 0)

                        # Calculate effective impedance of ideal Load
                        imp = self.uPhaseShiftImpedance(50, phaseDelay, imp)

                        # calc ideal Load response taking into account the delay
                        (idealLoadS11Mag, idealLoadS11Deg) = self.uImpedanceToRefco(self.S21JigR0, imp)

                        #calc S21 from the refco of the effective impedance
                        (idealLoadS21dB, idealLoadS21Deg) = self.uRefcoToShuntS21DB(idealLoadS11Mag, idealLoadS11Deg)

                        if self.oslDbg:
                            f.write("%2d idealLoadS21 %s\n" % (i, pol((idealLoadS21dB, idealLoadS21Deg))))

                        # Adjust by the same amount that the measured Open was high
                        idealLoadS21dB = idealLoadS21dB - S21dB
                        idealLoadS21Deg = uNormalizeDegrees(idealLoadS21Deg - S21Deg)

                        self.OSLcalOpen[i] = (0, 0)          # Adjust open with itself as reference, resulting in 0 (dB/ang form)
                        self.OSLstdShort[i] = complex(-1,0)  # Force spec of short to be ideal (real/imag)
                        self.OSLcalShort[i] = (idealShortS21dB, idealShortS21Deg)  # Pretend we measured the ideal short
                        self.OSLstdLoad[i] = complex(0, 0)   # Force spec of load to be ideal (real/imag)
                        self.OSLcalLoad[i] = (idealLoadS21dB, idealLoadS21Deg)     # Pretend we measured the ideal load

#                 else    'series fixture
# Series is similar to shunt, except cal is with Short, and we don't deal with delays so everything is simpler.
#                     call uRefcoToSeriesS21DB S11Mag, S11Deg, S21dB, S21Deg      'S21 that the actual short would produce
#                     if S11dB>-0.25 and S11Deg<5 and S11Deg>-5 then _
#                         notice "Reference calibration standard is too close to an Open." : OSLError=1 : exit sub
#                     OSLcalShort(i,0)=0 : OSLcalShort(i,1)=0  'Adjust short with itself as reference, resulting in 0 (dB/ang form)
#                     OSLstdOpen(i,0)=1 : OSLstdOpen(i,1)=0   'Force spec of Open to be ideal  (real/imag)
#                     OSLcalOpen(i,0)=-99-S21dB : OSLcalOpen(i,1)=uNormalizeDegrees(0-S21Deg)   'Pretend we measured the ideal Open (dB/ang form)
#                     OSLstdLoad(i,0)=0 : OSLstdLoad(i,1)=0  'Force spec of load to be ideal (real/imag)
# Load would be 3.52 dB below ideal short; actual short would produce
# S21dB@S21Deg but we set measured short to zero, so we also have to
# subtract S21dB@S21Deg from ideal load.
#                     OSLcalLoad(i,0)=-3.52-S21dB : OSLcalLoad(i,1)=uNormalizeDegrees(0-S21Deg)  'Pretend we measured the ideal load (dB/ang form)
#                 end if
#             end if
#             OSLBandRef(i,0)=ReflectArray(i,0)    'freq--actual tuning freq, not equiv 1G freq
#             OSLBandRef(i,1)=measDB :OSLBandRef(i,2)=measDeg 'save reference   'Save the measured reference
#         next i

                    else:    # series fixture
                        # Series is similar to shunt, except cal is with Short, and we don't
                        # deal with delays so everything is simpler.

                        # S21 that the actual short would produce
                        (S21dB, S21Deg) = self.uRefcoToSeriesS21DB(S11Mag, S11Deg)
                        if S11dB > -0.25 and S11Deg < 5 and S11Deg > -5:
                            message("Reference calibration standard is too close to an Open.") # EON Jan 29, 2014
                            self.OSLError = True
                            return

                        # Adjust short with itself as reference, resulting in 0 (dB/ang form)
                        self.OSLcalShort[i] = (0, 0)
                        # Force spec of Open to be ideal  (real/imag)
                        self.OSLstdOpen[i] = complex(1, 0)
                        # Pretend we measured the ideal Open (dB/ang form)
                        self.OSLcalOpen[i] = (-99 - S21dB, uNormalizeDegrees(-S21Deg))
                        # Force spec of load to be ideal (real/imag)
                        self.OSLstdLoad[i] = complex(0, 0)

                        # Load would be 3.52 dB below ideal short; actual short would produce
                        # S21dB@S21Deg but we set measured short to zero, so we also have to
                        # subtract S21dB@S21Deg from ideal load.

                        # Pretend we measured the ideal load (dB/ang form)
                        self.OSLcalLoad[i] = (-3.52 - S21dB, uNormalizeDegrees(-S21Deg))

                if self.oslDbg:
                    f.write("%2d, calOpen (%10.3e, %10.3e)," % (i, self.OSLcalOpen[i][0], self.OSLcalOpen[i][1]))
                    f.write(" calShort (%10.3e, %10.3e)" % (self.OSLcalShort[i][0], self.OSLcalShort[i][1]))
                    f.write(" calLoad (%10.3e, %10.3e)\n" % (self.OSLcalLoad[i][0], self.OSLcalLoad[i][1]))

                    f.write("%2d, stdOpen (%10.3e, %10.3e)," % (i, self.OSLstdOpen[i].real, self.OSLstdOpen[i].imag))
                    f.write(" stdShort (%10.3e, %10.3e)" % (self.OSLstdShort[i].real, self.OSLstdShort[i].imag))
                    f.write(" stdLoad (%10.3e, %10.3e)\n" % (self.OSLstdLoad[i].real, self.OSLstdLoad[i].imag))

                    f.write("%2d, freq %7.0f, measDB %10.3e, measDeg %10.3e\n\n" % (i, freq, measDB, measDeg))
                self.OSLBandRef[i] = (measDB, measDeg)


#     else    'All three standards used   'ver116-4n
# We need to determine what to use for the reference. It will be Open,
# Short or Load, whichever has the largest value.  The goal is to avoid
# the Open with a series fixture or a Short with a shunt fixture.
#         open1=OSLcalOpen(0,0) : load1=OSLcalLoad(0,0) : short1=OSLcalShort(0,0)
#         if open1>=load1 then    'choose biggest
#             if open1>=short1 then OSLBandRefType$="Open" else OSLBandRefType$="Short"
#         else
#             if load1>short1 then OSLBandRefType$="Load" else OSLBandRefType$="Short"
#         end if
#
#         for i=0 to globalSteps  'copy reference and adjust measurements per reference
#             OSLBandRef(i,0)=ReflectArray(i,0)    'freq--actual tuning freq, not equiv 1G freq
#             select case OSLBandRefType$
#                 case "Open" : refdB=OSLcalOpen(i,0) : refDeg=OSLcalOpen(i,1)
#                 case "Short" : refdB=OSLcalShort(i,0) : refDeg=OSLcalShort(i,1)
#                 case else : refdB=OSLcalLoad(i,0) : refDeg=OSLcalLoad(i,1)
#             end select
#             OSLBandRef(i,1)=refdB :OSLBandRef(i,2)=refDeg 'save reference
#             OSLcalOpen(i,0)=OSLcalOpen(i,0)-refdB : OSLcalOpen(i,1)=uNormalizeDegrees(OSLcalOpen(i,1)-refDeg)   'Adjust measurements per reference
#             OSLcalLoad(i,0)=OSLcalLoad(i,0)-refdB : OSLcalLoad(i,1)=uNormalizeDegrees(OSLcalLoad(i,1)-refDeg)
#             OSLcalShort(i,0)=OSLcalShort(i,0)-refdB : OSLcalShort(i,1)=uNormalizeDegrees(OSLcalShort(i,1)-refDeg)

        else:    # All three standards used
            # We need to determine what to use for the reference. It will be Open,
            # Short or Load, whichever has the largest value.  The goal is to avoid
            # the Open with a series fixture or a Short with a shunt fixture.
            open1 = self.OSLcalOpen[0][0]
            load1 = self.OSLcalLoad[0][0]
            short1 = self.OSLcalShort[0][0]
            if self.oslDbg:
                f.write("open %10.3e load %10.3e short %10.3e\n" % (open1, load1, short1))
            if open1 >= load1:
                if open1 >= short1:
                    self.OSLBandRefType = "Open"
                else:
                    self.OSLBandRefType = "Short"
            else:
                if load1 > short1:
                    self.OSLBandRefType = "Load"
                else:
                    self.OSLBandRefType = "Short"

            if self.oslDbg:
                f.write("%s\n" % (self.OSLBandRefType))

            for i in range(self._nSteps):
                if self.OSLBandRefType == "Open":
                    (refdB, refDeg) = self.OSLcalOpen[i]
                elif self.OSLBandRefType == "Short":
                    (refdB, refDeg) = self.OSLcalShort[i]
                else:
                    (refdB, refDeg) = self.OSLcalLoad[i]

                if self.oslDbg:
                    f.write("%2d, ref  %s\n" % (i, pol((refdB, refDeg))))

                self.OSLBandRef[i] = (refdB, refDeg)

                # Adjust measurements per reference
                (db, deg) = self.OSLcalOpen[i]
                self.OSLcalOpen[i] = (db - refdB, uNormalizeDegrees(deg - refDeg))
                (db, deg) = self.OSLcalLoad[i]
                self.OSLcalLoad[i] = (db - refdB, uNormalizeDegrees(deg - refDeg))
                (db, deg) = self.OSLcalShort[i]
                self.OSLcalShort[i] = (db - refdB, uNormalizeDegrees(deg - refDeg))

#         next i
#     end if
#
# ver116-4k deleted creation of missing standard when we have two. Current procedure never allows us to end up with two.
#     OSLError=0  'ver116-4k
#

        self.OSLError = False

# We want to convert the OSLcalxxx() data into S11 in rectangular form
# (real, imaginary), and calc OSL coefficients.  We leave the reference
# data in db, ang (degrees) format

#     kDegToRad=uRadsPerDegree()
#     for i=0 to globalSteps
#         rho=10^(OSLcalOpen(i,0)/20) : rad=OSLcalOpen(i,1)*kDegToRad 'to polar, radians
#         OSLcalOpen(i,0)=cos(rad)*rho : OSLcalOpen(i,1)=sin(rad)*rho 'polar to rectangular
#         rho=10^(OSLcalLoad(i,0)/20) : rad=OSLcalLoad(i,1)*kDegToRad
#         OSLcalLoad(i,0)=cos(rad)*rho : OSLcalLoad(i,1)=sin(rad)*rho
#         rho=10^(OSLcalShort(i,0)/20) : rad=OSLcalShort(i,1)*kDegToRad
#         OSLcalShort(i,0)=cos(rad)*rho : OSLcalShort(i,1)=sin(rad)*rho
#     next i

        # We want to convert the OSLcalxxx() data into S11 in rectangular form
        # (real, imaginary), and calc OSL coefficients.  We leave the reference
        # data in db, ang (degrees) format

        for i in range(self._nSteps):
            (db, deg) = self.OSLcalOpen[i]
            if self.oslDbg:
                f.write("%2d, calOpen  %s," % (i, pol((db, deg))))
            self.OSLcalOpen[i] = cmath.rect(10 ** (db / 20), deg * RadsPerDegree)
            if self.oslDbg:
                f.write(" %s\n" % cpx(self.OSLcalOpen[i]))

            (db, deg) = self.OSLcalLoad[i]
            if self.oslDbg:
                f.write("%2d, calLoad  %s," % (i, pol((db, deg))))
            self.OSLcalLoad[i] = cmath.rect(10 ** (db / 20), deg * RadsPerDegree)
            if self.oslDbg:
                f.write(" %s\n" % cpx(self.OSLcalLoad[i]))

            (db, deg) = self.OSLcalShort[i]
            if self.oslDbg:
                f.write("%2d, calShort %s," % (i, pol((db, deg))))
            self.OSLcalShort[i] = cmath.rect(10 ** (db / 20), deg * RadsPerDegree)
            if self.oslDbg:
                f.write(" %s\n\n" % cpx(self.OSLcalShort[i]))

        if self.oslDbg:
            f.close()

        # Calculate A, B, C coefficients; set OSLError to 1 if math error
        self.CalcOSLCoeff()

# end sub
#

# sub CalcOSLCoeff

    def CalcOSLCoeff(self):

#
# Calc coeff a, b, c for base or band OSL cal
#
# We calculate OSL coefficients for the most general case, where no
# advance assumptions are made about the cal standards.  OSLcalOpen(),
# OSLcalShort() and OSLcalLoad() have the raw calibration data (real,
# imag form) OSLstdOpen and OSLstdOpen() have the S11 data for the Open
# and Short standards (real, imag form) MO,ML, MS are the measured
# responses with the open, load and short attached SO, SL, SS are the
# actual reflection coeff. of the open, short and load standards
#
# The error model equation is as follows, where S is the actual S11 and M is
#
# the measured S11:
#   S = (M - b) / (a - c * M)
#
# Using S and M for the Open, Short and Load, we can calculate the
# coefficients a, b and c.  The double letter variables Mx and Sx are
# the measured and actual values, the second letter (O, S or L)
# indicating open, short or load.
#
# The double letter variables Mx and Sx are the measured and actual
# values, with the second letter (O, S or L) indicating open, short or
# load.
#
#    K1 = ML - MS
#    K2 = MS - MO
#    K3 = MO - ML
#    K4 = SL * SS * K1
#    K5 = SO * SS * K2
#    K6 = SL * SO * K3
#    K7 = SO * K1
#    K8 = SL * K2
#    K9 = SS * K3
#
#    D = K4 + K5 + K6
#
#    a = (MO * K7 + ML * K8 + MS * K9) / D
#    b = (MO * K4 + ML * K5 + MS * K6) / D
#    c = (K7 + K8 + K9) / D
#
#     for calStep=0 to globalSteps
#         MOr=OSLcalOpen(calStep,0) : MOi=OSLcalOpen(calStep,1)     'Measured open, real and imag
#         MLr=OSLcalLoad(calStep,0) : MLi=OSLcalLoad(calStep,1)     'Measured load, real and imag
#         MSr=OSLcalShort(calStep,0) : MSi=OSLcalShort(calStep,1)     'Measured short, real and imag
#         SOr=OSLstdOpen(calStep,0) : SOi=OSLstdOpen(calStep,1)     'Open standard, real and imag
#         SLr=OSLstdLoad(calStep,0) : SLi=OSLstdLoad(calStep,1)     'Load standard, real and imag
#         SSr=OSLstdShort(calStep,0) : SSi=OSLstdShort(calStep,1)     'Short standard, real and imag

        if self.oslDbg:
            f = open("OSLCoef1.txt", "w")
        for i in range(self._nSteps):
            MO = self.OSLcalOpen[i]     # Measured open, real and imag
            ML = self.OSLcalLoad[i]     # Measured load, real and imag
            MS = self.OSLcalShort[i]    # Measured short, real and imag

            SO = self.OSLstdOpen[i]     # Open standard, real and imag
            SL = self.OSLstdLoad[i]     # Load standard, real and imag
            SS = self.OSLstdShort[i]    # Short standard, real and imag
            if self.oslDbg:
                f.write("%3d mo (%10.3e, %10.3e) ml (%10.3e, %10.3e) ms (%10.3e, %10.3e)\n" % (i, MO.real, MO.imag, ML.real, ML.imag, MS.real, MS.imag))
                f.write("%3d so (%10.3e, %10.3e) sl (%10.3e, %10.3e) ss (%10.3e, %10.3e)\n" % (i, SO.real, SO.imag, SL.real, SL.imag, SS.real, SS.imag))

#         K1r=MLr-MSr : K1i=MLi-MSi   'K1=ML-MS, real and imag
#         K2r=MSr-MOr : K2i=MSi-MOi   'K2=MS-MO, real and imag
#         K3r=MOr-MLr : K3i=MOi-MLi   'K3=MO-ML, real and imag
#
#         Wr=SLr*SSr-SLi*SSi : Wi=SLr*SSi+SLi*SSr   'W=SL*SS
#         K4r=Wr*K1r-Wi*K1i : K4i=Wr*K1i+Wi*K1r     'K4=SL*SS*K1
#
#         Wr=SOr*SSr-SOi*SSi : Wi=SOr*SSi+SOi*SSr   'W=SO*SS
#         K5r=Wr*K2r-Wi*K2i : K5i=Wr*K2i+Wi*K2r     'K5=SO*SS*K2
#
#         Wr=SLr*SOr-SLi*SOi : Wi=SLr*SOi+SLi*SOr   'W=SL*SO
#         K6r=Wr*K3r-Wi*K3i : K6i=Wr*K3i+Wi*K3r     'K6=SL*SO*K3
#
#         K7r=SOr*K1r-SOi*K1i : K7i=SOr*K1i+SOi*K1r     'K7=SO*K1
#
#         K8r=SLr*K2r-SLi*K2i : K8i=SLr*K2i+SLi*K2r     'K8=SL*K2
#
#         K9r=SSr*K3r-SSi*K3i : K9i=SSr*K3i+SSi*K3r     'K9=SS*K3
#
#         Dr=K4r+K5r+K6r : Di=K4i+K5i+K6i    'D = K4 + K5 + K6

            K1 = ML - MS
            K2 = MS - MO
            K3 = MO - ML
            K4 = SL * SS * K1
            K5 = SO * SS * K2
            K6 = SL * SO * K3

            K7 = SO * K1
            K8 = SL * K2
            K9 = SS * K3

            if self.oslDbg:
                f.write("%3d k1 (%10.3e, %10.3e) k2 (%10.3e, %10.3e) k3 (%10.3e, %10.3e)\n" % (i, K1.real, K1.imag, K2.real, K2.imag, K3.real, K3.imag))
                f.write("%3d k4 (%10.3e, %10.3e) k5 (%10.3e, %10.3e) k6 (%10.3e, %10.3e)\n" % (i, K4.real, K1.imag, K5.real, K5.imag, K6.real, K6.imag))
                f.write("%3d k7 (%10.3e, %10.3e) k8 (%10.3e, %10.3e) k9 (%10.3e, %10.3e)\n" % (i, K7.real, K1.imag, K8.real, K8.imag, K9.real, K9.imag))

            D = K4 + K5 + K6

#         if Dr=0 and Di=0 then notice "Divide by zero in calculating OSL coefficients." : OSLError=1 : exit sub  'ver115-4j
#         call cxInvert Dr, Di, invDr, invDi   'invD= 1/D
# Now calculate coefficient a
#         Wr=MOr*K7r-MOi*K7i : Wi=MOr*K7i+MOi*K7r   'W=MO*K7
#         Xr=MLr*K8r-MLi*K8i : Xi=MLr*K8i+MLi*K8r   'X=ML*K8
#         Yr=MSr*K9r-MSi*K9i : Yi=MSr*K9i+MSi*K9r   'Y=MS*K9
#         Zr=Wr+Xr+Yr : Zi=Wi+Xi+Yi                  'Z=MO*K7 + ML*K8 + MS*K9
#         ar=Zr*invDr-Zi*invDi : ai=Zr*invDi+Zi*invDr   'a=(MO*K7 + ML*K8 + MS*K9)/D
#
# The procedure for calculating b is identical to that for a,
# just changing the K values.
#         Wr=MOr*K4r-MOi*K4i : Wi=MOr*K4i+MOi*K4r   'W=MO*K4
#         Xr=MLr*K5r-MLi*K5i : Xi=MLr*K5i+MLi*K5r   'X=ML*K5
#         Yr=MSr*K6r-MSi*K6i : Yi=MSr*K6i+MSi*K6r   'Y=MS*K6
#         Zr=Wr+Xr+Yr : Zi=Wi+Xi+Yi                  'Z=MO*K4 + ML*K5 + MS*K6
#         br=Zr*invDr-Zi*invDi : bi=Zr*invDi+Zi*invDr   'b=(MO*K4 + ML*K5 + MS*K6)/D
#
# Calculate coefficient c.
#         Wr=K7r+K8r+K9r : Wi=K7i+K8i+K9i     'W = K7 + K8 + K9
#         cr=Wr*invDr-Wi*invDi : ci=Wr*invDi+Wi*invDr   'c = (K7 + K8 + K9)/D
#
# Put coefficients into OSLBandx()
#         OSLBandA[i]=ar : OSLBandA(calStep,1)=ai
#         OSLBandB[i]=br : OSLBandB(calStep,1)=bi
#         OSLBandC[i]=cr : OSLBandC(calStep,1)=ci
#     next calStep

            try:
                invD = 1 / D
            except ZeroDivisionError:
                message("Divide by zero in calculating OSL coefficients.") # EON Jan 29, 2014
                self.OSLError = True
                return

            # Now calculate coefficient a
            a = (MO * K7 + ML * K8 + MS * K9) * invD

            # The procedure for calculating b is identical to that for a,
            # just changing the K values.
            b = (MO * K4 + ML * K5 + MS * K6) * invD

            # Calculate coefficient c.
            c = (K7 + K8 + K9) * invD

            # Put coefficients into OSLBandx()
            self.OSLBandA[i] = a
            self.OSLBandB[i] = b
            self.OSLBandC[i] = c
            if self.oslDbg:
                f.write("%3d a (%10.3e, %10.3e), b (%10.3e, %10.3e), c (%10.3e, %10.3e)\n\n" % (i, a.real, a.imag, b.real, b.imag, c.real, c.imag))

        if self.oslDbg:
            f.close()
# end sub
#

# sub CalcOSLCoeff1

    def CalcOSLCoeff1(self):

# Here we use the measured reflection coefficients for the open, load
# and short to determine OSL coefficients a, b and c. These in turn can
# be used to calculate actual reflection coefficients from measured
# reflection coefficients by the following formulas:
#
#        M = (S + a) / (b * S + c)
#        S = (a - c * M) / (b * M - 1)
#
# where S is the actual reflection coefficient and M is the measured
# reflection coefficient.  For subscripting variables in code and in
# the comments, the suffixes O, L and S mean Open, Load and Short,
# respectively. For example, SL is the actual reflection coefficient of
# the load; MS is the measured reflection loss of the short.
#
# The measured return losses for the open, load and short are
# determined at each frequency step before invoking this method, and
# placed into the arrays OSXOpenR, OSXOpenI, OSXLoadR, OSXLoadI,
# OSXShortR and OSXShortI. Variable names use the suffixes R and I for
# the real and imaginary parts, respectively.  We could first do a line
# calibration with the Open and then measure just the load and short,
# assigning a perfect "1" to the Open.  But to keep this calculation
# generic, if that is done the entries for the measured
#
# Open should just be assigned a value of 1 before invoking CalcOSL.
# We allow for the actual return losses of the open and short to be
# something other than ideal, by using arrays to hold their values at
# each frequency step.
#

#
# Calc coeff a, b, c for base or band OSL cal
#
# OSLcalOpen(), OSLcalShort() and OSLcalLoad() have the raw calibration
# data (real, imag form) OSLstdOpen and OSLstdOpen() have the S11 data
# for the Open and Short standards (real, imag form)
#
# MO,ML, MS are the measured responses with the open, load and short
# attached SO, SL, SS are the actual reflection coeff. of the open,
# short and load standards
#
# (SL is assumed=0)
# All must be in real, imaginary form
# The adjustment is made by the following formula:
#
#       S = (a - c * M) / (b * M - 1)
#
# This model is different from that used in CalcOSLCoeff where S is
# the actual reflection coefficient and M is the measured reflection
# coefficient.
#
# The coefficients a, b and c are calculated according to the following
# formulas:
#
# K1 = ML - MO; approx. -1
# K2 = MS - ML; appro.x -1
# K3 = MO - MS; approx. 2
#
# D = MS * SS * K1 + MO * SO * K2; approx -2
#
# c = SO * SS * K3 / D
# a = ML * c
# b = [SO * K2 + SS * K1] / D
#
#     for calStep=0 to globalSteps
#         MOr=OSLcalOpen(calStep,0) : MOi=OSLcalOpen(calStep,1)     'Measured open, real and imag
#         MLr=OSLcalLoad(calStep,0) : MLi=OSLcalLoad(calStep,1)     'Measured load, real and imag
#         MSr=OSLcalShort(calStep,0) : MSi=OSLcalShort(calStep,1)     'Measured short, real and imag
#         SOr=OSLstdOpen(calStep,0) : SOi=OSLstdOpen(calStep,1)     'Open standard, real and imag
#         SSr=OSLstdShort(calStep,0) : SSi=OSLstdShort(calStep,1)     'Short standard, real and imag

        for i in range(self._nSteps):
            MO = self.OSLcalOpen[i]    # Measured open, real and imag
            ML = self.OSLcalLoad[i]    # Measured load, real and imag
            MS = self.OSLcalShort[i]   # Measured short, real and imag
            SO = self.OSLstdOpen[i]    # Open standard, real and imag
            SS = self.OSLstdShort[i]   # Short standard, real and imag

#
# Compute Ks
#         K1r=MLr-MOr : K1i=MLi-MOi   'K1, real and imag
#         K2r=MSr-MLr : K2i=MSi-MLi   'K2, real and imag
#         K3r=MOr-MSr : K3i=MOi-MSi   'K3, real and imag

            # Compute Ks
            K1 = ML - MO
            K2 = MS - ML
            K3 = MO - MS

#
# Compute 1/D
#         Wr=MSr*SSr-MSi*SSi : Wi=MSr*SSi+MSi*SSr     'MS*SS
#         Xr=Wr*K1r-Wi*K1i : Xi=Wr*K1i+Wi*K1r     'MS*SS*K1
#         Yr=MOr*SOr-MOi*SOi : Yi=MOr*SOi+MOi*SOr     'MO*SO
#         Zr=Yr*K2r-Yi*K2i : Zi=Yr*K2i+Yi*K2r     'MO*SO*K2
#         Dr=Xr+Zr : Di=Xi+Zi     'D=MS*SS*K1 + MO*SO*K2
#         if Dr=0 and Di=0 then notice "Divide by zero in calculating OSL coefficients." : OSLError=1 : exit sub  'ver115-4j
#         call cxInvert Dr, Di, DinvR, DinvI       'Invert of D is in Dinv

            # Compute 1/D
            D = (MS * SS * K1) + (MO * SO * K2)
            try:
                invD = 1 / D
            except ZeroDivisionError:
                message("Divide by zero in calculating OSL coefficients.") # EON Jan 29, 2014
                self.OSLError = True
                return

# Compute c
#         Wr=SOr*SSr-SOi*SSi : Wi=SOr*SSi+SOi*SSr     'SO*SS
#         Xr=Wr*K3r-Wi*K3i : Xi=Wr*K3i+Wi*K3r     'X=SO*SS*K3
#         cr=DinvR*Xr-DinvI*Xi : ci=DinvR*Xi+DinvI*Xr     'c=X/D
# Compute a
#         ar=MLr*cr-MLi*ci : ai=MLr*ci+MLi*cr     'a=ML*c
# Compute b
#         Wr=SOr*K2r-SOi*K2i : Wi=SOr*K2i+SOi*SSr     'SO*K2
#         Xr=SSr*K1r-SSi*K1i : Xi=SSr*K1i+SSi*K1r     'SS*K1
#         Yr=Wr+Xr : Yi=Wi+Xi                    'Y=SO*K2 + SS*K1
#         br=DinvR*Yr-DinvI*Yi : bi=DinvR*Yi+DinvI*Yr     'b=Y/D

            c = (SO * SS * K3) * invD
            a = ML * c
            b = (SO * K2 + SS * K1) * invD

# Put coefficients into OSLBandx()
#         OSLBandA(calStep,0)=ar : OSLBandA(calStep,1)=ai
#         OSLBandB(calStep,0)=br : OSLBandB(calStep,1)=bi
#         OSLBandC(calStep,0)=cr : OSLBandC(calStep,1)=ci

            # Put coefficients into OSLBandx()
            self.OSLBandA[i] = a
            self.OSLBandB[i] = b
            self.OSLBandC[i] = c

#     next calStep
# end sub

# sub CalcOSLStandards

    def CalcOSLStandards(self):

#
# Calculate ref. coeff. of OSL standards
#
# The Open, Short and Load are each characterized as either a series or
# parallel RLC circuit to ground at the end of a coax delay line. This
# follows the normal format of an RLC spec used by uRLCComboResponse,
# though it is usually fairly simple.
#
# The Open is generally characterized as a time delay plus a fringe
# capacitance. The Short is generally characterized as a time delay plus
# a parallel resistance/inductance shunted to ground. The Load is
# generally characterized as a delay and resistance, and either a
# parallel capacitance or a series inductance.
#
# For each frequency in datatable, calculate the Open and Short
# response. Put the open response into OSLstdOpen() and Short response
# into OSLstdShort(), both in real, imag form.  The response is
# calculated relative to the jig or bridge R0, not the graph R0.
#
#     if S11JigType$="Trans" then R0=S21JigR0 else R0=S11BridgeR0
#     for i=0 to globalSteps :uWorkArray(i+1,0)=ReflectArray(i,0) : next i 'load frequencies into uWorkArray
#     uWorkNumPoints=globalSteps+1    'number of points is one more than number of steps
#     isErr=uRLCComboResponse(OSLOpenSpec$, R0, "S11") 'Calculate open standard response at all frequencies
#     if isErr then notice "Error in OSL standards specifications" : OSLError=1 : exit sub
#     radsPerDeg=uRadsPerDegree() 'For conversion from degrees to rads
#     for i=0 to globalSteps
#         rho=uTenPower(uWorkArray(i+1,1)/20) : theta=uWorkArray(i+1, 2)*radsPerDeg
#         OSLstdOpen(i, 0)=rho*cos(theta) : OSLstdOpen(i,1)=rho*sin(theta)    'real, imag format
#     next i

        if self.oslDbg:
            f = open("ComboResponse1.txt","w")
            f.close()
            f = open("ComboImpedance1.txt","w")
            f.close()

        # Calculate open standard response at all frequencies
        if self.S11JigType == "Trans":
            R0 = self.S21JigR0
        else:
            R0 = self.S11BridgeR0

        spec = self.OslOpenSpec
        isErr = self.uRLCComboResponse(spec, R0, "S11")
        if isErr:
            message("Error in OSL standards specifications.") # EON Jan 29, 2014
            self.OSLError = True
            return

        if self.oslDbg:
            f = open("OSLstdOpen1.txt","w")

        for i in range(self._nSteps):
            (rho, theta) = self.comboResp[i]
            rho = (10 ** (rho / 20))
            theta = theta * RadsPerDegree
            self.OSLstdOpen[i] = cmath.rect(rho, theta)
            if self.oslDbg:
                f.write("%2d, freq %7.0f, rho %10.3e, theta %9.2e, stdOpen r %10.3e, i %9.2e\n" %
                        (i, self.Fmhz[i], rho, theta, self.OSLstdOpen[i].real, self.OSLstdOpen[i].imag))
        if self.oslDbg:
            f.close()

#     isErr=uRLCComboResponse(OSLShortSpec$, R0, "S11") 'Calculate short standard response at all frequencies
#     if isErr then notice "Error in OSL standards specifications" : OSLError=1 : exit sub
#     for i=0 to globalSteps
#         rho=uTenPower(uWorkArray(i+1,1)/20) : theta=uWorkArray(i+1, 2)*radsPerDeg
#         OSLstdShort(i, 0)=rho*cos(theta) : OSLstdShort(i,1)=rho*sin(theta)    'real, imag format
#     next i

        # Calculate short standard response at all frequencies
        spec = self.OslShortSpec
        isErr = self.uRLCComboResponse(spec, R0, "S11")
        if isErr:
            message("Error in OSL standards specifications.") # EON Jan 29, 2014
            self.OSLError = True
            return

        if self.oslDbg:
            f = open("OSLstdShort1.txt","w")
        for i in range(self._nSteps):
            (rho, theta) = self.comboResp[i]
            rho = (10 ** (rho / 20))
            theta = theta * RadsPerDegree
            self.OSLstdShort[i] = cmath.rect(rho, theta)
            if self.oslDbg:
                f.write("%2d, freq %7.0f, rho %10.3e, theta %9.2e, stdShort r %10.3e, i %9.2e\n" %
                        (i, self.Fmhz[i], rho, theta, self.OSLstdShort[i].real, self.OSLstdShort[i].imag))
        if self.oslDbg:
            f.close()

#     isErr=uRLCComboResponse(OSLLoadSpec$, R0, "S11") 'Calculate load standard response at all frequencies
#     if isErr then notice "Error in OSL standards specifications" : OSLError=1 : exit sub
#     for i=0 to globalSteps
#         rho=uTenPower(uWorkArray(i+1,1)/20) : theta=uWorkArray(i+1, 2)*radsPerDeg
#         OSLstdLoad(i, 0)=rho*cos(theta) : OSLstdLoad(i,1)=rho*sin(theta)    'real, imag format
#     next i

        # Calculate short standard response at all frequencies
        spec = self.OslLoadSpec
        isErr = self.uRLCComboResponse(spec, R0, "S11")
        if isErr:
            message("Error in OSL standards specifications.") # EON Jan 29, 2014
            self.OSLError = True
            return

        if self.oslDbg:
            f = open("OSLstdLoad1.txt","w")
        for i in range(self._nSteps):
            (rho, theta) = self.comboResp[i]
            rho = (10 ** (rho / 20))
            theta = theta * RadsPerDegree
            self.OSLstdLoad[i] = cmath.rect(rho, theta)
            if self.oslDbg:
                f.write("%2d, freq %7.0f, rho %10.3e, theta %9.2e, stdLoad r %10.3e, i %9.2e\n" %
                        (i, self.Fmhz[i], rho, theta, self.OSLstdLoad[i].real, self.OSLstdLoad[i].imag))
        if self.oslDbg:
            f.close()

# end sub

# sub uS11DBToImpedance R0, S11DB, S11Deg, byRef Res, byRef React   'Calc impedance from S11

    def uS11DBToImpedance(self, R0, S11DB, S11Deg):

#     if S11DB>0 then S11DB=0 'Error condition; could happen from noise or rounding 'ver115-1e
#     m=uTenPower(S11DB/20)    'S11 Mag
#     call uRefcoToImpedance R0, m, S11Deg, Res, React    'ver115-1e

        if S11DB > 0:
            S11DB = 0
        return self.uRefcoToImpedance(R0, 10 ** (S11DB / 20), S11Deg)

# end sub

# sub uRefcoToImpedance R0, rho, theta, byRef Res, byRef React   'Calc impedance from refco: rho, theta (deg)

    def uRefcoToImpedance(self, R0, rho, theta):

#
# Calc impedance from refco: rho, theta (deg)
#
# Z(DUT)= Ro*(1+G)/(1-G), where G is the reflection coefficient
# Special case : if a=1 and b=0 (or close), treat the impedance as huge
# resistance
#     if rho<0 then rho=0    'rho<0 is error but could happen due to rounding
#     if rho>1 then rho=1 'rho should never exceed 1 but might due to noise or rounding ver115-1e

        if rho < 0:
            rho = 0
        if rho > 1:
            rho = 1

#     p=theta*uRadsPerDegree()   'S11 Radians
#     a=rho*cos(p) : b=rho*sin(p)

        p = theta * RadsPerDegree
        a = rho * cos(p)
        b = rho * sin(p)

# a near +1 means rho is near 1 and theta is near zero. We treat these
# as large resistances
#     if 0.999999<a then Res=constMaxValue : React=0 : exit sub   'ver115-4b

        if a > 0.999999:
            return complex(constMaxValue, 0)
#
#     'ver115-1h deleted additional test for a>0.99
#         'Similarly, a near -1 means we have a very small resistance or reactance. It doesn't make much difference
#         'which way we go.
#     if -0.999999>a then Res=0 : React=0 : exit sub   'ver115-4b

        if a < -0.999999:
            return complex(0, 0)

#     Rnum=a*R0+R0 : Inum=R0*b : Rden=1-a : Iden=0-b  'ver115-1e

        num = complex(a * R0 + R0, R0 * b)
        den = complex(1 - a, -b)

# Now do the divide, copying the procedure of cxDivide; faster than
# calling cxDivide First invert the denominator
#     D=Rden^2+Iden^2
#     if D<0.0000000001 then Res=constMaxValue : React=0: exit sub    'a near 1 and b near 0 ver115-1e

        if abs(den) < 0.0000000001:
            return complex(constMaxValue, 0)

#     Rinv=Rden/D : Iinv=0-Iden/D
# Now multiply Rnum+jInum times Rinv+jIinv
#     Res=Rnum*Rinv-Inum*Iinv
#     React=Rnum*Iinv+Inum*Rinv

        Z = num / den

#     if Res<0.001 then Res=0 'avoids printing tiny values
#     if React>-0.001 and React<0.001 then React=0 'avoids printing tiny values

        if Z.real < 0.001:
            Z = complex(0, Z.imag)
        if Z.imag > -0.001 and Z.imag < 0.001:
            Z = complex(Z.real, 0)
        return Z

# end sub

# sub uImpedanceToRefco R0, R, I, byref rho, byref theta 'Calc reflection coefficient as mag/angle from impedance

    def uImpedanceToRefco(self, R0, Z):

# Refco = (Z - R0) / (Z + R0)
#     if R<0 then rho=1 : theta=180 : exit sub  'Negative resistance is error; we return refco of -1, which is right for R=0 ver115-1e

        if R0 < 0:
            return(1, 180)

#     Rnum=R-R0 : Inum=I : Rden=R+R0 : Iden=I
# Now do the divide, copying the procedure of cxDivide; faster than calling cxDivide
# First invert the denominator
#     D=Rden^2+Iden^2
#     if D=0 then Rres=constMaxValue : Ires=0: exit sub
#     Rinv=Rden/D : Iinv=0-Iden/D
# Now multiply Rnum+jInum times Rinv+jIinv
#     refR=Rnum*Rinv-Inum*Iinv
#     refI=Rnum*Iinv+Inum*Rinv

        try:
            Z = (Z - R0) / (Z + R0)
        except ZeroDivisionError:
            return(constMaxValue, 0)

# Convert to polar form
#     rho=sqr(refR^2+refI^2)
#     theta=uATan2(refR, refI)

        (rho, theta) = cmath.polar(Z)
        theta = theta * DegreesPerRad
        return rho, theta

# end sub

# sub uImpedanceToRefcoRI R0, R, I, byref GR, byref GI 'Calc reflection coefficient as real/imag from impedance

    def uImpedanceToRefcoRI(self, R0, Z):

# Refco = (Z - R0) / (Z + R0)
#     if R<0 then GR=-1 : GI=0 : exit sub  'Negative resistance is error; we return refco of -1, which is right for R=0 ver115-1e

        if Z.real < 0:
            return complex(-1, 0)

#     Rnum=R-R0 : Inum=I : Rden=R+R0 : Iden=I
# Now do the divide, copying the procedure of cxDivide; faster than calling cxDivide
# First invert the denominator
#     D=Rden^2+Iden^2
#     if D=0 then Rres=constMaxValue : Ires=0: exit sub
#     Rinv=Rden/D : Iinv=0-Iden/D
# Now multiply Rnum+jInum times Rinv+jIinv
#     GR=Rnum*Rinv-Inum*Iinv
#     GI=Rnum*Iinv+Inum*Rinv

        try:
            Z = (Z - R0) / (Z + R0)
        except ZeroDivisionError:
            Z = complex(constMaxValue, 0)
        return Z

# end sub

# sub uSeriesImpedanceToS21DB R0, R, I, byref db, byref deg 'Calc S21 as db, degrees for series impedance when source,load=R0

    def uSeriesImpedanceToS21DB(self, R0, Z, db, deg):

# S21(Series) = 2 * R0 / (2 * R0 + Z) = 1 / (1 + Z / (2 * R0)) this is in complex number format
#     if R<0 then R=0 'error, but could happen from noise/rounding ver115-1e
#     doubleR0=2*R0

        if Z.real < 0:
            Z = complex(0, Z.imag)

#     doubleR0=2*R0
#     call cxInvert 1+R/doubleR0, I/doubleR0, Rres, Ires
#     deg=uATan2(Rres, Ires)		'phase in degrees
#     db=10*uSafeLog10(Rres^2+Ires^2)	'magnitude in db; mult by 10 not 20, because magnitude is squared

        doubleR0 = 2 * R0
        Z = doubleR0 / (doubleR0 + Z)
        (db, deg) = polarDbDeg(Z)
        return(db, deg)

# end sub

#
# sub uShuntImpedanceToS21DB R0, R, I, delay, freq, byref db, byref deg 'Calc S21 as db, degrees for shunt impedance when source,load=R0

    def uShuntImpedanceToS21DB(self, R0, Z, delay, freq):

# If delay<>0, then we adjust for the connector length of delay ns
# If delay=0, we don't need to know freq here.
# delay is in ns. freq is in Hz
# S21(Shunt) = 2 * Z / (2 * Z + R0) this is in complex number format

#     if delay<>0 then    'ver115-1e
#         'The impedance R+jI is transformed by the transmission line into a different
#         'impedance. We find that impedance and then apply the formula to find S21(Shunt)
#         theta=0.000000360*delay*freq    'degrees
#         call uPhaseShiftImpedance 50, theta, R,I    'We assume a 50-ohm connector no matter what the jig R0. ver115-4a
#     end if

        if delay != 0:
            # The impedance R+jI is transformed by the transmission line into a different
            # impedance. We find that impedance and then apply the formula to find S21(Shunt)
            theta = 0.000000360 * delay * freq
            Z = self.uPhaseShiftImpedance(50, theta, Z) # We assume a 50-ohm connector no matter what the jig R0.

#     if R<0 then R=0 'error, but could happen from noise/rounding ver115-1e
#     call cxDivide 2*R, 2*I, R0+2*R, 2*I, Rres, Ires
#     deg=uATan2(Rres, Ires)   'phase in degrees
#     db=10*uSafeLog10(Rres^2+Ires^2)       'magnitude in db; mult by 10 not 20, because magnitude is squared

        if Z.real < 0:
            Z = complex(0, Z.imag)  #error, but could happen from noise/rounding
        Z = (2 * Z) / (2 * Z + R0)
        (db,deg) = polarDbDeg(Z)
        return db, deg

# end sub

# sub uRefcoToSeriesS21DB rho, theta, byref db, byref deg  'Calc S21 in series jig for impedance with specified relect coeff

    def uRefcoToSeriesS21DB(self, rho, theta):

# refco is reflection coefficient, mag angle; we calculate S21 for shunt
# fixture in db, angle format Reference impedance for S21 is whatever it
# was for S11; it doesn't enter into the calculation
#
# S21 = 2 * (1 - S11) / (2 + (1 - S11)); then convert S21 to db
#     if rho<0 then rho=0    'rho<0 is error but could happen due to rounding
#     if rho>1 then rho=1 'rho should never exceed 1 but might due to noise or rounding ver115-1e

        if rho < 0:
            rho = 0
        if rho > 1:
            rho = 1

#     p=theta*uRadsPerDegree()   'S11 Radians
#     a=rho*cos(p) : b=rho*sin(p) 'S11 rectangular

        p = theta * RadsPerDegree
        a = rho * cos(p)
        b = rho * sin(p)

#     if a>0.99999999 then db=-199 : deg=0 : exit sub   'close to Open so no output ver116-4k

        if a > 0.99999999:
            return -199, 0

#     oneMinusS11Real=1-a : oneMinusS11Imag=0-b
#     call cxDivide 2*oneMinusS11Real, 2*oneMinusS11Imag, 2+oneMinusS11Real, oneMinusS11Imag, S21Real, S21Imag  '2(1-S11)/(2+(1-S11))
#     deg=uATan2(S21Real, S21Imag)   'phase in degrees
#     db=10*uSafeLog10(S21Real^2+S21Imag^2)       'magnitude in db; mult by 10 not 20, because magnitude is squared
#     if db<-199 then db=-199

        oneMinusS11 = complex(1 - a, -b)
        S21 = 2 * oneMinusS11 / (2 + oneMinusS11)
        (db, deg) = polarDbDeg(S21)
        if db < -199:
            db = -199
        return db, deg

# end sub

# sub uRefcoToShuntS21DB rho, theta, byref db, byref deg  'Calc S21 in shunt jig for impedance with specified relect coeff ver116-4k

    def uRefcoToShuntS21DB(self, rho, theta):

# refco is reflection coefficient, mag angle; we calculate S21 for shunt
# fixture in db, angle format delayNS is the connector delay in the
# shunt fixture; freqHZ is the frequency in MHz.  Reference impedance
# for S21 is whatever it was for S11; it doesn't enter into the calculation
#
# S21 =2 * (1 + S11) / (2 + (1 + S11)); then convert S21 to db
#
# This assumes no connector delay in the shunt fixture. To deal with
# that, rho and theta should be calculated from the original impedance
# at the end of an appropriate transmission line, with uPhaseShiftImpedance.
#
#     if rho<0 then rho=0    'rho<0 is error but could happen due to rounding
#     if rho>1 then rho=1 'rho should never exceed 1 but might due to noise or rounding ver115-1e

        if rho < 0:
            rho = 0
        if rho > 1:
            rho = 1

#     p=theta*uRadsPerDegree()   'S11 Radians
#     a=rho*cos(p) : b=rho*sin(p) 'S11 rectangular

        p = theta * RadsPerDegree
        a = rho * cos(p)
        b = rho * sin(p)

#     if a<-0.999999999 then db=-199 : deg=0 : exit sub   'close to short so no output ver116-4k

        if a < -0.99999999:
            return -199, 0

#     onePlusS11Real=1+a : onePlusS11Imag=b
#     call cxDivide 2*onePlusS11Real, 2*onePlusS11Imag, 2+onePlusS11Real, onePlusS11Imag, S21Real, S21Imag  '2(1+S11)/(2+(1+S11))
#     deg=uATan2(S21Real, S21Imag)   'phase in degrees
#     db=10*uSafeLog10(S21Real^2+S21Imag^2)       'magnitude in db; mult by 10 not 20, because magnitude is squared
#     if db<-199 then db=-199

        onePlusS11 = complex(1 + a, b)
        S21 = 2 * onePlusS11 / (2 + onePlusS11)
        (db, deg) = polarDbDeg(S21)
        if db < -199:
            db = -199
        return db, deg

# end sub
#
# function uParseRLC(spec$, byref connect$, byref R, byref L, byref C, byref QL, byref QC, byRef D, byref coaxSpecs$)  'Parse spec for parallel or series RLC; return 1 if error

    def uParseRLC(self, spec):

# spec$ describes a series or parallel combo of R, L and C, possibly at
# the end of a transmission line described per CoaxParseSpecs or by the
# delay factor D. It is in this form:
#
# RLC[S, R25, L10n, C200p, QL10, QC10, D2], Coax[xxx,xxx...]
#
# First item is S for series or P for parallel, referring to the RLC
# combination Remaining items are optional; one R,L,C QL, QC, and D are
# allowed; remaining items are data for coax cable.  Coax data is
# returned as a string, without the "Coax" or brackets, in coaxSpecs$ R,
# L, C and D are in ohms, Henries, Farads and seconds. Multiplier
# characters (k, u, n, etc.) are allowed.  QL and QC are the Q values
# for the L and C D is the delay in seconds (one-way) prior to the
# terminating components. It can be used only if there are no coax specs
# and is forced to 0 if there are.  We return the specified values, and
# return a function value of 0 for no error, 1 for error

#     tagPos=instr(spec$, "RLC")  'find RLC tag
#     if tagPos=0 then
#         RLC$=""
#     else
#         openBracket=instr(spec$, "[", tagPos)   'find open bracket after RLC
#         closeBracket=instr(spec$, "]", tagPos)  'find close bracket after RLC
#         if closeBracket=0 or closeBracket=0 or openBracket>=closeBracket then uParseRLC=1 : exit function
#         RLC$=Mid$(spec$, openBracket+1, closeBracket-openBracket-1) 'Get data in brackets
#     end if

        m = re.match("RLC\\[(.+?)\\]", spec)
        if m == None:
            RLC = ""
        else:
            RLC = m.group(1)

#
#     tagPos=instr(spec$, "Coax")  'find Coax tag
#     if tagPos=0 then
#         coaxSpecs$=""
#     else
#         openBracket=instr(spec$, "[", tagPos)   'find open bracket after Coax
#         closeBracket=instr(spec$, "]", tagPos)  'find close bracket after Coax
#         if closeBracket=0 or closeBracket=0 or openBracket>closeBracket-1 then uParseRLC=1 : exit function
#         coaxSpecs$=Mid$(spec$, openBracket+1, closeBracket-openBracket-1) 'Get data in brackets
#     end if

        m = re.match("Coax\\[(.+?)\\]", spec)
        if m == None:
            coaxSpec = ""
        else:
            coaxSpec = m.group(1)

#      'ver116-4i changed the defaults for backward compatibility with old method to specify OSL standards
#     connect$="P" : R=constMaxValue : L=constMaxValue : C=0 : D=0  'default is series RLC with high impedance and no delay
#     QL=100000 : QC=100000 'ver116-4i
#     commaPos=0
#     if RLC$<>"" then
#         specLen=len(RLC$)
#         isErr=0
#         while commaPos<specLen
#             oldCommaPos=commaPos
#             commaPos=instr(RLC$,",", commaPos+1)
#             if commaPos=0 then commaPos=specLen+1     'Pretend comma follows the string
#             compon$=Trim$(Mid$(RLC$,oldCommaPos+1, commaPos-oldCommaPos-1))   'get this component spec
#             if compon$="" then exit while  'get next word; done if there is none
#             firstChar$=Left$(compon$,1)   'data tag, single character
#             if firstChar$="Q" then
#                 tag$=Left$(compon$,2)   'QL or QC is two characters
#                 data$=Mid$(compon$,3)   'From third character to end
#                 if data$<>"" then v=uValWithMult(data$)   'Value of everything after first char
#             else
#                 tag$=firstChar$
#                 data$=Mid$(compon$,2)   'From second character to end
#                 if data$<>"" then v=uValWithMult(data$)   'Value of everything after first char
#             end if
#             select tag$   'Assign value to proper variable
#                 case "S"
#                     connect$="S"
#                     R=0 : L=0 : C=constMaxValue 'Defaults in case any components are not specified
#                 case "P"
#                     connect$="P"
#                     R=constMaxValue : L=constMaxValue : C=0 'Defaults in case any components are not specified
#                 case "R"
#                     R=v : if R<0 then isErr=1
#                 case "L"
#                     L=v
#                 case "C"
#                     C=v
#                 case "QL"  'ver151-4b
#                     QL=v : if QL<=0 then isErr=1
#                 case "QC"   'ver151-4b
#                     QC=v : if QC<=0 then isErr=1
#                 case "D"   'ver16-4i
#                     if coaxSpecs$="" then D=v   'Record D only if no coax specs
#                 case else   'Invalid component spec
#                     isErr=1
#             end select
#             if connect$="" or isErr then uParseRLC=1 : exit function
#         wend
#     end if  'end RLC

        connect = "P"
        R = constMaxValue
        L = constMaxValue
        C = 0
        D = 0
        QL = 100000
        QC = 100000
        isErr = False
        args = re.split(", *",RLC)
        for val in args:
            m = re.match("([A-Z]+)(.*)",val)
            tag = m.group(1)
            v = m.group(2)
            if tag == "S":
                connect = "S"
                R = 0
                L = 0
                C = constMaxValue
            elif tag == "P":
                connect = "P"
                R = constMaxValue
                L = constMaxValue
                C = 0
            elif v != "":
                v = floatSI(v)
                if tag == "R":
                    R = v
                elif tag == "L":
                    L = v
                elif tag == "C":
                    C = v
                elif tag == QL:
                    QL = v
                elif tag == QC:
                    QC = v
                elif tag == "D":
                    if coaxSpec == "":
                        D = v
                else:
                    isErr = True
            else:
                isErr = True
        return isErr, connect, R, L, C, QL, QC, D, coaxSpec

#     uParseRLC=0
# end function

# sub uComboImpedance connect$, R, L, C, QL, QC, freq, byref Zr, byref Zi   'Calc impedance Zr+j*Zi for RLC combo

    def uComboImpedance(self, connect, R, L, C, QL, QC, freq):

# connect = P for parallel, S for series. R, L and C are connected in
# series or parallel.  For Series circuit, C>=constMaxvalue means treat
# C as a short--there is no C in the circuit For Parallel circuit,
# L>=constMaxValue means treat L as open--there is no L in the circuit
# Units are ohms, Henries, Farads, Hz. Same results are achieved with
# ohms, uh, uf and MHz.  QL is Q of inductor; QC is Q of capacitor
# (Q=reactance/resistance)
#
#     twoPiF=2*uPi()*freq
#     if QC<=0 then QC=0.000001   'avoids problems below
#     if QL<=0 then QC=0.000001

        if self.oslDbg:
            f = open("ComboImpedance1.txt","a")
            f.write("%8.0f %s %5.0f %5.0f %5.0f %5.0f %5.0f\n" % (freq, connect, R, L, C, QL, QC))

        twoPiF = 2 * pi * freq
        if QC <= 0:
            QC = 0.000001
        if QL <= 0:
            QC = 0.000001

#     if freq<>0 and abs(L)<constMaxValue then 'If freq=0, we already have Ai=0; also, ignore huge parallel L
#         ZLi=twoPiF*L :ZLr=ZLi/QL     'Inductor impedance, imag and real, with Q
#     else
#         ZLi=constMaxValue : ZLr=0
#     end if

        if freq != 0 and abs(L) < constMaxValue:
            ZLi = twoPiF * L
            ZL = complex(ZLi / QL, ZLi)
        else:
            ZL = complex(0, constMaxValue)

#     if freq<>0 and C<>0 then    'Ignore C if freq or C is zero, because huge reactance in parallel is irrelevant
#         ZCi=-1/(twoPiF*C) :ZCr=abs(ZCi)/QC     'Capacitor impedance, imag and real, with Q
#     else    'zero freq or C; note that series connection ignores these
#         ZCi=0-constMaxValue : ZCr=0
#     end if

        if freq != 0 and C != 0:
            ZCi = -1 / (twoPiF * C)
            ZC = complex(abs(ZCi) / QC, ZCi)
        else:
            ZC = complex(0, -constMaxValue)

#
#     if connect$="S" then
#         Zr=R+ZLr
#         Zi=ZLi
#         if C=0 or freq=0 then
#             Zi=0-constMaxValue
#         else
#             if abs(C)<constMaxValue then Zi=Zi+ZCi : Zr=Zr+ZCr
#         end if

        if connect == "S":
            Z = R + ZL
            if C == 0 or freq == 0:
                Z = complex(0, -constMaxValue)
            else:
                if abs(C) < constMaxValue:
                    Z = Z + ZC

#     else 'this section modver115-1a
#         if R=0 or L=0 or abs(C)>=constMaxValue then  'parallel with a zero-ohm component
#             Zr=0 : Zi=0
#         else
#             'Parallel Add admittances and then invert
#             Ar=1/R
#             if freq=0 or abs(L)>=constMaxValue then
#                 Ai=0        'Parallel inductance is huge so C will determine the reactance
#             else
#                 call cxInvert ZLr, ZLi, YLr, YLi 'convert to admittance
#                 Ar=Ar+YLr : Ai=YLi      'Add to resistor admittance
#             end if
#             if C=0 then
#                 YCr=0 : YCi =0  'causes cap to be ignored
#             else
#                 call cxInvert ZCr, ZCi, YCr, YCi 'convert to admittance
#             end if
#             Ar=Ar+YCr : Ai=Ai+YCi      'Add to resistor plus inductor admittance
#
#             call cxInvert Ar, Ai, Zr, Zi     'Invert admittance to get impedance of combined circuit
#         end if
#     end if

        else:
            # Parallel Add admittances and then invert
            if (R == 0) or (L == 0) or (abs(C) >= constMaxValue):
                Z = complex(0, 0)
            else:
                A = complex(1 / R, 0)
                if freq == 0 or abs(L) >= constMaxValue:
                    A = complex(A.real, 0) # Parallel inductance is huge so C will determine the reactance
                else:
                    YL = 1 / ZL
                    A = A.real + YL
                if C == 0:
                    YC = complex(0, 0)
                else:
                    YC = 1 / ZC
                A = A + YC
                Z = 1 / A

#     if Zi>constMaxValue then Zi=constMaxValue       'ver115-4h imposed limits
#     if Zi<0-constMaxValue then Zi=0-constMaxValue
#     if Zr>constMaxValue then Zr=constMaxValue

        if self.oslDbg:
            f.write("%10.3e %10.3e\n" % (Z.real, Z.imag))
        if Z.imag > constMaxValue:
            Z = complex(Z.real,constMaxValue)
        if Z.imag < -constMaxValue:
            Z = complex(Z.real, -constMaxValue)
        if Z.real > constMaxValue:
            Z = complex(constMaxValue, Z.imag)
        if Z.real < 0:
            Z = complex(0,Z.imag)
        if self.oslDbg:
            f.write("%10.3e %10.3e\n" % (Z.real, Z.imag))
            f.close()
        return Z

# end sub

# function uRLCComboResponse(spec$, Z0, jig$)

    def uRLCComboResponse(self, spec, Z0, jig):

#
# Calc S21 or S11 response of RLC combo; return 1 if error
# spec$ describes the RLC combo, per uParseRLC
#
# We use the frequencies in uWorkArray (MHz) and calculate S11 or S21
# (db/degrees) for the specified RLC combo We store the resulting db in
# uWorkArray(N, 1) and degrees in uWorkArray(N,2) uWorkArray has
# uWorkNumPoints valid frequency points.  RLC combo connected per
# connect is tested at ref resistance R0 for S21 or S11 If jig == "S11"
# we do S11; if "S21Shunt" we do S21 for shunt connection; otherwise we
# do S21 for series connection.  We calculate the actual S21 or S11
# response that would have been produced by the combination after a
# theoretical perfect calibration is applied. Thus, we do not include
# the effect of S21JigShuntDelay, because that effect would be removed
# by calibration.
#
#     isErr=uParseRLC(spec$, connect$, R, L, C, QL,QC, D, coaxSpecs$)
#     if isErr=0 then isErr=CoaxParseSpecs(coaxSpecs$, R0, VF, K1, K2, lenFeet) 'ver115-5d
#     if isErr or Z0<=0 or R0<=0 then uRLCComboResponse=1 : exit function 'ver115-4a

        (isErr, connect, R, L, C, QL, QC, D, coaxSpecs) = self.uParseRLC(spec)
        if not isErr:
            if coaxSpecs != "":
                from coax import Coax
                (isErr, R0, VF, K1, K2, lenFeet) = Coax.CoaxParseSpecs(coaxSpecs)
            else:
                R0 = 50

#     twoPi=2*uPi()
# Note R0 is the impedance of any transmission line in the RLC combo; Z0 is the reference impedance for
# calculating S11 or S21. Both are pure resistances.
#     for i=1 to uWorkNumPoints       'uWorkNumPoints contains the number of frequency points in uWorkArray
#         freq=uWorkArray(i,0)*1000000
#         'if freq<0 then freq=0-freq  'Make frequencies positive delver115-1a
#         call uComboImpedance connect$, R, L, C, QL,QC,freq, RLCZr, RLCZi  'ver115-4b
#         if coaxSpecs$="" and D=0 then   'Simple case--no coax and no delay factor
#             ZReal=RLCZr : ZImag=RLCZi
#         else 'Get impedance of coax terminated by the RLC
#             if jig$="S11" or jig$="S21Shunt" then
#                 if coaxSpecs$<>"" then  'Presence of coax overrides the delay factor
#                     call CoaxTerminatedZFromSpecs coaxSpecs$, uWorkArray(i,0), RLCZr, RLCZi, ZReal, ZImag
#                 else    'Here apply delay factor D (sec) instead of a coax delay ver116-4i
#                     call uImpedanceToRefco R0, RLCZr, RLCZi, rho, theta       'convert to refco
#                     phaseDelay=D*360*freq         'phase delay (deg)=delay(sec)*degrees/cycle*cycles/sec
#                     theta=theta-2*phaseDelay      'Delay reflection by twice phaseDelay, for round trip.
#                     call uRefcoToImpedance R0, rho, theta, ZReal, ZImag
#                 end if
#             else
# Series S21. Any terminating impedance is deemed to be in series, but if the transmission
# line specs are not blank the termination is ignored and the coax is used by itself
#                 if coaxSpecs$<>"" then call CoaxS21FromSpecs Z0, 0, coaxSpecs$, uWorkArray(i,0), db, theta 'ver115-4e
#             end if
#         end if

        if self.oslDbg:
            f = open("ComboResponse1.txt","a")
            f.write("%s, %f, %s, %s, R0 - %f, R - %f, L - %f, C - %f, %f %f\n" % 
                    (spec, Z0, jig, connect, R0, R, L, C, QL, QC))
        for i in range(self._nSteps):
            freq = self.Fmhz[i] * 1e6
            RLCZ = self.uComboImpedance(connect, R, L, C, QL, QC, freq)
            if coaxSpecs == "":
                Z = RLCZ
            else:
                if jig == "S11" or jig == "S21Shunt":
                    if coaxSpecs != "":
                        Z = Coax.CoaxTerminatedZFromSpecs(coaxSpecs, freq, RLCZ) # EON Jan 29, 2014
                    else:
                        (rho, theta) = self.uImpedanceToRefco(R0, RLCZ)
                        phaseDelay = D * 360 * freq    #phase delay (deg)=delay(sec)*degrees/cycle*cycles/sec
                        theta = theta - 2 * phaseDelay #Delay reflection by twice phaseDelay, for round trip.
                        Z = self.uRefcoToImpedance(R0, rho, theta)
                else:
                    if coaxSpecs != "":
                        (db, theta) = Coax.CoaxS21FromSpecs(Z0, 0, coaxSpecs, freq) # EON Jan 29, 2014

#         if jig$="S11" then
#             call uImpedanceToRefco Z0, ZReal, ZImag, rho, theta   'Impedance to reflection coefficient
#             db=20*uSafeLog10(rho)   'rho to db
#         else
#             if jig$="S21Shunt" then
#                 call uShuntImpedanceToS21DB Z0, ZReal, ZImag, 0,freq, db, theta 'ver115-4h--Removed S21JigShuntDelay
#             else
# Series S21. If no coax, we use the RLC values in series. If coax,
# we ignore "termination" and just use the S21 (db, theta) calculated above
#                 if coaxSpecs$="" then call uSeriesImpedanceToS21DB Z0, ZReal, ZImag, db, theta 'ver115-1e
#             end if
#         end if

            if jig == "S11":
                (rho, theta) = self.uImpedanceToRefco(Z0, Z)
                db = 20 * uSafeLog10(rho)
            else:
                if jig == "S21Shunt":
                    (db, theta) = self.uShuntImpedanceToS21DB(Z0, Z, 0, freq)
                else:
                    if coaxSpecs == "":
                        (db,theta) = self.uSeriesImpedanceToS21DB(Z0, Z)

#         theta=theta mod 360
#         if theta<=-180 then theta=theta+360  'Put angle in bounds
#         if theta>180 then theta=theta-360
#         uWorkArray(i, 1)=db : uWorkArray(i,2)=theta 'Store db, degrees in uWorkArray

            theta = theta % 360
            if theta <= -180:
                theta = theta + 360
            if theta > 180:
                theta = theta - 360
            if self.oslDbg:
                f.write("%2d, %7.0f, %10.3e, %10.3e, %10.3e, %10.3e\n" % (i, freq, RLCZ.real, RLCZ.imag, db, theta))
            self.comboResp[i] = (db, theta)
        if self.oslDbg:
            f.close()

#     next i
#     uRLCComboResponse=0  'no error
# end function

#sub uPhaseShiftImpedance R0, theta, byref Zr, byref Zi   'Calc impedance of trans line terminated by Zr+j*Zi; replace Zr, Zi

    def uPhaseShiftImpedance(self, R0, theta, Z):

# Theta is in degrees, and can be positive or negative.
#
# If an impedance Z is placed at the end of a transmission line of
# characteristic impedance R0, with a length that causes (one-way)
# phase delay of theta degrees, then the impedance at the input of
# the transmission line is:
#
# newZ=R0*(Z + j*R0*tan(theta))/(R0 + j*Z*tan(theta))
#
# This equation also works with negative theta, which effectively
# calculates the impedance that would produce Zr+jZi after the
# transformation caused by the transmission line with length
# abs(theta).
#
#    while theta>180 : theta=theta-360 : wend
#    while theta<-180 : theta=theta+360 : wend

        theta = uNormalizeDegrees(theta)

#    TanTheta=0
#    if abs(theta-90)<.00000001 then TanTheta=1e9    'near 90; use huge value for tangent
#    if abs(theta+90)<.00000001 then TanTheta=-1e9   'near -90 use huge negative value for tangent
#    if TanTheta=0 then TanTheta=tan(theta*uRadsPerDegree())

        TanTheta=0
        if abs(theta - 90) < .00000001:
            TanTheta = 1e9
        if abs(theta + 90) < .00000001:
            TanTheta=-1e9
        if TanTheta == 0:
            TanTheta=tan(theta * RadsPerDegree)

#    Rnum=Zr : Inum=Zi+R0*TanTheta
#    Rden=R0-Zi*TanTheta : Iden=Zr*TanTheta  'denominator.

        Znum = complex(Z.real, Z.imag + R0 * TanTheta)
        Zden = complex(R0 - Z.imag * TanTheta, Z.real * TanTheta)

#    if abs(Rden)<0.000000001 and abs(Iden)<0.000000001 then
#        Zr=1e9 : Zi=0   'This can only happen if TanTheta=-R0/Zi and Zr=0
#    else
#        call cxInvert Rden,Iden, Rinv, Iinv     'Invert denominator into Rinv+j*Iinv
#        Zr=R0*(Rnum*Rinv-Inum*Iinv)  'Multiply R0 * numerator * inverted denominator
#        Zi=R0*(Rnum*Iinv+Inum*Rinv)
#    end if

        if abs(Zden.real) < 1e-9 and abs(Zden) < 1e-9:
            Z = complex(1e9, 0)
        else:
            Z = R0 * Znum / Zden
        return Z

#
#end sub
