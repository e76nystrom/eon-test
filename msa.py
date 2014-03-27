#!/usr/bin/env python
# -*- coding: utf-8 -*-
###############################################################################
#
#                       MODULAR SPECTRUM ANALYZER 
#
# The original Python software, written by Scott Forbes, was a complete rewrite
# of the original Liberty Basic code developed by Scotty Sprowls (the designer
# of the Spectrum Analyzer) and Sam Weterlin. Over a period of nine months,
# comencing in May/June, 2013, Scott's code has been expanded and debugged by
# Jim Hontoria, W1JGH and Eric Nystrom, W1EON in close consultation with Scotty.
# Other contributors to the testing have been Will Dillon and  Earle Craig.
#
# Copyright (c) 2011, 2013 Scott Forbes
#
# This file may be distributed and/or modified under the terms of the
# GNU General Public License version 2 as published by the Free Software
# Foundation. (See COPYING.GPL for details.)
#
# This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
# WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
#
###############################################################################

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

SetModuleVersion("msa",("1.02","JGH.f","03/24/2014"))

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
        global msa
        msa = self
        self.frame = frame
        p = frame.prefs
        self.mode = p.get("mode", self.MODE_SA) # Default start mode
        # Exact frequency of the Master Clock (in MHz).
        self.masterclock = p.get("masterclock", 64.)
        # 2nd LO frequency (MHz). 1024 is nominal,
        # Must be integer multiple of PLL2phasefreq
        self.appxLO2 = p.get("appxLO2", 1024.)
        # list of Final Filter freq (MHz), bw (kHz) pairs
        ##self.RBWFilters = p.get("RBWFilters", [(10.698375, 8)])
        # JGH changed above line for next line
        self.RBWFilters = p.get("RBWFilters", [(10.7, 300.), (10.7, 30.), (10.7, 3.), (10.7, 0.3)]) # Defaults
        # selected Final Filter index
        self.RBWSelindex = self.switchRBW = i = p.get("RBWSelindex", 0)
        # Final Filter frequency, MHz; Final Filter bandwidth, KHz
        self.finalfreq, self.finalbw = self.RBWFilters[i]
        self.bitsRBW = 4 * i  # JGH 10/31/13
        # Video Filters
        self.vFilterNames = ["Wide", "Medium", "Narrow", "XNarrow"]
        self.vFilterCaps = p.get("vFilterCaps", [0.001, 0.1, 1.0, 10.0]) # Defaults
        self.vFilterSelindex = p.get("vFilterSelindex", 2) # JGH This is the default mode
        self.vFilterSelname = self.vFilterNames[self.vFilterSelindex]
##        self.bitsVideo = p.get("vFilterSelindex", 2)
##        self.cftest = p.get("cftest", False)
        self.cftest = cftest = False
        # Trace blanking gap
        self.bGap = p.get("bGap", False)
        # Where RBW switch is connected
        self.rbwP4 = p.get("rbwP4", False)

        # SG output frequency (MHz)
        self._sgout = 10.
        # =0 if TG is normal, =1 if TG is in reverse.
        self._normrev = 0
        # TG offset frequency
        self._offset = 0
        # FWD/REV and TRANS/REFL
        self.switchFR = p.get("switchFR", False)
        self.switchTR = p.get("switchTR", 0)
##        self.bitsFR = 16 * self.switchFR
##        self.bitsTR = 32 * self.switchTR
        # this assures Spur Test is OFF.
        self.spurcheck = 0
        # 1, 2 or 3, indicating bands 1G, 2G and 3G
        p.switchBand = p.get("switchBand", 1)
        if p.switchBand == 2:
##            self.bitsBand = 64 * 1 # Band 2
            self._GHzBand = 2
        else:
##            self.bitsBand = 64 * 0 # Bands 1 and 3
            self._GHzBand = 1 # (or 3)
        # Pulse switch
        self.switchPulse = p.get("switchPulse", 0)
##        self.bitsPulse = 128 * self.switchPulse
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
    #NOT USED WITHIN THIS MODULE

    def DumpEvents(self):
        print ("------------ MSA Events ---------------")
        for event in self._events:
            print ("%6d.%03d:" % (event.when/1000, event.when % 1000),event.what)
        print ("---------------------------------------")

    #--------------------------------------------------------------------------
    # Write debugging event lists to a file.
    # NOT USED WITHIN THIS MODULE

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
    # Calculate all steps for LO1 synthesizer.
    # NOT USED ANY MORE: CODE MOVED TO CREATE SWEEP ARRAY

    def _CalculateAllStepsForLO1Synth(self, thisfreq, band):
        self._GHzBand = band
        thisfreq = self._Equiv1GFreq(thisfreq)  # get equivalent 1G frequency
        # calculate actual LO1 frequency
        LO1.Calculate(thisfreq + LO2.freq - self.finalfreq)

    #--------------------------------------------------------------------------
    # Calculate all steps for LO3 synthesizer.
    # CODE TENTATIVELY MOVED TO CREATE SWEEP ARRAY

    def _CalculateAllStepsForLO3Synth(self, TrueFreq):
        
        thisfreq = self._Equiv1GFreq(TrueFreq)  # get equivalent 1G frequency

        LO2freq = LO2.freq
        if self.mode != self.MODE_SA:
            offset = self._offset
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
    def _CommandAllSlims(self): # IS CALLED AT EVERY STEP OF THE SWEEP
        # NOTE that the ByteList is pre-stored in the step indexed StepArray
        global cb
        p = self.frame.prefs
        f = self._freqs[0]
        band = min(max(int(f/1000) + 1, 1), 3) # JGH Initial band

        step1k = self.step1k ; step2k =self.step2k
        if p.sweepDir == 0:
            if ((step1k != None and self._step == (step1k - 1)) or \
                (step2k != None and self._step == (step2k - 1))):
                band = band + 1
                self._SetFreqBand(band)
                cb.msWait(100)
            self.sendByteList()
        if p.sweepDir == 1:
            if (self._step == (step1k) or self._step == (step2k)):
                band = band - 1
                self._SetFreqBand(band)
                cb.msWait(100)
            self.sendByteList() # JGH Change this to account for reciprocal
    #--------------------------------------------------------------------------

    def sendByteList(self):
        global cb
        p = self.frame.prefs
        byteList = self.SweepArray[self._step]
        cb.SendDevBytes(byteList, cb.P1_Clk)    # JGH 2/9/14

        # print (">>>>> 2106, Remove data, leaving bitsRBW data to filter bank"
        if p.rbwP4 == False:
            cb.SetP(1, self.bitsRBW)
        elif p.rbwP4 == True:
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
        switchBits = self.getSwitchBits()

        self._GHzBand = band
        band += extraBits
        if self._GHzBand == 2:
            self.bitsBand = 64 * 0
        else:
            self.bitsBand = 64 * 1
        if self.rbwP4 == True:
            # Clear the frequency band bits (bit 6 of P4)
            bitPos = 6 ; switchBits &= ~(1 << bitPos)
            switchBits = switchBits + self.bitsBand
        else:
            # Clear the frequency band bits (bits 2 and 3 of P4)
            bitPos = 2 ; switchBits &= ~(1 << bitPos)
            bitPos = 3 ; switchBits &= ~(1 << bitPos)
            
            switchBits = switchBits + self.bitsBand
        cb.SetP(4, switchBits)
        cb.setIdle()
        if debug:
            print ("G%02x" % band )

    #--------------------------------------------------------------------------
    # Get the switch bits

    def getSwitchBits(self):
        p = self.frame.prefs
        self.vFilterSelindex = p.get("vFilterSelindex", 1)   # Values 0-3
        self.switchRBW = p.get("RBWSelindex", 0) # Values 0-3
        self.switchFR = p.get("switchFR", False) # Values 0,1
        self.switchTR = p.get("switchTR", 0) # Values 0,1
        self.switchBand = p.get("switchBand", 1) # 1: 0-1GHz, 2: 1-2GHz, 3: 2-3GHz
        self.switchPulse = 0 # JGH Oct23 Set this here and follow with a 1 sec delay

        self.bitsVideo = self.vFilterSelindex # V0/V1 Bits 0,1
        self.bitsFR = 16 * self.switchFR # Bit 4
        self.bitsTR = 32 * self.switchTR    # Bit 5
        self.bitsPulse = 128 * self.switchPulse # Bit 7
        if self.rbwP4 == True:
            self.bitsBand = 64 * self. switchBand # G0 Bit 6 of P4
            self.bitsRBW = 4 * self.switchRBW # A0/A1 Bits 2, 3 of P4
            switchBits = self.bitsVideo + self.bitsRBW + self.bitsFR + \
                    self.bitsTR + self.bitsBand + self.bitsPulse
        elif self.rbwP4 == False:
            self.bitsBand = 4 * self. switchBand # G0 Bits 2, 3 of P4
            switchBits = self.bitsVideo + self.bitsFR + \
                    self.bitsTR + self.bitsBand + self.bitsPulse
        if 0 or debug:
            print ("msa>376< switchBits: ", bin(switchBits))
        return switchBits

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
            if p.syntData:
##                print ("\nmsa>2463< GENERATING SYNTHETIC DATA") # JGH syndutHook2
                from synDUT import SynDUTDialog
                self.syndut = SynDUTDialog(self.gui)
                wx.Yield()
                self.gui.Raise()

        # Instantiate MSA's 3 local oscillators
        
        PLL1phasefreq = p.get("PLL1phasefreq", 0.974)
        if self.cftest == False:
            PLL2phasefreq = p.get("PLL2phasefreq", 4.000)
        else:
            PLL2phasefreq = 0.1
        if 0 or debug:    
            print("msa>459< Entering Initialize Hardware with cftest:", self.cftest, \
                  "and PLL2phasefreq:", PLL2phasefreq)
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
        # JGH: This may require some investigation for RBWinP4
        cb.OutPort(0)
        # latch "0" into all SLIM Control Board Buffers
        cb.OutControl(cb.SELTINITSTRBAUTO)
        # begin with all control lines low
        cb.OutControl(cb.contclear)

        self._SetFreqBand(1)
##        self.lastBand = 1
        self.lastStepAttenDB = -1 # TODO: ATTENUATOR

        # 6. Initialize DDS3 by reseting to serial mode.
        # Frequency is commanded to zero
        # TODO: Check if USB needs a different value (see LB code)
        LO3.ResetDDSserSLIM()

        # JGH starts 3/16/14
        # Precalculate all non-frequency dependent PLL parameters

        # Get Rcounter, pdf (phase detector frequency
        LO1.rcounter, LO1.pdf = LO1.CreateRcounter(LO1.appxdds)
        LO2.rcounter, LO2.pdf = LO2.CreateRcounter(self.masterclock)
        LO3.rcounter, LO3.pdf = LO3.CreateRcounter(LO3.appxdds)

        # 7. Initialize PLO3. No frequency command yet.
        LO3.CommandPLLR()

        # 8.initialize and command PLO2 to proper frequency
        # Command PLL2R and Init Buffers (needs:PLL2phasepolarity,SELT,PLL2)
        LO2.CommandPLLR()
        # Ncounter
        # (needs: PLL2 (aka appxVCO), rcounter, fcounter)
        # (For LO2: creates: ncounter, fcounter(0))
        # LO1 and LO3 are frequency dependent (see LO1.Calculate)
        # LO2 is frequency dependent during the cavity filter test
        # Here we are just initializing hardware so:
        
        # CreateIntegerNcounter(needs: PLL2 (aka appxVCO), rcounter, fcounter)
        appxVCO = self.appxLO2  # JGH: HardwareConfig Dialog value, 1024 nominal
        LO2.CreateIntegerNcounter(appxVCO, self.masterclock)
        # This will be recreated in CreateSweepArray for cftest
        if 0 or debug:
            print("msa>533< LO2.ncounter; ", LO2.ncounter)

        # Nregister: Acounter, Bcounter, Nbits
        # LO1 and LO3 are frequency dependent

        # LO2 is frequency dependent only during the cavity filter test
        # (needs: ncounter, fcounter, PLL2)
        LO2.CreatePLLN()    # Creates Bcounter,Acounter, and PLLbits N0-N23)
        if 0 or debug:
            print("msa>542< LO2 Acounter, BCounter, PLLbits: ", \
              LO2.Acounter, LO2.Bcounter, LO2.PLLbits)

        # 8b. Actual LO2 frequency
        LO2.freq = ((LO2.Bcounter*LO2.preselector) + LO2.Acounter + \
                    (LO2.fcounter/16))*LO2.pdf
        if 0 or debug:
            print("msa>549< Actual LO2 frequency: ", LO2.freq)

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
        # condition. reset serial DDS1 without disturbing Filter Bank or PDM
        LO1.ResetDDSserSLIM()   # SCOTTY TO MODIFY THIS TO LIMIT HIGH CURRENT

        # JGH added 10a. Set Port 4 switches 2/24/14
        switchBits = self.getSwitchBits()
        cb.SetP(4, switchBits)
        # Commanding P1 for RBW switching is done somewhere else

        # JGH addition ended
        print("*********************************************************")
        print("*********************************************************")
        print("*********************************************************")
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
        if 0 or debug:
            print ("msa>587< _ReadAD16Status: mag=0x%x, phase=0x%x" % \
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
                print ("msa>600< msa.InputSynth: length mismatch: \
                        nf=%d nM=%d nP=%d" % (nf, nM, nP))
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
                    self.invPhase ^= 1
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
                        print ("msa>671< invPhase failed at %13.6f mag %5d orig %5d new %5d" \
                               % (f, self._magdata, oldPhase, self._phasedata))
                        self.invPhase ^= 1

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
                            print ("msa>769< jumped gap=", f, H1f, f // 1000, \
                                H1f // 1000, dSdb)
                    if show:
                        print ("msa>772< hist=", ["%7.2f %7.2f %7.2f" % x for x in hist], \
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
        self._normrev    = parms.normRev # 0 for nrmal TG, 1 for TG in reverse
        self._sweepDir   = parms.sweepDir
        self._isLogF     = parms.isLogF
        self._contin     = parms.continuous

        # set start and stop frequencies, swapped if sweeping downward
        fStart = parms.fStart
        fStop  = parms.fStop

        #The following conditonal may not be needed here

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
            self._freqs = linspace(fStart, fStop, nSteps+1) # (numpy)
            # Note: if sweep changes direction at the end of the sweep,
            # the array should be read backwards.
            # This happens at the end of the sweep, NOT HERE
            # A flag is set in the sweep dialog

        self.step1k = self.step2k = None
        # Note: step1k and step2k are used to signal the switchBand relay
        for x, y in enumerate(self._freqs):
            if y == 1000:
                self.step1k = x
            if y == 2000:
                self.step2k = x
        if 0 or debug:
            print("msa>920< 1000 is at step #", self.step1k)
            print("msa>921< 2000 is at step #", self.step2k)

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
                self.CreateSweepArray() # Creates SweepArray
                self.LogEvent("ContinueScan start_new_thread")
                self.scanEnabled = self._scanning = True
                thread.start_new_thread(self._ScanThread, ())
            self.LogEvent("ContinueScan exit")

    #--------------------------------------------------------------------------
    # SweepArray and StepArray # JGH all new code 3/15/14
    # (send data and clocks without changing Filter Bank)
    #  0-15 is DDS1bit*4 + DDS3bit*16, data = 0 to PLL 1 and PLL 3.
    # (see CreateCmdAllArray). new Data with no clock,latch high,latch low,
    # present new data with clock,latch high,latch low. repeat for each bit.
    # (40 data bits and 40 clocks for each module, even if they don't need that many)
    # This format guarantees that the common clock will
    # not transition with a data transition, preventing crosstalk in LPT cable.

    def CreateSweepArray(self):
        global cb
        p = self.frame.prefs
        SweepArray = [] # aka GEORGE
        VarsArray = []  # VarsArray size = VariableList size  # aka MARTHA
        StepArray = []  # StepArray size = Number of steps # aka BIG BERTHA

        for f in self._freqs:
##            band = min(max(int(f/1000) + 1, 1), 3) # JGH Values 1,2,3
            _GHzBand = min(max(int(f/1000) + 1, 1), 3) # JGH Values 1,2,3
            self._GHzBand = _GHzBand
##            thisfreq = self._Equiv1GFreq(thisfreq)  # get equivalent 1G frequency
            thisfreq = self._Equiv1GFreq(f)  # get equivalent 1G frequency
            # With this we got all LO1.freq (thisfreq)
            # Calculate all Steps for LO2. When in cftest mode, the
            # fixed value parameters will be modified

            # Calculate All Steps For LO1.freq (PLL1 Synthesizer)
            # Calculate actual LO1 frequency.
            # Gets ncounter, fcounter, pdf and ddsoutput
            LO1.Calculate(thisfreq + LO2.freq - self.finalfreq)
            if 0 or debug:
                print("msa>988< f, LO2.freq, thisfreq, LO1.freq: ", f, thisfreq, LO1.freq)

            # Ncounter (For LO2: creates: ncounter, fcounter(0))
            if self.cftest == False:
                # Calculate actual LO1 frequency.
                # Gets ncounter, fcounter, pdf and ddsoutput
                appxVCO = self.appxLO2
                LO2.CreateIntegerNcounter(appxVCO, self.masterclock)
                LO2.CreatePLLN()
                LO2.DDSbits = 0 ; LO2.fcounter = 0
            else:
        #--------------------------------------------------------------------------
                # THIS SECTION TO BE USED IN cftest
                # LO2 is frequency dependent during the cavity filter test
##                cavityLO2 = self.finalfreq + LO1.freq
                cavCenterFreq = 1013.3
                cavityLO2 = thisfreq + self.finalfreq + cavCenterFreq 
                LO2.CreateIntegerNcounter(cavityLO2, self.masterclock)
                if 0 or debug:
                    print("msa>1007< cavityLO2, ncounter, fcounter: ", \
                          cavityLO2, LO2.ncounter, LO2.fcounter)
                LO2.CreatePLLN()
                LO2.freq = ((LO2.Bcounter*LO2.preselector) + LO2.Acounter+ \
                            (LO2.fcounter/16))*LO2.pdf
                LO2.DDSbits = 0 ; LO2.fcounter = 0
                if 0 or debug:
                    print("msa>1014< cavityLO2, rcounter, pdf, ncounter, fcounter, \
                          Acounter, Bcounter, PLLbits: ",\
                          cavityLO2, LO2.rcounter, LO2.pdf, LO2.ncounter, LO2.fcounter,
                          LO2.Acounter, LO2.Bcounter, LO2.PLLbits)
        #--------------------------------------------------------------------------
            LO2freq = LO2.freq

            # Calculate All Steps For LO3 Synthesizer
            # Gets ncounter, fcounter, pdf and ddsoutput
            self._CalculateAllStepsForLO3Synth(f)

            # HERE IS WHERE WE HAVE TO ADD THE LO2 PARAMS
            # No need to worry for DATAPLL2 since is common to DDS3
            # PLLs go out MSB first, with a 16-bit leader of zeros
            PLL1bits = LO1.PLLbits
            PLL2bits = LO2.PLLbits
            PLL3bits = LO3.PLLbits
            msb = 23 + 16
            shift1 = msb - cb.P1_PLL1DataBit
            shift2 = msb - cb.P1_PLL2DataBit 
            shift3 = msb - cb.P1_PLL3DataBit
            mask = 1 << msb
            # pre-shift 40 bits for each DDS so the LSB aligns with its port
            # serial-data bit
            DDS1bits = LO1.DDSbits << cb.P1_DDS1DataBit
            DDS3bits = LO3.DDSbits << cb.P1_DDS3DataBit
            if 0 or debug:
                print ("PLL1bits=0x%010x" % PLL1bits)
                print ("DDS1bits=0x%010x" % DDS1bits)
                print ("DDS3bits=0x%010x" % DDS3bits)

            byteList = []   # JGH 2/9/14
            for i in range(40):
                # combine the current bit for each device and clk them out together
                a = (DDS3bits & cb.P1_DDS3Data) + ((PLL3bits & mask) >> shift3) + \
                     (DDS1bits & cb.P1_DDS1Data) + ((PLL1bits & mask) >> shift1)
                if self.cftest == True:
                    a += ((PLL2bits & mask) >> shift2)
                if self.rbwP4 == False:       
                    a += self.bitsRBW 
                byteList.append(a)  # JGH 2/9/14
                # shift next bit into position NOT USED ANYMORE
                DDS3bits >>= 1; PLL3bits <<= 1
                DDS1bits >>= 1; PLL1bits <<= 1
                
            SweepArray.append(byteList)

            # MARTHA: array containg all parameters for ONE step

##            The RealFinalIF as defined in LB is:
##            LO2 - (PLL1array(thisstep,45)*DDS1array(thisstep,46)/rcounter1) + \
##                datatable(thisstep,1) + baseFrequency, 5, 380, 180, 13
##            with:
##            PLL1array(thisstep,45) = ncounter1
##            DDS1array(thisstep,46) = dds1output
##            datatable(thisstep, 1) = thisfreq
##            baseFrequency =
##            and ends up saying:
##            RealFinalIF = LO2 -(LO1-thisfreq)
            RealFinalIF = LO2.freq -(LO1.freq - thisfreq)
            
            VarsArray = [f, \
                         LO1.ddsoutput, LO1.freq, LO1.pdf, LO1.ncounter, LO1.Bcounter, \
                         LO1.Acounter,  LO1.fcounter, LO1.rcounter, \
                         LO2.ddsoutput, LO2.freq, LO2.pdf, LO2.ncounter, LO2.Bcounter, \
                         LO2.Acounter,  LO2.fcounter, LO2.rcounter, \
                         LO3.ddsoutput, LO3.freq, LO3.pdf, LO3.ncounter, LO3.Bcounter, \
                         LO3.Acounter,  LO3.fcounter, LO3.rcounter, \
                         RealFinalIF, self.masterclock]

            # BIG BERTHA: array containing parameters for ALL steps, used to Show Variables
            StepArray.append(VarsArray)

        if 0 or debug:
            print("msa>1088< StepArray[0]: ", StepArray[0])
            print("msa>1089< Last Step: ", StepArray[self._nSteps])
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
        textList = [
            "this step = %d" % step,
            "frequency = %0.6g MHz" % self.StepArray[step][0],
            "dds1output = %0.9g MHz" % self.StepArray[step][1],
            "LO1 = %0.9g MHz" % self.StepArray[step][2],
            "pdf1 = %0.9g MHz" % self.StepArray[step][3],
            "ncounter1 = %d" % self.StepArray[step][4],
            "Bcounter1 = %d" % self.StepArray[step][5],
            "Acounter1 = %d" % self.StepArray[step][6],
            "fcounter1 = %d" % self.StepArray[step][7],
            "rcounter1 = %d" % self.StepArray[step][8],
            "LO2 = %0.6f MHz" % self.StepArray[step][10],
            "pdf2 = %0.6f MHz" % self.StepArray[step][11],
            "ncounter2 = %d" % self.StepArray[step][12],
            "Bcounter2 = %d" % self.StepArray[step][13],
            "Acounter2 = %d" % self.StepArray[step][14],
            "rcounter2 = %d" % self.StepArray[step][16],
            "dds3output = %0.9g MHz" % self.StepArray[step][17],
            "LO3 = %0.6f MHz" % self.StepArray[step][18],
            "pdf3 = %0.6f MHz" % self.StepArray[step][19],
            "ncounter3 = %d" % self.StepArray[step][20],
            "Bcounter3 = %d" % self.StepArray[step][21],
            "Acounter3 = %d" % self.StepArray[step][22],
            "fcounter3 = %d" % self.StepArray[step][23],
            "rcounter3 = %d" % self.StepArray[step][24],
            "Magdata=%d mag=%0.5g" % (self._magdata, self._Sdb),
            "Phadata=%d PDM=%0.5g" % (self._phasedata, self._Sdeg),
            "Real Final I.F. = %f" % self.StepArray[step][25],
            "Masterclock = %0.6f" % self.StepArray[step][26]
            ]
        return textList

    #--------------------------------------------------------------------------
    # Spectrum accessors.

    def HaveSpectrum(self):
        return self._fStart != None

    def NewSpectrumFromRequest(self, title):
        return Spectrum(title, self.RBWSelindex+1, self._fStart, self._fStop,
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
        self.preselector = 32               # DEFAULT
        if 0 or debug:
            print ("msa>1191< LO%d init: PDF=%f" % (id, PLLphasefreq))

        # PLL R counter
        self.CreateRcounter(self.appxdds)
        if GetMsa().spurcheck:
            self.rcounter += 1  # only do this for IntegerN PLL
            self.pdf = 0   # phase detector frequency of PLL (MHz)

    #--------------------------------------------------------------------------
    # Create rcounter, pdf.

    def CreateRcounter(self, reference):
        self.rcounter = int(round(divSafe(reference, self.PLLphasefreq)))
        self.pdf = divSafe(reference, self.rcounter)
        if 0 or debug:
            print ("msa>1206< LO%d: R=%d=0x%06x pdf=%f" % (self.id, self.rcounter, \
                        self.rcounter, self.pdf))
        return self.rcounter, self.pdf # JGH 2/1/14

    #--------------------------------------------------------------------------
    # Set a PLL's register.

    def CommandPLL(self, data):
        global cb
        # CommandPLLslim --
        if 0 or debug:
            print ("msa>1220< LO%d CommandPLL 0x%06x" % (self.id, data))
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
            preselector = 32 # DEFAULT
            # N15 = 1 if preselector = 32, = 0 for preselector = 64, default 1
            if preselector == 32:
                N15 = 0x1
##                self.CommandPLL((self.rcounter << 1) + 0x1 + (0x1 << 15))
            elif preselector == 64 : # OPTIONAL
                N15 = 0x0
##                self.CommandPLL((self.rcounter << 1) + 0x1)
            self.preselector = preselector
            self.CommandPLL((self.rcounter << 1) + 0x1 + (N15 << 15))

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
            preselector = 32 # DEFAULT
            if preselector == 8:
                N22=0x0; N23=0x0
            elif preselector == 16:
                N22=0x1; N23=0x0
            elif preselector == 32:
                N22=0x0; N23=0x1
            elif preselector == 64:
                N22=0x1; N23=0x1
##            self.CommandPLL((self.phasepolarity << 7) + 0x3 + (0x1 << 15)
##                            + (0x1 << 18) + (0x1 << 23))
##            self.CommandPLL((self.rcounter << 2) + (0x1 << 23)) # changed from 22
            self.preselector = preselector
            self.CommandPLL((self.phasepolarity << 7) + 0x3 + (0x1 << 15) \
                            + (0x1 << 18) + (N23 << 23))
            # Note: if the 4112 tends to oscillate due to high charge pump
            # current, change above to:
            # self.CommandPLL((self.phasepolarity << 7) + 0x3 + (0x9 << 15) \
            #               + (0x1 << 18) + (N23 << 23))
            self.CommandPLL((self.rcounter << 2) + (N22 << 22))

    #--------------------------------------------------------------------------
    # Reset serial DDS without disturbing Filter Bank or PDM.

    def ResetDDSserSLIM(self):
        global cb
        # must have DDS (AD9850/9851) hard wired. pin2=D2=0, pin3=D1=1,
        # pin4=D0=1, D3-D7 are don# t care. this will reset DDS into
        # parallel, invoke serial mode, then command to 0 Hz.
        if 0 or debug:
            print ("msa>1300< ResetDDSserSLIM")
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

        # (flush and command DDSx) D7, WCLK up, WCLK down, (repeat39more),
        # FQUD up, FQUD down present data to buffer,latch buffer,disable
        # buffer, present data+clk to buffer,latch buffer,disable buffer

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
        if 0 or debug:
            print ("msa>1397< ResetDDSserSLIM done")

    #--------------------------------------------------------------------------
    # Create Integer Mode N counter.

    def CreateIntegerNcounter(self, appxVCO, reference):
        # approximates the Ncounter for PLL
        ncount = divSafe(appxVCO, divSafe(reference, self.rcounter))
        ncounter = int(round(ncount))
        if 0 or debug:
            print("msa>1407< appxVCO, reference, ncounter: ", \
                  appxVCO, reference, ncounter)
        self.fcounter = 0
        # actual phase freq of PLL
        self.pdf = divSafe(appxVCO, ncounter) # JGH 2/2/14 Beware of globals!
        self.ncounter = ncounter

    #--------------------------------------------------------------------------
    # Create PLL N register.

    def CreatePLLN(self):
        preselector = self.preselector
        fcounter = 0 # EON Jan 29, 2014

        # CreateNBuffer,

        Bcounter = int(self.ncounter/preselector)
        Acounter = int(self.ncounter-(Bcounter*preselector))

        if 0 or debug:
            print("msa>1422< self.PLLtype, ncounter: ", self.PLLtype, self.ncounter)
            print("msa>1423< LO%d: Acounter=" % self.id, Acounter, "Bcounter=", Bcounter)

        if self.PLLtype == "2325":
            if Bcounter < 3:
                raise RuntimeError(self.PLLtype + "Bcounter <3")
            if Bcounter > 2047:
                raise RuntimeError(self.PLLtype + "Bcounter > 2047")
            if Bcounter < Acounter:
                raise RuntimeError(self.PLLtype + "Bcounter < Acounter")
            Nreg = (Bcounter << 8) + (Acounter << 1)

        if (self.PLLtype == "2326" or self.PLLtype == "4118"):
            if Bcounter < 3:
                raise RuntimeError(self.PLLtype + "Bcounter <3")  # JGH Error < 3 common to all
            if Bcounter > 8191:
                raise RuntimeError(self.PLLtype + "Bcounter >8191")
            if Bcounter < Acounter:
                raise RuntimeError(self.PLLtype + "Bcounter < Acounter")
            # N20 is Phase Det Current, 1= 1 ma (add 1 << 20), 0= 250 ua
            Nreg = 1 + (1 << 20) + (Bcounter << 7) + (Acounter << 2)

        if self.PLLtype == "2350":
            if Bcounter < 3:
                raise RuntimeError(self.PLLtype + "Bcounter <3")  # JGH Error < 3 common to all
            if Bcounter > 1023:
                raise RuntimeError(self.PLLtype + "Bcounter > 2047")
            if Bcounter < Acounter + 2:
                raise RuntimeError(self.PLLtype + "Bcounter < Acounter")
            # N21: 0 if preselector = 16 else if preselector =32 then = 1 and add (1 << 21)
            Nreg = 3 + (Bcounter << 11) + (Acounter << 6) + (fcounter << 2) + (1 << 21)

        if self.PLLtype == "2353":
            if Bcounter < 3:
                raise RuntimeError(self.PLLtype + "Bcounter <3")  # JGH Error < 3 common to all
            if Bcounter > 1023:
                raise RuntimeError(self.PLLtype + "Bcounter > 2047") # EON Jan 29, 2014
            if Bcounter < Acounter + 2:
                raise RuntimeError(self.PLLtype + "Bcounter < Acounter")
            # N21: 0 if preselector = 16 else if preselector =32 then = 1 and add (1 << 21)
            Nreg = (3 + (Bcounter << 11) + (Acounter << 6) + (fcounter << 2)) + (1 << 21)

        if (self.PLLtype == "4112" or self.PLLtype == "4113"):
            if Bcounter < 3:
                raise RuntimeError(self.PLLtype + "Bcounter <3")  # JGH Error < 3 common to all
            if Bcounter > 8191:
                raise RuntimeError(self.PLLtype + "Bcounter > 2047")
            if Bcounter < Acounter:
                raise RuntimeError(self.PLLtype + "Bcounter < Acounter")
            # N21:  0=Chargepump setting 1; 1=setting 2; default 0
            Nreg = 1 + (Bcounter << 8) + (Acounter << 2)

        self.PLLbits = Nreg
        self.Acounter = Acounter
        self.Bcounter = Bcounter

        if 0 or debug:
            print("msa>1479< LO%d: N= 0x%06x" % (self.id, Nreg))
            print("msa>1480< PLLbits(Nreg), Acounter, Bcounter: ", self.PLLbits, self.Acounter, self.Bcounter)

    #--------------------------------------------------------------------------
    # Calculate PLL and DDS settings for given frequency.
    # Place them in an array indexed by _step

    def Calculate(self, freq):
        global msa
        self.freq = freq
        appxVCO = freq
        reference = self.appxdds

        if 0 or debug:
            print ("msa>1497< LO%d: freq=" % self.id, freq, "ref=", reference, \
                "rcounter=", self.rcounter)

        self.CreateIntegerNcounter(appxVCO, reference) # JGH 2/7/14

        if 0 or debug:
            print ("msa>1503< LO%d: ncounter=" % self.id, self.ncounter, "fcounter=", \
                self.fcounter, "pdf=", self.pdf)

        # actual output of DDS (input Ref to PLL)
        self.ddsoutput = self.pdf * self.rcounter

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
        if 0 or debug:
            print ("msa>1526< LO%d: base=%f=0x%x" % (self.id, base, base))
