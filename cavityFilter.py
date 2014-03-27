from msaGlobal import GetLO2, SetLO2, GetMsa, SetMsa, SetModuleVersion
from msa import LO2
from util import message
import wx

SetModuleVersion("cavityFilter",("1.02","JGH_a","03/24/2014"))
# Update of
# SetModuleVersion("cavityFilter",("1.02","EON","03/11/2014"))

#==============================================================================
    # CAVITY FILTER TEST # JGH 1/26/14

class CavityFilterTest(wx.Dialog):
    def __init__(self, frame):
        global msa, LO2
        msa = GetMsa()
        self.frame = frame
        p = self.prefs = frame.prefs
        framePos = frame.GetPosition()
        pos = p.get("CavFiltTestWinPos", (framePos.x + 100, framePos.y + 100))
        wx.Dialog.__init__(self, frame, -1, "Cavity Filter Test", pos, \
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        # Keep initial values
        self.keepers = [p.nSteps, p.fStart, p.fStop, p.mode]

        text = "Scans around zero in 0.1 MHz increments, therefore the number "\
        "of steps is 10 times the span expressed in MHz. For example, if the "\
        "span is from -10 to 40 MHz, the steps = 400. If the steps are set wrong, "\
        "the proper value will be calculated by the system. Upon exit, the "\
        "system returns to the parameters that where set upon entry.\n"\
        "Sweep can be halted at any time and Sweep Parameters can be changed, "\
        "then click Continue or Restart.\n"\
        "The Cavity Filter Test window must be closed before MSA returns to normal. "\
        "Then click 'Restart'."
                           
        learnMore ="\nThis test will display the frequency response of the Coaxial "\
        "Cavity Filter. It reconfigures the MSA second local oscillator, PLO2 into "\
        "a variable oscillator rather than a fixed one.\n"\
        " This test modifies the normal MSA software to command the PLO2 "\
        "to maintain an offset from PLO1 of exactly the amount of the Final I.F. "\
        "that is, PLO2 will always be equal to PLO1+IF. The PLL2 Rcounter buffer "\
        "is commanded one time, to assure pdf will be 100 KHz; this is done "\
        "during Init after 'Restart'. "\
        "The PLO2 Ncounter buffer is commanded at each step in the sweep. "\
        "The actual frequency that is passed through the Cavity Filter is the "\
        "displayed frequency plus 1024 MHz. The Cavity Filter sweep limitations are: \n"\
        "   -the lowest frequency possible is where PLO 1 cannot legally command\n"\
        "   -(Bcounter=31, appx 964 MHz)\n"\
        "   -(PLO1 or PLO2 bottoming out at 0V is also limit, likely below 964 MHz)\n"\
        "   -the highest frequency possible is where PLO2 tops out (vco volts "\
        "near 5v, somewhere between 1050 to 1073 MHz)\n"\
        " The purpose of sweeping the cavity Filter is to determine its center "\
        "frequency with accuracy, its 3dB bandwidth (nominally 2MHz), its in-band "\
        "ripple and its attenuation to a signal image at 1034.7 (-80dBc, minimum). "\
        "This image corresponds to the second harmonic of the IF frequency"  
        self.learnMore = learnMore
        
        c = wx.ALIGN_CENTER
        
        sizerV = wx.BoxSizer(wx.VERTICAL)        
        st = wx.StaticText(self, -1, text)
        st.Wrap(560)
        sizerV.Add(st, 0, c|wx.ALL, 10)

        # Info, Test and Close buttons
        sizerG = wx.GridBagSizer(hgap=120, vgap=5)
        btn0 = wx.Button(self, -1, "Test Cavity Filter")
        sizerG.Add(btn0, (0,1), wx.DefaultSpan, wx.ALIGN_CENTER)
        btn0.Bind(wx.EVT_BUTTON, self.OnCFTest)
        btn1 = wx.Button(self, -1, "Info")
        btn1.Bind(wx.EVT_BUTTON, self.LearnMore)
        sizerG.Add(btn1, (1,0), wx.DefaultSpan, wx.ALIGN_CENTER)
##        butSizer.Add((0, 0), 0, wx.EXPAND)
##        btn2 = wx.Button(self, wx.ID_CANCEL)
##        butSizer.Add(btn2, 0, wx.ALL, 5)
        btn3 = wx.Button(self, -1, "Close")
        btn3.Bind(wx.EVT_BUTTON, self.CloseCavityFilterTest)
        sizerG.Add(btn3, (1,2), wx.DefaultSpan, wx.ALIGN_CENTER)
        sizerV.Add(sizerG, 0, c|wx.ALL, 10)

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if pos == wx.DefaultPosition:
            self.Center()
    #------------------------------------------------------------------------
    def OnCFTest(self, event=None): # JGH 2/3/14 Fully modified
        global msa, LO2
        p = self.frame.prefs
        if msa.cftest == True and GetMsa().IsScanning():
            self.frame.StopScanAndWait()

        GetMsa().cftest =True
        # Change mode to SA, set steps to 10 x Span
        self.frame.SetMode_SA()
        p.fStop = int(p.fStop) ; p.fStart = int(p.fStart)
        p.nSteps = (abs(10 * (p.fStop - p.fStart)))

        self.Refreshing = False
        self.frame.ScanPrecheck(False, True) # JGH True is for HaltAtEnd (msapy.py module)

    #------------------------------------------------------------------------

    def CloseCavityFilterTest(self, event=None):
        global msa, LO2
        # will come here when Cavity Filter Test Window is closed
        p = self.frame.prefs
        self.frame.StopScanAndWait()
        msa.cftest = False
        # Restore initial values
        p.nSteps, p.fStart,  p.fStop, mode = self.keepers
        self.frame.SetMode(mode)
        GetLO2().PLLphasefreq = p.PLL2phasefreq
        p.CavFiltTestWinPos = self.GetPosition().Get()
        self.Destroy()

    #------------------------------------------------------------------------------
    def LearnMore(self, event):
        message(self.learnMore, caption="Cavity Filter Test Backgrounder")
