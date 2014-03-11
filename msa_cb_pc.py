from msaGlobal import SetModuleVersion
from msa_cb import MSA_CB
from ctypes import windll

SetModuleVersion("msa_cb_pc",("1.02","EON","03/11/2014"))

#==============================================================================
# USBPAR interface module connected to MSA CB parallel port.
#
# 'control' port is FX2 port D
#   DB25 pins {1, 14, 16, 17} = FX2 port D [3:0] = {STRB, AUTO, INIT, SELT}
#   (to match Dave Roberts' hardware) This port includes the latched switches
# 'port' port is FX2 port B
#   DB25 pins {9:2} = FX2 port B [7:0]
# 'status' port is FX2 port A
#   DB25 pins {11, 10} = FX2 port A [5:4] = {WAIT, ACK}

class MSA_CB_PC(MSA_CB):
    # standard parallel port addresses
    port = 0x378
    status = port + 1
    control = port + 2

    # parallel 'control' port values {~SELT, INIT, ~AUTO, ~STRB}
    contclear = 0x0b    # take all LPT control lines low
    SELTINITSTRBAUTO = 0x04  # take all high
    STRB      = 0x0a    # take LPT-pin 1 high. (Strobe line, STRB)
    AUTO      = 0x09    # take LPT-pin 14 high. (Auto Feed line, AUTO)
    INIT      = 0x0f    # take LPT-pin 16 high. (Init Printer line, INIT)
    SELT      = 0x03    # take LPT-pin 17 high. (Select In line, SELT)
    #                     P1    P2    P3    P4
    controlPortMap = (0, SELT, INIT, AUTO, STRB)

    def OutPort(self, data):
        windll.inpout32.Out32(self.port, data)

    def OutControl(self, data):
        windll.inpout32.Out32(self.control, data)

    def ReadStatus(self):
        return windll.inpout32.Inp32(self.status)

    def InStatus(self):
        return windll.inpout32.Inp32(self.status)

    # Send 40 bytes of PLL and DDC register data out port P1
    def SendDevBytes(self, byteList, clkMask): # JGH 2/9/14
        for byte in byteList: # JGH 2/9/14
            self.SetP(1, byte)             # data with clock low
            self.SetP(1, byte + clkMask)   # data with clock high

    # request a read of the ADCs, reading n bits
    def GetADCs(self, n):
        # take CVN high. Begins data conversion inside AtoD, and is completed
        # within 2.2 usec. keep CVN high for 3 port commands to assure full
        # AtoD conversion
        self.SetP(3, self.P3_ADCONV)
        # Status bit 15 of the serial data is valid and can be read at any time
        mag = phase = 0
        for i in range(n):
            self.SetP(3, self.P3_ADSERCLK) # CVN low and SCLK=1
            # read data, statX is an 8 bit word for the Status Port
            stat = self.InStatus()
            mag =   (mag   << 1) | (stat & self.P5_MagData)
            phase = (phase << 1) | (stat & self.P5_PhaseData)
            self.SetP(3, 0)          # SCLK=0, next bit is valid
        return (mag, phase)
