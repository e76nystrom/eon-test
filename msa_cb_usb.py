from msaGlobal import isMac, resdir, SetModuleVersion
from util import msWait
import os, string, subprocess, sys, usb
from msa_cb import MSA_CB
import array as uarray
import usb.backend.libusb01 as libusb01

SetModuleVersion("msa_cb_usb",("1.30","EON","05/20/2014"))

debug = False

usbSync = True
usbReadCount = 0
usbSyncCount = 20

RequiredFx2CodeVersion = "0.1"

class Bus(object):
    r"""Bus object."""
    def __init__(self):
        self.dirname = ''
        self.localtion = 0
        self.devices = [usb.Device(d) \
                        for d in usb.core.find(find_all=True,
                                               backend=libusb01.get_backend())]

class MSA_CB_USB(MSA_CB):
    # constants
    USB_IDVENDOR_CYPRESS = 0x04b4
    USB_IDPRODUCT_FX2 = 0x8613

    def __init__(self):
        self.show = debug
        self._wrCount = 0
        self._rdSeq = 0
        self._expRdSeq = 0
        self._writeFIFO = ""
        self._readFIFO = uarray.array('B', []) # JGH numpy raises its ugly head
        self._firstRead = True
        self.usbFX2 = None
        # self.min = 20

    # Look for the FX2 device on USB and initialize it and self.usbFX2 if found

    def busses(self):
        r"""Return a tuple with the usb busses."""
        return (Bus(),)

    def FindInterface(self):
        if not self.usbFX2:
            try:
                usbBusses = self.busses()
            except:
                print ("usb library not installed")
                return

            for bus in usbBusses:
                for dev in bus.devices:
                    if dev.idVendor == self.USB_IDVENDOR_CYPRESS and dev.idProduct == self.USB_IDPRODUCT_FX2:
                        odev = dev.open()
                        if 1:
                        # Run prog to download code into the FX2
                        # Disable if the code is permanently loaded into the EPROM
                            try:
                                cycfx2progName = os.path.join(resdir, "cycfx2prog")
                                usbparName = os.path.join(resdir, "usbpar.ihx")
                                cmd = [cycfx2progName, "prg:%s" % usbparName, "run"]
                                if debug:
                                    print (" ".join(cmd))

                                p = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT,
                                            env=os.environ)

                                result = p.wait()  # JGH ??????????????

                                for line in p.stdout.readlines():
                                    print ("cycfx2prog:", line)
                            except OSError:
                                print ("Error: cycfx2prog:", sys.exc_info()[1].strerror)
                                return
                            if result != 0:
                                print ("cycfx2prog returned", result)
                                return
                            print ("CYPRESS DEVICE FOUND")
                            try:
                                odev = dev.open()

                                # --------------------------------------------------

    ##                            # If the program doesn't start, let it detach the
    ##                            # Kernel driver ONCE, and then comment out the line
    ##                            odev.detachKernelDriver(0)
    ##                            if debug:
    ##                               print ("Kernel Driver detached")
    ##                            odev.setConfiguration(1) # JGH 10/31/13
    ##                            if debug:
    ##                                print ("Configuration has been set")
    ##                            odev.releaseInterface() # JGH 10/14/13
    ##                            if debug:
    ##                                print ("Interface released")

                                # --------------------------------------------------

                                odev.claimInterface(0)
                                # Alt Interface 1 is the Bulk intf: claim device
                                odev.setAltInterface(1)
                                self.usbFX2 = odev
                                print ("")
                                print ("      **** FINISHED WITHOUT ERRORS ****")
                                print ("")
                            except usb.USBError:
                                print ("USBError Exception")
                                return

    # For debug only # JGH 1/25/14
    def ReadUSBdevices(self):
        # libusb-0.1 version: search USB devices for FX2

        for bus in usb.busses():
            for dev in bus.devices:
                if dev.idVendor == self.USB_IDVENDOR_CYPRESS and dev.idProduct == self.USB_IDPRODUCT_FX2:

                    if debug:
                        print (">>>>> CONFIGURATIONS:")
                        for cfg in dev:
                            print (">>>>> bConfigurationValue: ", cfg.bConfigurationValue, " <<<<<")
                            print (">>>>> bNumInterfaces: ", cfg.bNumInterfaces, " <<<<<")
                            print (">>>>> iConfiguration: ", cfg.iConfiguration, " <<<<<")
                            print (">>>>> bmAttributes: ", cfg.bmAttributes, " <<<<<")
                            print (">>>>> bMaxpower: ", cfg.bMaxPower, " <<<<<")
                            print ("")
                            print (">>>>> INTERFACES:")
                            for intf in cfg:
                                print (">>>>> bInterfaceNumber ", intf.bInterfaceNumber, " <<<<<")
                                print (">>>>> bAlternateSetting: ", intf.bAlternateSetting, " <<<<<")
                                print ("")
                                print (">>>>> END POINTS:")
                                for ep in intf:
                                    print (">>>>> bEndpointAddress: ", ep.bEndpointAddress, " <<<<<")
                                    print ("")

    # Send buffered write data to FX2
    def Flush(self):
        if debug:
            print (">>>894<<< MSA_CB_USB:Flush()", len(self._writeFIFO))
        if len(self._writeFIFO) > 0:
            fx2 = self.usbFX2
            if debug:
                print (">>>898<<< fx2:  " + str(fx2))
            fx2.bulkWrite(2, self._writeFIFO, 5000)
            self._writeFIFO = ""

    # Put write data to send (as a string) into the buffer
    def _write(self, data):
        if (len(self._writeFIFO) + len(data)) > 512:
            self.Flush()
        self._writeFIFO += data

    # Read any FX2 data, with a silent timout if none present
    def _read(self):
        fx2 = self.usbFX2
        try:
            data = fx2.bulkRead(0x86, 512, 1000)
            if self.show:
                print ("_read ->", string.join(["%02x" % b for b in data]))
        except usb.USBError:
            data = uarray.array('B', [])
            if self.show:
                print ("_read -> none")
        return data

    # Request a write of a byte to the data port
    def OutPort(self, byte):
        if self.show:
            print ("OutPort(0x%02x)" % byte)
        if debug:
            print ("MSA_CB_USB: OutPort at line 915")
        self._write("D" + chr(byte))

    # Request a write of a byte to the control port
    def OutControl(self, byte):
        if self.show:
            print ("OutControl(0x%02x)" % byte)
        if debug:
            print ("MSA_CB_USB: OutControl at line 845")
        self._write("C" + chr(byte))

    # Read the status register
    def ReadStatus(self):
        self._write("S" + chr(0));
        self.FlushRead();
        self.Flush();
        msWait(100);
        if self.HaveReadData() >= 1:
            result = self._readFIFO[0]
            self._readFIFO = self._readFIFO[1:]
        else:
            result = 0
        return result

    # Send 40 bytes of PLL and DDC register data out port P1
    def SendDevBytes(self, byteList, clkMask): # JGH 2/9/14
        s = string.join(map(chr, byteList), '')    # JGH 2/9/14
        if self.show:
            print ("SendDevBytes(clk=0x%02x, len=%d)" % (clkMask, len(s)))
        self._write("P" + chr(clkMask) + chr(len(s)) + s)

    # Request a delay given number of milliseconds before next output
    def msWait(self, ms):
        if self.show:
            print ("msWait(%d)" % ms)
        if type(ms) != type(1) or ms < 1:
            ##print ("msWait: bad value", ms)
            ms = 1
        if ms <= 255:
            self._write("W" + chr(ms))
        else:
            msWait(ms)

    # Request a flush of the read buffer in the FX2
    def FlushRead(self):
        if self.show:
            print ("FlushRead()")
        self._write("F" + chr(0))

    # Check for read data waiting in the FX2, returning the num of bytes read
    def HaveReadData(self):
        if self.show:
            print ("HaveReadData start")
        r = self._read()
        if self.show:
            print ("read:", r)
        if not isMac:
            r = uarray.array('B', r)
        self._readFIFO += r
        if self.show:
            print ("HaveReadData ->", len(self._readFIFO))
        return len(self._readFIFO)

    # Get the requested read-status data byte
    def InStatus(self):
        if self.show:
            print ("InStatus start")
        retry = 5
        while len(self._readFIFO) < 1:
            r = self._read()
            if not isMac:
                r = uarray.array('B', r)
            self._readFIFO += r
            if --retry == 0:
                break
        #if retry < self.min:
        #   self.min = retry
        #    print ("retry %d" % retry)
        if len(self._readFIFO) < 1:
            print ("InStatus: no data")
            return 0
        # put {WAIT, ACK} in bits [7:6]
        # result = ((self._readFIFO[0] << 2) & 0xc0) ^ 0x80
        result = self._readFIFO[0]
        self._readFIFO = self._readFIFO[1:]
        if self.show:
            print ("InStatus -> 0x%02x" % result)
        return result

    # Request a read of the ADCs, reading n bits
    def ReqReadADCs(self, n):
        if self.show:
            print ("ReqReadADCs(%d)" % n)
        self._write("A" + chr(n))

    # Return the data previously read from the ADCs
    def GetADCs(self, n):
        global usbSync, usbReadCount, usbSyncCount
        mag = phase = 0
        tmp = 16
        for i in range(n):
            stat = self.InStatus()   # read data
            if usbSync:
                usbReadCount += 1
                err = False
                if i == 0:
                    if ((stat & 0xf) != 0xf):
                        print ("%10d out of sync %x" % (usbReadCount, stat))
                        err = True
                else:
                    if (stat & 0xf) != (tmp & 0x7):
                        print ("%10d out of sync %2d %2d %02x" % (usbReadCount, i, tmp, stat))
                        err = True
                    tmp -= 1;
                if err:
                    usbSyncCount -= 1
                    if usbSyncCount < 0:
                        usbSync = False
            stat = ((stat << 2) & 0xff) ^ 0x80
            mag =   (mag   << 1) | (stat & self.P5_MagData)
            phase = (phase << 1) | (stat & self.P5_PhaseData)
        if self.show:
            print ("GetADCs(%d) -> " % n, mag, phase)
        return (mag, phase)

    # Check that the FX2 is loaded with the proper version of code
    def ValidVersion(self):
        self._write("V" + chr(0))
        self.FlushRead()
        self.Flush()
        msWait(100)
        fx2Vers = None
        if self.HaveReadData() >= 2:
            fx2Vers = "%d.%d" % tuple(self._readFIFO[:2])
            if self.show:
                print (">>>1018<<< fx2Vers: " + str(fx2Vers))
            self._readFIFO = self._readFIFO[2:]
        if self.show:
            print ("ValidVersion ->", fx2Vers)
        if fx2Vers != RequiredFx2CodeVersion:
            print (">>>1023<<< Wrong FX2 code loaded: ", \
                   fx2Vers, " need: ", RequiredFx2CodeVersion)
            return False
        else:
            return True

    # Clear the read and write buffers and counts
    def Clear(self):
        self.FindInterface()
        self.FlushRead()
        self.Flush()
        # this clears out any FIFOed reads, but also causes a timeout
        ##if self._firstRead:
        ##    self._read()
        ##    self._firstRead = False
        self._wrCount = 0
        self._rdSeq = 0
        self._expRdSeq = 0
        self._writeFIFO = ""
        self._readFIFO =  uarray.array('B', [])
