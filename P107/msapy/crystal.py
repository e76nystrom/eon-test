from msaGlobal import GetMsa, SetModuleVersion
import sys, wx
from numpy import floor, isnan, pi
from wx.lib.dialogs import alertDialog
from functionDialog import FunctionDialog
from msa import MSA
from util import floatOrEmpty, gstr, MHz, Ohms, pF, si, uH
from marker import Marker

SetModuleVersion(__name__,("1.0","3/6/2014"))

#==============================================================================
# The Crystal Analysis dialog box.

class CrystAnalDialog(FunctionDialog):
    def __init__(self, frame):
        FunctionDialog.__init__(self, frame, "Crystal Analysis", "crystal")
        p = frame.prefs
        self.sizerV = sizerV = wx.BoxSizer(wx.VERTICAL)
        c = wx.ALIGN_CENTER

        global msa
        msa = GetMsa()
        if msa.mode >= MSA.MODE_VNATran:
            FsMsg = \
                "Fs is the parameter needing the most precision, and it will "\
                "be located by interpolation to find zero phase, so a step "\
                "size of 100 Hz or less likely provides sufficient accuracy."
        else:
            FsMsg = \
                "A small scan step size is important to locating Fs accurate"\
                "ly so you likely need a step size in the range 5-50 Hz."

        self.helpText = \
            "Crystal analysis will determine the motional parameters (Rm, Cm "\
            "and Lm) for a crystal. It will also determine the parallel "\
            "capacitance from lead to lead (Cp), and the series and parallel "\
            "resonant frequencies.\n\n"\
            "The crystal must be mounted in a series fixture, and you must "\
            "specify the R0 of the fixture. A regular 50-ohm fixture is "\
            "fine, but the standard for crystal analysis is 12.5 ohms.\n\n"\
            "You must enter the Crystal Analysis function with a "\
            "Transmission scan already existing, including the series "\
            "resonance peak and the -3 dB points around it. You may also "\
            "include the parallel resonance dip, or you may elect to "\
            "explicitly specify the parallel resonant frequency, which is "\
            "needed to determine Cp.\n\n"\
            "%s\n\n"\
            "You can reduce the step size by using the Zoom to Fs button, "\
            "which will rescan the area around Fs." % FsMsg

        # description
        st = wx.StaticText(self, -1, "DETERMINATION OF CRYSTAL PARAMETERS")
        sizerV.Add(st, 0, c|wx.TOP|wx.LEFT|wx.RIGHT, 10)
        st = wx.StaticText(self, -1, \
            "There must be an existing S21 scan of the crystal in a Series "\
            "Fixture. Enter the fixture R0. Select the type of scan. If "\
            "desired, click Zoom to Fs to improve the scan resolution. The "\
            "current step size is %sHz/step." % \
            si(MHz*(p.fStop - p.fStart) / p.nSteps))
        st.Wrap(600)
        sizerV.Add(st, 0, wx.ALL, 10)

        sizerG1 = wx.GridBagSizer(2, 2)
        self.fullScanRB = rb = wx.RadioButton(self, -1, \
            "The current scan extends from below the series resonance peak " \
            "to above the parallel resonance dip.", style= wx.RB_GROUP)
        rb.SetValue(True)
        self.Bind(wx.EVT_RADIOBUTTON, self.UpdateFpBoxState, rb)
        sizerG1.Add(rb, (0, 0), (1, 6))
        self.seriesScanRB = rb = wx.RadioButton(self, -1, \
            "The scan includes the series resonance peak only; the parallel" \
            " resonant frequency Fp is stated below.")
        sizerG1.Add(rb, (1, 0), (1, 6))
        self.Bind(wx.EVT_RADIOBUTTON, self.UpdateFpBoxState, rb)
        sizerV.Add(sizerG1, 0, c|wx.ALL, 10)

        # Fp entry, fixture R0, and zoom
        sizerH1 = wx.BoxSizer(wx.HORIZONTAL)
        self.FpLabel1 = st = wx.StaticText(self, -1, "Fp:")
        sizerH1.Add(st, 0, c|wx.RIGHT, 5)
        self.FpBox = tc = wx.TextCtrl(self, -1, "0", size=(80, -1))
        tc.SetInsertionPoint(2)
        sizerH1.Add(tc, 0, c)
        self.FpLabel2 = st = wx.StaticText(self, -1, "MHz")
        sizerH1.Add(st, 0, c|wx.LEFT, 5)
        sizerH1.Add((50, 0), 0, wx.EXPAND)
        self.UpdateFpBoxState()
        sizerH1.Add(wx.StaticText(self, -1, "Fixture R0:"), 0, c|wx.RIGHT, 5)
        self.R0Box = tc = wx.TextCtrl(self, -1, gstr(self.R0), size=(40, -1))
        tc.SetInsertionPoint(2)
        sizerH1.Add(tc, 0, c)
        sizerH1.Add(wx.StaticText(self, -1, Ohms), 0, c|wx.LEFT, 5)
        sizerH1.Add((50, 0), 0, wx.EXPAND)
        self.zoomToFsBtn = btn = wx.Button(self, -1, "Zoom to Fs")
        btn.Bind(wx.EVT_BUTTON, self.OnZoomToFs)
        sizerH1.Add(btn, 0, c|wx.ALL, 5)
        sizerV.Add(sizerH1, 0, c|wx.ALL, 10)

        # text box for analysis results
        self.resultsBox = rb = wx.TextCtrl(self, -1, "", size=(400, -1))
        sizerV.Add(rb, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 20)

        #  bottom row buttons
        sizerH3 = wx.BoxSizer(wx.HORIZONTAL)
        self.analyzeBtn = btn = wx.Button(self, -1, "Analyze")
        btn.Bind(wx.EVT_BUTTON, self.OnAnalyze)
        sizerH3.Add(btn, 0, c|wx.ALL, 5)
        self.rescanBtn = btn = wx.Button(self, -1, "Rescan")
        btn.Bind(wx.EVT_BUTTON, self.OnRescan)
        sizerH3.Add(btn, 0, c|wx.ALL, 5)
        sizerH3.Add((30, 0), 0, wx.EXPAND)
        self.addListBtn = btn = wx.Button(self, -1, "Add to List")
        btn.Enable(False)       # disable until we have done an analysis
        btn.Bind(wx.EVT_BUTTON, self.OnAddToList)
        sizerH3.Add(btn, 0, c|wx.ALL, 5)
        self.setIdNumBtn = btn = wx.Button(self, -1, "Set ID Num")
        btn.Bind(wx.EVT_BUTTON, self.OnSetIDNum)
        sizerH3.Add(btn, 0, c|wx.ALL, 5)
        sizerH3.Add((30, 0), 0, wx.EXPAND)
        self.helpBtn = btn = wx.Button(self, -1, "Help")
        btn.Bind(wx.EVT_BUTTON, self.OnHelpBtn)
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

    #--------------------------------------------------------------------------
    # Update the Fp setting box enable state.

    def UpdateFpBoxState(self, event=None):
        self.fullSweep = full = self.fullScanRB.GetValue()
        self.FpLabel1.Enable(not full)
        self.FpBox.Enable(not full)
        self.FpLabel2.Enable(not full)

    #--------------------------------------------------------------------------
    # Zoom frequency axis to L-R range around Fs peak. Mode set to series.

    def OnZoomToFs(self, event):
        frame = self.frame
        if msa.IsScanning():
            msa.StopScan()
        else:
            self.EnableButtons(False, self.zoomToFsBtn)
            self.rescanBtn.Enable(False)
            frame.ExpandLR()
            frame.WaitForStop()
            self.EnableButtons(True, self.zoomToFsBtn, "Zoom to Fs")
            self.fullScanRB.SetValue(False)
            self.seriesScanRB.SetValue(True)
            self.fullSweep = False

    #--------------------------------------------------------------------------
    # Analyze the scan to extract crystal parameters.

    def OnAnalyze(self, event):
        frame = self.frame
        p = frame.prefs
        specP = frame.specP
        isLogF = p.isLogF
        show = 0
        try:
            if not self.fullSweep:
                self.Fp = floatOrEmpty(self.FpBox.GetValue())

            PeakS21DB, Fdb3A, Fdb3B = self.FindPoints(self.fullSweep)
            Fs, Fp = self.Fs, self.Fp

            # Refine the value of Fs by finding the point with zero phase or
            # reactance. Reactance is best for reflection mode. The main
            # advantage of this approach is that transmission phase and
            # reflection reactance are linear near series resonance, so
            # interpolation can find Fs precisely even with a coarse scan.
            # Note: At the moment, we don't do crystal analysis in reflection
            # mode.
            if msa.mode != MSA.MODE_VNATran:
                alertDialog(self, "Analysis requires VNA Trans mode", "Error")
                return

            # initially put marker 1 at Fs
            magName = self.MagTraceName()
            trMag = specP.traces[magName]
            markers = specP.markers
            markers["1"]  = m1 =  Marker("1", magName, Fs)
            m1.SetFromTrace(trMag, isLogF)
            jP = trMag.Index(m1.mhz, isLogF)

            # will be searching continuous phase for nearest
            # multiple-of-180-deg crossing
            trPh = trMag.phaseTrace
            vals = trPh.v
            targVal = floor((vals[jP]+90) / 180.) * 180.
            if show:
                print ("targVal=", targVal, "jP=", jP, "[jP]=", vals[jP])
            # now move marker 1 to where phase zero to find exact Fs
            # search to right if phase above zero at peak
            searchR = vals[jP] > targVal
            signP = (-1, 1)[searchR]
            m1.FindValue(trPh, jP, isLogF, signP, searchR, targVal, show)
            if isnan(m1.mhz):
                m1.FindValue(trPh, jP, isLogF, -signP, 1-searchR, targVal, show)
            if 1:   # set 0 to disable zero-phase Fs use to match Basic
                Fs = m1.mhz

            specP.markersActive = True
            specP.FullRefresh()
            wx.Yield()

            self.R0 = float(self.R0Box.GetValue())

            # compute crystal parameters from measurements
            Rm, Cm, Lm, Cp, Qu, QL = \
              CrystalParameters(Fs, Fp, PeakS21DB, Fdb3A, Fdb3B, self.R0, True)
            self.Rm, self.Cm, self.Lm, self.Cp = Rm, Cm, Lm, Cp

        except RuntimeError:
            alertDialog(self, sys.exc_info()[1].message, "Analyze Error")
            return

        # show results
        self.resultsBox.SetValue("Fs=%sHz, Fp=%sHz, Rm=%s, Lm=%sH, Cm=%sF, "\
            "Cp=%sF" % (si(Fs*MHz, 9), si(Fp*MHz, 9), si(Rm, 4), si(Lm*uH),
             si(Cm*pF), si(Cp*pF)))
        self.FpBox.SetValue("%g" % Fp)
        self.addListBtn.Enable(True)
        self.haveAnalyzed = True

    #--------------------------------------------------------------------------
    # Rescan, possibly another crystal.

    def OnRescan(self, event):
        frame = self.frame
        if msa.IsScanning():
            msa.StopScan()
        else:
            self.EnableButtons(False, self.rescanBtn)
            self.zoomToFsBtn.Enable(False)
            frame.DoExactlyOneScan()
            frame.WaitForStop()
            self.EnableButtons(True, self.rescanBtn, "Rescan")

    #--------------------------------------------------------------------------
    # Copy results to "Crystal List" text window, file.

    def OnAddToList(self, event):
        p = self.frame.prefs
        rw = self.resultsWin
        if not rw:
            pos = p.get("crystalResultsWinPos", (600, 50))
            self.resultsWin = rw = TextWindow(self.frame, "CrystalList", pos)
            rw.Show()
            wx.Yield()
            self.Raise()
            rw.Write(" ID    Fs(MHz)       Fp(MHz)    Rm(ohms)   Lm(mH)" \
                     "      Cm(fF)      Cp(pF)\n")
        rw.Write("%4d %12.6f %12.6f %9.2f %11.6f %11.6f %7.2f\n" % \
            (self.id, self.Fs, self.Fp, self.Rm, self.Lm/1000, self.Cm*1000,
             self.Cp))
        self.id += 1

    #--------------------------------------------------------------------------
    # Set ID number- included in crystal results file.

    def OnSetIDNum(self, event):
        dlg = wx.TextEntryDialog(self, "Enter numeric ID for this crystal",
                "Crystal ID", "")
        if dlg.ShowModal() == wx.ID_OK:
            self.id = int(dlg.GetValue())

    #--------------------------------------------------------------------------
    # Enable/disable buttons- disabled while actively rescanning.

    def EnableButtons(self, enable, cancelBtn, label="Cancel"):
        cancelBtn.SetLabel(label)
        if enable:
            self.zoomToFsBtn.Enable(enable)
            self.rescanBtn.Enable(enable)
        self.fullScanRB.Enable(enable)
        self.seriesScanRB.Enable(enable)
        self.analyzeBtn.Enable(enable)
        self.setIdNumBtn.Enable(enable)
        if self.haveAnalyzed:
            self.addListBtn.Enable(enable)
        self.okBtn.Enable(enable)

    #--------------------------------------------------------------------------
    # Save results file upon dialog close.

    def OnClose(self, event):
        rw = self.resultsWin
        if rw:
            self.frame.prefs.crystalResultsWinPos = rw.GetPosition().Get()
            rw.Close()
        FunctionDialog.OnClose(self, event)

#------------------------------------------------------------------------------
# Calculate crystal parameters in Series or Shunt Jig.
# Can also use this for series RLC combinations; just provide a bogus Fp and
# ignore Cp.
#
# Fs: series resonance in MHz
# Fp: parallel resonance in MHz
# PeakS21DB: S21 db at Fs (a negative value in db)
# Fdb3A, Fdb3B: -3db frequencies, in MHz, around Fs;
#                   (absolute -3dB frequencies if shunt jig)
# R0: impedance of the test jig
# isSeries: True if a series jig
#
# Returns Rm, Cm(pF), Lm(uH), Cp(pF), Qu, QL

def CrystalParameters(Fs, Fp, PeakS21DB, Fdb3A, Fdb3B, R0, isSeries):
    if Fs <= 0 or Fp <= 0 or Fdb3A >= Fs or Fdb3B <= Fs:
        raise RuntimeError("Invalid frequency data for calculation:" \
                "Fs=%g Fp=%g Fdb3A=%g Fdb3B=%g" % (Fs, Fp, Fdb3A, Fdb3B))
    if R0 <= 0:
        raise RuntimeError("Invalid R0")
    S21 = 10**(-PeakS21DB/20)
    ws = 2*pi*Fs*MHz
    wp = 2*pi*Fp*MHz
    if isSeries:
        # internal crystal resistance at Fs, in ohms
        Rm = 2*R0 * (S21 - 1)
        # effective load seen by crystal--external plus internal
        Reff = 2*R0 + Rm
    else: # shunt fixture
        Rm = (R0/2) / (S21 - 1)
        Reff = R0/2 + Rm
    Rm = max(Rm, 0.001)
    BW = Fdb3B - Fdb3A
    # loaded Q at Fs
    QL = Fs / BW
    Lm = QL * Reff / ws
    Cm = 1 / (ws**2 * Lm)
    # net reactance of motional inductance and capacitance at Fp, ohms
    Xp = wp*Lm - 1/(wp*Cm)
    Cp = 1 / (wp*Xp)
    # unloaded Q is L reactance divided by series resistance
    Qu = QL * Reff / Rm
    return Rm, Cm/pF, Lm/uH, Cp/pF, Qu, QL

checkPass = True
def check(result, desired):
    global checkPass
    if abs(result - desired) > abs(result) * 0.01:
        print ("*** ERROR: expected %g, got %g" % (desired, result))
        checkPass = False
    ##else:
    ##    print ("OK. Expected %g, got %g" % (desired, result)

# To test: Use Fs = 20.015627, Fp = 20.07, PeakS21DB = -1.97,Fdb3a = 20.014599,
#           Fdb3B = 20.016655
#  (from methodology 3 in Clifton Labs "Crystal Motional Parameters")
# Results should be Rm = 6.36, Cm = 26.04 fF, Lm = 2427.9 uH, Cp = 4.79
if 0:
    Rm, Cm, Lm, Cp, Qu, QL = \
        CrystalParameters(20.015627, 20.07, -1.97, 20.014599, 20.016655, 12.5,
                            True)
    check(Rm, 6.36); check(Cm, 0.02604); check(Lm, 2427.9); check(Cp, 4.79)
    check(Qu, 47974.); check(QL, 9735.)
    if not checkPass:
        print ("*** CrystalParameters check FAILED.")

#==============================================================================
# A text window for results, savable to a file.

class TextWindow(wx.Frame):
    def __init__(self, frame, title, pos):
        self.frame = frame
        self.title = title
        wx.Frame.__init__(self, frame, -1, title, pos)
        scroll = wx.ScrolledWindow(self, -1)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.textBox = tc = wx.TextCtrl(scroll, -1, "",
                        style = wx.TE_MULTILINE|wx.HSCROLL)
        tc.SetFont(wx.Font(fontSize, wx.TELETYPE, wx.NORMAL, wx.NORMAL))
        sizer.Add(tc, 1, wx.EXPAND)
        scroll.SetSizer(sizer)
        scroll.Fit()
        scroll.SetScrollbars(20, 20, 100, 100)
        self.SetSize((600, 200))

        self.saveAsID = ident = wx.NewId()
        if isMac:
            # Mac uses existing menu but adds "Save As"
            self.Bind(wx.EVT_ACTIVATE, self.OnActivate)
        else:
            # create local menu bar for Windows and Linux
            mb = wx.MenuBar()
            menu = wx.Menu()
            menu.Append(ident, "Save As...")
            self.Connect(ident, -1, wx.wxEVT_COMMAND_MENU_SELECTED, self.SaveAs)
            mb.Append(menu, "&File")
            menu = wx.Menu()
            mb.Append(menu, "&Edit")
            self.SetMenuBar(mb)
        self.Bind(wx.EVT_CLOSE, self.OnExit)
        self.dirty = False

    #--------------------------------------------------------------------------
    # Write text to text window, appending to end.

    def Write(self, text):
        self.textBox.AppendText(text)
        self.dirty = True

    #--------------------------------------------------------------------------
    # Text box activated/deactivated: update related menus.

    def OnActivate(self, event):
        active = event.GetActive()
        frame = self.frame
        ident = self.saveAsID   # JGH 2/10/14
        if active:
            frame.fileMenu.Append(ident, "Save As...")  # JGH 2/10/14
            frame.Connect(ident, -1, wx.wxEVT_COMMAND_MENU_SELECTED, self.SaveAs)   # JGH 2/10/14
        else:
            frame.fileMenu.Remove(ident)    # JGH 2/10/14
        event.Skip()

    #--------------------------------------------------------------------------
    # Text box closed: optionally save any changed text to a file.

    def OnExit(self, event):
        if self.dirty:
            dlg = wx.MessageDialog(self, \
                "Do you want to save this to a file?", \
                "Save", style=wx.YES_NO|wx.CANCEL|wx.CENTER)
            answer = dlg.ShowModal()
            if answer == wx.ID_YES:
                self.SaveAs()
        event.Skip()

    #--------------------------------------------------------------------------
    # Save text to a file.

    def SaveAs(self, event=None):
        p = self.frame.prefs
        wildcard = "Text (*.txt)|*.txt"
        while True:
            dataDir = p.get("dataDir", appdir)
            dlg = wx.FileDialog(self, "Save file as...", defaultDir=dataDir,
                    defaultFile=self.title + ".txt", wildcard=wildcard,
                                style=wx.SAVE)
            answer = dlg.ShowModal()
            if answer != wx.ID_OK:
                break
            path = dlg.GetPath()
            p.dataDir = os.path.dirname(path)
            if ShouldntOverwrite(path, self.frame):
                continue
            f = open(path, "w")
            f.write(self.textBox.GetValue())
            f.close()
            print ("Wrote to", path)
            self.dirty = False
            break
