from msaGlobal import SetModuleVersion
from util import message, msWait

SetModuleVersion("msa_cb",("1.30","EON","05/20/2014"))

debug = False

#==============================================================================
# MSA Control Board.

class MSA_CB:
    # Port P1 bits and bitmasks
    P1_ClkBit = 0
    P1_PLL1DataBit = 1
    P1_DDS1DataBit = 2
    P1_PLL3DataBit = 3
    P1_DDS3DataBit = 4
    P1_PLL2DataBit = 4    # same bit as DDS3
    P1_FiltA0Bit = 5
    P1_FiltA1Bit = 6
    P1_Clk      = 1 << P1_ClkBit
    P1_PLL1Data = 1 << P1_PLL1DataBit
    P1_DDS1Data = 1 << P1_DDS1DataBit
    P1_PLL3Data = 1 << P1_PLL3DataBit
    P1_DDS3Data = 1 << P1_DDS3DataBit

    # P2 bits and bitmasks
    P2_le1   = 1 << 0  # LEPLL1
    P2_fqud1 = 1 << 1  # FQUD DDS1
    P2_le3   = 1 << 2  # LEPLL3
    P2_fqud3 = 1 << 3  # FQUD DDS3
    P2_le2   = 1 << 4  # LEPLL2
    P2_pdminvbit = 6   # INVERT PDM

    # P3 bits and bitmasks
    P3_ADCONV   = 1 << 7
    P3_ADSERCLK = 1 << 6
    P3_switchTR   = 5  # Trans/Refl switch
    P3_switchFR    = 4  # Fwd/Rev switch
    P3_switchPulse = 3  # Pulse
    P3_spare       = 2  # Spare
    P3_videoFiltV1 = 1  # Video filter V1, high bit
    P3_videoFiltV0 = 0  # Video filted V0, low bit

    # P4 bits and bitmasks
    P4_BandBit       = 0
    P4_Band1Bit1     = 1
    P4_Atten5Bit     = 2
    P4_AttenLEBit    = 3
    P4_AttenClkBit   = 4
    P4_AttenDataBit  = 5
    P4_AttenLE    = 1 << P4_AttenLEBit
    P4_AttenClk   = 1 << P4_AttenClkBit

    # P5 (status) bits and bitmasks
    P5_PhaseDataBit = 6   # from LPT-pin 10 (ACK)
    P5_MagDataBit   = 7   # from LPT-pin 11 (WAIT)
    P5_PhaseData = 1 << P5_PhaseDataBit
    P5_MagData   = 1 << P5_MagDataBit

    # default parallel 'control' port values
    contclear = 0x00    # take all LPT control lines low
    SELTINITSTRBAUTO = 0x0f  # take all high
    STRB      = 0x08    # take LPT-pin 1 high. (Strobe line, STRB)
    AUTO      = 0x04    # take LPT-pin 14 high. (Auto Feed line, AUTO)
    INIT      = 0x02    # take LPT-pin 16 high. (Init Printer line, INIT)
    SELT      = 0x01    # take LPT-pin 17 high. (Select In line, SELT)
    #                     P1    P2    P3    P4
    controlPortMap = (0, SELT, INIT, AUTO, STRB)

    show = False
    if debug:
        show = True   # JGH

    #--------------------------------------------------------------------------
    # Set the Control Board Port Px.

    def SetP(self, x, data):
        if self.show:
            print ("SetP%d 0x%02x" % (x, data))
        self.OutPort(data)
        self.OutControl(self.controlPortMap[x])
        self.OutControl(self.contclear)

    #--------------------------------------------------------------------------
    # Return Control Board data lines to idle state.

    def setIdle(self):
        self.OutPort(0)

    #--------------------------------------------------------------------------
    # Default interface: do nothing if no hardware present (for debugging UI).

    def OutPort(self, data):
        if self.show:
            print ("OutPort(0x%02x)" % data)

    def OutControl(self, data):
        if self.show:
            print ("OutControl(0x%02x)" % data)

    def ReadStatus(self):
        if self.show:
            print "ReadStatus"
        return 0

    def InStatus(self):
        if self.show:
            print ("InStatus")
        return 0

    def Flush(self):
        if self.show:
            print ("Flush")
        pass

    def SendDevBytes(self, byteList, clkMask): # JGH 2/9/14
        if self.show:
            print ("SendDevBytes")
        pass

    def ReqReadADCs(self, n):
        if self.show:
            print ("ReadReqADCs")
        pass

    def GetADCs(self, n):
        if self.show:
            print ("GetADCs")
        pass

    # Delay given number of milliseconds before next output
    def msWait(self, ms):
        if self.show:
            print ("msWait")
        msWait(ms)

    def FlushRead(self):
        if self.show:
            print ("FlushRead")
        pass

    def HaveReadData(self):
        if self.show:
            print ("HaveReadData")
        return 0

    def Clear(self):
        if self.show:
            print ("Clear")
        pass

#==============================================================================
class MSA_RPI(MSA_CB):
    # constants
    
    def __init__(self):
        self.show = debug
        text = "This interface has not been implemented yet"
        message(text, caption="RPI Error")

#==============================================================================
class MSA_BBB(MSA_CB):
    # constants
    
    def __init__(self):
        self.show = debug
        text = "This interface has not been implemented yet"
        message(text, caption="BBB Error")
