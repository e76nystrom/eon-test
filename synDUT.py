from msaGlobal import GetMsa, isMac, SetHardwarePresent, \
    SetModuleVersion
import wx
from numpy import angle, arange, cos, exp, \
    interp, log10, logspace, linspace, \
    pi, poly1d, sin, random, sqrt, zeros, zeros_like
from numpy.fft import fft
from msa import MSA
from util import db, floatOrEmpty, floatSI, EquivS11FromS21, \
    modDegree, si, SI_ASCII, fF, kHz, GHz, mH, MHz, Ohms, pF, pH

SetModuleVersion(__name__,("1.02","03/10/2014"))

debug = False        # set True to write debugging messages to msapy.log

#==============================================================================
# Synthetic DUT (Device Under Test) parameters Dialog, used when no MSA
# hardware is present.

class SynDUTDialog(wx.Dialog):
    def __init__(self, frame):
        global msa
        msa = GetMsa()
        self.frame = frame
        self.prefs = p = frame.prefs
        framePos = frame.GetPosition()
        frameSize = frame.GetSize()
        self.pos = p.get("syndutWinPos", (framePos.x + frameSize.x + 204,
                                framePos.y))
        wx.Dialog.__init__(self, frame, -1, "Synthetic DUT", self.pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        sizerV = wx.BoxSizer(wx.VERTICAL)
        c = wx.ALIGN_CENTER
        chb = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM

        # DUT waveform generator or circuit type choices
        choices = ["Tones", "Square", "RLC", "Crystal", "Cheb Filter",
                    "Through", "Shunt Open", "Shunt Short", "Shunt Load"]
        dutType = p.get("syndutType", "Tones")
        self.sigTypeCB = cbox = wx.ComboBox(self, -1, dutType, (0, 0), (120, -1),
                                            choices)
        self.Bind(wx.EVT_COMBOBOX, self.OnType, cbox)
        sizerV.Add(cbox, 0, c|wx.ALL, 10)

        # parameters: a 2D array of (name, label, value, used) tuples
        parms = [[("Fs",        "Fs (MHz)",     "100",      (0,1,4)),
                  ("magdb",     "Mag (dB)",     "-20",      (0,1)),
                  ("downdb",    "Down By (dB)", "-2.5",     (0,1,4)),
                  ("BW",        "BW (kHz)",     "10",       (4,))],
                 [("noisedbm",  "noise (dBm)",  "-90",      (0,1,2,3,4,5)),
                  ("R0",        "R0 ("+Ohms+")", "50",      (2,3)),
                  ("windowing", "Windowing",    "1",        (0,1)),
                  ("ripple",    "Ripple (dB)",  "1",        (4,))],
                 [("Rm",        "Rm ("+Ohms+")","10.25",    (3,)),
                  ("Lm",        "Lm (mH)",      "13.05624", (3,)),
                  ("Cm",        "Cm (fF)",      "16.823144",(3,)),
                  ("Cp",        "Cp (pF)",      "3.89",     (3,))],
                 [("Rs",        "Rs ("+Ohms+")","0",        (2,)),
                  ("Ls",        "Ls (H)",       "0",        (2,)),
                  ("Cs",        "Cs (F)",       "1",        (2,)),
                  ("isSerLs",   "LsCs in Series", "1",      (2,))],
                 [("Rsh",       "Rsh ("+Ohms+")", "1e99",   (2,)),
                  ("Lsh",       "Lsh (H)",      "0",        (2,)),
                  ("Csh",       "Csh (F)",      "1",        (2,)),
                  ("isSerLsh",  "LshCsh in Ser", "1",       (2,))],
                ]
        self.parms = parms

        # entry boxes for the parameters
        # TODO: set each box's visibility based on where used
        self.parmBoxes = {}
        sizerG2 = wx.GridBagSizer(0, 10)
        for i in range(len(parms)):
            for j in range(len(parms[0])):
                name, label, value, used = parms[i][j]
                st = wx.StaticText(self, -1, label)
                sizerG2.Add(st, (2*i, j), flag=chb)
                value = p.get("syndut_" + name, float(value))
                tc = wx.TextCtrl(self, -1, si(value, flags=SI_ASCII), \
                                 size=(80, -1), style=wx.TE_PROCESS_ENTER)
                self.Bind(wx.EVT_TEXT_ENTER, self.GenSynthInput, tc)
                tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
                tc.Bind(wx.EVT_KILL_FOCUS, self.GenSynthInput)
                self.parmBoxes[name] = tc
                sizerG2.Add(tc, (2*i+1, j), flag=c|wx.BOTTOM, border=5)
        sizerV.Add(sizerG2, 0, c|wx.LEFT|wx.RIGHT|wx.TOP, 10)

        # option checkboxes
        sizerH2 = wx.BoxSizer(wx.HORIZONTAL)
        self.noiseEn = chk = wx.CheckBox(self, -1, "Noise")
        chk.SetValue(p.get("syndutNoiseEn", False))
        chk.Bind(wx.EVT_CHECKBOX, self.GenSynthInput)
        sizerH2.Add(chk, 0, c|wx.ALL, 10)
        self.serRLCEn = chk = wx.CheckBox(self, -1, "RLC-Serial")
        chk.SetValue(p.get("syndutSerRLCEn", False))
        chk.Bind(wx.EVT_CHECKBOX, self.GenSynthInput)
        sizerH2.Add(chk, 0, c|wx.ALL, 10)
        self.shuntRLCEn = chk = wx.CheckBox(self, -1, "RLC-Shunt")
        chk.SetValue(p.get("syndutShuntRLCEn", False))
        chk.Bind(wx.EVT_CHECKBOX, self.GenSynthInput)
        sizerH2.Add(chk, 0, c|wx.ALL, 10)
        sizerV.Add(sizerH2, 0, c)

        # set the current choice and show the dialog
        if not dutType in choices:
            dutType = choices[0]
        self.sigTypeCB.SetSelection(choices.index(dutType))
        self.OnType()
        self.SetSizer(sizerV)
        sizerV.Fit(self)
        self.Show()
        self.Bind(wx.EVT_CLOSE, self.Close)

    #--------------------------------------------------------------------------
    # DUT type changed: enable its subset of parameters.

    def OnType(self, event=None):
        iType = self.sigTypeCB.GetSelection()
        parms = self.parms
        for i in range(len(parms)):
            for j in range(len(parms[0])):
                name, l, v, used = parms[i][j]
                self.parmBoxes[name].Enable(iType in used)
        self.GenSynthInput()

    #--------------------------------------------------------------------------
    # Entering a text box: select all text to make it easier to replace.

    def OnSetFocus(self, event):
        tc = event.GetEventObject()
        if isMac:
            tc.SelectAll()
        event.Skip()

    #--------------------------------------------------------------------------
    # Save current preferences on closing.

    def Close(self, event=None):
        global cb
        p = self.prefs
        p.syndutType = self.type
        p.syndutWinPos = self.GetPosition().Get()

        for parmRows in self.parms:
            for name, l, v, u in parmRows:
                value = floatSI(self.parmBoxes[name].GetValue())
                setattr(p, "syndut_" + name, value)

        p.syndutNoiseEn = self.noiseEn.GetValue()
        p.syndutSerRLCEn = self.serRLCEn.GetValue()
        p.syndutShuntRLCEn = self.shuntRLCEn.GetValue()

        # deselect syndut, leaving nothing for input
        msa.syndut = None
        SetHardwarePresent(True)
        if event:
            event.Skip()

    #--------------------------------------------------------------------------
    # Adjust magnitudes in dBm and phases in degrees, pre-uncorrecting ADC.

    def AdjustMag(self, magDbm):
        magVp = 10**(magDbm/20) * self.vsrmw
        if len(msa.magTableADC) > 0:
            # use the ADC linearity table backwards to pre-uncorrect
            magADC = interp(magDbm, msa.magTableDBm, msa.magTableADC)
        else:
            # given a linear estimate gain:
            #   mag = (self._magdata / 65536. - 0.5) * 200.
            # use the estimate backwards to uncorrect
            magADC = ((magDbm / 200) + 0.5) * 65536
        # scale ADC values to rough dBm to keep exponent in range
        magADCdB = magADC/300 - 100
        magVpAdj = 10**(magADCdB/20) * self.vsrmw
        ##print ("magDbm=", magDbm[0], "magVp=", magVp[0], "magADC=", magADC[0],
        ##      "magVpAdj=", magVpAdj[0]
        if magVpAdj == None:
            print ("AdjustMag: **** magVpAdj == None ****")
            print ("len(table)=", len(msa.magTableADC))
            print ("magDbm=", magDbm[0], len(magDbm))
        return magVpAdj

    def AdjustPhase(self, magDbm, Sdeg):
        if len(msa.magTableADC) > 0:
            # use the ADC linearity table backwards to pre-uncorrect
            diffPhase = interp(magDbm, msa.magTableADC, msa.magTablePhase)
            return modDegree(Sdeg + diffPhase)
        return Sdeg

    #--------------------------------------------------------------------------
    # Generate synthetic data for spectrum test.

    def GenSynthInput(self, event=None):
        ##print ("Generating synthetic data for spectrum test"
        self.type = sigType = self.sigTypeCB.GetValue()

        for parmRows in self.parms:
            for name, l, v, u in parmRows:
                setattr(self, name, self.parmBoxes[name].GetValue())
        p = self.prefs
        # volts peak per sqrt mW for 50 ohm
        self.vsrmw = sqrt(50/1000) * sqrt(2)
        self.msaInputDbm = -20
        self.noiseFloor = 10**(float(self.noisedbm)/20)
        serRLCEn = self.serRLCEn.GetValue()
        shuntRLCEn = self.shuntRLCEn.GetValue()

        if sigType in ("Tones", "Square"):
            # --- DUT is a waveform generator ---
            nyquist = 4 * GHz
            dt = 1 / (2*nyquist)
            n = 2**16
            t = arange(n) * dt
            f0 = float(self.Fs) * MHz
            magDbm = float(self.magdb)
            downdb = float(self.downdb)
            # generate spectrum from FFT of time domain waveform
            if sigType == "Square":
                # example: a 100 MHz -20 dBm square wave
                # should have a fundamental up by db(4/pi), or -17.90 dBm
                # then harmonics -27.45 dBm @ 300, -31.88 dBm @ 500.
                magVp = self.AdjustMag(magDbm)
                s = magVp * (2*(sin(2*pi*f0*t) > 0) - 1)
            else:
                # generate tones every Fs MHz, starting at magDbm and down
                # by downBydb each
                s = zeros_like(t)
                for i in range(30):
                    magVp = self.AdjustMag(downdb * i + magDbm)
                    if i == 10:
                        print ("GenSynth tones: i=", i, "magDbm=", magDbm, \
                                "magVp=", magVp)
                    s += magVp * sin(2*pi*f0*(i+1)*t)

            if int(floatOrEmpty(self.windowing)):
                # apply a window function to prep for FFT
                p2n = 2*pi*arange(n) / (n - 1)
                if self.windowing.upper() == "BN":
                    # Blackman-Nuttall window
                    w = 0.3635819 - 0.4891775*cos(p2n) + 0.1365995*cos(2*p2n) \
                         - 0.0106411*cos(3*p2n)
                else:
                    # Flat top window -- good for measuring dBm
                    w = 1 - 1.93*cos(p2n) + 1.29*cos(2*p2n) - \
                         0.388*cos(3*p2n) + 0.032*cos(4*p2n)
                wArea = w.sum()
                w *= n / wArea
                s *= w

            # transform into a spectrum
            nf = n/2
            self.synSpecVp = fft(s)[:nf] / nf
            self.synSpecF = 2*nyquist/MHz * arange(nf)/n

        else:
            # --- DUT emulates a circuit ---
            f0 = max(p.fStart, 0.001)
            f1 = p.fStop
            n = 2*p.nSteps + 1
            if p.isLogF:
                self.synSpecF = f = logspace(log10(f0), log10(f1), n)
            else:
                self.synSpecF = f = linspace(f0, f1, n) # JGH linspace comes from numpy
            w = 2*pi*f*MHz
            R0 = float(self.R0)

            if sigType == "Crystal":
                Rm = float(self.Rm)
                Lm = float(self.Lm) * mH
                Cm = float(self.Cm) * fF
                Cp = float(self.Cp) * pF
                print ("Crystal: Rm=", Rm, "Lm=", Lm, "Cm=", Cm, "Cp=", Cp, \
                        "f0=", f0, "f1=", f1, "n=", n)
                Xp = -1/(w*Cp)
                Xm = w*Lm - 1/(w*Cm)
                Zs = 1j*Xp * (Rm + 1j*Xm) / (Rm + 1j*(Xm + Xp))

                # DUT in series
                S21 = 1 / (Zs/(2*R0) + 1)
                # DUT shunt
                ##S21 = 1 / (R0/(2*Zsh) + 1)

            elif sigType == "RLC":
                if debug:
                    print ("RLC")
                Rs = max(floatSI(self.Rs), 0)
                Ls = max(floatSI(self.Ls), 1*pH)
                Cs = max(floatSI(self.Cs), 1*fF)
                Rsh = max(floatSI(self.Rsh), 0)
                Lsh = max(floatSI(self.Lsh), 1*pH)
                Csh = max(floatSI(self.Csh), 1*fF)
                isSerLs  = self.isSerLs = int(floatSI(self.isSerLs))
                isSerLsh = self.isSerLsh = int(floatSI(self.isSerLsh))

                Zs =  par3(Rs,  1j*w*Ls,  -1j/(w*Cs),  isSerLs)
                Zsh = par3(Rsh, 1j*w*Lsh, -1j/(w*Csh), isSerLsh)

                print ("RLC: Rs=", Rs, "Ls=", Ls, "Cs=", Cs, "ser=", isSerLs, \
                    "Rsh=", Rsh, "Lsh=", Lsh, "Csh=", Csh, "ser=", isSerLsh)

                ##print ("RLC Fixture: series=", serRLCEn, "shunt=", shuntRLCEn
                # combined series & shunt
                if serRLCEn and shuntRLCEn:
                    Zp = par2(Zsh, R0)
                    S21 = 2 * Zp / (R0 + Zs + Zp)
                elif serRLCEn:
                    # DUT in series
                    S21 = 1 / (Zs/(2*R0) + 1)
                elif shuntRLCEn:
                    # DUT shunt
                    S21 = 1 / (R0/(2*Zsh) + 1)
                else:
                    S21 = zeros_like(Zsh) + 1
                ##print ("RLC: Zs=", Zs[1], "Zsh=", Zsh[1], "S21=", S21[1]

            elif sigType == "Cheb Filter":
                # Chebyshev I filter for testing ripple measurement
                Fs = max(float(self.Fs), 0)
                BW = max(float(self.BW), 0) * kHz / MHz
                down = 10**(float(self.downdb)/20)
                ripple = 0.05 * max(float(self.ripple), 0) + 0.01
                Fa = Fs - 2*BW
                Fb = Fs + 2*BW
                ia = int(n * (Fa - f0) / (f1 - f0))
                ib = int(n * (Fb - f0) / (f1 - f0))
                iab = ib - ia
                iam = max(min(ia, n-1), 0)
                ibm = max(min(ib, n-1), 0)
                S21 = zeros(n) + 1e-10
                print ("Fa=", Fa, "n=", n, "f1=", f1, "ia=", ia, "ib=", ib)
                if (ib - ia) > 0:
                    # degree 8 Chebyshev
                    T = poly1d((128, 0, -256, 0, 160, 0, -32, 0, 1))
                    ##print T
                    x = 8*arange(float(iab))/iab - 4
                    # ripple=0.5 = -6.0 dB gives 9.511 dB

                    y = down / (ripple*T(x) + 1.001)
                    if ia > 0:
                        S21[iam:ibm] = y[0:ibm-iam]
                    else:
                        S21[:ibm] = y[-ia:ibm-ia]

            elif sigType == "Through":
                # Through -- for calibrating S21 baseline
                print ("Through")
                S21 = zeros(n) + 1+0j

            elif sigType == "Shunt Open":
                # Shunt open (and series shorted: same as Through, except
                # with opposite phase)
                S21 = zeros(n) + 1 - 1e-10-1e-10j

            elif sigType == "Shunt Short":
                # Shunt shorted
                S21 = zeros(n) + 0+0j

            elif sigType == "Shunt Load":
                # 50 ohm Shunt
                S21 = zeros(n) + (2/3)+0j

            if p.mode == MSA.MODE_VNARefl and not \
                    (p.isSeriesFix or p.isShuntFix):
                # reflectance mode: if fixture is a bridge, transform
                # S21 to S11 (here called "S21")
                S21, Z = EquivS11FromS21(S21, p.isSeriesFix, R0)
            ##print ("SynDUT: S21=", S21[0]

            synSpecVp = self.AdjustMag(db(abs(S21)) + self.msaInputDbm)
            self.synSpecVp = synSpecVp * exp(1j*angle(S21))

        # add noise floor, Vp to rough dBm, then unscale to get ADC values
        self.RegenSynthInput()

    #--------------------------------------------------------------------------
    # Regenerate synthetic data, just updating dynamic noise portion.

    def RegenSynthInput(self):
        # add a noise floor
        synSpecVp = self.synSpecVp
        if self.noiseEn.GetValue():
            n = len(synSpecVp)
            r = self.AdjustMag(db(random.random(n) * self.noiseFloor))
            synSpecVp = synSpecVp + r * exp(1j*2*pi*random.random(n))

        # Vp to rough dBm, then unscale to get ADC values again
        self.synSpecM = (db(abs(synSpecVp)/self.vsrmw) + 100) * 300
        synSpecP = angle(synSpecVp, deg=True)
        self.synSpecP = self.AdjustPhase(self.synSpecM, synSpecP) / 360 * \
                    65536

# Conditionally form a parallel circuit with elements in list.

def par2(a, b, isSeries=False):
    if isSeries:
        return a + b
    return (a*b) / (a+b)

def par3(a, b, c, isSeries=False):
    if isSeries:
        return a + b + c
    return (a*b*c) / (b*c + a*c + a*b)

