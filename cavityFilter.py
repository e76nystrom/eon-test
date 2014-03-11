from msaGlobal import GetLO2, GetMsa, SetModuleVersion
import wx

SetModuleVersion("cavityFilter",("1.02","EON","03/11/2014"))

#==============================================================================
    # CAVITY FILTER TEST # JGH 1/26/14

class CavityFilterTest(wx.Dialog):
    def __init__(self, frame):
        self.frame = frame
        p = self.prefs = frame.prefs
        framePos = frame.GetPosition()
        pos = p.get("CavFiltTestsWinPos", (framePos.x + 100, framePos.y + 100))
        wx.Dialog.__init__(self, frame, -1, "Cavity Filter Test", pos, \
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        self.cftest = p.cftest = 0
        sizerV = wx.BoxSizer(wx.VERTICAL)
        # panel = wx.Panel(self, -1) # JGH 2/10/14 panel not used
        st = wx.StaticText(self, -1, \
        "\nScans around zero in 0.1 MHz increments--e.g. span=10, steps=100, "\
        "span=10 to 50, or steps=span/0.1. User sets up scan, restarts, halts, "\
        "and clicks the Test Cavity Filter button. "\
        "The software will command the PLO2 to maintain an offset from PLO1 by "\
        "exactly the amount of the final IF, that is, PLO2 will always be equal"\
        "to PLO1+IF. The PLL2 Rcounter buffer is commanded one time, to assure pdf "\
        "will be 100 KHz; this is done during Init after 'Restart'. The PLO2 N"\
        "counter buffer is commanded at each step in the sweep. The actual frequency that is "\
        "passed through the Cavity Filter is the displayed frequency plus 1024 MHz. "\
        "The Cavity Filter sweep limitations are: \n"\
        "   -the lowest frequency possible is where PLO 1 cannot legally command\n"\
        "   -(Bcounter=31, appx 964 MHz)\n"\
        "   -(PLO1 or PLO2 bottoming out at 0V is also limit, likely below 964 MHz)\n"\
        "   -the highest frequency possible is where PLO2 tops out (vco volts "\
        "near 5v, somewhere between 1050 to 1073 MHz)\n"\
        "Sweep can be halted at any time and Sweep Parameters can be changed, "\
        "then click Continue or Restart.\n"\
        "The Cavity Filter Test window must be closed before MSA returns to normal. "\
        "Then click 'Restart'.")
        st.Wrap(600)
        c = wx.ALIGN_CENTER
        sizerV.Add(st, 0, c|wx.ALL, 10)

        btn = wx.Button(self, -1, "Test Cavity Filter")
        btn.Bind(wx.EVT_BUTTON, self.OnCFTest)
        sizerV.Add(btn, 0, c|wx.ALL, 5)

        # Cancel and OK buttons
        butSizer = wx.BoxSizer(wx.HORIZONTAL)
        butSizer.Add((0, 0), 0, wx.EXPAND)
        btn = wx.Button(self, wx.ID_CANCEL)
        butSizer.Add(btn, 0, wx.ALL, 5)
        btn = wx.Button(self, -1, "Close")
        btn.Bind(wx.EVT_BUTTON, self.CloseCavityFilterTest)
        butSizer.Add(btn, 0, wx.ALL, 5)
        sizerV.Add(butSizer, 0, wx.ALIGN_RIGHT|wx.ALIGN_BOTTOM|wx.ALL, 10)

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if pos == wx.DefaultPosition:
            self.Center()
    #------------------------------------------------------------------------
    def OnCFTest(self, event=None): # JGH 2/3/14 Fully modified
        p = self.frame.prefs
        if self.cftest == 1 and GetMsa().IsScanning():
            self.frame.StopScanAndWait()
        p.cftest = 1
        self.Refreshing = False
        self.enterPLL2phasefreq = p.PLL2phasefreq
        GetLO2().PLLphasefreq = p.PLL2phasefreq = .1 # JGH 2/5/14
        # Goto restart
        self.frame.ScanPrecheck(False) # JGH True is for HaltAtEnd

    #------------------------------------------------------------------------

    def CloseCavityFilterTest(self, event=None):
        # will come here when Cavity Filter Test Window is closed
        p = self.frame.prefs
        p.cftest = 0
        GetLO2().PLLphasefreq = p.PLL2phasefreq = self.enterPLL2phasefreq # JGH 2/5/14
        p.CavFiltTestWinPos = self.GetPosition().Get()
        self.Destroy()

    # JGH ends

#------------------------------------------------------------------------------
