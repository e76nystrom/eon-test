from msaGlobal import GetMsa, isMac, SetModuleVersion
import wx
from msa import MSA
from util import floatOrEmpty, gstr, mhzStr, message
from events import LogGUIEvent
from util import StartStopToCentSpan, CentSpanToStartStop
from stepAtten import SetStepAttenuator
from theme import DarkTheme, LightTheme

SetModuleVersion("sweepDialog",("1.03","EON","03/22/2014"))
# Update from ("sweepDialog",("1.02","EON.C","03/14/2014"))

debug = False

#==============================================================================
# The Sweep Parameters modeless dialog window.

class SweepDialog(wx.Dialog):
    def __init__(self, frame):
        global msa
        msa = GetMsa()
        self.frame = frame
        self.mode = None
        self.modeCtrls = []   # JGH modeCtrls does not exist anywhere
        self.prefs = p = frame.prefs
        pos = p.get("sweepWinPos", (20, min(720, frame.screenHeight-275)))
        wx.Dialog.__init__(self, frame, -1, "Sweep Parameters", pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        c = wx.ALIGN_CENTER

        self.sizerH = sizerH = wx.BoxSizer(wx.HORIZONTAL)
        self.sizerV1 = sizerV1 = wx.BoxSizer(wx.VERTICAL)

        # Mode selection # Commented out by JGH 3/8/14
##        sizerV1.Add(wx.StaticText(self, -1, "Data Mode"), 0)
##        samples = ["0(Normal Operation)", "1(Graph Mag Cal)",
##                   "2(Graph Freq Cal)", "3(Graph Noisy Sine)",
##                   "4(Graph 1MHz Peak)"]
##        cm = wx.ComboBox(self, -1, samples[0], (0, 0), (160, -1), samples)
##        self.dataModeCM = cm
##        cm.Enable(False)
##        sizerV1.Add(cm, 0, 0)

        # Create list of Final RBW Filters
        self.finFiltSamples = samples = []
        i = 1
        for freq, bw in msa.RBWFilters:
            samples.append("P%d  %sKHz BW" % (i, gstr(bw))) # JGH 2/16/14
            i += 1

        sizerV1.Add(wx.StaticText(self, -1, "Final RBW Filter Path"), 0)

        self.RBWPath = cm1 = wx.ComboBox(self, -1, samples[0], (0, 0), \
                                         (160, -1), samples)
        sizerV1.Add(cm1, 0, wx.ALIGN_LEFT, 0)

        # Video Filters
        sizerV1.Add(wx.StaticText(self, -1, "Video Filters"), 0, wx.TOP, 2)
        # samples = ["Wide", "Medium", "Narrow", "XNarrow"]
        samples = msa.vFilterNames
        self.videoFilt = cm2 = wx.ComboBox(self, -1, samples[2], (0, 0), (100, -1), samples)
        cm2.SetSelection(p.vFilterSelindex)
        self.Bind(wx.EVT_COMBOBOX, self.calculateWait, cm2)
        sizerV1.Add(cm2, 0, wx.ALIGN_LEFT, 0)

        self.sizerV1V1 = sizerV1V1 = wx.BoxSizer(wx.VERTICAL)
        sizerV1V1.Add(wx.StaticText(self, -1, "Smith Norm"), 0, wx.TOP, 2)
        sizerV1H1 = wx.BoxSizer(wx.HORIZONTAL)
        p.graphR = p.get("graphR", 50)
        self.graphRBox = tc = wx.TextCtrl(self, -1, "%2.0f" % p.graphR, \
                                          size=(50, -1))
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        sizerV1H1.Add(tc, 0, wx.ALIGN_LEFT)
        sizerV1H1.Add(wx.StaticText(self, -1, "  ohms"), 0, c|wx.LEFT, 2)
        sizerV1V1.Add(sizerV1H1, 0, wx.LEFT)
        sizerV1.Add(self.sizerV1V1, 0, wx.LEFT)
        sizerV1.Show(sizerV1V1, False)

        sizerH.Add(sizerV1, 0, wx.ALL, 10)

        sizerV2 = wx.BoxSizer(wx.VERTICAL)
        if 0:
            # these aren't implemented yet
            self.refreshCB = chk = wx.CheckBox(self, -1, "Refresh Screen Each Scan")
            chk.Enable(False)
            sizerV2.Add(chk, 0, 0)

            self.dispSweepTimeCB = chk = wx.CheckBox(self, -1, "Display Sweep Time")
            chk.Enable(False)
            sizerV2.Add(chk, 0, 0)

            self.spurTestCB = chk = wx.CheckBox(self, -1, "Spur Test")
            chk.Enable(False)
            sizerV2.Add(chk, 0, wx.BOTTOM, 10)

        self.atten5CB = cb = wx.CheckBox(self, -1, "Attenuate 5dB")
        sizerV2.Add(cb, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.BOTTOM, 10)

        sizerV2.Add(wx.StaticText(self, -1, "Step Attenuator"), 0, c|wx.TOP)
        sizerH2 = wx.BoxSizer(wx.HORIZONTAL)
        sizerH2.Add(wx.StaticText(self, -1, "  "), 0, c|wx.RIGHT, 2)
        self.stepAttenBox = tc1 = wx.TextCtrl(self, -1, str(p.stepAttenDB), size=(40, -1))
        sizerH2.Add(tc1, 0, 0)
        sizerH2.Add(wx.StaticText(self, -1, "dB"), 0, c|wx.LEFT, 2)
        sizerV2.Add(sizerH2, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, 2)

        # Mode-dependent section: filled in by UpdateFromPrefs()
        self.modeBoxTitle = wx.StaticBox(self, -1, "")
        self.sizerVM = wx.StaticBoxSizer(self.modeBoxTitle, wx.VERTICAL)
        sizerV2.Add(self.sizerVM, 0, 0)
        sizerH.Add(sizerV2, 0, wx.ALL, 10)

        # Cent-Span or Start-Stop frequency entry
        sizerV3 = wx.BoxSizer(wx.VERTICAL)
        freqBoxTitle = wx.StaticBox(self, -1, "")
        freqBox = wx.StaticBoxSizer(freqBoxTitle, wx.HORIZONTAL)
        freqSizer = wx.GridBagSizer(2, 2)
        self.centSpanRB = rb = wx.RadioButton(self, -1, "", style= wx.RB_GROUP)
        self.skip = False
        self.Bind(wx.EVT_RADIOBUTTON, self.AdjFreqTextBoxes, rb)
        freqSizer.Add(rb, (0, 0), (2, 1), 0, 0)
        cl = wx.ALIGN_CENTER|wx.LEFT
        cr = wx.ALIGN_CENTER|wx.RIGHT
        freqSizer.Add(wx.StaticText(self, -1, "Cent"), (0, 1), (1, 1), 0, cr, 2)
        self.centBox = tc = wx.TextCtrl(self, -1, "", size=(80, -1))
        freqSizer.Add(tc, (0, 2), (1, 1), 0, 0)
        self.Bind(wx.EVT_TEXT, self.AdjFreqTextBoxes, tc)
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        freqSizer.Add(wx.StaticText(self, -1, "MHz"), (0, 3), (1, 1), 0, cl, 2)
        freqSizer.Add(wx.StaticText(self, -1, "Span"), (1, 1), (1, 1), cr, 2)
        self.spanBox = tc = wx.TextCtrl(self, -1, "", size=(80, -1))
        freqSizer.Add(tc, (1, 2), (1, 1), 0, 0)
        self.Bind(wx.EVT_TEXT, self.AdjFreqTextBoxes, tc)
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        freqSizer.Add(wx.StaticText(self, -1, "MHz"), (1, 3), (1, 1), cl, 2)
        self.startstopRB = rb = wx.RadioButton(self, -1, "")
        self.Bind(wx.EVT_RADIOBUTTON, self.AdjFreqTextBoxes, rb)
        freqSizer.Add(rb, (0, 4), (2, 1), wx.LEFT, 5)
        freqSizer.Add(wx.StaticText(self, -1, "Start"), (0, 5), (1, 1), 0,cr, 2)
        self.startBox = tc = wx.TextCtrl(self, -1, "", size=(80, -1))
        freqSizer.Add(tc, (0, 6), (1, 1), 0, 0)
        self.Bind(wx.EVT_TEXT, self.AdjFreqTextBoxes, tc)
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        freqSizer.Add(wx.StaticText(self, -1, "MHz"), (0, 7), (1, 1), 0, cl, 2)
        freqSizer.Add(wx.StaticText(self, -1, "Stop"), (1, 5), (1, 1), 0, cr, 2)
        self.stopBox = tc = wx.TextCtrl(self, -1, "", size=(80, -1))
        freqSizer.Add(tc, (1, 6), (1, 1), 0, 0)
        self.Bind(wx.EVT_TEXT, self.AdjFreqTextBoxes, tc)
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        freqSizer.Add(wx.StaticText(self, -1, "MHz"), (1, 7), (1, 1), 0, cl, 2)
        freqBox.Add(freqSizer, 0, wx.ALL, 2)
        sizerV3.Add(freqBox, 0, 0)

        # other sweep parameters
        sizerH3 = wx.BoxSizer(wx.HORIZONTAL)
        sizerH3V1 = wx.BoxSizer(wx.VERTICAL)
        sizerH3V1.Add(wx.StaticText(self, -1, "Steps/Sweep"), 0, wx.TOP, 5)
        sizerH3V1H1 = wx.BoxSizer(wx.HORIZONTAL)
        self.stepsTB = tc = wx.TextCtrl(self, -1, str(p.nSteps), size=(50, -1))
        self.Bind(wx.EVT_TEXT, self.setStepsTB, tc)
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        sizerH3V1H1.Add(tc, 0, c)
        self.continCB = chk3 = wx.CheckBox(self, -1, "Continuous")
        sizerH3V1H1.Add(chk3, 0, c|wx.LEFT, 10)
        sizerH3V1.Add(sizerH3V1H1, 0, 0)

        sizerH3V1.Add(wx.StaticText(self, -1, "Wait (ms)"), 0, wx.TOP, 2)
        sizerH3V1H2 = wx.BoxSizer(wx.HORIZONTAL)
        self.waitTB = tc = wx.TextCtrl(self, -1, str(p.wait), size=(50, -1))
        self.Bind(wx.EVT_TEXT, self.setWaitTB, tc)
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        sizerH3V1H2.Add(tc, 0, c)
        self.autoWaitCB = chk4 = wx.CheckBox(self, -1, "Auto Wait")
        chk4.Bind(wx.EVT_CHECKBOX, self.configAutoWait)
        sizerH3V1H2.Add(chk4, 0, c|wx.LEFT, 10)
        sizerH3V1.Add(sizerH3V1H2, 0, wx.ALIGN_LEFT, 0)

        sizerH3V1.Add(wx.StaticText(self, -1, "Graph Appear"), 0, wx.TOP, 2)
        samples = ["Dark", "Light"]
        self.graphAppear = cm3 = wx.ComboBox(self, -1, samples[1], (0, 0), (100, -1), samples)
        sizerH3V1.Add(cm3, 0, wx.ALIGN_LEFT, 0)

        sizerH3.Add(sizerH3V1, 0, 0)

        sizerH3V2 = wx.BoxSizer(wx.VERTICAL) # JGH 11/25/2013
        sweepBoxTitle = wx.StaticBox(self, -1, "Sweep")
        sweepSizer = wx.StaticBoxSizer(sweepBoxTitle, wx.VERTICAL)
        sweepH1Sizer = wx.BoxSizer(wx.HORIZONTAL)
        rb = wx.RadioButton(self, -1, "Linear", style= wx.RB_GROUP)
        self.linearRB = rb
        self.Bind(wx.EVT_RADIOBUTTON, self.AdjFreqTextBoxes, rb)
        sweepH1Sizer.Add(rb, 0, wx.RIGHT, 10)
        self.logRB = rb = wx.RadioButton(self, -1, "Log")
        self.Bind(wx.EVT_RADIOBUTTON, self.AdjFreqTextBoxes, rb)
        sweepH1Sizer.Add(rb, 0, 0)
        sweepSizer.Add(sweepH1Sizer, 0, 0)
        sweepH2Sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.lrRB = rb = wx.RadioButton(self, -1, "L-R", style= wx.RB_GROUP)
        sweepH2Sizer.Add(rb, 0, wx.RIGHT, 10)
        self.rlRB = rb = wx.RadioButton(self, -1, "R-L")
        sweepH2Sizer.Add(rb, 0, wx.RIGHT, 10)
        self.alternateRB = rb = wx.RadioButton(self, -1, "Alternate")
        sweepH2Sizer.Add(rb, 0, 0)
        sweepSizer.Add(sweepH2Sizer, 0, wx.TOP, 3)
        sizerH3V2.Add(sweepSizer, 0, wx.LEFT|wx.TOP, 10) # JGH 11/25/2013
        self.traceBlankCB = chk2 = wx.CheckBox(self, -1, "Trace Blanking")
        self.Bind(wx.EVT_CHECKBOX, self.TraceBlanking, chk2)
        sizerH3V2.Add(chk2, 0, wx.ALIGN_CENTER|wx.TOP, 5)

        fwdrevBoxTitle = wx.StaticBox(self, -1, "DUT Fwd/Rev")
        self.fwdrevSizer = fwdrevSizer = wx.StaticBoxSizer(fwdrevBoxTitle, wx.VERTICAL)
        # DUT Forward/Reverse
        fwdrevH1Sizer = wx.BoxSizer(wx.HORIZONTAL)
        rb = wx.RadioButton(self, -1, "Forward", style= wx.RB_GROUP)
        self.forwardFR = rb
        self.Bind(wx.EVT_RADIOBUTTON, self.SetDUTfwdrev, rb)
        fwdrevH1Sizer.Add(rb, 0, wx.RIGHT, 10)
        self.reverseFR = rb = wx.RadioButton(self, -1, "Reverse")
        self.Bind(wx.EVT_RADIOBUTTON, self.SetDUTfwdrev, rb)
        fwdrevH1Sizer.Add(rb, 4, 0)
        fwdrevSizer.Add(fwdrevH1Sizer, 4, 0)
        sizerH3V2.Add(fwdrevSizer, 0, wx.LEFT|wx.TOP|wx.EXPAND, 5)
        sizerH3V2.Show(fwdrevSizer, False, True)

        sizerH3.Add(sizerH3V2, 0, 0) # JGH 11/25/2013
        sizerV3.Add(sizerH3, 0, 0)
        self.sizerH3V1 = sizerH3V1
        self.sizerH3V2 = sizerH3V2

        # Apply, Cancel, and OK buttons
        sizerV3.Add((0, 0), 1, wx.EXPAND)
        butSizer = wx.BoxSizer(wx.HORIZONTAL)
        butSizer.Add((0, 0), 0, wx.EXPAND)
        btn = wx.Button(self, -1, "Apply")
        btn.Bind(wx.EVT_BUTTON, self.Apply)
        butSizer.Add(btn, 0, wx.ALL, 5)
        btn = wx.Button(self, -1, "One Scan")
        btn.Bind(wx.EVT_BUTTON, self.DoOneScan)
        btn.SetDefault()
        butSizer.Add(btn, 0, wx.ALL, 5)
        btn = wx.Button(self, wx.ID_CANCEL)
        btn.Bind(wx.EVT_BUTTON, self.OnClose)
        butSizer.Add(btn, 0, wx.ALL, 5)
        btn = wx.Button(self, wx.ID_OK)
        btn.Bind(wx.EVT_BUTTON, self.OnOK)
        butSizer.Add(btn, 0, wx.ALL, 5)
        sizerV3.Add(butSizer, 0, wx.ALIGN_RIGHT)
        sizerH.Add(sizerV3, 0, wx.EXPAND|wx.ALL, 10)

        # set up Close shortcut
        if isMac:
            frame.Connect(wx.ID_CLOSE, -1, wx.wxEVT_COMMAND_MENU_SELECTED,
                self.OnClose)
            frame.closeMenuItem.Enable(True)
        else:
            # TODO: Needs clarification of its purpose
            accTbl = wx.AcceleratorTable([(wx.ACCEL_CTRL, ord('W'),
                                        wx.ID_CLOSE)])
            self.SetAcceleratorTable(accTbl)
            self.Connect(wx.ID_CLOSE, -1, wx.wxEVT_COMMAND_MENU_SELECTED,
                         self.OnClose)

        # get current parameters from prefs
        self.SetSizer(sizerH)
        self.UpdateFromPrefs()
        (self.startBox, self.centBox)[p.isCentSpan].SetFocus()

    #--------------------------------------------------------------------------
    # Update all controls to current prefs.

    def UpdateFromPrefs(self):
        global msa
        p = self.prefs
        LogGUIEvent("UpdateFromPrefs start=%g stop=%g" % (p.fStart, p.fStop))
        if p.fStop < p.fStart:
            tmp = p.fStop
            p.fStop = p.fStart
            p.fStart = tmp

##        self.dataModeCM.SetValue(p.get("dataMode", "0(Normal Operation)"))

        self.RBWPath.SetValue(self.finFiltSamples[p.RBWSelindex])
        # JGH: Get RBW switch bits (Correspond directly to msa.RBWSelindex)
        self.switchRBW = p.RBWSelindex

        # JGH: Get Video switch bits  (= vFilterSelindex)
        self.vFilterSelname = p.vFilterSelname = self.videoFilt.GetValue()
        self.vFilterSelindex = p.vFilterSelindex = msa.vFilterNames.index(p.vFilterSelname)

        self.graphAppear.SetValue(p.get("graphAppear", "Light"))

##        self.syntDataCB.SetValue(p.get("syntdata", True))
        self.traceBlankCB.SetValue(p.get("bGap", True))
            

        if 0:
            # these aren't implemented yet
            self.refreshCB.SetValue(p.get("sweepRefresh", True))
            self.dispSweepTimeCB.SetValue(p.get("dispSweepTime", False))
            self.spurTestCB.SetValue(p.get("spurTest", False))
        ##self.atten5CB.SetValue(p.get("atten5", False))
        self.stepAttenBox.SetValue(str(p.stepAttenDB))

        # Mode-dependent section
        oldMode = self.mode
        newMode = msa.mode
        if oldMode != newMode:
            # delete previous mode-dependent controls, if any
            sizerVM = self.sizerVM
            sizerVM.Clear(deleteWindows=True)
            self.sizerH3V2.Show(self.fwdrevSizer, False, True)
            self.sizerV1.Show(self.sizerV1V1, False, True)

            # create new mode-dependent controls
            c = wx.ALIGN_CENTER
            ch = wx.ALIGN_CENTER_HORIZONTAL
            if newMode == MSA.MODE_SA:
                # Spectrum Analyzer mode
                self.modeBoxTitle.SetLabel("Signal Generator")
##                sizerVM.Add(wx.StaticText(self, -1, "Sig Gen Freq"), ch, 0)
                sizerH = wx.BoxSizer(wx.HORIZONTAL)
                tc = wx.TextCtrl(self, -1, str(p.sigGenFreq), size=(80, -1))
                self.sigGenFreqBox = tc
                sizerH.Add(tc, 0, 0)
                sizerH.Add(wx.StaticText(self, -1, "MHz"), 0, c|wx.LEFT, 2)
                sizerVM.Add(sizerH, 0, 0)

            elif newMode == MSA.MODE_SATG:
                # Tracking Generator mode
                self.modeBoxTitle.SetLabel("Tracking Generator")
                self.tgReversedChk = chk = wx.CheckBox(self, -1, "Reversed")
                chk.SetValue(p.get("normRev", 0))
                sizerVM.Add(chk, 0, ch|wx.BOTTOM, 4)
                sizerH = wx.BoxSizer(wx.HORIZONTAL)
                sizerH.Add(wx.StaticText(self, -1, "Offset"), 0, c|wx.RIGHT, 2)
                tc = wx.TextCtrl(self, -1, str(p.tgOffset), size=(40, -1))
                self.tgOffsetBox = tc
                sizerH.Add(tc, 0, 0)
                sizerH.Add(wx.StaticText(self, -1, "MHz"), 0, c|wx.LEFT, 2)
                sizerVM.Add(sizerH, 0, 0)

            else:
                # VNA modes
                self.modeBoxTitle.SetLabel("VNA")
                st = wx.StaticText(self, -1, "PDM Inversion (deg)")
                sizerVM.Add(st, 0, c, 0)
                tc1 = wx.TextCtrl(self, -1, str(p.invDeg), size=(60, -1))
                self.invDegBox = tc1
                sizerVM.Add(tc1, 0, ch|wx.ALL, 2)
                st = wx.StaticText(self, -1, "Plane Extension")
                sizerVM.Add(st, 0, c|wx.TOP, 4)

                sizerH = wx.BoxSizer(wx.HORIZONTAL)
                sizerH.Add(wx.StaticText(self, -1, "  "), 0, c|wx.RIGHT, 2)
                tc2 = wx.TextCtrl(self, -1, str(p.planeExt[0]), size=(40, -1))
                self.planeExtBox = tc2
                sizerH.Add(tc2, 0, 0)
                sizerH.Add(wx.StaticText(self, -1, "ns"), 0, c|wx.LEFT, 2)
                sizerVM.Add(sizerH, 0, ch|wx.ALL, 2)

                # plane extensions for 2G and 3G bands are relative to 1G's
                st = wx.StaticText(self, -1, "PE Adjustments")
                sizerVM.Add(st, 0, c|wx.TOP, 4)
                sizerH = wx.BoxSizer(wx.HORIZONTAL)
                self.planeExt2G3GBox = []
                planeExt2G3G = [x - p.planeExt[0] for x in p.planeExt[1:]]
                for i, planeExt in enumerate(planeExt2G3G):
                    sizerH.Add(wx.StaticText(self, -1, " %dG:" % (i+2)), 0, \
                               c|wx.RIGHT, 2)
                    sizerH.Add((2, 0), 0, 0)
                    tc2 = wx.TextCtrl(self, -1, str(planeExt), size=(40, -1))
                    self.planeExt2G3GBox.append(tc2)
                    sizerH.Add(tc2, 0, 0)
                sizerH.Add(wx.StaticText(self, -1, "ns"), 0, c|wx.LEFT, 2)
                sizerVM.Add(sizerH, 0, ch|wx.ALL, 2)

                self.sizerH3V2.Show(self.fwdrevSizer, True, True)

                # For reflection only, Graph R()
                if msa.mode == MSA.MODE_VNARefl:
                    self.sizerV1.Show(self.sizerV1V1, True)

            self.mode = newMode
            sizerVM.Layout()

        tmp = self.skip
        self.skip = True
        # Cent-Span or Start-Stop frequency entry
        isCentSpan = p.get("isCentSpan", True)
        self.centSpanRB.SetValue(isCentSpan)
        fCent, fSpan = StartStopToCentSpan(p.fStart, p.fStop, p.isLogF)
        self.centBox.SetValue(mhzStr(fCent))
        self.spanBox.SetValue(mhzStr(fSpan))
        self.startstopRB.SetValue(not isCentSpan)
        self.startBox.SetValue(str(p.fStart))
        self.stopBox.SetValue(str(p.fStop))
        self.skip = tmp

        # other sweep parameters
        self.stepsTB.SetValue(str(p.nSteps))
        self.continCB.SetValue(p.get("continuous", False))
        if self.autoWaitCB.GetValue() == False: # JGH 12/18/13
            self.waitTB.SetValue(str(p.get("wait", 10)))
        else:
            self.calculateWait()
            self.autoWaitCB.SetValue(True)

        isLogF = p.get("isLogF", False)
        self.linearRB.SetValue(not isLogF)
        self.logRB.SetValue(isLogF)
        sweepDir = p.get("sweepDir", 0)
        self.lrRB.SetValue(sweepDir == 0)
        self.rlRB.SetValue(sweepDir == 1)
        self.alternateRB.SetValue(sweepDir == 2)

        self.AdjFreqTextBoxes(final=True)
        self.sizerH.Fit(self)
        
    #--------------------------------------------------------------------------

    def setStepsTB(self, event=None):
        p = self.frame.prefs
        #print("sweepDialog>410< Steps box has; ", self.stepsTB.GetValue())
        if p.cftest == False:
            p.nSteps = int(self.stepsTB.GetValue())

    #--------------------------------------------------------------------------

    def setWaitTB(self, event=None):
        p = self.frame.prefs
        p.wait = int(self.waitTB.GetValue())
        
    #--------------------------------------------------------------------------    

    def configAutoWait(self, event):  # JGH added this method
        p = self.frame.prefs
        if self.autoWaitCB.GetValue() == True:
            self.calculateWait()
        else:
            self.waitTB.ChangeValue(str(p.wait))
        
        #--------------------------------------------------------------------------

    def calculateWait(self, event=None):    # JGH added this  method
        # Set the wait time to 10 x time constant of video filter
        # With R=10K and C in uF, RC = C/100 secs and wait=C/10 secs = 100C msecs
        p = self.frame.prefs
        C = float(p.vFilterCaps[self.videoFilt.GetSelection()])
        p.wait = int(100 * C) # msecs
        if self.autoWaitCB.GetValue() == True:
            self.waitTB.ChangeValue(str(p.wait))

        #--------------------------------------------------------------------------

    def SetDUTfwdrev(self, event):  # JGH added this method
        sender = event.GetEventObject()
        p = self.frame.prefs
##        p.DUTfwdrev = sender.GetValue()
        if sender.GetValue() == 0:  # Forward
            p.switchFR = 0
        else:
            p.switchFR = 1  # Reverse

    #--------------------------------------------------------------------------

    def TraceBlanking(self, event):
        sender = event.GetEventObject()
        p = self.frame.prefs
        if sender.GetValue() == 0:  # Do not use
            p.bGap = False
        else:
            p.bGap = True  # Allow
    #--------------------------------------------------------------------------
    # Key focus changed.

    def OnSetFocus(self, event):
        tc = event.GetEventObject()
        if isMac:
            tc.SelectAll()
        self.tcWithFocus = tc
        event.Skip()
 
    #--------------------------------------------------------------------------
    # One Scan pressed- apply before scanning.

    def DoOneScan(self, event):
        if self.Apply():
            self.frame.DoExactlyOneScan()

    #--------------------------------------------------------------------------
    # Only enable selected freq text-entry boxes, and make other values track.

    def AdjFreqTextBoxes(self, event=None, final=False):
        if event and self.skip:
            return
        isLogF = self.logRB.GetValue()
        isCentSpan = self.centSpanRB.GetValue()
        self.centBox.Enable(isCentSpan)
        self.spanBox.Enable(isCentSpan)
        self.startBox.Enable(not isCentSpan)
        self.stopBox.Enable(not isCentSpan)

        if isCentSpan:
            fCent = floatOrEmpty(self.centBox.GetValue())
            fSpan = floatOrEmpty(self.spanBox.GetValue())
            if final and fSpan < 0 and self.tcWithFocus != self.stopBox:
                fSpan = 0
                self.spanBox.ChangeValue(mhzStr(fSpan))
            fStart, fStop = CentSpanToStartStop(fCent, fSpan, isLogF)
            self.startBox.ChangeValue(mhzStr(fStart))
            self.stopBox.ChangeValue(mhzStr(fStop))
        else:
            fStart = floatOrEmpty(self.startBox.GetValue())
            fStop = floatOrEmpty(self.stopBox.GetValue())
            if final and fStop < fStart:
                if self.tcWithFocus == self.startBox:
                    tmp = fStop
                    fStop = fStart
                    fStart = tmp
                    self.stopBox.ChangeValue(mhzStr(fStop))
                    self.startBox.ChangeValue(mhzStr(fStart))
            fCent, fSpan = StartStopToCentSpan(fStart, fStop, isLogF)
            self.centBox.ChangeValue(mhzStr(fCent))
            self.spanBox.ChangeValue(mhzStr(fSpan))

        if isLogF and final:
            fStart = max(fStart, 0.001)
            fStop = max(fStop, 0.001)
            self.startBox.ChangeValue(mhzStr(fStart))
            self.stopBox.ChangeValue(mhzStr(fStop))
            fCent, fSpan = StartStopToCentSpan(fStart, fStop, isLogF)
            self.centBox.ChangeValue(mhzStr(fCent))
            self.spanBox.ChangeValue(mhzStr(fSpan))

    #--------------------------------------------------------------------------
    # Grab new values from sweep dialog box and update preferences.

    def Apply(self, event=None):
        global msa
        frame = self.frame
        specP = frame.specP
        p = self.prefs
        LogGUIEvent("Apply")
##        p.dataMode = self.dataModeCM.GetValue()

        i = self.RBWPath.GetSelection()
        # JGH added in case the SweepDialog is opened and closed with no action
        if i >= 0:
            msa.RBWSelindex = p.RBWSelindex = i
        # JGH end
        (msa.finalfreq, msa.finalbw) = p.RBWFilters[p.RBWSelindex]
        p.rbw = msa.finalbw # JGH added
        p.switchRBW = p.RBWSelindex

        self.calculateWait

        i = self.videoFilt.GetSelection()
        if i>= 0:
            msa.vFilterSelindex = p.vFilterSelindex = i

        p.vFilterSelindex = self.vFilterSelindex
        p.vFilterSelname = self.vFilterSelname

        p.graphAppear = self.graphAppear.GetValue()
        p.theme = (DarkTheme, LightTheme)[p.graphAppear == "Light"]
        if 0:
            # these aren't implemented yet
            p.sweepRefresh = self.refreshCB.IsChecked()
            p.dispSweepTime = self.dispSweepTimeCB.IsChecked()
            p.spurTest = self.spurTestCB.IsChecked()
        ##p.atten5 = self.atten5CB.IsChecked()
        p.atten5 = False
        p.stepAttenDB = attenDB = floatOrEmpty(self.stepAttenBox.GetValue())
        SetStepAttenuator(attenDB)
        if self.mode == MSA.MODE_SA:
            p.sigGenFreq = floatOrEmpty(self.sigGenFreqBox.GetValue())
        elif self.mode == MSA.MODE_SATG:
            p.normRev = self.tgReversedChk.GetValue()
            p.tgOffset = floatOrEmpty(self.tgOffsetBox.GetValue())
        else:
            p.invDeg = floatOrEmpty(self.invDegBox.GetValue())
            p.planeExt = [floatOrEmpty(self.planeExtBox.GetValue())]
            p.planeExt += [floatOrEmpty(box.GetValue()) + p.planeExt[0] \
                           for box in self.planeExt2G3GBox]
        p.isCentSpan = self.centSpanRB.GetValue()
        p.nSteps = int(self.stepsTB.GetValue())
        p.continuous = self.continCB.GetValue()

        if self.autoWaitCB.GetValue() == True:   # JGH 11/27/13
            self.calculateWait()
            self.waitTB.SetValue(str(p.wait))
            if 0 or debug:
                print ("waitBox: ", self.waitBox.GetValue())
        else:
            p.wait = int(self.waitTB.GetValue())

        if p.wait < 0:
            p.wait = 0
            self.waitTB.SetValue(str(p.wait))

        p.isLogF = self.logRB.GetValue()
        self.AdjFreqTextBoxes(final=True)
        p.fStart = floatOrEmpty(self.startBox.GetValue())
        p.fStop = floatOrEmpty(self.stopBox.GetValue())

        if self.lrRB.GetValue():
            p.sweepDir = 0
        elif self.rlRB.GetValue():
            p.sweepDir = 1
        else:
            p.sweepDir = 2

        if msa.mode == MSA.MODE_VNARefl:
            graphR = float(self.graphRBox.GetValue())
            if p.graphR != graphR:
                frame.smithDlg.Destroy()
                from smithPanel import SmithDialog
                frame.smithDlg = SmithDialog(frame)
            p.graphR = graphR

        if p.fStart < -48:
            message("Start frequency out of range.")
            return False

        frame.StopScanAndWait()

        msa.NewScanSettings(p)
        frame.spectrum = None
        specP.results = None

        LogGUIEvent("Apply: new spectrum")
        frame.ReadCalPath()
        frame.ReadCalFreq()
        frame.ScanPrecheck(scan=False)
        msa.scanResults.put((0, 0, 0, 0, 0, 0, 0, 0, 0))
        return True

    #--------------------------------------------------------------------------
    # Close pressed- save parameters back in prefs and close window.

    def OnClose(self, event=None):
        frame = self.frame
        frame.closeMenuItem.Enable(False)
        self.prefs.sweepWinPos = self.GetPosition().Get()
        self.Destroy()
        frame.sweepDlg = None

    def OnOK(self, event):
        if self.Apply():
            self.OnClose()
