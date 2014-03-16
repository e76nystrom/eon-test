from msaGlobal import GetHardwarePresent, GetMsa, isWin, \
    logEvents, msPerUpdate, SetCb, SetHardwarePresent, \
    SetLO1, SetLO2, SetLO3, SetModuleVersion, winUsesParallelPort
import thread, time, traceback, wx
from numpy import interp, isnan, linspace, log10, logspace, nan
from Queue import Queue
from util import divSafe, modDegree, msElapsed
from events import Event
from msaGlobal import UpdateGraphEvent
from spectrum import Spectrum

SetModuleVersion("msa",("1.02","JGH.b","03/16/2014"))

# for raw magnitudes less than this the phase will not be read-- assumed
# to be noise
# goodPhaseMagThreshold = 0x2000
goodPhaseMagThreshold = 0x0000 # Scotty will determine usefulness of this 3/2/14

debug = False
cb = None

#******************************************************************************
#****                          MSA Hardware Back End                      *****
#******************************************************************************

#==============================================================================
# Modular Spectrum Analyzer.

class MSA:
    # Major operating modes
    MODE_SA = 0
    MODE_SATG = 1
    MODE_VNATran = 2
    MODE_VNARefl = 3
    modeNames = ("Spectrum Analyzer", "Spectrum Analyzer with TG",
                 "VNA Transmission", "VNA Reflection")
    shortModeNames = ("SA", "SATG", "VNATran", "VNARefl")

    def __init__(self, frame):
        self.frame = frame
        p = frame.prefs
        self.mode = p.get("mode", self.MODE_SA) # JGH: This is the default mode for EON
        # Exact frequency of the Master Clock (in MHz).
        self.masterclock = p.get("masterclock", 64.)
        # 2nd LO frequency (MHz). 1024 is nominal, Must be integer multiple
        # of PLL2phasefreq
        self.appxLO2 = p.get("appxLO2", 1024.)
        # list of Final Filter freq (MHz), bw (kHz) pairs
        ##self.RBWFilters = p.get("RBWFilters", [(10.698375, 8)])
        # JGH changed above line for next line
        self.RBWFilters = p.get("RBWFilters", [(10.7, 300.), (10.7, 30.), (10.7, 3.), (10.7, 0.3)]) # Defaults
        # selected Final Filter index
        self.indexRBWSel = self.switchRBW = i = p.get("indexRBWSel", 0)
        # Final Filter frequency, MHz; Final Filter bandwidth, KHz
        self.finalfreq, self.finalbw = self.RBWFilters[i]
        self.bitsRBW = 4 * i  # JGH 10/31/13
        # Video Filters
        self.vFilterNames = ["Wide", "Medium", "Narrow", "XNarrow"]
        self.vFilterCaps = p.get("vFilterCaps", [0.001, 0.1, 1.0, 10.0]) # Defaults
        self.vFilterSelIndex = p.get("vFilterSelIndex", 2) # JGH This is the default mode
        self.vFilterSelName = self.vFilterNames[self.vFilterSelIndex]
        self.bitsVideo = p.get("vFilterSelIndex", 2)
        self.cftest = p.get("cftest", False)
        # Trace blanking gap
        self.bGap = p.get("bGap", False)
        
        # SG output frequency (MHz)
        self._sgout = 10.
        # =0 if TG is normal, =1 if TG is in reverse.
        self._normrev = 0
        # TG offset frequency
        self._offset = 0
        # FWD/REV and TRANS/REFL
        self.switchFR = p.get("switchFR", 0)
        self.switchTR = p.get("switchTR", 0)
        self.bitsFR = 16 * self.switchFR
        self.bitsTR = 32 * self.switchTR
        # this assures Spur Test is OFF.
        self.spurcheck = 0
        # 1, 2 or 3, indicating bands 1G, 2G and 3G
        p.switchBand = p.get("switchBand", 1)
        if p.switchBand == 0:
            self.bitsBand = 64 * 0 # Band 2
            self._GHzBand = 2
        else:
            self.bitsBand = 64 * 1 # Bands 1 and 3
            self._GHzBand = 1 # (or 3)
        # Pulse switch
            self.switchPulse = p.get("switchPulse", 0)
            self.bitsPulse = 128 * self.switchPulse
        # set when in inverted-phase mode
        self.invPhase = 0
        # amount (degrees) to subtract from phase to invert it
        self.invDeg = p.get("invDeg", 180.)    # Default on Startup
        # set when running calibration
        self.calibrating = False
        # calibration level (0=None, 1=Base, 2=Band)
        self.calLevel = p.get("calLevel", 0)
        p.calLevel = self.calLevel = 0 # EON Jan 13 2013
        # calibration arrays, if present
        self.baseCal = None # Calibration of through response with a genereric wideband sweep
        self.bandCal = None #
        # set when calibration data doesn't align with current spectrum
        self.calNeedsInterp = False
        self.oslCal = None # EON Jan 10 2014
        # set when doing a scan
        self._scanning = False
        # results from last CaptureOneStep()
        self._magdata = 0
        self._phasedata = 0
        self._Sdb = 0
        self._Sdeg = 0
        self.fixtureR0 = p.get("fixtureR0", 50)
        self.lastBand = None

        # magnitude correction table ADC values
        self.magTableADC = []
        # magnitude correction table true magnitudes
        self.magTableDBm = []
        # magnitude correction table phase adjustments
        self.magTablePhase = []
        # frequency-dependent magnitude correction table frequencies
        self.freqTableMHz = []
        # frequency-dependent magnitude correction table magnitude adjustements
        self.freqTableDBM = []

        # requested frequencies to scan
        self._fStart = None
        self._fStop = None
        self._nSteps = 0
        self._freqs = []
        self._step = 0
        # step history for maintaining continuity
        self._Hquad = 0
        self._history = []
        self._baseSdb = 0
        self._baseSdeg = 0
        # debugging events list
        self._events = []
        # error message queue, sent to GUI to display
        self.errors = Queue()
        # queue of scan results per step: Sdb, Sdeg, etc.
        self.scanResults = Queue()
        # active Synthetic DUT
        self.syndut = None  # JGH 2/8/14 syndutHook1

    #--------------------------------------------------------------------------
    # Log one MSA event, given descriptive string. Records current time too.

    def LogEvent(self, what):
        if logEvents: # EON Jan 22, 2014
            self._events.append(Event(what))

    #--------------------------------------------------------------------------
    # Dump list of events to log.

    def DumpEvents(self):
        print ("------------ MSA Events ---------------")
        for event in self._events:
            print ("%6d.%03d:" % (event.when/1000, event.when % 1000),event.what)
        print ("---------------------------------------")

    #--------------------------------------------------------------------------
    # Write debugging event lists to a file.

    def WriteEvents(self, guiEvents):
        events = [(e.when, "M  ", e.what) for e in self._events] + \
                 [(e.when, "GUI", e.what) for e in guiEvents]

        f = open("events.txt", "w")
        events.sort()
        t0 = events[0][0]
        for e in events:
            when = e[0] - t0
            f.write("%6d.%03d: %s %s\n" % (when/1000, when % 1000, e[1], e[2]))
        f.close()

    #--------------------------------------------------------------------------
    # Set major operating mode.

    def SetMode(self, mode):
        self.mode = mode

    #--------------------------------------------------------------------------
    # Return equivalent 1G frequency for f, based on _GHzBand.

    def _Equiv1GFreq(self, f):
        if self._GHzBand == 1:
            return f
        elif  self._GHzBand == 2:
            return f - LO2.freq
        else:
            return f - 2*(LO2.freq - self.finalfreq)

    #--------------------------------------------------------------------------
    # Calculate all steps for LO1 synth.

    def _CalculateAllStepsForLO1Synth(self, thisfreq, band):
        self._GHzBand = band
##        if self._GHzBand != 1:
##            # get equivalent 1G frequency
        thisfreq = self._Equiv1GFreq(thisfreq)
        # calculate actual LO1 frequency
        LO1.Calculate(thisfreq + LO2.freq - self.finalfreq)

    #--------------------------------------------------------------------------
    # Calculate all steps for LO3 synth.

    def _CalculateAllStepsForLO3Synth(self, TrueFreq, band):
        self._GHzBand = band
        if self._GHzBand == 1:
            thisfreq = TrueFreq
        else:
            # get equivalent 1G frequency
            thisfreq = self._Equiv1GFreq(TrueFreq)

        LO2freq = LO2.freq
        offset = self._offset
        if self.mode != self.MODE_SA:
            if self._normrev == 0:
                if self._GHzBand == 3:
                    # Mode 3G sets LO3 differently
                    LO3freq = TrueFreq + offset - LO2freq
                else:
                    # Trk Gen mode, normal
                    LO3freq = LO2freq + thisfreq + offset
            else:
                # Frequencies have been pre-calculated --
                # We can just retrieve them in reverse order.
                TrueFreq = self._freqs[self._nSteps - self._step]
                if self._GHzBand == 1:
                    revfreq = TrueFreq
                else:
                    # get equiv 1G freq
                    revfreq = self._Equiv1GFreq(TrueFreq)
                if self._GHzBand == 3:
                    # Mode 3G sets LO3 differently
                    LO3freq = TrueFreq + offset - LO2freq
                else:
                    # Trk Gen mode, normal
                    LO3freq = LO2freq + revfreq + offset

        else:
            # Sig Gen mode
            LO3freq = LO2freq + self._sgout

        LO3.Calculate(LO3freq)

    #--------------------------------------------------------------------------
    # _CommandAllSlims -- for SLIM Control and SLIM modules.
    # (send data and clocks without changing Filter Bank)
    #  0-15 is DDS1bit*4 + DDS3bit*16, data = 0 to PLL 1 and PLL 3.
    # (see CreateCmdAllArray). new Data with no clock,latch high,latch low,
    # present new data with clock,latch high,latch low. repeat for each bit.
    # (40 data bits and 40 clocks for each module, even if they don't need that many)
    # This format guarantees that the common clock will
    # not transition with a data transition, preventing crosstalk in LPT cable.

    
##    def _CommandAllSlims(self, f):
    def _CommandAllSlims(self):
        global cb
        p = self.frame.prefs
        f = self._freqs[0]
        band = min(max(int(f/1000) + 1, 1), 3) # JGH Initial band

        if band != self.lastBand:
            self._SetFreqBand(band)
            self.lastBand = band

        step1k = self.step1k ; step2k =self.step2k
        if p.sweepDir == 0:
            if ((step1k != None and self._step == (step1k - 1)) or \
                (step2k != None and self._step == (step2k - 1))):
                self.sendByteList()
                band = band + 1
                self._SetFreqBand(band)
                cb.msWait(100)
            else:
                self.sendByteList()
        if p.sweepDir == 1:
            if (self._step == (step1k) or self._step == (step2k)):
                self.sendByteList()
                band = band - 1
                self._SetFreqBand(band)
                cb.msWait(100)
            else:
                self.sendByteList()
    #--------------------------------------------------------------------------

    def sendByteList(self):
        global cb
        byteList = self.SweepArray[self._step]
        cb.SendDevBytes(byteList, cb.P1_Clk)    # JGH 2/9/14

        # print (">>>>> 2106, Remove data, leaving bitsRBW data to filter bank"
        #cb.SetP(1, self.bitsRBW) # JGH not needed here, instead use next line
        cb.SetP(1, 0)

        # send LEs to PLL1, PLL3, FQUDs to DDS1, DDS3, and command PDM
        # begin by setting up init word=LEs and Fquds + PDM state for thisstep
        pdmcmd = self.invPhase << cb.P2_pdminvbit
        # present data to buffer input
        cb.SetP(2, cb.P2_le1 + cb.P2_fqud1 + cb.P2_le3 + cb.P2_fqud3 + pdmcmd)
        # remove the added latch signal to PDM, leaving just the static data
        cb.SetP(2, pdmcmd)
        cb.setIdle
##        f = self._freqs[self._step]
##        band = min(max(int(f/1000) + 1, 1), 3) # JGH Values 1,2,3
##        if band != self.lastBand:
##            self.lastBand = band
##            # give PLLs more time to settle too
##        cb.msWait(100)
                     
    #--------------------------------------------------------------------------
    # Command just the PDM's static data.

    def _CommandPhaseOnly(self):
        global cb
        cb.SetP(2, self.invPhase << cb.P2_pdminvbit)
        cb.setIdle()

    #--------------------------------------------------------------------------
    # Set the GHz frequency band: 1, 2, or 3.

    def _SetFreqBand(self, band, extraBits=0):
        global cb
        self._GHzBand = band
        band += extraBits
        if self._GHzBand == 2:
            self.bitsBand = 64 * 0
        else:
            self.bitsBand = 64 * 1
        cb.SetP(4, self.bitsVideo + self.bitsRBW + self.bitsFR + \
                self.bitsTR + self.bitsBand + self.bitsPulse)
        ##print ("SetFreqBand: %02x" % band
        cb.setIdle()
        if debug:
            print ("G%02x" % band )

    #--------------------------------------------------------------------------
    # Initialize MSA hardware.

    def InitializeHardware(self):
        global cb, hardwarePresent, LO1, LO2, LO3

        from msa_cb import MSA_CB
        hardwarePresent = GetHardwarePresent()
        if not hardwarePresent:
            if cb == None:
                cb = MSA_CB()
            return

        # Determine which interface to use to talk to the MSA's Control Board

        if not cb:
            if isWin and winUsesParallelPort:
                from msa_cb_pc import MSA_CB_PC
                cb = MSA_CB_PC()
            else:
                from msa_cb_usb import MSA_CB_USB
                cb = MSA_CB_USB()
                cb.FindInterface()
                if not cb.usbFX2 or not cb.ValidVersion():
                    cb = MSA_CB()
                    hardwarePresent = False
                    SetHardwarePresent(hardwarePresent)
        else:
            # test interface to see that it's still there
            try:
                cb.OutPort(0)
                cb.Flush()
            except:
                cb = MSA_CB()
                hardwarePresent = False
                SetHardwarePresent(hardwarePresent)
        SetCb(cb)

        p = self.frame.prefs

        if not hardwarePresent:
##            print ("\n>>>2462<<<    NO HARDWARE PRESENT")
##            print ("\n>>>2463<<< GENERATING SYNTHETIC DATA") # JGH syndutHook2
            if p.syntData:
                print ("\n>>>2463<<< GENERATING SYNTHETIC DATA") # JGH syndutHook2
                from synDUT import SynDUTDialog
                self.syndut = SynDUTDialog(self.gui)
                wx.Yield()
                self.gui.Raise()
            else:
                message("Hardware not present. If you want to run with "
                        "Synthetic Data, use Hardware Configuration Manager "
                        "to enable Synthetic Data.",
                        caption="Hardware not Present")

        # Instantiate MSA's 3 local oscillators
        PLL1phasefreq = p.get("PLL1phasefreq", 0.974)
        PLL2phasefreq = p.get("PLL2phasefreq", 4.000)
        PLL3phasefreq = p.get("PLL3phasefreq", 0.974)
        PLL1phasepol = p.get("PLL1phasepol", 0)
        PLL2phasepol = p.get("PLL2phasepol", 1)
        PLL3phasepol = p.get("PLL3phasepol", 0)
        appxdds1 =  p.get("appxdds1", 10.7)
        appxLO2 = p.get("appxLO2", 1024.)
        appxdds3 =  p.get("appxdds3", 10.7)
        dds1filbw = p.get("dds1filbw", 0.015)
        dds3filbw = p.get("dds3filbw", 0.015)
        PLL1type = p.get("PLL1type", "2326")
        PLL2type = p.get("PLL2type", "2326")
        PLL3type = p.get("PLL3type", "2326")
        # LO1 = MSA_LO(1, 0.,    cb.P1_PLL1DataBit, cb.P2_le1, cb.P2_fqud1, 0.974, 0, appxdds1, dds1filbw)
        # LO2 = MSA_LO(2, 1024., cb.P1_PLL2DataBit, cb.P2_le2, 0, 4.,    1, 0,        0)
        # LO3 = MSA_LO(3, 0.,    cb.P1_PLL3DataBit, cb.P2_le3, cb.P2_fqud3, 0.974, 0, appxdds3, dds3filbw)

        # JGH above three lines changed to
        LO1 = MSA_LO(1, 0., cb.P1_PLL1DataBit, cb.P2_le1, cb.P2_fqud1, \
                     PLL1phasefreq, PLL1phasepol, appxdds1, dds1filbw, PLL1type)
        SetLO1(LO1)
        LO2 = MSA_LO(2, appxLO2, cb.P1_PLL2DataBit, cb.P2_le2, 0, PLL2phasefreq, \
                     PLL2phasepol, 0, 0, PLL2type)
        SetLO2(LO2)
        LO3 = MSA_LO(3, 0., cb.P1_PLL3DataBit, cb.P2_le3, cb.P2_fqud3, PLL3phasefreq, \
                     PLL3phasepol, appxdds3, dds3filbw, PLL3type)
        SetLO3(LO3)

        # JGH change end

        # 5. Command Filter Bank to Path one. Begin with all data lines low
        cb.OutPort(0)
        # latch "0" into all SLIM Control Board Buffers
        cb.OutControl(cb.SELTINITSTRBAUTO)
        # begin with all control lines low
        cb.OutControl(cb.contclear)

        self._SetFreqBand(1)
##        self.lastBand = 1
        self.lastStepAttenDB = -1 # TODO: ATTENUATOR

        # 6.if configured, initialize DDS3 by reseting to serial mode.
        # Frequency is commanded to zero
        LO3.ResetDDSserSLIM()

        # JGH starts 3/16/14
        # Precalculate all non-frequency dependent PLL parameters

        # R counter, pdf
        LO1.rcounter, LO1.pdf = LO1.CreateRcounter(LO1.appxdds)
        print(">>>448<<< LO1.rcounter, LO1.pdf: ", LO1.rcounter, LO1.pdf)
        LO2.rcounter, LO2.pdf = LO2.CreateRcounter(self.masterclock)
        print(">>>450<<< LO2.rcounter, LO2.pdf: ", LO2.rcounter, LO2.pdf)
        LO3.rcounter, LO3.pdf = LO3.CreateRcounter(LO3.appxdds)
        print(">>>452<<<LO3.rcounter, LO3.pdf: ", LO3.rcounter, LO3.pdf)

        # Ncounter
        # (needs: PLL2 (aka appxVCO), rcounter, fcounter)
        # (For LO2: creates: ncounter, fcounter(0))
        # LO1 and LO3 are frequency dependent (see LO1.Calculate)
        # LO2 is frequency dependent during the cavity filter test
        appxVCO = self.appxLO2
        LO2.CreateIntegerNcounter(appxVCO, self.masterclock)

        # Nregister

        # A counter, B counter, N bits
        # LO1 and LO3 are frequency dependent
        # LO2 is frequency dependent during the cavity filter test
        # (needs: ncounter, fcounter, PLL2)
        # (creates: Bcounter,Acounter, and N Bits N0-N23)
        #LO1.CreatePLLN()
        LO2.CreatePLLN()
        #LO3.CreatePLLN()
        # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

####        LO3.rcounter, LO3.pdf = LO3.CreateRcounter(LO3.appxdds)
       
        # 7. Once configured, initialize PLO3. No frequency command yet.
        LO3.CommandPLLR()

        # 8.initialize and command PLO2 to proper frequency
####        LO2.rcounter, LO2.pdf = LO2.CreateRcounter(self.masterclock)
        # Command PLL2R and Init Buffers (needs:PLL2phasepolarity,SELT,PLL2)
        LO2.CommandPLLR()
        # CreatePLL2N
####        appxVCO = self.appxLO2 # JGH: appxLO2 is the Hardware Config Dialog value
        # 8a. CreateIntegerNcounter(needs: PLL2 (aka appxVCO), rcounter, fcounter)
####        LO2.CreateIntegerNcounter(appxVCO, self.masterclock)

####        LO2.CreatePLLN()    # (needs: ncounter, fcounter, PLL2)
        #                     (creates: Bcounter,Acounter, and N Bits N0-N23)
        # 8b. Actual LO2 frequency
        LO2.freq = ((LO2.Bcounter*LO2.preselector) + LO2.Acounter + \
                    (LO2.fcounter/16))*LO2.pdf
        print(">>>489<<< Step8b LO2.freq: ", LO2.freq)
        
        # 8c. CommandPLL2N
        # needs:N23-N0,control,Jcontrol=SELT,port,contclear,LEPLL=8
        # commands N23-N0,old ControlBoard
        LO2.CommandPLL(LO2.PLLbits)
        
        # 9.Initialize PLO 1. No frequency command yet.
        # CommandPLL1R and Init Buffers
        # needs:rcounter1,PLL1phasepolarity,SELT,PLL1
        # Initializes and commands PLL1 R Buffer(s)
        LO1.CommandPLLR()
        # 10.initialize DDS1 by resetting. Frequency is commanded to zero
        # It should power up in parallel mode, but could power up in a bogus
        #  condition. reset serial DDS1 without disturbing Filter Bank or PDM
        LO1.ResetDDSserSLIM()   # SCOTTY TO MODIFY THIS TO LIMIT HIGH CURRENT

        # JGH added 10a. Set Port 4 switches 2/24/14
        self.vFilterSelIndex = p.get("vFilterSelIndex", 1)   # Values 0-3
        self.switchRBW = p.get("switchRBW", 0) # Values 0-3
        self.switchFR = p.get("switchFR", 0) # Values 0,1
        self.switchTR = p.get("switchTR", 0) # Values 0,1
        self.switchBand = p.get("switchBand", 1) # 1: 0-1GHz, 2: 1-2GHz, 3: 2-3GHz
        self.switchPulse = 0 # JGH Oct23 Set this here and follow with a 1 sec delay
        # Pulse must be added here, in the mean time use 0
        self.bitsVideo = self.vFilterSelIndex # V0/V1 Bits 0,1
        self.bitsRBW = 4 * self.switchRBW # A0/A1 Bits 2, 3
        self.bitsFR = 16 * self.switchFR # Bit 4
        self.bitsTR = 32 * self.switchTR    # Bit 5
        self.bitsBand = 64 * self. switchBand # G0 Bit 6
        self.bitsPulse = 128 * self.switchPulse # Bit 7
        
        cb.SetP(4, self.bitsVideo + self.bitsRBW + self.bitsFR + \
                self.bitsTR + self.bitsBand + self.bitsPulse)
        if debug:
            print(">>>2580<<< Steps9/10 commanded and switches set ************")
        # JGH addition ended
    #--------------------------------------------------------------------------
    # Read 16-bit magnitude and phase ADCs.

    def _ReadAD16Status(self):
        global cb
        # Read16wSlimCB --
        mag, phase = cb.GetADCs(16)
        mag   >>= cb.P5_MagDataBit
        phase >>= cb.P5_PhaseDataBit
        self._magdata = mag
        self._phasedata = 0x10000 - phase
        if debug:
            print ("_ReadAD16Status: mag=0x%x, phase=0x%x" % \
                    (self._magdata, self._phasedata))

    #--------------------------------------------------------------------------
    # Use synthetic data as input.

    def _InputSynth(self, f): # JGH 2/8/14 syndutHook3
        syndut = self.syndut
        if syndut:
            nf = len(syndut.synSpecF)
            nM = len(syndut.synSpecM)
            nP = len(syndut.synSpecP)
            if nf != nM or nf != nP:
                print ("msa.InputSynth: length mismatch: nf=%d nM=%d nP=%d" % \
                       (nf, nM, nP))
            else:
                self._magdata =   interp(f, syndut.synSpecF, syndut.synSpecM)
                self._phasedata = interp(f, syndut.synSpecF, syndut.synSpecP)

    #--------------------------------------------------------------------------
    # Capture magnitude and phase data for one step.

    def CaptureOneStep(self, post=True, useCal=True, bypassPDM=False):
        global cb
        p = self.frame.prefs  # JGH/SCOTTY 2/6/14
        step = self._step
        self.LogEvent("CaptureOneStep %d" % step)
        f = self._freqs[step]
##        print (">>>2572<<< step: ", step , ", f: ", f)
        if f < -48:
            Sdb = nan
            Sdeg = nan
            Mdb = nan
            Mdeg = nan
        else:
            doPhase = self.mode > self.MODE_SATG
            #invPhase = self.invPhase
            if hardwarePresent:
                if 0:
                    self.LogEvent("CaptureOneStep hardware, f=%g" % f)
                # set MSA to read frequency f
##                self._CommandAllSlims(f) # SweepArray doesn't need f
                self._CommandAllSlims()

    # ------------------------------------------------------------------------------
                if p.cftest == 1:
##                      cavityLO2 = self.finalfreq + LO1.freq
                    cavityLO2 =1013.3 + self.finalfreq + f
                    print ("freq: ", f)
                    LO2.CreateIntegerNcounter(cavityLO2, self.masterclock)
                    LO2.CreatePLLN()
                    LO2.freq = ((LO2.Bcounter*LO2.preselector) + LO2.Acounter+(LO2.fcounter/16))*LO2.pdf
                    LO2.CommandPLL(LO2.PLLbits)
    # ------------------------------------------------------------------------------
                if 0:
                    self.LogEvent("CaptureOneStep delay")
                if step == 0:
                    # give the first step extra time to settle
                    cb.msWait(200)
##                    self._CommandAllSlims(f)
                    self._CommandAllSlims() # SweepArray doesn't need f
                cb.msWait(self.wait)
                # read raw magnitude and phase
                if 0:
                    self.LogEvent("CaptureOneStep read")
                cb.ReqReadADCs(16)
                cb.FlushRead()
                cb.Flush()
                time.sleep(0)
                self._ReadAD16Status()
                if 0: # JGH 3/9/14
                    self.LogEvent("CaptureOneStep got %06d" % self._magdata)
                if self._magdata < goodPhaseMagThreshold:
                    doPhase = False

                # check if phase is within bad quadrant, invert phase and
                # reread it
                # JGH This shall be modified if autoPDM is used (Nov 9, 2013)
                if doPhase and not bypassPDM and \
                        (self._phasedata < 13107 or self._phasedata > 52429):
                    oldPhase = self._phasedata
                    self.invPhase = 1 - self.invPhase
                    self._CommandPhaseOnly()
                    if 0:
                        self.LogEvent("CaptureOneStep phase delay")
                    cb.msWait(200)
                    if 0:
                        self.LogEvent("CaptureOneStep phase reread")
                    cb.ReqReadADCs(16)
                    cb.FlushRead()
                    cb.Flush()
                    time.sleep(0)
                    self._ReadAD16Status()
                    # inverting the phase usually fails when signal is noise
                    if self._phasedata < 13107 or self._phasedata > 52429:
                        print ("invPhase failed at %13.6f mag %5d orig %5d new %5d" %
                               (f, self._magdata, oldPhase, self._phasedata))
                        self.invPhase = 1 - self.invPhase

            else:
                self.LogEvent("CaptureOneStep synth, f=%g" % f)
                self._InputSynth(f) # JGH syndutHook4
                #invPhase = 0
                time.sleep(self.wait / 1000.0)

            ##print ("Capture: magdata=", self._magdata
            if useCal and len(self.magTableADC) > 0:
                # adjust linearity of values using magTable
                Sdb = interp(self._magdata, self.magTableADC, self.magTableDBm)
                ##print ("Capture: Sdb=", Sdb
                ##self.LogEvent("CaptureOneStep magTableADC")
            else:
                # or just assume linear and estimate gain
                Sdb = (self._magdata / 65536.0 - 0.5) * 200
                ##self.LogEvent("CaptureOneStep Linear estimate")

            if useCal and len(self.freqTableMHz) > 0:
                # correct the magnitude based on frequency
                ##print ("Capture: Sdb=", Sdb, "f=", f, self.freqTableMHz[-1]
                if f <= self.freqTableMHz[-1]:
                    Sdb += interp(f, self.freqTableMHz, self.freqTableDB)
                else:
                    Sdb += self.freqTableDB[-1]
                ##print ("Capture: Sdb=", Sdb, "after freqTableMHz"
            Mdb = Sdb

            if doPhase:
                if bypassPDM:
                    Sdeg = modDegree(self._phasedata / 65536.0 * 360.0)
                else:
                    Sdeg = modDegree(self._phasedata / 65536.0 * 360.0 - \
                            self.invPhase * self.invDeg)
                # phase in 3G band is inverted
                if self._GHzBand == 3:
                    Sdeg = -Sdeg
                ##print ("%4dM: %5d %6.2f  %5d %6.2f" % (f, self._magdata,
                ##       Sdb, self._phasedata, Sdeg)

                if useCal:
                    # look up phase correction in magTable
                    if len(self.magTableADC) > 0:
                        diffPhase = interp(self._magdata, self.magTableADC,
                                            self.magTablePhase)
                        # a diffPhase near 180 deg indicates the phase is
                        # invalid: set it to 0
                        if abs(diffPhase) >= 179:
                            Sdeg = 0.
                        else:
                            Sdeg = modDegree(Sdeg - diffPhase)

                    # add in plane extension in ns. (0.001 = ns*MHz)
                    planeExt = self._planeExt[self._GHzBand-1]
                    Sdeg = modDegree(Sdeg + 360 * f * planeExt * 0.001)
            else:
                Sdeg = nan
            Mdeg = Sdeg

            # determine which phase cycle this step is in by comparing
            # its phase quadrant to the previous one and adjusting the
            # base when it wraps
            if isnan(Sdeg):
                Squad = 0
            else:
                Squad = int((Sdeg + 180) / 90)
            if self._Hquad == 3 and Squad == 0:
                self._baseSdeg += 360
            elif self._Hquad == 0 and Squad == 3:
                self._baseSdeg -= 360
            self._Hquad = Squad

            # always make a continuous phase (wrapped phase is taken from it)
            Sdeg += self._baseSdeg

            # if enabled, make mag continuous so cal interp doesn't glitch
            if self._contin:
                Sdb += self._baseSdb

                hist = self._history
                show = False
                if len(hist) > 1:
                    # H2f is frequency at current step minus 2, etc.
                    H2f, H2db, H2deg = hist[0]
                    H1f, H1db, H1deg = hist[1]

                    if f > 500 and (f // 1000) != (H1f // 1000):
                        # just crossed into a new GHz band: adjust bases
                        dSdb  = Sdb  - (2*H1db  - H2db )
                        dSdeg = Sdeg - (2*H1deg - H2deg)
                        self._baseSdb  -= dSdb
                        self._baseSdeg -= dSdeg
                        Sdb  -= dSdb
                        Sdeg -= dSdeg
                        if show:
                            print ("jumped gap=", f, H1f, f // 1000, \
                                H1f // 1000, dSdb)
                    if show:
                        print ("hist=", ["%7.2f %7.2f %7.2f" % x for x in hist], \
                            "Sdb=%7.2f" % Sdb, "Sdeg=%7.2f" % Sdeg, \
                            "Hq=%d" % self._Hquad, "Sq=%1d" % Squad, \
                            "bases=%7.2f" % self._baseSdb, \
                            "%7.2f" % self._baseSdeg)
                    hist.pop(0)

                # keep history
                hist.append((f, Sdb, Sdeg))


            # subtract any selected base or band calibration
            if not self.calibrating:
                cal = (None, self.baseCal, self.bandCal)[self.calLevel]
                if cal:
                    # Start EON Jan 10 2014
                    if self.mode == MSA.MODE_VNARefl:
                        if cal.oslCal:
                            calM, calP = cal[step]
                            Sdb -= calM
                            Sdeg -= calP
                            (Sdb, Sdeg) = cal.ConvertRawDataToReflection(step, Sdb, Sdeg)
                    else:
                    # End EON Jan 10 2014
                        if self.calNeedsInterp:
                            calM = interp(f, cal.Fmhz, cal.Sdb)
                            calP = interp(f, cal.Fmhz, cal.Scdeg)
                        else:
                            calF, calM, calP = cal[step]
                        Sdb -= calM
                        if doPhase:
                            Sdeg -= calP

        # either pass the captured data to the GUI through the scanResults
        # buffer if 'post' set, or return it
        self._Sdb = Sdb
        Scdeg = Sdeg
        self._Sdeg = Sdeg = modDegree(Sdeg)
        self.LogEvent("CaptureOneStep done, Sdb=%g Sdeg=%g" % (Sdb, Sdeg))
        if post:
            self.scanResults.put((step, Sdb, Sdeg, Scdeg,
                self._magdata, self._phasedata, Mdb, Mdeg, msElapsed()))
        else:
            return f, self._magdata, Sdb, Sdeg

    #--------------------------------------------------------------------------
    # Internal scan loop thread.

    def _ScanThread(self):
        global cb
        try:
            self.LogEvent("_ScanThread")

            # clear out any prior FIFOed data from interface
            cb.Clear()
            elapsed = 0
            while self.scanEnabled:
                self.LogEvent("_ScanThread wloop, step %d" % self._step)
                self.CaptureOneStep()
                self.NextStep()
                elapsed += int(self.wait) + 3
                self.LogEvent("_ScanThread: step=%d Req.nSteps=%d" % \
                              (self._step, self._nSteps))
                if self._step == 0 or self._step == self._nSteps+1:
                    if self.haltAtEnd:
                        self.LogEvent("_ScanThread loop done")
                        self.scanEnabled = False
                        break
                    else:
                        self.LogEvent("_ScanThread to step 0")
                        self.WrapStep()
                # yield some time to display thread
                if elapsed > msPerUpdate:
                    elapsed = 0
                    evt = UpdateGraphEvent()
                    wx.PostEvent(self.gui, evt)

        except:
            self.showError = True
            traceback.print_exc()
            self.showError = False

        if self.haltAtEnd:
            self.scanEnabled = False

        self.LogEvent("_ScanThread exit")
        self._scanning = False

    #--------------------------------------------------------------------------
    # Stop any current scan and set up for a new spectrum scan.

    def NewScanSettings(self, parms):

        self.LogEvent("NewScanSettings nSteps=%d" % parms.nSteps)

        # if scan already running, disable it and wait for it to finish
        if self._scanning:
            self.scanEnabled = False
            while self._scanning:
                time.sleep(0.1)

        # set current parameters to given values
        self.wait        = parms.wait
        self._sgout      = parms.sigGenFreq
        self._offset     = parms.tgOffset
        self.invDeg      = parms.invDeg
        self._planeExt   = parms.planeExt
        self._normrev    = parms.normRev
        self._sweepDir   = parms.sweepDir
        self._isLogF     = parms.isLogF
        self._contin     = parms.continuous

        # set start and stop frequencies, swapped if sweeping downward
        fStart = parms.fStart
        fStop  = parms.fStop

        if self._sweepDir == 1:
            self._sweepInc = -1
            self._fStart = fStop
            self._fStop  = fStart
        else:
            self._sweepInc = 1
            self._fStart = fStart
            self._fStop  = fStop
            
        self._nSteps = nSteps = parms.nSteps


        # create array of frequencies in scan range, linear or log scale
        if self._isLogF:
            parms.fStart = fStart = max(fStart, 1e-6)
            self._freqs = logspace(log10(fStart), log10(fStop), num=nSteps+1)
        else:
            # JGH linspace comes from numpy
            # self._freqs = linspace(self._fStart, self._fStop, nSteps+1)
            self._freqs = linspace(fStart, fStop, nSteps+1)

        self.step1k = self.step2k = None            
        for x, y in enumerate(self._freqs):
            if y == 1000:
                self.step1k = x ; print("1000 is at step #", x)
            if y == 2000:
                self.step2k = x ; print("2000 is at step #", x)

    #--------------------------------------------------------------------------
    # Start an asynchronous scan of a spectrum. The results may be read at
    # any time. Returns True if scan wasn't already running.

    def ConfigForScan(self, gui, parms, haltAtEnd):
        self.LogEvent("Scan")
        if self._scanning:
            return False
        self.gui = gui
        self.haltAtEnd = haltAtEnd
        self.NewScanSettings(parms)
        self.InitializeHardware()
        self._step = 0
        self._history = []
        self._baseSdb = 0
        self._baseSdeg = 0
        self.ContinueScan()
        self.LogEvent("Scan exit")
        return True

    #--------------------------------------------------------------------------
    # Continue a halted scan starting at the current step.

    def ContinueScan(self):
        self.LogEvent("ContinueScan: step=%d" % self._step)
        if hardwarePresent or self.syndut != None:
            if not self._scanning:
                self.CreateSweepArray() # Creates GEORGE
                self.LogEvent("ContinueScan start_new_thread")
                self.scanEnabled = self._scanning = True
                thread.start_new_thread(self._ScanThread, ())
            self.LogEvent("ContinueScan exit")

    #--------------------------------------------------------------------------
    # SweepArray
    # (send data and clocks without changing Filter Bank)
    #  0-15 is DDS1bit*4 + DDS3bit*16, data = 0 to PLL 1 and PLL 3.
    # (see CreateCmdAllArray). new Data with no clock,latch high,latch low,
    # present new data with clock,latch high,latch low. repeat for each bit.
    # (40 data bits and 40 clocks for each module, even if they don't need that many)
    # This format guarantees that the common clock will
    # not transition with a data transition, preventing crosstalk in LPT cable.

    def CreateSweepArray(self): # aka GEORGE
        global cb
        SweepArray = []
        StepArray = []  # StepArray size = VariableList size
        VarsArray = []  # VarsArray size = Number of steps
       
        
        for f in self._freqs:
            band = min(max(int(f/1000) + 1, 1), 3) # JGH Values 1,2,3
            
            self._CalculateAllStepsForLO1Synth(f, band)
            self._CalculateAllStepsForLO3Synth(f, band)
            
            # PLLs go out MSB first, with a 16-bit leader of zeros
            PLL1bits = LO1.PLLbits
            PLL3bits = LO3.PLLbits
            msb = 23 + 16
            shift1 = msb - cb.P1_PLL1DataBit
            shift3 = msb - cb.P1_PLL3DataBit
            mask = 1 << msb
            # pre-shift 40 bits for each DDS so the LSB aligns with its port
            # serial-data bit
            DDS1bits = LO1.DDSbits << cb.P1_DDS1DataBit
            DDS3bits = LO3.DDSbits << cb.P1_DDS3DataBit
            if debug:
                print ("PLL1bits=0x%010x" % PLL1bits)
                print ("DDS1bits=0x%010x" % DDS1bits)
                print ("DDS3bits=0x%010x" % DDS3bits)

            byteList = []   # JGH 2/9/14
            for i in range(40):
                # combine the current bit for each device and clk them out together
    ##            a = (DDS3bits & cb.P1_DDS3Data) + ((PLL3bits & mask) >> shift3) + \
    ##                (DDS1bits & cb.P1_DDS1Data) + ((PLL1bits & mask) >> shift1) + \
    ##                self.bitsRBW # JGH line changed for next one
                a = (DDS3bits & cb.P1_DDS3Data) + ((PLL3bits & mask) >> shift3) + \
                    (DDS1bits & cb.P1_DDS1Data) + ((PLL1bits & mask) >> shift1)
                byteList.append(a)  # JGH 2/9/14
                # shift next bit into position
                DDS3bits >>= 1; PLL3bits <<= 1; DDS1bits >>= 1; PLL1bits <<= 1
            SweepArray.append(byteList)

            # Build VarsArray
            p = self.frame.prefs
            if p.cftest == False:
                LO2.ddsoutput = LO2.fcounter = 0
            RealFinalIF = LO2.freq - 0
            VarsArray = [LO1.ddsoutput, LO1.freq, LO1.pdf, LO1.ncounter, LO1.Bcounter, LO1.Acounter, \
                         LO1.fcounter, LO1.rcounter, \
                         LO2.ddsoutput, LO2.freq, LO2.pdf, LO2.ncounter, LO2.Bcounter, LO2.Acounter, \
                         LO2.fcounter, LO2.rcounter, \
                         LO3.ddsoutput, LO3.freq, LO3.pdf, LO3.ncounter, LO3.Bcounter, LO3.Acounter, \
                         LO3.fcounter, LO3.rcounter, \
                         RealFinalIF, self.masterclock]
            StepArray.append(VarsArray)
   
        print(StepArray[350])
        #step1k = self.step1k ; step2k =self.step2k
        self.SweepArray = SweepArray
        self.StepArray = StepArray
            
    #--------------------------------------------------------------------------
    # Stop current scan.

    def StopScan(self):
        self.LogEvent("StopScan")
        self.scanEnabled = False

    #--------------------------------------------------------------------------
    # Return True if scan running.

    def IsScanning(self):
        return self._scanning

    #--------------------------------------------------------------------------
    # Get, wrap-around, or increment step number.

    def GetStep(self):
        return self._step

    def WrapStep(self):
        lastStep = self._step
        self._step = lastStep % (self._nSteps+1)
        if abs(self._step - lastStep) > 1:
            self._baseSdb = 0
            self._baseSdeg = 0
            self._history = []

    def NextStep(self): # EN 12/23/13 Modified this method as follows
        if self._sweepDir == 2:
            # sweep back and forth
            if (self._step == self._nSteps) and (self._sweepInc == 1): # EN 12/23/13
                self._sweepInc = -1
            elif (self._step == 0) and (self._sweepInc == -1):
                self._sweepInc = 1
            else:
                self._step += self._sweepInc
        elif self._sweepDir == 1:
            # sweep right to left
            if self._step == 0:
                self._step = self._nSteps
                self._sweepInc = -1
            else:
                self._step += self._sweepInc
        else:
            self._step += self._sweepInc

    #--------------------------------------------------------------------------
    # Return a string of variables and their values for the Variables window.

    def GetVarsTextList(self):
        step = max(self._step - 1, 0) # JGH has a question about this line
##        return [
##            "this step = %d" % step,
##            "dds1output = %0.9g MHz" % LO1.ddsoutput, # self.StepArray[step][0]
##            "LO1 = %0.9g MHz" % LO1.freq, # self.StepArray[step][1]
##            "pdf1 = %0.9g MHz" % LO1.pdf, # self.StepArray[step][2]
##            "ncounter1 = %d" % LO1.ncounter, # self.StepArray[step][3]
##            "Bcounter1 = %d" % LO1.Bcounter, # self.StepArray[step][4]
##            "Acounter1 = %d" % LO1.Acounter, # self.StepArray[step][5]
##            "fcounter1 = %d" % LO1.fcounter, # self.StepArray[step][6]
##            "rcounter1 = %d" % LO1.rcounter, # self.StepArray[step][7]
##            "LO2 = %0.6f MHz" % LO2.freq, # self.StepArray[step][9]
##            "pdf2 = %0.6f MHz" % LO2.pdf, # self.StepArray[step][10]
##            "ncounter2 = %d" % LO2.ncounter, # self.StepArray[step][11]
##            "Bcounter2 = %d" % LO2.Bcounter, # self.StepArray[step][12]
##            "Acounter2 = %d" % LO2.Acounter, # self.StepArray[step][13]
##            "rcounter2 = %d" % LO2.rcounter, # self.StepArray[step][15]
##            "dds3output = %0.9g MHz" % LO3.ddsoutput, # self.StepArray[step][16]
##            "LO3 = %0.6f MHz" % LO3.freq, # self.StepArray[step][17]
##            "pdf3 = %0.6f MHz" % LO3.pdf, # self.StepArray[step][18]
##            "ncounter3 = %d" % LO3.ncounter, # self.StepArray[step][19]
##            "Bcounter3 = %d" % LO3.Bcounter, # self.StepArray[step][20]
##            "Acounter3 = %d" % LO3.Acounter, # self.StepArray[step][21]
##            "fcounter3 = %d" % LO3.fcounter, # self.StepArray[step][22]
##            "rcounter3 = %d" % LO3.rcounter, # self.StepArray[step][23]
##            "Magdata=%d mag=%0.5g" % (self._magdata, self._Sdb),
##            "Phadata=%d PDM=%0.5g" % (self._phasedata, self._Sdeg),
##            "Real Final I.F. = %f" % (LO2.freq  - 0), # self.StepArray[step][24]
##            "Masterclock = %0.6f" % self.masterclock # self.StepArray[step][25]
##        ]
        return [
            "this step = %d" % step,
            "dds1output = %0.9g MHz" % self.StepArray[step][0],
            "LO1 = %0.9g MHz" % self.StepArray[step][1],
            "pdf1 = %0.9g MHz" % self.StepArray[step][2],
            "ncounter1 = %d" % self.StepArray[step][3],
            "Bcounter1 = %d" % self.StepArray[step][4],
            "Acounter1 = %d" % self.StepArray[step][5],
            "fcounter1 = %d" % self.StepArray[step][6],
            "rcounter1 = %d" % self.StepArray[step][7],
            "LO2 = %0.6f MHz" % self.StepArray[step][9],
            "pdf2 = %0.6f MHz" % self.StepArray[step][10],
            "ncounter2 = %d" % self.StepArray[step][11],
            "Bcounter2 = %d" % self.StepArray[step][12],
            "Acounter2 = %d" % self.StepArray[step][13],
            "rcounter2 = %d" % self.StepArray[step][15],
            "dds3output = %0.9g MHz" % self.StepArray[step][16],
            "LO3 = %0.6f MHz" % self.StepArray[step][17],
            "pdf3 = %0.6f MHz" % self.StepArray[step][18],
            "ncounter3 = %d" % self.StepArray[step][19],
            "Bcounter3 = %d" % self.StepArray[step][20],
            "Acounter3 = %d" % self.StepArray[step][21],
            "fcounter3 = %d" % self.StepArray[step][22],
            "rcounter3 = %d" % self.StepArray[step][23],
            "Magdata=%d mag=%0.5g" % (self._magdata, self._Sdb),
            "Phadata=%d PDM=%0.5g" % (self._phasedata, self._Sdeg),
            "Real Final I.F. = %f" % self.StepArray[step][24],
            "Masterclock = %0.6f" % self.StepArray[step][25]
        ]
    #--------------------------------------------------------------------------
    # Spectrum accessors.

    def HaveSpectrum(self):
        return self._fStart != None

    def NewSpectrumFromRequest(self, title):
        return Spectrum(title, self.indexRBWSel+1, self._fStart, self._fStop,
                        self._nSteps, self._freqs)

#==============================================================================
# An MSA Local Oscillator DDS and PLL.

class MSA_LO:
    # def __init__(self, id, freq, pllBit, le, fqud, PLLphasefreq, phasepolarity, appxdds, ddsfilbw):
    # JGH Above line substituted by the following
    def __init__(self, loid, freq, pllBit, le, fqud, PLLphasefreq, phasepolarity, \
                 appxdds, ddsfilbw, PLLtype): # JGH 2/7/14 Fractional mode not used
        self.id = loid                      # LO number, 1-3
        self.freq = freq                    # LO frequency
        self.CBP1_PLLDataBit = pllBit       # port 1 bit number for PLL data
        self.CBP2_LE = le                   # port 2 mask for Latch Enable line
        self.CBP2_FQUD = fqud               # port 2 mask for FQUD line
        self.PLLphasefreq = PLLphasefreq    # Approx. Phase Detector Frequency for PLL.
                # Use .974 when DDS filter is 15 KHz wide.
                # PLLphasefreq must be less than the following formula:
                # PLLphasefreq < (VCO 1 minimum frequency) x self.ddsfilbw/appxdds
        self.phasepolarity = phasepolarity
        self.appxdds = appxdds              # nominal DDS output frequency, to steer the PLL.
                # (Near 10.7 MHz). appxdds must be the center freq. of DDS xtal filter;
                # Exact value determined in calibration.
        self.ddsfilbw = ddsfilbw            # DDS xtal filter bandwidth (in MHz), at the 3 dB points.
                #Usually 15 KHz.
        self.PLLtype = PLLtype              # JGH COMMENT: PLLtype not needed here?
        
        self.ddsoutput = 0.                 # actual output of DDS (input Ref to PLL)
        self.ncounter = 0.                  # PLL N counter
        self.Acounter = 0.                  # PLL A counter
        self.Bcounter = 0.                  # PLL B counter
        self.fcounter = 0.                  # PLL fractional-mode N counter
        if debug:
            print ("LO%d init: PDF=%f" % (id, PLLphasefreq))

        # PLL R counter
##        self.rcounter = int(round(divSafe(self.appxdds, self.PLLphasefreq)))
        self.CreateRcounter(self.appxdds)
##        if msa.spurcheck and not self.PLLmode:  # JGH 2/7/14 Fractional mode not used
        if GetMsa().spurcheck:
            self.rcounter += 1  # only do this for IntegerN PLL

            self.pdf = 0   # phase detector frequency of PLL (MHz)


    #--------------------------------------------------------------------------
    # Create rcounter, pdf.

    def CreateRcounter(self, reference):
        self.rcounter = int(round(divSafe(reference, self.PLLphasefreq)))
        self.pdf = divSafe(reference, self.rcounter)
        if debug:
            print ("LO%d: R=%d=0x%06x pdf=%f" % (self.id, self.rcounter, \
                        self.rcounter, self.pdf))
        return self.rcounter, self.pdf # JGH 2/1/14

    #--------------------------------------------------------------------------
    # Set a PLL's register.

    def CommandPLL(self, data):
        global cb
        # CommandPLLslim --
        if debug:
            print ("LO%d CommandPLL 0x%06x" % (self.id, data))
        shift = 23 - self.CBP1_PLLDataBit
        mask = 1 << 23
        # shift data out, MSB first
        for i in range(24):
##            a = ((data & mask) >> shift) + msa.bitsRBW # JGH Use next line
            a = ((data & mask) >> shift)
            cb.SetP(1, a)                  # data with clock low
            cb.SetP(1, a + cb.P1_Clk)      # data with clock high
            # shift next bit into position
            data <<= 1
        # remove data, leaving bitsRBW data to filter bank.
##        cb.SetP(1, msa.bitsRBW) # JGH use next line
        cb.SetP(1, 0)

        # send LEs to PLL1, PLL3, FQUDs to DDS1, DDS3, and command PDM
        # begin by setting up init word=LEs and Fquds + PDM state for thisstep
        pdmcmd = GetMsa().invPhase << cb.P2_pdminvbit
        cb.SetP(2, self.CBP2_LE + pdmcmd) # present data to buffer input
        # remove the added latch signal to PDM, leaving just the static data
        cb.SetP(2, pdmcmd)
        cb.setIdle()

    #--------------------------------------------------------------------------
    # Initialize the PLL's R register.

    def CommandPLLR(self): #JGH added additional PLL types

        if self.PLLtype == "2325":
            # N15 = 1 if preselector = 32, = 0 for preselctor = 64, default 1
            self.CommandPLL((self.rcounter << 1) + 0x1 + (0x1 << 15))

        # Command2326R --
        if (self.PLLtype == "2326" or self.PLLtype == "4118"):
            self.CommandPLL((self.phasepolarity << 7) + 0x3)
            self.CommandPLL(self.rcounter << 2)

        if self.PLLtype == "2350":
            self.CommandPLL((0X123 << 6) + (0x61 << 17))
            self.CommandPLL(0x1 + (0x1 << 14) + (0x1 << 18) + (0x1 << 22))
            self.CommandPLL(0x2 + (self.rcounter << 2) + (0x15 << 18))

        if self.PLLtype == "2353":
            self.CommandPLL((0x1 << 22))
            self.CommandPLL((0x1))
            #N23 Fractional mode, delay line 0= slow,1 =fast
            self.CommandPLL(0x2 + (self.rcounter << 2) + (self.phasepolarity << 17)
                             + (0x15 << 18))

        if (self.PLLtype == "4112" or self.PLLtype == "4113"):
            # If preselector = 8 then N22=0, N23=0
            # If preselector =16 then N22=1, N23=0
            # If preselector =32 then N22=0, N23=1 , default 32
            # if preselector =64 then N22=1, N23=1
            self.CommandPLL((self.phasepolarity << 7) + 0x3 + (0x1 << 15)
                            + (0x1 << 18) + (0x1 << 23))
            self.CommandPLL((self.rcounter << 2) + (0x1 << 23)) # changed from 22

    #--------------------------------------------------------------------------
    # Reset serial DDS without disturbing Filter Bank or PDM.

    def ResetDDSserSLIM(self):
        global cb
        # must have DDS (AD9850/9851) hard wired. pin2=D2=0, pin3=D1=1,
        # pin4=D0=1, D3-D7 are don# t care. this will reset DDS into
        # parallel, invoke serial mode, then command to 0 Hz.
        if debug:
            print ("XXXXX 996, ResetDDSserSLIM XXXXX")
        pdmcmd = GetMsa().invPhase << cb.P2_pdminvbit
        #bitsRBW = msa.bitsRBW

        # (reset DDS1 to parallel) WCLK up, WCLK up and FQUD up, WCLK up and
        # FQUD down, WCLK down
        # apply last known filter path and WCLK=D0=1 to buffer
##        cb.SetP(1, bitsRBW + cb.P1_Clk) # JGH use next line instead
        cb.SetP(1, cb.P1_Clk)
        # apply last known pdmcmd and FQUD=D3=1 to buffer
        cb.OutPort(pdmcmd + self.CBP2_FQUD)
        # DDSpin8, FQUD up,DDS resets to parallel,register pointer will reset
        cb.OutControl(cb.INIT)
        # DDSpin8, FQUD down
        cb.OutPort(pdmcmd)
        # disable buffer, leaving last known PDM state latched
        cb.OutControl(cb.contclear)
        # apply last known filter path and WCLK=D0=0 to buffer
##        cb.SetP(1, bitsRBW) # JGH Use next line instead
        cb.SetP(1, 0)
        # (invoke serial mode DDS1)WCLK up, WCLK down, FQUD up, FQUD down
        # apply last known filter path and WCLK=D0=1 to buffer
##        cb.OutPort(bitsRBW + cb.P1_Clk) # JGH Use next line instead
        cb.OutPort(cb.P1_Clk)
        # DDSpin9, WCLK up to DDS
        cb.OutControl(cb.SELT)
        # apply last known filter path and WCLK=D0=0 to DDS
##        cb.OutPort(bitsRBW) # JGH Use next line instead
        cb.OutPort(0)
        # disable buffer, leaving bitsRBW
        cb.OutControl(cb.contclear)
        # apply last known pdmcmd and FQUD=D3=1 to buffer
        cb.OutPort(pdmcmd + self.CBP2_FQUD)
        # DDSpin8, FQUD up,DDS resets to parallel,register pointer will reset
        cb.OutControl(cb.INIT)
        # DDSpin8, FQUD down
        cb.OutPort(pdmcmd)
        # disable buffer, leaving last known PDM state latched
        cb.OutControl(cb.contclear)

        # (flush and command DDS1) D7, WCLK up, WCLK down, (repeat39more),
        # FQUD up, FQUD down present data to buffer,latch buffer,disable
        # buffer, present data+clk to buffer,latch buffer,disable buffer

        # JGH the following block, changed to the next below
##        a = bitsRBW
##        for i in range(40):
##            # data with clock low
##            cb.SetP(1, a)
##            # data with clock high
##            cb.SetP(1, a + cb.P1_Clk)
##        # leaving bitsRBW latched
##        cb.SetP(1, a)

        #a = 0
        for i in range(40):
            # data with clock low
            cb.SetP(1, 0)
            # data with clock high
            cb.SetP(1, cb.P1_Clk)
        # leaving bitsRBW latched
        cb.SetP(1, 0)

        # apply last known pdmcmd and FQUD=D3=1 to buffer
        cb.OutPort(pdmcmd + self.CBP2_FQUD)
        # DDSpin8, FQUD up,DDS resets to parallel,register pointer will reset
        cb.OutControl(cb.INIT)
        # DDSpin8, FQUD down
        cb.OutPort(pdmcmd)
        # disable buffer, leaving last known PDM state latched
        cb.OutControl(cb.contclear)
        if debug:
            print ("ResetDDSserSLIM done")

    #--------------------------------------------------------------------------
    # Create Fractional Mode N counter. NOT USED ANY MORE

##    def _CreateFractionalNcounter(self, appxVCO, reference):
##        # approximates the Ncounter for PLL
##        ncount = divSafe(appxVCO, (reference/self.rcounter))
##        self.ncounter = int(ncount)
##        fcount = ncount - self.ncounter # EON Jan 29, 2014
##        self.fcounter = int(round(fcount*16))
##        if self.fcounter == 16:
##            self.ncounter += 1
##            self.fcounter = 0
##        # actual phase freq of PLL
##        self.pdf = divSafe(appxVCO, (self.ncounter + (self.fcounter/16)))

    #--------------------------------------------------------------------------
    # Create Integer Mode N counter.

    def CreateIntegerNcounter(self, appxVCO, reference):
        # approximates the Ncounter for PLL
        ncount = divSafe(appxVCO, divSafe(reference, self.rcounter))
        self.ncounter = int(round(ncount))
        if 1:
            print(">>>1285<<< appxVCO, reference, ncounter: ", \
                  appxVCO, reference, self.ncounter)
        self.fcounter = 0
        # actual phase freq of PLL
        #self.pdf = divSafe(appxVCO, self.ncounter) # JGH 2/2/14 Beware of globals!

    #--------------------------------------------------------------------------
    # Create PLL N register.

    def CreatePLLN(self):

##        self.preselector = (32, 16)[self.PLLmode] # JGH 2/7/14 PLLmode not used
        self.preselector = 32
        fcounter = 0 # EON Jan 29, 2014

        # CreateNBuffer,
        PLLN = self.PLLtype  # JGH added

        Bcounter = int(self.ncounter/self.preselector)
        Acounter = int(self.ncounter-(Bcounter*self.preselector))

        if debug:
            print(">>>1364<<< PLLN: ", PLLN)
            print("ncounter: ", self.ncounter)
            print ("LO%d: Acounter=" % self.id, Acounter, "Bcounter=", Bcounter)

        if PLLN == "2325":
            if Bcounter < 3:
                raise RuntimeError(PLLN + "Bcounter <3")
            if Bcounter > 2047:
                raise RuntimeError(PLLN + "Bcounter > 2047")
            if Bcounter < Acounter:
                raise RuntimeError(PLLN + "Bcounter<Acounter")
            Nreg = (Bcounter << 8) + (Acounter << 1)

        if (PLLN == "2326" or PLLN == "4118"):
            if Bcounter < 3:
                raise RuntimeError(PLLN + "Bcounter <3")  # JGH Error < 3 common to all
            if Bcounter > 8191:
                raise RuntimeError(PLLN + "Bcounter >8191")
            if Bcounter < Acounter:
                raise RuntimeError(PLLN + "Bcounter<Acounter")
            # N20 is Phase Det Current, 1= 1 ma (add 1 << 20), 0= 250 ua
            Nreg = 1 + (1 << 20) + (Bcounter << 7) + (Acounter << 2)

        if PLLN == "2350":
            if Bcounter < 3:
                raise RuntimeError(PLLN + "Bcounter <3")  # JGH Error < 3 common to all
            if Bcounter > 1023:
                raise RuntimeError(PLLN + "Bcounter > 2047")
            if Bcounter < Acounter + 2:
                raise RuntimeError(PLLN + "Bcounter<Acounter")
            # N21: 0 if preselector = 16 else if preselector =32 then = 1 and add (1 << 21)
            Nreg = 3 + (Bcounter << 11) + (Acounter << 6) + (fcounter << 2)

        if PLLN == "2353":
            if Bcounter < 3:
                raise RuntimeError(PLLN + "Bcounter <3")  # JGH Error < 3 common to all
            if Bcounter > 1023:
                raise RuntimeError(PLLN + "Bcounter > 2047") # EON Jan 29, 2014
            if Bcounter < Acounter + 2:
                raise RuntimeError(PLLN + "Bcounter<Acounter")
            # N21: 0 if preselector = 16 else if preselector =32 then = 1 and add (1 << 21)
            Nreg = (3 + (Bcounter << 11) + (Acounter << 6) + (fcounter << 2))

        if (PLLN == "4112" or PLLN == "4113"):
            if Bcounter < 3:
                raise RuntimeError(PLLN + "Bcounter <3")  # JGH Error < 3 common to all
            if Bcounter > 8191:
                raise RuntimeError(PLLN + "Bcounter > 2047")
            if Bcounter < Acounter:
                raise RuntimeError(PLLN + "Bcounter<Acounter")
            # N21:  0=Chargepump setting 1; 1=setting 2; default 0
            Nreg = 1 + (Bcounter << 8) + (Acounter << 2)

        self.PLLbits = Nreg
        self.Acounter = Acounter
        self.Bcounter = Bcounter

        if debug:
            print ("LO%d: N= 0x%06x" % (self.id, Nreg))
            print("PLLbits(Nreg), Acounter, Bcounter: ", self.PLLbits, self.Acounter, self.Bcounter)

    #--------------------------------------------------------------------------
    # Calculate PLL and DDS settings for given frequency.
    # Place the in an array indexed by _step

    def Calculate(self, freq):
        self.freq = freq
        appxVCO = freq
        reference = self.appxdds
        if debug:
            print ("LO%d: freq=" % self.id, freq, "ref=", reference, \
                "rcounter=", self.rcounter)

##        if self.PLLmode: # PLLmode not used, always Integer
##            self._CreateFractionalNcounter(appxVCO, reference)
##        else:
##            self.CreateIntegerNcounter(appxVCO, reference)
##            self.pdf = divSafe(appxVCO, self.ncounter) # JGH 2/2/14
        # JGH 2/7/14
        self.CreateIntegerNcounter(appxVCO, reference)
        self.pdf = divSafe(appxVCO, self.ncounter) # JGH 2/2/14
        # JGH 2/7/14

        if debug:
            print ("LO%d: ncounter=" % self.id, self.ncounter, "fcounter=", \
                self.fcounter, "pdf=", self.pdf)

        # actual output of DDS (input Ref to PLL)
        self.ddsoutput = self.pdf * self.rcounter

# JGH 2/7/14 starts: PLLmode not used, always Integer
##        if self.PLLmode:
##            # AutoSpur-- used only in MSA when PLL is Fractional
##            # reset spur, and determine if there is potential for a spur
##            spur = 0
##            LO2freq = msa.LO2freq
##            finalfreq = msa.finalfreq
##            firstif = LO2freq - finalfreq
##            # fractional frequency
##            ff = divSafe(self.ddsoutput, (self.rcounter*16))
##            if ff != 0:
##                harnonicb = int(round(firstif / ff))
##                harnonica = harnonicb - 1
##                harnonicc = harnonicb + 1
##                firstiflow = LO2freq - (finalfreq + msa.finalbw/1000)
##                firstifhigh = LO2freq - (finalfreq - msa.finalbw/1000)
##                if (harnonica*ff > firstiflow and \
##                    harnonica*ff < firstifhigh) or \
##                   (harnonicb*ff > firstiflow and \
##                    harnonicb*ff < firstifhigh) or \
##                   (harnonicc*ff > firstiflow and \
##                    harnonicc*ff < firstifhigh):
##                    spur = 1
##                    if self.ddsoutput < self.appxdds:
##                        self.fcounter -= 1
##                    elif self.ddsoutput > self.appxdds:
##                        self.fcounter += 1
##                if self.fcounter == 16:
##                    self.ncounter += 1
##                    self.fcounter = 0
##                elif self.fcounter < 0:
##                    self.ncounter -= 1
##                    self.fcounter = 15
##                self.pdf = divSafe(self.freq, (self.ncounter + \
##                    (self.fcounter/16)))
##                # actual output of DDS (input Ref to PLL)
##                self.ddsoutput = self.pdf * self.rcounter
##                if debug:
##                    print ("LO%d: AutoSpur ddsoutput=" % self.id, \
##                        self.ddsoutput, "pdf=", self.pdf)
##
##            # ManSpur -- used only in MSA when PLL is Fractional
##            #            and Spur Test button On
##            if msa.spurcheck:
##                if self.ddsoutput < self.appxdds:
##                    # causes +shift in pdf
##                    self.fcounter -= 1
##                elif self.ddsoutput > self.appxdds:
##                    # causes -shift in pdf
##                    self.fcounter += 1
##            if self.fcounter == 16:
##                self.ncounter += 1
##                self.fcounter = 0
##            elif self.fcounter < 0:
##                self.ncounter -= 1
##                self.fcounter = 15
##            self.pdf = divSafe(self.freq, (self.ncounter + (self.fcounter/16)))
##            # actual output of DDS (input Ref to PLL)
##            self.ddsoutput = self.pdf * self.rcounter
##            if debug:
##                print ("LO%d: ManSpur ddsoutput=" % self.id, self.ddsoutput, \
##                        "pdf=", self.pdf)
# JGH 2/7/14 ends

        self.CreatePLLN()

        # CalculateThisStepDDS1 --
        # JGH 2/2/14
        if abs(self.ddsoutput-self.appxdds) > self.ddsfilbw/2:
            raise RuntimeError("DDS%doutput outside filter range: output=%g "\
                               "pdf=%g" % (self.id, self.ddsoutput, self.pdf))


        #CreateBaseForDDSarray --

        # The formula for the frequency output of the DDS
        # (AD9850, 9851, or any 32 bit DDS) is taken from:
        # ddsoutput = base*msa.masterclock/2^32
        # rounded off to the nearest whole bit
        base = int(round(divSafe(self.ddsoutput * (1<<32), GetMsa().masterclock))) # JGH 2/2/14
        self.DDSbits = base
        if debug:
            print ("LO%d: base=%f=0x%x" % (self.id, base, base))
