#!/usr/bin/env python
# -*- coding: utf-8 -*-
###############################################################################
#
# msapy.py -- Modular Spectrum Analyzer Application Interface, in wxPython.
#
# The majority of this code is from spectrumanalyzer.bas, written by
# Scotty Sprowls and modified by Sam Wetterlin.
#
# Copyright (c) 2011, 2013 Scott Forbes
#
# This file may be distributed and/or modified under the terms of the
# GNU General Public License version 2 as published by the Free Software
# Foundation. (See COPYING.GPL for details.)
#
# This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
# WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
###############################################################################
from __future__ import division

##Updated with LB ver117rev0-A
##msaVersion$="117"   'ver117rev0
##msaRevision$="A"    'ver117a

version = "0.2.70_JGH Dec 23, 2013 PRELIM"
#released for editing as msapyP102 on 12/23/13
version = "0.2.71_EON Jan 10, 2014 PRELIM"
#released for editing as msapyP105 on 1/22/2014
version = "0.2.72 Jan 22, 2014 PRELIM"
version = "2.7.P3 (2/2/14)"
version = "2.7.P106 (2/3/14)"
version = "2.7.P04 (2/4/14)"

# NOTE by JGH Dec 8, 2013: An attempt has been made to convert the Python 2.7 code to Python 3.
# The conversion has been completed and affected print statements (require parentheses),
# lambda functions (require being enclosed in parentheses) and unicode encoding using chr().
# The print statements are now parenthesized. but the unicode and lambda are left as they were.

# This is the source for the MSAPy application. It's composed of two parts:
#
# Hardware Back End
#   * Communicates with the spectrum analyzer hardware.
#   * Has functions to initialize hardware, set modes, and capture data.
#
# GUI Front End
#   * Communicates with the user using the wxPython GUI library.
#   * Refreshes the spectrum graph on each timer tick whenever more capture data
#     from the back end is ready, or whenever its window is resized.
#
# The code is mostly a set of object-oriented classes, arranged starting with
# the most primitive; a search from the top will usually locate an item's
# definition. A search for "#=" will find the class definitions.
#
#
# TODO:
#   Reflection calibration.
#   More than 2 scales.
#   First scans of R-L scan mode disappear or go out-of-bounds
#   An "extrapolate ends" of cal table.
#   A "save" button in cal.

import sys
print ("Python:", sys.version) # Requires python v2.7

isWin   = (sys.platform == "win32")
isLinux = (sys.platform == "linux2")
isRpi = (sys.platform == "raspbian") # JGH to be worked out later
isBBB = (sys.platform == "beaglebone") # JGH to be worked out later
isMac = not (isWin or isLinux or isRpi or isBBB) # EON Jan 29, 2014

print ("PLATFORM: ", sys.platform)

import os, time, re, string, traceback, wx, warnings, random, thread
import cmath # EON Jan 10
import array as uarray
import copy as dcopy
from math import *
from wx.lib.dialogs import *
import wx.lib.newevent as newevent
import wx.lib.inspection
import wx.grid #JGH 1/17/14
## _ = wx.GetTranslation
import numpy.version
from numpy import *
from numpy.fft import *
from Queue import *
import subprocess
from StringIO import StringIO
import wx.lib.colourselect as csel
from bisect import bisect_right

# Start EON Jan 22, 2014
incremental = True
memLeak = False
logEvents = False

if memLeak:
    from collections import defaultdict
    import gc
    from gc import get_objects
    import objgraph   # JGH requires python-objgraph module
    objdump = 5
    fill_before = True
    before = defaultdict(int)
    fil = open("dbg.txt","w")
    fil.close()
# End EON Jan 22, 2014

RequiredFx2CodeVersion = "0.1"
CalVersion = "1.03" # compatible version of calibration files

# debugging and profiling settings

debug = False        # set True to write debugging messages to msapy.log
showProfile = 0     # set to 1 to generate msa.profile. Then run showprof.py.
showThreadProfile = 0  # set to 1 to generate msa.profile for both threads
#print(sys.argv[1:])
if "-h" in sys.argv[1:]:
    print ("")
    print ("COMMAND LINE ARGUMENTS:")
##    print ("The following are mutually exclusive:")
##    print ("-bbb for unix using BeagleBoneBlack")
##    print ("-rpi for unix using RaspberryPi")
##    print ("-wpp for windows using parallel port")
##    print ("-wu for windows using USB")
##    print ("")
##    print (" No arguments: unix with USB")
##    print ("")
    print (" The following work with all systems:")
    print ("-h for this help")
    print ("-dbg for debug mode")
    print ("-pro for profiler")
    print ("")
if "-dbg" in sys.argv[1:]:
    print ("Debug mode is ON")
    debug = True
else:
    print ("Debug mode is OFF")
    debug = False
if "-pro" in sys.argv[1:]:
    print ("Profile mode is ON")
    showProfile = 1   # set to 1 to generate msa.profile. Then run showprof.py.
    showThreadProfile = 0  # set to 1 to generate msa.profile for both threads
else:
    print ("Profile mode is OFF")
    showProfile = 0
    showThreadProfile = 0  # set to 1 to generate msa.profile for both threads


# Graph update interval, in milliseconds. The tradoff is between smooth
# "cursor" movement and drawing overhead.
msPerUpdate = 100

# for raw magnitudes less than this the phase will not be read-- assumed
# to be noise
goodPhaseMagThreshold = 0x2000

# Set to truncate S11 to the unity circle to ignore error due to S21
# measurement losses during calibrating
truncateS11ToUnity = False

# set numpy divide-by-zero errors to be fatal
##seterr(all="raise")

# Set to use parallel port I/O instead of USB on Windows
##if "-wpp" in sys.argv[1:]:
##    print ("MODE IS Windows using Parallel Port")
##    winUsesParallelPort = True
##else:
##    winUsesParallelPort = False
winUsesParallelPort = False

# appdir is the directory containing this program
appdir = os.path.abspath(os.path.dirname(sys.argv[0]))
resdir = appdir
if isWin:
    resdir = os.environ.get("_MEIPASS2")
    if not resdir:
        resdir = appdir
elif os.path.split(appdir)[1] == "Resources":
    appdir = os.path.normpath(appdir + "/../../..")

# standard font pointsize-- will be changed to calibrated size for this system
fontSize = 11

# set to disable auto-double-buffering and use of anti-aliased GraphicsContext
slowDisplay = isWin
print ("PROGRAM STARTED")

# Start EON Jan 10 2014
# globals for OSL calibration calculations

calWait = 50 # sweep wait during calibration # EON Jan 29, 2014

RadsPerDegree = pi / 180
DegreesPerRad = 180 / pi
constMaxValue = 1e12

def message(message, caption="", style=wx.OK): # EON Jan 29, 2014
    dlg = wx.MessageDialog(msa.frame, message, caption, style)
    dlg.ShowModal()
    dlg.Destroy()
# End EON Jan 10 2014

#******************************************************************************
#****                          MSA Hardware Back End                      *****
#******************************************************************************

# Utilities.

# Convert to decibels.

def db(x):
    try:
        return 20. * log10(x)
    except FloatingPointError:
        print ("db(", x, ")?")
        raise

# Adjust degrees to be in range -180 to +180.

def modDegree(deg):
    return mod(deg + 180., 360.) - 180.

# Return an array of minimums/maximums between corresponding arrays a and b

def min2(a, b):
    return select([b < a], [b], default=a)

def max2(a, b):
    return select([b > a], [b], default=a)

# Convert string s to floating point, with an empty string returning 0.

def floatOrEmpty(s):
    if s == "":
        return 0.
    try:
        return float(s)
    except ValueError:
        ##print ("Bad float: '%s'" % s
        return 0.

# Convert an integer or float to a string, retaining precision

def gstr(n):
    return "%0.10g" % n

# Convert a value in MHz to a string with 1 Hz resolution

def mhzStr(mhz):
    return "%0.10g" % round(mhz, 6)

if 1:
    # Unicode-encoded special characters
    mu = u"\u03BC" # JGH mod4P3 -> mu = chr(956)
    Ohms = u"\u2126" #JGH mod4P3 -> Ohms = chr(8486)
    Infin = u"\u221E" # JGH mod4P3 -> Infin = chr(8734)
else:
    mu = "u"
    Ohms = "Ohms"
    Infin = "inf"

# SI-units prefixes, in order of power
SIPrefixes = ("f", "p", "n",  mu, "m", "", "k", "M", "G", "T", "Z")

# dictionary of the power-of-ten of each SI-unit prefix string
SIPowers = {}
i = -15
for pr in SIPrefixes:
    SIPowers[pr] = i
    i += 3

# useful units multipliers
fF = 1e-15
pF = pH = ps = 1e-12
nF = nH = ns = 1e-9
uF = uH = us = 1e-6
mOhm = mF = mH = mW = mV = 1e-3
kOhm = kHz = 1e3
MOhm = MHz = 1e6
GOhm = GHz = 1e9

# Add SI prefix to a string representation of a number.
# places:   significant digits.
# flags:    sum of any of:
SI_NO       = 1 # suppress SI units
SI_ASCII    = 2 # suppress Unicode

def si(n, places=5, flags=0):
    if n == None:
        return None
    if n == 0 or (flags & SI_NO):
        return "%%0.%gg" % places % round(n, places)
    if abs(n) == Inf:
        return ("-", "")[n > 0] + Infin
    thou = min(max(int((log10(abs(n)) + 15) / 3), 0), 9)
    p = SIPrefixes[thou]
    if (flags & SI_ASCII) and p == mu:
        p = "u"
    return "%%0.%gg%%s" % places % (n * 10**(15-3*thou), p)

# Return the corresponding multiplier for an SI-unit prefix string.

def siScale(s):
    return 10**(SIPowers[s])

# Convert string s to floating point, with an empty string returning 0,
# String may be scaled by SI units.

numSIPat = r"([0-9.e\-+]+)([a-zA-Z]*)"

def floatSI(s):
    m = re.match(numSIPat, s)
    if m:
        try:
            sValue, units = m.groups()
            value = float(sValue)
            if len(units) > 0:
                p = units[0]
                if p in SIPrefixes:
                    value *= siScale(p)
                elif p == "u":
                    value *= siScale(mu)
                elif p == "K":
                    value *= siScale("k")
            return value
        except ValueError:
            ##print ("Bad float: '%s'" % s
            pass
    return 0.

# Convert frequencies between start,stop and center,span pairs, using
# a geometric mean if isLogF is True.

def StartStopToCentSpan(fStart, fStop, isLogF):
    if isLogF:
        fCent = sqrt(fStart * fStop)
    else:
        fCent = (fStart + fStop) / 2
    return fCent, fStop - fStart

def CentSpanToStartStop(fCent, fSpan, isLogF):
    if isLogF:
        # given span is always arithmetic, so convert it to geometric span
        # using quadradic formula
        r = fSpan / (2*fCent)
        fSpanG2 = r + sqrt(r**2 + 1)
        fStart = fCent / fSpanG2
        fStop = fCent * fSpanG2
    else:
        fSpan2 = fSpan / 2
        fStart = fCent - fSpan2
        fStop = fCent + fSpan2
    return fStart, fStop

# Divide without raising a divide-by-zero exception. Only used in register
# setup, where wrong values just give wrong frequencies.

def divSafe(a, b):
    if b != 0:
        return a / b;
    return a

# Start EON Jan 10 2014
# Return base 10 log of aVal; special rule for small and non-positive arguments

def uSafeLog10(aVal):
    if aVal <= 1e-20:           #0.00001^4
        return -20
    else:
        return log10(aVal)

# Put deg in range -180 < deg <= 180

def uNormalizeDegrees(deg):
    while deg <= -180:
        deg += 360
    while deg > 180:
        deg -= 360
    return deg

def polarDbDeg(Z):
    (mag, phase) = cmath.polar(Z)
    db = 20 * uSafeLog10(mag)
    deg = phase * DegreesPerRad
    return db, deg

def cpx(Z):
    val = "(%10.3e,%10.3e)" % (Z.real, Z.imag)
    return val

def pol(X):
    val = "(m %10.3e,p %10.3e)" % (X[0], X[1])
    return val
# End EON Jan 10 2014

#------------------------------------------------------------------------------
# Transform S21 data to equivalent S11.
# Returns S11, Z

def EquivS11FromS21(S21, isSeries, R0):
    save = seterr(all="ignore")
    if isSeries:
        # transform S21 back to series Zs
        Z = 2*R0*(1/S21 - 1)
    else:
        # transform S21 back to shunt Zsh
        Sinv = nan_to_num(1/S21)
        Z = R0/(2*(Sinv - 1))

    # then transform that to S11
    Z = nan_to_num(Z)
    S11 = nan_to_num((Z-R0) / (Z+R0))
    seterr(**save)
    if truncateS11ToUnity:
        S21 = select([abs(S11) > 1.], [exp(1j*angle(S11))], default=S11) # EON Jan 29, 2014
    return S11, Z

#------------------------------------------------------------------------------
# Debug-event gathering. These events are stored without affecting timing or
# the display, and may be dumped later via the menu Data>Debug Events.

eventNo = 0

class Event:
    def __init__(self, what):
        global eventNo
        self.what = what
        self.when = int(msElapsed())*1000 + eventNo
        if debug:
            print ("Event %5d.%3d: %s" % (self.when/1000, \
                mod(self.when, 1000), what))
        eventNo += 1

guiEvents = []

def ResetEvents():
    global eventNo, guiEvents
    eventNo = 0
    guiEvents = []

# Log one GUI event, given descriptive string. Records elapsed time.

def LogGUIEvent(what):
    global guiEvents
    if logEvents: # EON Jan 22, 2014
        guiEvents.append(Event(what))

#------------------------------------------------------------------------------
# Time delays that have higher resolution and are more reliable than time.sleep
# which is limited to OS ticks and may return sooner if another event occurs.

# Get current time in milliseconds relative to loading program, with typically
# 1 microsecond resolution.

if isWin:
    time0 = time.clock()

    def msElapsed():
        return (time.clock() - time0) * 1000

else:
    from datetime import datetime
    time0 = datetime.now()

    def msElapsed():
        dt = datetime.now() - time0
        return dt.seconds*1000 + dt.microseconds/1000

# Delay given number of milliseconds. May be over by the amount of an
# intervening task's time slice.

def msWait(ms):
    start = msElapsed()
    dt = 0
    while dt < ms:
        ##if (ms - dt) > 50:
        ##    # use sleep() for longer durations, as it saves power
        ##    time.sleep((ms - dt - 50)/1000)
        dt = msElapsed() - start

# Measure the mean and standard deviation of 100 time delays of given duration.
# The deviation will typically be large for small ms, due to the occasional
# relatively long delay introduced by the OS scheduling. The chance of that
# 'pause' hitting near the end of a longer delay is lower.

def meas(ms):
    ts = []
    t1 = msElapsed()
    for i in range(100):
        msWait(ms)
        t2 = msElapsed()
        ts.append(t2 - t1)
        t1 = t2
    return (mean(ts), std(ts), ts)

# Conditionally form a parallel circuit with elements in list.

def par2(a, b, isSeries=False):
    if isSeries:
        return a + b
    return (a*b) / (a+b)

def par3(a, b, c, isSeries=False):
    if isSeries:
        return a + b + c
    return (a*b*c) / (b*c + a*c + a*b)

# Convert a dictionary into a structure. Representation is evaluatable.

class Struct:
    def __init__(self, **entries):
        self.__dict__.update(entries)

    def __repr__(self):
        return "Struct(**dict(" + string.join(["%s=%s" % \
            (nm, repr(getattr(self, nm))) \
            for nm in dir(self) if nm[0] != "_"], ", ") + "))"

# Check that the file at path has one of the allowed extensions.
# Returns the path with extension added if necessary, or None if invalid.

def CheckExtension(path, parent, allowedExt, defaultExt=None):
    base, ext = os.path.splitext(path)
    if ext == "":
        if defaultExt:
            ext = defaultExt
        else:
            ext = allowedExt[0]
    elif not ext in allowedExt:
        alertDialog(parent, "Urecognized extension '%s'" % ext, "Error")
        return None
    return base + ext

# Check if a file exists at path and return True if not allowed to overwrite.

def ShouldntOverwrite(path, parent):
    if os.path.exists(path):
        dlg = wx.MessageDialog(parent,
            "A file with that name already exists. Overwrite it?",
            style=wx.ICON_EXCLAMATION|wx.YES_NO|wx.NO_DEFAULT)
        return dlg.ShowModal() != wx.ID_YES
    return False


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
# Parallel port I/O interface.

if isWin and winUsesParallelPort:
    # Windows DLL for accessing parallel port
    from ctypes import windll
    try:
        windll.LoadLibrary(os.path.join(resdir, "inpout32.dll"))
    except WindowsError:
        # Start up an application just to show error dialog
        app = wx.App(redirect=False)
        app.MainLoop()
        dlg = ScrolledMessageDialog(None,
                        "\n  inpout32.dll not found", "Error")
        dlg.ShowModal()
        sys.exit(-1)
elif isLinux:
    import usb
else:
    # OSX: tell ctypes that the libusb backend is located in the Frameworks directory
    fwdir = os.path.normpath(resdir + "/../Frameworks")
    print ("fwdir :    " + str(fwdir))
    if os.path.exists(fwdir):
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = fwdir
    import usb

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


#==============================================================================
# USBPAR interface module connected to MSA CB parallel port.
#
# 'control' port is FX2 port D
#       DB25 pins {1, 14, 16, 17} = FX2 port D [3:0] = {STRB, AUTO, INIT, SELT}
#        (to match Dave Roberts' hardware) This port includes the latched switches
# 'port' port is FX2 port B
#       DB25 pins {9:2} = FX2 port B [7:0]
# 'status' port is FX2 port A
#       DB25 pins {11, 10} = FX2 port A [5:4] = {WAIT, ACK}


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
        self.min = 20

    # Look for the FX2 device on USB and initialize it and self.usbFX2 if found

    def FindInterface(self):
        if not self.usbFX2:
            for bus in usb.busses():
                for dev in bus.devices:
                    if dev.idVendor == self.USB_IDVENDOR_CYPRESS and dev.idProduct == self.USB_IDPRODUCT_FX2:
                        odev = dev.open()
##                        if 1:
                        # run prog to download code into the FX2
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
##                        if debug: # JGH 1/25/14
##                            self.ReadUSBdevices() # JGH Non iterable error

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
        if type(ms) != type(1) or ms > 255 or ms < 1:
            ##print ("msWait: bad value", ms)
            ms = 1
        self._write("W" + chr(ms))

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
        if retry < self.min:
            self.min = retry
            print ("retry %d" % retry)
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
        mag = phase = 0
        for i in range(n):
            stat = self.InStatus()   # read data
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


cb = None               # the current MSA Control Board, if present.
hardwarePresent = True  # True when cb represents actual hardware.


#==============================================================================
# An MSA Local Oscillator DDS and PLL.

class MSA_LO:
    # def __init__(self, id, freq, pllBit, le, fqud, PLLphasefreq, phasepolarity, appxdds, ddsfilbw):
    # JGH Above line substituted by the following
    def __init__(self, id, freq, pllBit, le, fqud, PLLphasefreq, phasepolarity, \
                 appxdds, ddsfilbw, PLLtype): # JGH 2/7/14 Fractional mode not used
        self.id = id                # LO number, 1-3
        self.freq = freq            # LO frequency
        self.CBP1_PLLDataBit = pllBit # port 1 bit number for PLL data
        self.CBP2_LE = le           # port 2 mask for Latch Enable line
        self.CBP2_FQUD = fqud       # port 2 mask for FQUD line
        self.phasepolarity = phasepolarity
        self.ddsoutput = 0.         # actual output of DDS (input Ref to PLL)
        self.ncounter = 0.          # PLL N counter
        self.Acounter = 0.          # PLL A counter
        self.Bcounter = 0.          # PLL B counter
        self.fcounter = 0.          # PLL fractional-mode N counter
        if debug:
            print ("LO%d init: PDF=%f" % (id, PLLphasefreq))

        # nominal DDS output frequency, MHz, that steers the PLL. Near 10.7.
        # appxdds must be the center freq. of DDS xtal filter; exact value
        # determined in calibration.
        self.appxdds = appxdds
        # DDS xtal filter bandwidth (in MHz), at the 3 dB points Usually 15 KHz.
        self.ddsfilbw = ddsfilbw
        # Approx. Phase Detector Frequency (MHz) for PLL. Use .974 when DDS
        # filter is 15 KHz wide.
        # PLLphasefreq must be less than the following formula:
        #  PLLphasefreq < (VCO 1 minimum frequency) x self.ddsfilbw/appxdds
        self.PLLphasefreq = PLLphasefreq
        # 0 = Integer Mode, 1 = Fractional Mode for the PLL.
        # I don't recommend Fractional Mode for PLL 1, although it will work
        # (noiser)
##        self.PLLmode = PLLmode # JGH 2/7/14 Fractional mode not used
        # JGH addition:
        self.PLLtype = PLLtype  # JGH COMMENT: PLLtype not needed here?
        # JGH addition end

        # PLL R counter
        self.rcounter = int(round(divSafe(self.appxdds, self.PLLphasefreq)))
##        if msa.spurcheck and not self.PLLmode:  # JGH 2/7/14 Fractional mode not used
        if msa.spurcheck:
            self.rcounter += 1  # only do this for IntegerN PLL

        self.pdf = 0        # phase detector frequency of PLL (MHz)


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
        pdmcmd = msa.invPhase << cb.P2_pdminvbit
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
            self.CommandPLL((self.rcounter << 2) + (0x1 << 22))

    #--------------------------------------------------------------------------
    # Reset serial DDS without disturbing Filter Bank or PDM.

    def ResetDDSserSLIM(self):
        # must have DDS (AD9850/9851) hard wired. pin2=D2=0, pin3=D1=1,
        # pin4=D0=1, D3-D7 are don# t care. this will reset DDS into
        # parallel, involk serial mode, then command to 0 Hz.
        if debug:
            print ("XXXXX 996, ResetDDSserSLIM XXXXX")
        pdmcmd = msa.invPhase << cb.P2_pdminvbit
        bitsRBW = msa.bitsRBW

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

        a = 0
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
    # Create Fractional Mode N counter.

    def _CreateFractionalNcounter(self, appxVCO, reference):
        # approximates the Ncounter for PLL
        ncount = divSafe(appxVCO, (reference/self.rcounter))
        self.ncounter = int(ncount)
        fcount = ncount - self.ncounter # EON Jan 29, 2014
        self.fcounter = int(round(fcount*16))
        if self.fcounter == 16:
            self.ncounter += 1
            self.fcounter = 0
        # actual phase freq of PLL
        self.pdf = divSafe(appxVCO, (self.ncounter + (self.fcounter/16)))

    #--------------------------------------------------------------------------
    # Create Integer Mode N counter.

    def CreateIntegerNcounter(self, appxVCO, reference):
        # approximates the Ncounter for PLL
        ncount = divSafe(appxVCO, divSafe(reference, self.rcounter))
        self.ncounter = int(round(ncount))
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

        if PLLN == "2325":
            if debug:
                print ("LO%d: Acounter=" % self.id, Acounter, "Bcounter=", Bcounter)
            if Bcounter < 3:
                raise RuntimeError(PLLN + "Bcounter <3")
            if Bcounter > 2047:
                raise RuntimeError(PLLN + "Bcounter > 2047")
            if Bcounter < Acounter:
                raise RuntimeError(PLLN + "Bcounter<Acounter")
            Nreg = (Bcounter << 8) + (Acounter << 1)

        if (PLLN == "2326" or PLLN == "4118"):
            if debug:
                print ("LO%d: Acounter=" % self.id, Acounter, "Bcounter=", Bcounter)
            if Bcounter < 3:
                raise RuntimeError(PLLN + "Bcounter <3")  # JGH Error < 3 common to all
            if Bcounter > 8191:
                raise RuntimeError(PLLN + "Bcounter >8191")
            if Bcounter < Acounter:
                raise RuntimeError(PLLN + "Bcounter<Acounter")
            # N20 is Phase Det Current, 1= 1 ma (add 1 << 20), 0= 250 ua
            Nreg = 1 + (1 << 20) + (Bcounter << 7) + (Acounter << 2)

        if PLLN == "2350":
            if debug:
                print ("LO%d: Acounter=" % self.id, Acounter, "Bcounter=", Bcounter)
            if Bcounter < 3:
                raise RuntimeError(PLLN + "Bcounter <3")  # JGH Error < 3 common to all
            if Bcounter > 1023:
                raise RuntimeError(PLLN + "Bcounter > 2047")
            if Bcounter < Acounter + 2:
                raise RuntimeError(PLLN + "Bcounter<Acounter")
            # N21: 0 if preselector = 16 else if preselector =32 then = 1 and add (1 << 21)
            Nreg = 3 + (Bcounter << 11) + (Acounter << 6) + (fcounter << 2)

        if PLLN == "2353":
            if debug:
                print ("LO%d: Acounter=" % self.id, Acounter, "Bcounter=", Bcounter)
            if Bcounter < 3:
                raise RuntimeError(PLLN + "Bcounter <3")  # JGH Error < 3 common to all
            if Bcounter > 1023:
                raise RuntimeError(PLLN + "Bcounter > 2047") # EON Jan 29, 2014
            if Bcounter < Acounter + 2:
                raise RuntimeError(PLLN + "Bcounter<Acounter")
            # N21: 0 if preselector = 16 else if preselector =32 then = 1 and add (1 << 21)
            Nreg = (3 + (Bcounter << 11) + (Acounter << 6) + (fcounter << 2))

        if (PLLN == "4112" or PLLN == "4113"):
            if debug:
                print ("LO%d: Acounter=" % self.id, Acounter, "Bcounter=", Bcounter)
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

        # The formula for the frequency output of the DDS(AD9850, 9851, or
        # any 32 bit DDS) is: ddsoutput = base*msa.masterclock/2^32
        # rounded off to the nearest whole bit
        base = int(round(divSafe(self.ddsoutput * (1<<32), msa.masterclock))) # JGH 2/2/14
        self.DDSbits = base
        if debug:
            print ("LO%d: base=%f=0x%x" % (self.id, base, base))


#==============================================================================
# Holder of the parameters and results of one scan.

class Spectrum:
    def __init__(self, when, pathNo, fStart, fStop, nSteps, Fmhz):
        # Start EON Jan 10 2014
        self.isLogF = (Fmhz[0] + Fmhz[2])/2 != Fmhz[1]
        self.desc = "%s, Path %d, %d %s steps, %g to %g MHz." % \
            (when, pathNo, nSteps, ("linear", "log")[self.isLogF], fStart, fStop)
        # End EON Jan 10 2014
        self.nSteps = nSteps        # number of steps in scan
        self.Fmhz = Fmhz            # array of frequencies (MHz), one per step
        n = nSteps + 1
        self.oslCal = False	    # EON Jan 10 2014
        self.Sdb = zeros(n)         # array of corresponding magnitudes (dB)
        self.Sdeg = zeros(n)        # phases (degrees)
        self.Scdeg = zeros(n)       # continuous phases (degrees)
        self.Mdb = zeros(n)         # raw magnitudes (dB)
        self.Mdeg = zeros(n)        # raw phases (degrees)
        self.magdata = zeros(n)     # magnitude data from ADC
        self.phasedata = zeros(n)   # phase data from ADC
        self.Tread = zeros(n)       # times when captured (ms from start)
        self.step = 0               # current step number
        self.vaType = None
        self.trva = None
        self.vbType = None
        self.trvb = None
        LogGUIEvent("Spectrum n=%d" % n)

    # Set values on step i in the spectrum. Returns True if last step.

    def SetStep(self, valueSet):
        i, Sdb, Sdeg, Scdeg, magdata, phasedata, Mdb, Mdeg, Tread = valueSet
        if i <= self.nSteps:
            self.step = i
            LogGUIEvent("SetStep %d, len(Sdb)=%d" % (i, len(self.Sdb)))
            self.Sdb[i] = Sdb
            self.Sdeg[i] = Sdeg
            self.Scdeg[i] = Scdeg
            self.Mdb[i] = Mdb
            self.Mdeg[i] = Mdeg
            self.magdata[i] = magdata
            self.phasedata[i] = phasedata
            self.Tread[i] = Tread
            if self.trva:
                self.trva.SetStep(self, i)
            if self.trvb:
                self.trvb.SetStep(self, i)
        return i == self.nSteps

    # Spectrum[i] returns the tuple (Fmhz, Sdb, Sdeg) for step i
    def __getitem__(self, i):
        return self.Fmhz[i], self.Sdb[i], self.Sdeg[i]

    #--------------------------------------------------------------------------
    # Write spectrum and input data to a text file.

    def WriteInput(self, fileName, p):
        f = open(fileName, "w")
        f.write( \
            " Step           Calc Mag  Mag A/D  Freq Cal Processed Pha A/D\n")
        f.write( \
            " Num  Freq (MHz)  Input   Bit Val   Factor    Phase   Bit Val\n")

        for i in range(len(self.Fmhz)):
            f.write("%4d %11.6f %8.3f %6d %9.3f %8.2f %8d\n" %\
                        (i, self.Fmhz[i], self.Sdb[i], self.magdata[i],
                        0., self.Sdeg[i], self.phasedata[i]))
        f.close()

    #--------------------------------------------------------------------------
    # Write spectrum to an S1P-format file.

    def WriteS1P(self, fileName, p, contPhase=False):
        f = open(fileName, "w")
        f.write("!MSA, msapy %s\n" % version)
        f.write("!Date: %s\n" % time.ctime())
        f.write("!%s Sweep Path %d\n" % \
            (("Linear", "Log")[p.isLogF], p.indexRBWSel+1))
        f.write("# MHz S DB R 50\n")
        f.write("!  MHz       S21_dB    S21_Deg\n")
        Sdeg = self.Sdeg
        if contPhase:
            Sdeg = self.Scdeg
        Sdeg = select([isnan(Sdeg)], [0], default=Sdeg)
        for freq, Sdb, Sdeg in zip(self.Fmhz, self.Sdb, Sdeg):
            f.write("%11.6f %10.5f %7.2f\n" % \
                    (freq, Sdb, Sdeg))
        f.close()

    #--------------------------------------------------------------------------
    # Read spectrum from an S1P file. Constructs the Spectrum too.

    @classmethod
    def FromS1PFile(cls, fileName):
        fScale = 1.
        R0 = 50
        Fmhz = []
        Sdb = []
        Sdeg = []
        when = "**UNKNOWN DATE**"
        pathNo = 1
        f = open(fileName, "r")

        for line in f.readlines():
            line = line.strip()
            if len(line) > 1:
                if line[0] == "!":
                    if line[1:6] == "Date:":
                        when = line[6:].strip()
                elif line[0] == "#":
                    words = string.split(line[1:])
                    i = 0
                    while i < len(words):
                        word = words[i]
                        i += 1
                        if len(word) > 1 and word[-2:] == "Hz":
                            fScale = siScale(word[:-2]) / MHz
                        elif word == "S":
                            sType = words[i]
                            if sType != "DB":
                                raise ValueError( \
                                    "Unsupported S type '%s' % sType")
                            i += 1
                        elif word == "R":
                            R0 = words[i]
                            i += 1
                        else:
                            raise KeyError("Unrecognized S1P keyword '%s'" \
                                            % word)
                else:
                    words = string.split(line)
                    if len(words) != 3:
                    # Start EON Jan 22, 2014
                        f.close()
                        return None
##                        raise ValueError( \
##                            "S1P file format wrong: expected freq, Sdb, Sdeg")
                    # End EON Jan 22, 2014
                    Fmhz.append(float(words[0]) * fScale)
                    Sdb.append(float(words[1]))
                    Sdeg.append(float(words[2]))
        f.close()

        n = len(Fmhz)
        if n == 0:
            # Start EON Jan 22, 2014
            return None
##            raise ValueError("S1P file: no data found")
            # End EON Jan 22, 2014

        print ("Read %d steps." % (n-1), "Start=", Fmhz[0], "Stop=", Fmhz[-1])
        this = cls(when, pathNo, Fmhz[0], Fmhz[-1], n - 1, array(Fmhz))
        this.Sdb = array(Sdb)
        this.Sdeg = array(Sdeg)
        this.Scdeg = this.Sdeg
        return this


#==============================================================================
# Synthetic DUT (Device Under Test) parameters Dialog, used when no MSA
# hardware is present.

class SynDUTDialog(wx.Dialog):
    def __init__(self, frame):
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
        global hardwarePresent, cb
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
        hardwarePresent = True
        cb = None  # JGH commented out TEMPORARILY  12/23/13
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
        self.type = type = self.sigTypeCB.GetValue()

        for parmRows in self.parms:
            for name, l, v, u in parmRows:
                setattr(self, name, self.parmBoxes[name].GetValue())
        p = self.prefs
        # volts peak per sqrt mW for 50 ohm
        self.vsrmw = sqrt(50/1000) * sqrt(2)
        self.msaInputDbm = msaInputDbm = -20
        self.noiseFloor = 10**(float(self.noisedbm)/20)
        serRLCEn = self.serRLCEn.GetValue()
        shuntRLCEn = self.shuntRLCEn.GetValue()

        if type in ("Tones", "Square"):
            # --- DUT is a waveform generator ---
            nyquist = 4 * GHz
            dt = 1 / (2*nyquist)
            n = 2**16
            t = arange(n) * dt
            f0 = float(self.Fs) * MHz
            magDbm = float(self.magdb)
            downdb = float(self.downdb)
            # generate spectrum from FFT of time domain waveform
            if type == "Square":
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

            if type == "Crystal":
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

            elif type == "RLC":
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

            elif type == "Cheb Filter":
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

            elif type == "Through":
                # Through -- for calibrating S21 baseline
                print ("Through")
                S21 = zeros(n) + 1+0j

            elif type == "Shunt Open":
                # Shunt open (and series shorted: same as Through, except
                # with opposite phase)
                S21 = zeros(n) + 1 - 1e-10-1e-10j

            elif type == "Shunt Short":
                # Shunt shorted
                S21 = zeros(n) + 0+0j

            elif type == "Shunt Load":
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


# Create a new Event class and EVT binder function
(UpdateGraphEvent, EVT_UPDATE_GRAPH) = newevent.NewEvent()


#==============================================================================
# Modular Spectrum Analyzer.

class MSA:
    # Major operating modes
    MODE_SA = 0
    MODE_SATG = 1
    MODE_VNATran = 2
    MODE_VNARefl = 3
    modeNames = ("Spectrum Analyzer", "Spec. Analyzer with TG",
                 "VNA Transmission", "VNA Reflection")
    shortModeNames = ("SA", "SATG", "VNATrans", "VNARefl")

    def __init__(self, frame):
        self.frame = frame
        p = frame.prefs
        self.mode = p.get("mode", self.MODE_VNATran)
        if debug:
            print ("")
            print (">>>>2029<<<< Initializing MSA")
        # Exact frequency of the Master Clock (in MHz).
        self.masterclock = p.get("masterclock", 63.998943)
        # 2nd LO frequency (MHz). 1024 is nominal, Must be integer multiple
        # of PLL2phasefreq
        self.appxLO2 = p.get("appxLO2", 1024)
        # list of Final Filter freq (MHz), bw (kHz) pairs
        ##self.RBWFilters = p.get("RBWFilters", [(10.698375, 8)])
        # JGH changed above line for next line
        self.RBWFilters = p.get("RBWFilters", [(10.703, 150), (10.710, 55), (10.743, 7), (10.739, 0.4)])
        # selected Final Filter index
        self.indexRBWSel = self.switchRBW = i = p.get("indexRBWSel", 0)
        # Final Filter frequency, MHz; Final Filter bandwidth, KHz
        self.finalfreq, self.finalbw = self.RBWFilters[i]
        self.bitsRBW = 4 * i  # JGH 10/31/13
        # Video Filters
        self.videoFilterNames = ["Wide", "Medium", "Narrow", "XNarrow"]
        self.VideoFilters = p.get("VideoFilters", [])
        self.nameVideoSel = p.nameVideoSel = p.get("nameVideoSel", "Medium") #Selected Video Filter name
        self.bitsVideo = p.indexVideoSel = p.get("indexVideoSel", 1) # JGH: Selected Video Filter index

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
            self_GHzBand = 1 # (or 3)
        # Pulse switch
            self.switchPulse = p.get("switchPulse", 0)
            self.bitsPulse = 128 * self.switchPulse
        # set when in inverted-phase mode
        self.invPhase = 0
        # amount (degrees) to subtract from phase to invert it
        self.invDeg = p.get("invDeg", 192.51)
        # set when running calibration
        self.calibrating = False
        # calibration level (0=None, 1=Base, 2=Band)
        self.calLevel = p.get("calLevel", 0)
        p.calLevel = self.calLevel = 0 # EON Jan 13 2013
        # calibration arrays, if present
        self.baseCal = None
        self.bandCal = None
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

    def WriteEvents(self):
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

    def _CalculateAllStepsForLO1Synth(self, thisfreq):
        if self._GHzBand != 1:
            # get equivalent 1G frequency
            thisfreq = self._Equiv1GFreq(thisfreq)
        # calculate actual LO1 frequency
        LO1.Calculate(thisfreq + LO2.freq - self.finalfreq)

    #--------------------------------------------------------------------------
    # Calculate all steps for LO3 synth.

    def _CalculateAllStepsForLO3Synth(self, TrueFreq):
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

    def _CommandAllSlims(self, f):
        p = self.frame.prefs
        band = min(max(int(f/1000) + 1, 1), 3) # JGH Values 1,2,3
        if debug:
            print (">>>2231<<< COMMAND ALL SLIMS")
            print (">>>2232<<< freq=", f, "band=", band)
        if band != self.lastBand or p.stepAttenDB != self.lastStepAttenDB:
            # shift attenuator value into pair of 6-bit attenuators
            self._SetFreqBand(band)
            # each attenuator value is 0-31 in 0.5-dB increments
            value = int(p.stepAttenDB * 2)
            if 1:
                # dual attenuators
                if value > 0x3f:
                    value = (0x3f << 6) | (value - 0x3f)   # (bitwise OR)
                for i in range(12):
                    bit = ((value >> 11) & 1) ^ 1
                    value <<= 1
                    self._SetFreqBand(band, (bit << cb.P4_AttenDataBit))
                    self._SetFreqBand(band, (bit << cb.P4_AttenDataBit) | cb.P4_AttenClk)
                    self._SetFreqBand(band, (bit << cb.P4_AttenDataBit))
            else:
                if 0:
                    # clock scope loop
                    while 1:
                        self._SetFreqBand(band, 0)
                        self._SetFreqBand(band, cb.P4_AttenClk)

                # single attenuator
                for i in range(6):
                    bit = ((value >> 5) & 1) ^ 1
                    value <<= 1
                    self._SetFreqBand(band, (bit << cb.P4_AttenDataBit))
                    self._SetFreqBand(band, (bit << cb.P4_AttenDataBit) | cb.P4_AttenClk)
                    self._SetFreqBand(band, (bit << cb.P4_AttenDataBit))
            # latch attenuator value and give relays time to settle
            self._SetFreqBand(band, cb.P4_AttenLE)
            self._SetFreqBand(band)
            self.lastStepAttenDB = p.stepAttenDB
            cb.msWait(100)

        self._CalculateAllStepsForLO1Synth(f)
        self._CalculateAllStepsForLO3Synth(f)

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
        if band != self.lastBand:
            self.lastBand = band
            # give PLLs more time to settle too
            cb.msWait(100)

    #--------------------------------------------------------------------------
    # Command just the PDM's static data.

    def _CommandPhaseOnly(self):
        cb.SetP(2, self.invPhase << cb.P2_pdminvbit)
        cb.setIdle()

    #--------------------------------------------------------------------------
    # Set the GHz frequency band: 1, 2, or 3.

    def _SetFreqBand(self, band, extraBits=0):
        self._GHzBand = band
        band += extraBits
        if self._GHzBand == 2:
            bitsBand = 64 * 0
        else:
            bitsBand = 64 * 1
        cb.SetP(4, self.bitsVideo + self.bitsRBW + self.bitsFR + \
                self.bitsTR + self.bitsBand + self.bitsPulse)
        ##print ("SetFreqBand: %02x" % band
        cb.setIdle()
        if debug:
            print ("G%02x" % band )

    #--------------------------------------------------------------------------
    # Initialize Video Filter
    def InitVideoFilter(self): # JGH New function in MSA

        i = self.videoFilterNames.index(msa.nameVideoSel)
        self.vfsmagCap, self.vfsphaCap, self.vfsmagTC, \
                        self.vfsphaTC = self.VideoFilters[i][self.nameVideoSel]
        if debug:
            print ("")
            print (">>>2350<<< Initialize Video Filter")
            print ("nameVideoSel", msa.nameVideoSel)
            print ("self.VideoFilters["+str(i)+"]: ", self.VideoFilters[i])
            print (self.VideoFilters[i][msa.nameVideoSel])
            print (self.vfsmagCap, self.vfsphaCap, self.vfsmagTC, self.vfsphaTC)


    #--------------------------------------------------------------------------
    # Initialize MSA hardware.

    def InitializeHardware(self):
        global cb, hardwarePresent, LO1, LO2, LO3

        if not hardwarePresent:
            return

        # Determine which interface to use to talk to the MSA's Control Board

        if not cb:
            if isWin and winUsesParallelPort:
                cb = MSA_CB_PC()
            # JGH added 1/19/14
            elif isRpi:
                cb = MSA_RPI()
            elif isBBB:
                cb = MSA_BBB()
            # JGH ends 1/19/14
            else:
                cb = MSA_CB_USB()
                cb.FindInterface()
                if not cb.usbFX2 or not cb.ValidVersion():
                    cb = MSA_CB()
                    hardwarePresent = False
        else:
            # test interface to see that it's still there
            try:
                cb.OutPort(0)
                cb.Flush()
            except:
                cb = MSA_CB()
                hardwarePresent = False
        if debug:
            print (">>>2400<<< cb: ", cb)

        if not hardwarePresent:
            print ("\n>>>2403<<< NO HARDWARE PRESENT")
            print ("\n>>>2404<<< GENERATING SYNTHETIC DATA") # JGH syndutHook2
            self.syndut = SynDUTDialog(self.gui)
            wx.Yield()
            self.gui.Raise()

        # JGH added Instantiate MSA's 3 PLLs
        p = self.frame.prefs
        PLL1type = p.get("PLL1type", "2326")
        PLL1phasepol = p.get("PLL1phasepol", 0)
        PLL1phasefreq = p.get("PLL1phasefreq", 0.974)
##        PLL1mode = p.get("PLL1mode", 0)
        PLL2type = p.get("PLL2type", "2326")
        PLL2phasepol = p.get("PLL2phasepol", 1)
        PLL2phasefreq = p.get("PLL2phasefreq", 4.000)
        PLL3type = p.get("PLL3type", "2326")
        PLL3phasepol = p.get("PLL3phasepol", 0)
        PLL3phasefreq = p.get("PLL3phasefreq", 0.974)
##        PLL3mode = p.get("PLL3mode", 0)

        cftest = p.get("cftest", 0) # JGH 2/3/14

        SwRBW  = p.get("SwRBW", True)
        SwVideo  = p.get("SwVideo", True)
        SwBand  = p.get("SwBand", False)
        SwTR  = p.get("SwTR", False)
        SwFR  = p.get("SwFR", False)

        self.switchRBW = p.get("switchRBW", 0) # Values 0-3
        self.indexVideoSel = p.get("indexVideoSel", 1)   # Values 0-3
        self.switchBand = p.get("switchBand", 1) # 1: 0-1GHz, 2: 1-2GHz, 3: 2-3GHz
        self.switchTR = p.get("switchTR", 0) # Values 0,1
        self.switchFR = p.get("switchFR", 0) # Values 0,1
        self.switchPulse = 0 # JGH Oct23 Set this here and follow with a 1 sec delay

        # JGH addition end

        # Instantiate MSA's 3 local oscillators
        ## p = self.frame.prefs
        appxdds1 =  p.get("appxdds1", 10.7)
        dds1filbw = p.get("dds1filbw", 0.015)
        appxdds3 =  p.get("appxdds3", 10.7)
        dds3filbw = p.get("dds3filbw", 0.015)
        # LO1 = MSA_LO(1, 0.,    cb.P1_PLL1DataBit, cb.P2_le1, cb.P2_fqud1, 0.974, 0, appxdds1, dds1filbw)
        # LO2 = MSA_LO(2, 1024., cb.P1_PLL2DataBit, cb.P2_le2, 0, 4.,    1, 0,        0)
        # LO3 = MSA_LO(3, 0.,    cb.P1_PLL3DataBit, cb.P2_le3, cb.P2_fqud3, 0.974, 0, appxdds3, dds3filbw)

        # JGH above three lines changed to
        LO1 = MSA_LO(1, 0., cb.P1_PLL1DataBit, cb.P2_le1, cb.P2_fqud1, \
                     PLL1phasefreq, PLL1phasepol, appxdds1, dds1filbw, PLL1type)
        LO2 = MSA_LO(2, 1024., cb.P1_PLL2DataBit, cb.P2_le2, 0, PLL2phasefreq, \
                     PLL2phasepol, 0, 0, PLL2type)
        LO3 = MSA_LO(3, 0., cb.P1_PLL3DataBit, cb.P2_le3, cb.P2_fqud3, PLL3phasefreq, \
                     PLL3phasepol, appxdds3, dds3filbw, PLL3type)
        # JGH change end



        # 5. Begin with all data lines low
        cb.OutPort(0)
        # latch "0" into all SLIM Control Board Buffers
        cb.OutControl(cb.SELTINITSTRBAUTO)
        # begin with all control lines low
        cb.OutControl(cb.contclear)

        # JGH added 5a. Set Port 4 switches
        # Pulse must be added here, in the mean time use 0
        self.bitsVideo = self.indexVideoSel
        self.bitsRBW = 4 * self.switchRBW
        self.bitsFR = 16 * self.switchFR
        self.bitsTR = 32 * self.switchTR
        self.bitsBand = 64 * self. switchBand
        self.bitsPulse = 128 * self.switchPulse
        cb.SetP(4, self.bitsVideo + self.bitsRBW + self.bitsFR + \
                self.bitsTR + self.bitsBand + self.bitsPulse)
        # JGH addition ended

        self._SetFreqBand(1)
        self.lastBand = 1
        self.lastStepAttenDB = -1

        # 6.if configured, initialize DDS3 by reseting to serial mode.
        # Frequency is commanded to zero
        LO3.ResetDDSserSLIM()

        # 7.if configured, initialize PLO3. No frequency command yet.
        # JGH starts 2/1/14
        LO3.rcounter, LO3.pdf = LO3.CreateRcounter(LO3.appxdds)
        # JGH ends 2/1/14
        LO3.CommandPLLR()

        # 8.initialize and command PLO2 to proper frequency
##        if p.cftest == 0: # JGH starts 2/3/14
##            print (">>>2489<<< cftest", p.cftest)
        # CreatePLL2R (needs: appxpdf, masterclock)
        LO2.rcounter, LO2.pdf = LO2.CreateRcounter(msa.masterclock) # JGH starts 2/1/14
        #                       (creates: rcounter, pdf)
        # Command PLL2R and Init Buffers (needs:PLL2phasepolarity,SELT,PLL2)
        LO2.CommandPLLR()
        # CreatePLL2N
        appxVCO = self.appxLO2 # JGH: appxLO2 is the Hardware Config Dialog value
        # CreateIntegerNcounter(needs: PLL2 (aka appxVCO), rcounter, fcounter)
        LO2.CreateIntegerNcounter(appxVCO, msa.masterclock)
        #                      (creates: ncounter, fcounter(0))
        #                      (needs: ncounter, fcounter, PLL2)
        LO2.CreatePLLN()
        #                      (creates: Bcounter,Acounter, and N Bits N0-N23)
        # actual LO2 frequency
        LO2.freq = ((LO2.Bcounter*LO2.preselector) + LO2.Acounter + \
                    (LO2.fcounter/16))*LO2.pdf
        # CommandPLL2N
        # needs:N23-N0,control,Jcontrol=SELT,port,contclear,LEPLL=8
        # commands N23-N0,old ControlBoard
        LO2.CommandPLL(LO2.PLLbits)
##        else:
##            # def CommandLO2forCavTest(self):
##            print (">>>2512<<< cftest", p.cftest)
####            appxVCO = msa.finalfreq + PLL1array(thisstep,43)  # ??????????????????? PLL1array
##            LO2.freq = msa.finalfreq + LO1.freq
##            print "LO1.freq, finalfreq, LO2.freq", LO1.freq, msa.finalfreq, LO2.freq
##            reference = msa.masterclock
##            print "masterclock", msa.masterclock
####            rcounter = rcounter2
##            LO2.rcounter, LO2.pdf = LO2.CreateRcounter(msa.masterclock) # JGH 2/5/14
##            self.rcounter = LO2.rcounter
##            print "LO2.rcounter", LO2.rcounter
##            # CreateIntegerNcounter needs:appxVCO,reference,rcounter ; creates:ncounter,fcounter(0)
####            self.CreateIntegerNcounter(appxVCO ,reference, rcounter)
##            LO2.CreateIntegerNcounter(LO2.freq, reference)
##            print "LO2.CreateIntegerNcounter", LO2.CreateIntegerNcounter(LO2.freq, reference)
####            ncounter2 = self.ncounter
####            fcounter2 = self.fcounter
##            # CreatePLL2N needs:ncounter,fcounter,PLL2 ; returns with Bcounter,Acounter, and N Bits N0-N23
####            self.CreatePLL2N(ncounter, fcounter, PLL2)
##            LO2.CreatePLLN()
##            print "LO2.CreatePLLN()", LO2.CreatePLLN()
##            Bcounter2 = self.Bcounter
##            Acounter2 = self.Acounter
##            # Calculate actual LO2 frequency
##            LO2.freq = ((sel.Bcounter*LO2.preselector) + self.Acounter+(self.fcounter/16))*LO2.pdf #actual LO2 frequency   ????? pdf2 = LO2.pdf
##            #CommandPLL2N
####            Jcontrol = SELT
####            LEPLL = 8
####            datavalue = 16
####            levalue = 1
##            #CommandPLL needs:N23-N0,control,Jcontrol,port,contclear,LEPLL ; commands N23-N0,old ControlBoard
####            self.CommandPLL(N23-N0, control, Jcontrol, port, contclear, LEPLL)
##            LO2.CommandPLL(LO2.PLLbits)
##        # JGH ends 2/3/14

        # 9.Initialize PLO 1. No frequency command yet.
        # CommandPLL1R and Init Buffers
        # needs:rcounter1,PLL1phasepolarity,SELT,PLL1
        # Initializes and commands PLL1 R Buffer(s)
        LO1.CommandPLLR()
        # 10.initialize DDS1 by resetting. Frequency is commanded to zero
        # It should power up in parallel mode, but could power up in a bogus
        #  condition. reset serial DDS1 without disturbing Filter Bank or PDM
        LO1.ResetDDSserSLIM()   # SCOTTY TO MODIFY THIS TO LIMIT HIGH CURRENT


    #--------------------------------------------------------------------------
    # Read 16-bit magnitude and phase ADCs.

    def _ReadAD16Status(self):
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
        p = self.frame.prefs  # JGH/SCOTTY 2/6/14
        step = self._step
        # Start EON Jan 22, 2014
        # if objdump != 0:
        if memLeak:
            global objdump, fill_before
            if step == 0:
                if fill_before:
                    fill_before = False
                    gc.collect()
                    objects = get_objects()
                    for obj in objects:
                        before[id(obj)] = 1
                    objects = None
            elif step == self._nSteps:
                gc.collect()
                objects = get_objects()
                fil = open("dbg.txt","a")
                i = 0
                for obj in objects:
                    if before[id(obj)] == 0:
                        objtype = type(obj).__name__
                        if  objtype != 'frame':
                            if objtype == 'instancemethod':
                                fil.write("i - %3d %8x %s\n" % (i, id(obj), obj.__name__))
                                if objdump > 0:
                                    objdump -= 1
                                    objgraph.show_backrefs(obj, filename="obj%d.png" % (objdump))
                            elif objtype == 'instance':
                                if obj.__class__ != '__main__.Event':
                                    fil.write("t - instance %s\n" % (obj.__class__))
                            elif objtype == 'tuple':
                                fil.write("t - tuple %3d %s\n" % (len(obj), obj))
                            elif objtype == 'dict':
                                fil.write("t - dict %3d\n" % (len(obj)))
                                if False:
                                    for val in obj.keys():
                                        fil.write("%s %s\n" % (val, obj[val]))
                                        break
                            else:
                                fil.write("t - %s %8x\n" % (objtype, id(obj)))
                            i += 1
                fil.write("total %4d\n\n" % (i))
                fil.close()
        # End EON Jan 22, 2014
        if logEvents:
            self._events.append(Event("CaptureOneStep %d" % step))
        f = self._freqs[step]
##        print (">>>2572<<< step: ", step , ", f: ", f)
        if f < -48:
            Sdb = nan
            Sdeg = nan
            Mdb = nan
            Mdeg = nan
        else:
            doPhase = self.mode > self.MODE_SATG
            invPhase = self.invPhase
            if hardwarePresent:
                self.LogEvent("CaptureOneStep hardware, f=%g" % f)
                # set MSA to read frequency f
                self._CommandAllSlims(f)

    # ------------------------------------------------------------------------------
                if p.cftest ==1:
##                      cavityLO2 = msa.finalfreq + LO1.freq
                    cavityLO2 =1013.3 + msa.finalfreq + f
                    print ("freq: ", f)
                    LO2.CreateIntegerNcounter(cavityLO2, msa.masterclock)
                    LO2.CreatePLLN()
                    LO2.freq = ((LO2.Bcounter*LO2.preselector) + LO2.Acounter+(LO2.fcounter/16))*LO2.pdf
                    LO2.CommandPLL(LO2.PLLbits)
    # ------------------------------------------------------------------------------
                self.LogEvent("CaptureOneStep delay")
                if step == 0:
                    # give the first step extra time to settle
                    cb.msWait(200)
                    self._CommandAllSlims(f)
                cb.msWait(self.wait)
                # read raw magnitude and phase
                self.LogEvent("CaptureOneStep read")
                cb.ReqReadADCs(16)
                cb.FlushRead()
                cb.Flush()
                time.sleep(0)
                self._ReadAD16Status()
                if logEvents: # EON Jan 22, 2014
                    self._events.append(Event("CaptureOneStep got %06d" % \
                                    self._magdata))
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
                    self.LogEvent("CaptureOneStep phase delay")
                    cb.msWait(200)
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
##                self._InputSynth(f) # JGH syndutHook4
                invPhase = 0
                cb.msWait(self.wait)
                # sleep for 1 ms to give GUI a chance to catch up on key events
                time.sleep(0.001)

            ##print ("Capture: magdata=", self._magdata
            if useCal and len(self.magTableADC) > 0:
                # adjust linearity of values using magTable
                Sdb = interp(self._magdata, self.magTableADC, self.magTableDBm)
                ##print ("Capture: Sdb=", Sdb
                ##self.LogEvent("CaptureOneStep magTableADC")
            else:
                # or just assume linear and estimate gain
                Sdb = (self._magdata / 65536 - 0.5) * 200
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
                    Sdeg = modDegree(self._phasedata / 65536 * 360)
                else:
                    Sdeg = modDegree(self._phasedata / 65536 * 360 - \
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
                    if msa.mode == MSA.MODE_VNARefl:
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
        try:
            self.LogEvent("_ScanThread")

            # clear out any prior FIFOed data from interface
            cb.Clear()
            elapsed = 0
            while self.scanEnabled:
                if logEvents: # EON Jan 22, 2014
                    self._events.append(Event("_ScanThread wloop, step %d" % \
                                              self._step))
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

    def NewScan(self, parms):

        self.LogEvent("NewScan nSteps=%d" % parms.nSteps)

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
            self._freqs = linspace(fStart, fStop, nSteps+1) # JGH linspace comes from numpy self._freqs = linspace(self._fStart, self._fStop, nSteps+1)

    #--------------------------------------------------------------------------
    # Start an asynchronous scan of a spectrum. The results may be read at
    # any time. Returns True if scan wasn't already running.

    def Scan(self, gui, parms, haltAtEnd):
        self.LogEvent("Scan")
        if self._scanning:
            return False
        self.gui = gui
        self.haltAtEnd = haltAtEnd
        self.NewScan(parms)
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
        if not self._scanning:
            self.LogEvent("ContinueScan start_new_thread")
            self.scanEnabled = self._scanning = True
            thread.start_new_thread(self._ScanThread, ())
        self.LogEvent("ContinueScan exit")

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
        step = max(self._step - 1, 0)
        return [
            "this step = %d" % step,
            "dds1output = %0.9g MHz" % LO1.ddsoutput,
            "LO1 = %0.9g MHz" % LO1.freq,
            "pdf1 = %0.9g MHz" % LO1.pdf,
            "ncounter1 = %d" % LO1.ncounter,
            "Bcounter1 = %d" % LO1.Bcounter,
            "Acounter1 = %d" % LO1.Acounter,
            "fcounter1 = %d" % LO1.fcounter,
            "rcounter1 = %d" % LO1.rcounter,
            "LO2 = %0.6f MHz" % LO2.freq,
            "pdf2 = %0.6f MHz" % LO2.pdf,
            "ncounter2 = %d" % LO2.ncounter,
            "Bcounter2 = %d" % LO2.Bcounter,
            "Acounter2 = %d" % LO2.Acounter,
            "rcounter2 = %d" % LO2.rcounter,
            "LO3 = %0.6f MHz" % LO3.freq,
            "pdf3 = %0.6f MHz" % LO3.pdf,
            "ncounter3 = %d" % LO3.ncounter,
            "Bcounter3 = %d" % LO3.Bcounter,
            "Acounter3 = %d" % LO3.Acounter,
            "fcounter3 = %d" % LO3.fcounter,
            "rcounter3 = %d" % LO3.rcounter,
            "dds3output = %0.9g MHz" % LO3.ddsoutput,
            "Magdata=%d mag=%0.5g" % (self._magdata, self._Sdb),
            "Phadata=%d PDM=%0.5g" % (self._phasedata, self._Sdeg),
            "Real Final I.F. = %f" % (LO2.freq  - 0),
            "Masterclock = %0.6f" % msa.masterclock

        ]

    #--------------------------------------------------------------------------
    # Spectrum accessors.

    def HaveSpectrum(self):
        return self._fStart != None

    def NewSpectrumFromRequest(self, title):
        return Spectrum(title, self.indexRBWSel+1, self._fStart, self._fStop,
                        self._nSteps, self._freqs)


#******************************************************************************
#****                          MSA GUI Front End                          *****
#******************************************************************************

# Waveform display colors

# light-theme colors
red       = wx.Colour(255,   0,   0)
blue      = wx.Colour(  0,   0, 255)
green     = wx.Colour(  0, 255,   0)
aqua      = wx.Colour(  0, 255, 255)
lavender  = wx.Colour(255,   0, 255)
yellow    = wx.Colour(255, 255,   0)
peach     = wx.Colour(255, 192, 203)
dkbrown   = wx.Colour(165,  42,  42)
teal      = wx.Colour(  0, 130, 130)
brown     = wx.Colour(130,   0, 130)
stone     = wx.Colour(240, 230, 140)
orange    = wx.Colour(255, 165,   0)
ltgray    = wx.Colour(180, 180, 180)

# original MSA dark-theme colors
msaGold   = wx.Colour(255, 190,  43)
msaAqua   = aqua
msaGreen  = wx.Colour(0,   255,   0)
msaYellow = wx.Colour(244, 255,   0)
msaGray   = wx.Colour(176, 177, 154)


#==============================================================================
# A Color theme.

class Theme:

    @classmethod
    def FromDict(cls, d):
        d = Struct(**d)
        this = cls()
        this.name       = d.name
        this.backColor  = d.backColor
        this.foreColor  = d.foreColor
        this.hColor     = d.hColor
        this.vColors    = d.vColors
        this.gridColor  = d.gridColor
        this.textWeight = d.textWeight
        this.iNextColor = 0
        return this

    def UpdateFromPrefs(self, p):
        for attrName in self.__dict__.keys():
            pAttrName = "theme_%s_%s" % (p.graphAppear, attrName)
            if hasattr(p, pAttrName):
                setattr(self, attrName, getattr(p, pAttrName))

    def SavePrefs(self, p):
        for attrName, attr in self.__dict__.items():
            if attrName[0] != "_":
                pAttrName = "theme_%s_%s" % (p.graphAppear, attrName)
                setattr(p, pAttrName, attr)

DarkTheme = Theme.FromDict(dict(
        name       = "Dark",
        backColor  = wx.BLACK,
        foreColor  = wx.WHITE,
        gridColor  = msaGray,
        hColor     = wx.WHITE,
        vColors    = [msaGold, msaAqua, msaGreen, msaYellow, teal, brown],
        textWeight = wx.BOLD))

LightTheme = Theme.FromDict(dict(
        name       = "Light",
        backColor  = wx.WHITE,
        foreColor  = wx.BLACK,
        gridColor  = ltgray,
        hColor     = wx.BLACK,
        vColors    = [red, blue, green, blue, aqua, lavender, yellow, peach,
                      dkbrown, stone, orange],
        textWeight = wx.NORMAL))


#==============================================================================
# Preferences as attributes.

class Prefs:
    def __init__(self):
        self._fName = None

    #--------------------------------------------------------------------------
    # Read a preferences file and translate it into attributes.

    @classmethod
    def FromFile(cls, fName):
        this = cls()
        this._fName = fName
        try:
            af = open(fName, "r")
            configPat = re.compile(r"^[ \t]*([^=]+)[ \t]*=[ \t]*(.*)$")

            for line in af.readlines():
                ##print ("line=", line)
                m = configPat.match(line)
                if m and line[0] != "|":
                    name, value = m.groups()
                    ##print ("parameter", name, "=", value)
                    try:
                        value = eval(value)
                    except:
                        pass
                    setattr(this, name, value)

            af.close()
        except IOError:
            print ("No prefs file found. Getting defaults.")
        return this

    #--------------------------------------------------------------------------
    # Save given preferences to file.

    def save(self, fName=None, header=None):
        if not fName:
            fName = self._fName
        pf = open(fName, "w")
        if header:
            pf.write("|%s\n" % header)

        for name in sorted(dir(self)):
            value = getattr(self, name)
            ##print ("Saving pref", name, value)
            if name[0] != '_' and type(value) != type(self.__init__):
                if type(value) == type(1.):
                    value = str(value)
                elif name == "theme":
                    value = value.name
                elif name.find(" "):
                    value = repr(value)
                pf.write("%s=%s\n" % (name, value))
        pf.close()

    #--------------------------------------------------------------------------
    # Get a preference value, possibly using the default.

    def get(self, name, defaultValue):
        if not hasattr(self, name):
            setattr(self, name, defaultValue)
        value = getattr(self, name)
        if type(value) != type(defaultValue) and type(value) == type(""):
            try:
                value = eval(value)
            except:
                pass
        return value


#==============================================================================
# The message pane and log file to which stdout and stderr are redirected to.

class Logger:
    def __init__(self, name, textCtrl, frame):
        global logFile
        logFile = file(name + ".log", "w+")
        self.textCtrl = textCtrl
        self.frame = frame
        self.lineCount = 0

    def write(self, s):
        global logFile
        # frame = self.frame    # JGH 2/10/14
        try:
            if "\n" in s:
                self.lineCount += 1
            maxLogWinLines = 10000
            if wx.Thread_IsMain() and self.lineCount < maxLogWinLines:
                logFile.write(s)
                self.textCtrl.AppendText(s)
            elif self.lineCount < maxLogWinLines or msa.showError:
                msa.errors.put(s)
        except:
            pass # don't recursively crash on errors


#==============================================================================
# Calculate spacing for a standard 1-2-5 sequence scale.
#   bot:    bottom range of scale (units)
#   top:    top range of scale (units)
#   size:   size of space for scale (pixels)
#   divSize: target size of one division (pixels)
# returns:
#   ds:     units per division
#   base:   next division equal to or above bot (units)
#   frac:   remainer between base and bot (units)
#   nDiv:   number of divisions in scale

def StdScale(bot, top, size, divSize):
    wid = top - bot
    dsExp, dsMantNo = divmod(log10(wid * divSize / size), 1)
    if isnan(dsMantNo):
        print ("StdScale dsMantNo=", dsMantNo)
        return 1, 0, 0, 0
    ds = (1.0, 2.0, 5.0, 5.0)[int(3 * dsMantNo + 0.1)] * 10**dsExp
    base = floor(bot/ds + 0.95) * ds
    frac = base - bot
    nDiv = max(int(wid/ds), 0) + 1
    return ds, base, frac, nDiv


#==============================================================================
# A graph vertical axis scale.
# Each trace refers to one of these, and these in turn refer to one primary
# (or only) trace for their color. The scale is placed on either side of the
# graph, with higher-priority scales on the inside.

class VScale:
    def __init__(self, typeIndex, mode, top, bot, primeTraceUnits):
        self.typeIndex = typeIndex
        self.top = top
        self.bot = bot
        self.maxHold = False
        self.primeTraceUnits = primeTraceUnits
        typeList = traceTypesLists[mode]
        self.dataType = typeList[min(typeIndex, len(typeList)-1)]

    #--------------------------------------------------------------------------
    # Perform auto-scale on limits to fit data.

    def AutoScale(self, frame):
        # specP = frame.specP    # JGH 2/10/14
        dataType = self.dataType
        if dataType.units == "Deg":
            self.top = 180
            self.bot = -180
        elif self.typeIndex > 0:
            tr = dataType(frame.spectrum, 0)
            v = tr.v
            vmin = v[v.argmin()]
            vmax = v[v.argmax()]
            if isfinite(vmin) and isfinite(vmax) and vmax > vmin:
                print ("Auto scale: values from", vmin, "to", vmax)
                # round min/max to next even power
                ds, base, frac, nDiv = StdScale(vmin, vmax, 1., 1.)
                print ("Auto scale: ds=", ds, "base=", base, "frac=", frac, "nDiv=", nDiv)
                if isfinite(base) and isfinite(ds):
                    if frac == 0:
                        bot = base
                    else:
                        bot = base - ds
                    top = bot + ds*nDiv
                    if top < vmax:
                        top += ds
                else:
                    bot = tr.bot
                    top = tr.top
            else:
                bot = tr.bot
                top = tr.top
            self.top = top
            self.bot = bot

    #--------------------------------------------------------------------------
    # Open the Vertical Scale dialog box and apply to this scale.

    def Set(self, frame, pos):
        specP = frame.specP
        dlg = VScaleDialog(specP, self, pos)
        save = dcopy.copy(self)
        if dlg.ShowModal() == wx.ID_OK:
            dlg.Update()
        else:
            self.top = save.top
            self.bot = save.bot
            self.typeIndex = save.typeIndex
            self.dataType = save.dataType
            frame.DrawTraces()
            specP.FullRefresh()


#==============================================================================
# A single trace in a graph.
# These are temporary objects, created by DrawTraces() from the spectrum on
# each graph update.
# spec: Spectrum containing trace data
# iScale: index into specP.vScales[]

class Trace:
    def __init__(self, spec, iScale):
        self.spec = spec
        self.iScale = iScale
        ##self.iColor = Theme.iNextColor
        ##Theme.iNextColor = (Theme.iNextColor+1) % len(LightTheme.vColors)
        self.Fmhz = spec.Fmhz
        self.dotSize = 1
        self.mathMode = 0
        self.ys = None
        self.displayed = True
        self.phaseTrace = None
        self.magTrace = None
        self.siFlags = 0
        self.isMain = True
        self.maxHold = False
        self.max = False
        try:
            self.LFmhz = log10(spec.Fmhz)
        except FloatingPointError:
            self.LFmhz = spec.Fmhz


    # Return the data index for a given frequency in MHz.
    # Optionally returns the index base frequency f0 and spacing df.

    def Index(self, mhz, isLogF, returnBaseSpacing=False):
        Fmhz = (self.Fmhz, self.LFmhz)[isLogF]
        if isLogF:
            mhz = log10(max(mhz, 1e-6))
        f0 = Fmhz[0]
        df = Fmhz[1] - f0
        if df > 0:
            j = int((mhz - f0) / df + 0.5)
        else:
            j = 0
        if returnBaseSpacing:
            return j, f0, df
        return j

class NoTrace(Trace):
    desc = "None"
    name = None
    units = None
    top = 0
    bot = 0
    def __init__(self, spec, iScale):
        Trace.__init__(self, spec, iScale)

    def SetStep(self, spec, i):
        pass

#------------------------------------------------------------------------------
# SA Mode Trace types.

class SATrace(Trace):
    def __init__(self, spec, iScale):
        Trace.__init__(self, spec, iScale)
        self.Sdb = dcopy.copy(spec.Sdb)

    def SetStep(self, spec, i):
        if not self.maxHold:
            self.Sdb[i] = spec.Sdb[i]
        else:
            if self.max:
                if spec.Sdb[i] > self.Sdb[i]:
                    self.Sdb[i] = spec.Sdb[i]
            else:
                self.Sdb[i] = spec.Sdb[i]
                if i == spec.nSteps:
                    self.max = True

class MagdBmTrace(SATrace):
    desc = "Magnitude (dBm)"
    name = "Mag"
    units = "dBm"
    top = 0
    bot = -120
    def __init__(self, spec, iScale):
        SATrace.__init__(self, spec, iScale)
        self.v = dcopy.copy(self.Sdb)

    def SetStep(self, spec, i):
        SATrace.SetStep(self, spec, i)
        self.v[i] = self.Sdb[i]

class MagWattsTrace(SATrace):
    desc = "Magnitude (Watts)"
    name = "MagW"
    units = "Watts"
    top = 1*mW
    bot = 0
    def __init__(self, spec, iScale):
        SATrace.__init__(self, spec, iScale)
        self.v = 10**(self.Sdb/10 - 3)

    def SetStep(self, spec, i):
        SATrace.SetStep(self, spec, i)
        self.v[i] = 10**(self.Sdb[i]/10 - 3)

class MagVoltsTrace(SATrace):
    desc = "Magnitude (Volts)"
    name = "MagV"
    units = "Volts"
    top = 1
    bot = 0
    def __init__(self, spec, iScale):
        SATrace.__init__(self, spec, iScale)
        self.v = sqrt(10**(self.Sdb/10 - 3) * 50)

    def SetStep(self, spec, i):
        SATrace.SetStep(self, spec, i)
        self.v[i] = sqrt(10**(self.Sdb[i]/10 - 3) * 50)

# A list of Reflection mode data types, in type-chooser order
traceTypesLists = [None]*4
traceTypesLists[MSA.MODE_SA] = (
    NoTrace,
    MagdBmTrace,
    MagWattsTrace,
    MagVoltsTrace,
)

#------------------------------------------------------------------------------
# SATG Mode.

class SATGTrace(Trace):
    def __init__(self, spec, iScale):
        Trace.__init__(self, spec, iScale)
        self.Sdb = dcopy.copy(spec.Sdb)

    def SetStep(self, spec, i):
        if not self.maxHold:
            self.Sdb[i] = spec.Sdb[i]
        else:
            if self.max:
                if spec.Sdb[i] > self.Sdb[i]:
                    self.Sdb[i] = spec.Sdb[i]
            else:
                self.Sdb[i] = spec.Sdb[i]
                if i == spec.nSteps:
                    self.max = True

class TransdBTrace(SATGTrace):
    desc = "Transmission (dB)"
    name = "Mag"
    units = "dB"
    top = 0
    bot = -120
    def __init__(self, spec, iScale):
        SATGTrace.__init__(self, spec, iScale)
        self.v = dcopy.copy(self.Sdb)

    def SetStep(self, spec, i):
        SATGTrace.SetStep(self, spec, i)
        self.v[i] = self.Sdb[i]

class TransRatTrace(SATGTrace):
    desc = "Transmission (Ratio)"
    name = "MagRat"
    units = "Ratio"
    top = 1
    bot = 0
    def __init__(self, spec, iScale):
        SATGTrace.__init__(self, spec, iScale)
        self.v = 10**(self.Sdb/20)

    def SetStep(self, spec, i):
        SATGTrace.SetStep(self, spec, i)
        self.v[i] = 10**(self.Sdb[i]/20)

class InsLossTrace(SATGTrace):
    desc = "Insertion Loss (dB)"
    name = "IL"
    units = "dB"
    top = 60
    bot = 0
    def __init__(self, spec, iScale):
        SATGTrace.__init__(self, spec, iScale)
        self.v = -self.Sdb

    def SetStep(self, spec, i):
        SATGTrace.SetStep(self, spec, i)
        self.v[i] = -self.Sdb[i]

traceTypesLists[MSA.MODE_SATG] = (
    NoTrace,
    TransdBTrace,
    TransRatTrace,
    InsLossTrace,
)

#------------------------------------------------------------------------------
# Transmission Mode.

class S21Trace(Trace):
    def __init__(self, spec, iScale):
        Trace.__init__(self, spec, iScale)
        self.Sdb = dcopy.copy(spec.Sdb)
        self.Sdeg = dcopy.copy(spec.Sdeg)
        self.S21 = 10**(spec.Sdb/20) + exp(1j*pi*spec.Sdeg/180)

    def SetStep(self, spec, i):
        if not self.maxHold:
            self.Sdb[i] = spec.Sdb[i]
        else:
            if self.max:
                if spec.Sdb[i] > self.Sdb[i]:
                    self.Sdb[i] = spec.Sdb[i]
            else:
                self.Sdb[i] = spec.Sdb[i]
                if i == spec.nSteps:
                    self.max = True
        self.Sdeg[i] = spec.Sdeg[i]
        self.S21[i] = 10**(spec.Sdb[i]/20) + exp(1j*pi*spec.Sdeg[i]/180)

class S21MagTrace(S21Trace):
    desc = "S21 Magnitude (dB)"
    name = "S21_dB"
    units = "dB"
    top = 0
    bot = -100
    def __init__(self, spec, iScale):
        S21Trace.__init__(self, spec, iScale)
        self.v = dcopy.copy(self.Sdb)

    def SetStep(self, spec, i):
        S21Trace.SetStep(self, spec, i)
        self.v[i] = self.Sdb[i]

class S21PhaseTrace(S21Trace):
    desc = "S21 Phase Angle"
    name = "S21_Deg"
    units = "Deg"
    top = 180
    bot = -180
    def __init__(self, spec, iScale):
        S21Trace.__init__(self, spec, iScale)
        self.v = self.Sdeg

    def SetStep(self, spec, i):
        S21Trace.SetStep(self, spec, i)
        self.v[i] = self.Sdeg[i]

class S21ConPhaseTrace(S21Trace):
    desc = "S21 Continuous Phase"
    name = "S21_CDeg"
    units = "CDeg"
    top = 180
    bot = -180
    def __init__(self, spec, iScale):
        S21Trace.__init__(self, spec, iScale)
        self.v = dcopy.copy(spec.Scdeg)

    def SetStep(self, spec, i):
        S21Trace.SetStep(self, spec, i)
        self.v[i] = spec.Scdeg[i]

class RawPowerTrace(S21Trace):
    desc = "Raw Power (dBm)"
    name = "Power"
    units = "dBm"
    top = 0
    bot = -100
    def __init__(self, spec, iScale):
        S21Trace.__init__(self, spec, iScale)
        self.v = spec.Mdb

    def SetStep(self, spec, i):
        S21Trace.SetStep(self, spec, i)
        self.v[i] = spec.Mdb[i]

class RawPhaseTrace(S21Trace):
    desc = "Raw Phase Angle"
    name = "RawPhase"
    units = "Deg"
    top = 180
    bot = -180
    def __init__(self, spec, iScale):
        S21Trace.__init__(self, spec, iScale)
        self.v = spec.Mdeg

    def SetStep(self, spec, i):
        S21Trace.SetStep(self, spec, i)
        self.v[i] = spec.Mdeg[i]

##class InsLossTrace(S21Trace): # EON Jan 29, 2014
##    desc = "Insertion Loss (dB)"
##    name = "IL"
##    units = "dB"
##    top = 60
##    def __init__(self, spec, iScale):
##        S21Trace.__init__(self, spec, iScale)
##        self.v = -self.Sdb

class GroupDelayTrace(S21Trace):
    desc = "S21 Group Delay"
    name = "GD"
    units = "sec"
    top = 0
    bot = 0
    def __init__(self, spec, iScale):
        S21Trace.__init__(self, spec, iScale)
        # first filter phases (n is boxcar width, must be odd)
        ph = pi*spec.Scdeg/180
        nb = (len(ph)//60)*2 + 3
        self.boxcar = zeros(nb) + 1/nb
        # apply boxcar and trim result because boxcar appends points
        ph = convolve(ph, self.boxcar)
        self.dn = len(ph) - len(spec.Scdeg)
        self.dn2 = self.dn // 2
        ph = ph[self.dn2:self.dn2-self.dn]
        # get pointwise delta-frequency (may be log scale)
        self.df = (append(spec.f[1:], 0) - spec.f) * MHz
        ##print ("gd len", nb, len(ph), len(spec.f), len(df)
        # then differentiate to get group delay
        gd = -diff(ph)
        # append because diff() takes off 1 point, and scale
        self.v = append(gd, 0) / (2*pi*self.df)
        ##print ("gd:", ph[20:25], gd[20:25], df[20:25]

    def SetStep(self, spec, i):
        S21Trace.SetStep(self, spec, i)
        # first filter phases (n is boxcar width, must be odd)
        ph = pi*spec.Scdeg/180
        # nb = (len(ph)//60)*2 + 3
        # boxcar = zeros(nb) + 1/nb
        # apply boxcar and trim result because boxcar appends points
        ph = convolve(ph, self.boxcar)
        # dn = len(ph) - len(spec.Scdeg)
        # dn2 = dn // 2
        ph = ph[self.dn2:self.dn2-self.dn]
        # get pointwise delta-frequency (may be log scale)
        # df = (append(spec.f[1:], 0) - spec.f) * MHz
        # then differentiate to get group delay
        gd = -diff(ph)
        # append because diff() takes off 1 point, and scale
        self.v = append(gd, 0) / (2*pi*self.df)

traceTypesLists[MSA.MODE_VNATran] = (
    NoTrace,
    S21MagTrace,
    S21PhaseTrace,
    S21ConPhaseTrace,
    RawPowerTrace,
    RawPhaseTrace,
    InsLossTrace,
    GroupDelayTrace,
)

#------------------------------------------------------------------------------
# Reflection Mode.

class S11Trace(Trace):
    top = 0
    bot = -100
    def __init__(self, spec, iScale):
        Trace.__init__(self, spec, iScale)
#         self.Sdb = spec.Sdb
        if incremental:
            self.Sdb = dcopy.copy(spec.Sdb)
        else:
            self.Sdb = spec.Sdb
        if truncateS11ToUnity:
            self.Sdb = min2(self.Sdb, 0)
#         self.Sdeg = spec.Sdeg
        if incremental:
            self.Sdeg = dcopy.copy(spec.Sdeg)
        else:
            self.Sdeg = spec.Sdeg
        S11 = S21 = 10**(spec.Sdb/20) * exp(1j*pi*spec.Sdeg/180)
        self.S21db = self.Sdb
        self.S21deg = self.Sdeg

        R0 = 50     # TEMP
        if spec.isSeriesFix or spec.isShuntFix:
            # Using a Series or Shunt "Reflectance" fixture:
            S11, Z = EquivS11FromS21(S11, spec.isSeriesFix, R0)
            self.Z = Z
            self.Sdb = db(abs(S11))
            self.Sdeg = 180*angle(S11)/pi

        self.S11 = S11
        ##print ("S11=", S11[0], "S21=", S21[0]
        save = seterr(all="ignore")
        self.Zs = Zs = 50 * (1 + S11) / (1 - S11)
        ##print ("Zs=", Zs[:5]
        # Zp is equivalent parallel impedance to Zs
        mag2 = Zs.real**2 + Zs.imag**2
        self.Zp = Zp = mag2/Zs.real + 1j*mag2/Zs.imag
        ##print ("Zp=", Zp[:5]
        seterr(**save)
        self.w = 2*pi*spec.f*MHz

    def SetStep(self, spec, i):
        if not self.maxHold:
            self.Sdb[i] = spec.Sdb[i]
        else:
            if self.max:
                if spec.Sdb[i] > self.Sdb[i]:
                    self.Sdb[i] = spec.Sdb[i]
            else:
                self.Sdb[i] = spec.Sdb[i]
                if i == spec.nSteps:
                    self.max = True

        if truncateS11ToUnity:
            self.Sdb[i] = min2(self.Sdb[i], 0)
        self.Sdeg[i] = spec.Sdeg[i]
        S11 = S21 = 10**(spec.Sdb[i]/20) * exp(1j*pi*spec.Sdeg[i]/180)
        self.S21db = self.Sdb[i]
        self.S21deg = self.Sdeg[i]
 
        R0 = 50     # TEMP
        if spec.isSeriesFix or spec.isShuntFix:
            # Using a Series or Shunt "Reflectance" fixture:
            S11, Z = EquivS11FromS21(S11[i], spec.isSeriesFix, R0)
            self.Z[i] = Z
            self.Sdb[i] = db(abs(S11))
            self.Sdeg[i] = 180*angle(S11)/pi
 
        self.S11[i] = S11
        save = seterr(all="ignore")
        self.Zs[i] = Zs = 50 * (1 + S11) / (1 - S11)
        # Zp is equivalent parallel impedance to Zs
        mag2 = Zs.real**2 + Zs.imag**2
        self.Zp[i] = Zp = mag2/Zs.real + 1j*mag2/Zs.imag
        seterr(**save)
        self.w[i] = 2*pi*spec.f[i]*MHz

class CapTrace(S11Trace):
    units = "F"
    top = 1*uF
    bot = 0
    def __init__(self, spec, iScale):
        S11Trace.__init__(self, spec, iScale)

    def SetV(self, Z):
        save = seterr(all="ignore")
        self.v = -1 / (Z.imag*self.w)
        seterr(**save)

    def Set(self, Z, i):
        save = seterr(all="ignore")
        self.v[i] = -1 / (Z[i].imag*self.w[i])
        seterr(**save)

    def SetStep(self, spec, i):
        S11Trace.SetStep(self, spec, i)
        pass

class InductTrace(S11Trace):
    units = "H"
    top = 1*uH
    bot = 0
    def __init__(self, spec, iScale):
        S11Trace.__init__(self, spec, iScale)

    def SetV(self, Z):
        save = seterr(all="ignore")
        self.v = Z.imag/self.w
        seterr(**save)

    def Set(self, Z, i):
        save = seterr(all="ignore")
        self.v[i] = Z[i].imag/self.w[i]
        seterr(**save)

    def SetStep(self, spec, i):
        S11Trace.SetStep(self, spec, i)

class S11MagTrace(S11Trace):
    desc = "S11 Magnitude (dB)"
    name = "S11_dB"
    units = "dB"
    top = 0
    bot = -100
    def __init__(self, spec, iScale):
        S11Trace.__init__(self, spec, iScale)
        self.v = self.Sdb

    def SetStep(self, spec, i):
        S11Trace.SetStep(self, spec, i)
        self.v[i] = self.Sdb[i]

class S11PhaseTrace(S11Trace):
    desc = "S11 Phase Angle (Deg)"
    name = "S11_Deg"
    units = "Deg"
    top = 180
    bot = -180
    def __init__(self, spec, iScale):
        S11Trace.__init__(self, spec, iScale)
        self.v = self.Sdeg

    def SetStep(self, spec, i):
        S11Trace.SetStep(self, spec, i)
        self.v[i] = self.Sdeg[i]

class RhoTrace(S11Trace):
    desc = "Reflect Coef. Mag (Rho)"
    name = "Rho"
    units = "Ratio"
    top = 1
    bot = 0
    def __init__(self, spec, iScale):
        S11Trace.__init__(self, spec, iScale)
        self.v = 10**(self.Sdb/20)

    def SetStep(self, spec, i):
        S11Trace.SetStep(self, spec, i)
        self.v[i] = 10**(self.Sdb[i]/20)

class ThetaTrace(S11Trace):
    desc = "Reflect Coef. Angle (Theta)"
    name = "Theta"
    units = "Deg"
    top = 180
    bot = -180
    def __init__(self, spec, iScale):
        S11Trace.__init__(self, spec, iScale)
        self.v = self.Sdeg

    def SetStep(self, spec, i):
        S11Trace.SetStep(self, spec, i)
        self.v[i] = self.Sdeg[i]

##class S21MagTrace(S11Trace): EON Jan 29, 2014
##    desc = "S21 Magnitude (dB)"
##    name = "S21_dB"
##    units = "dB"
##    top = 0
##    bot = -100
##    def __init__(self, spec, iScale):
##        S11Trace.__init__(self, spec, iScale)
##        self.v = self.S21db
##
##class S21PhaseTrace(S11Trace): EON Jan 29, 2014
##    desc = "S21 Phase Angle (Deg)"
##    name = "S21_Deg"
##    units = "Deg"
##    def __init__(self, spec, iScale):
##        S11Trace.__init__(self, spec, iScale)
##        self.v = self.S21deg

class ZMagTrace(S11Trace):
    desc = "Impedance Mag (Z Mag)"
    name = "Z_Mag"
    units = "ohms"
    top = 200
    bot = 0
    def __init__(self, spec, iScale):
        S11Trace.__init__(self, spec, iScale)
        self.v = abs(self.Zs) # EON Jan 10 2014

    def SetStep(self, spec, i):
        S11Trace.SetStep(self, spec, i)
        self.v[i] = abs(self.Zs[i])

class ZPhaseTrace(S11Trace):
    desc = "Impedance Angle (Z Ang)"
    name = "Z_Ang"
    units = "Deg"
    top = 180
    bot = -180
    def __init__(self, spec, iScale):
        S11Trace.__init__(self, spec, iScale)
        self.v = 180*angle(self.Zs)/pi # EON Jan 10 2014

    def SetStep(self, spec, i):
        S11Trace.SetStep(self, spec, i)
        self.v[i] = 180*angle(self.Zs[i])/pi

class SerResTrace(S11Trace):
    desc = "Series Resistance (Rs)"
    name = "Rs"
    units = "ohms"
    top = 200
    bot = 0
    def __init__(self, spec, iScale):
        S11Trace.__init__(self, spec, iScale)
        self.v = self.Zs.real

    def SetStep(self, spec, i):
        S11Trace.SetStep(self, spec, i)
        self.v[i] = self.Zs[i].real

class SerReactTrace(S11Trace):
    desc = "Series Reactance (Xs)"
    name = "Xs"
    units = "ohms"
    top = 200
    bot = -200
    def __init__(self, spec, iScale):
        S11Trace.__init__(self, spec, iScale)
        self.v = self.Zs.imag

    def SetStep(self, spec, i):
        S11Trace.SetStep(self, spec, i)
        self.v[i] = self.Zs[i].imag

class SerCapTrace(CapTrace):
    desc = "Series Capacitance (Cs)"
    name = "Cs"
    top = 1*uF
    bot = 0
    def __init__(self, spec, iScale):
        CapTrace.__init__(self, spec, iScale)
        self.SetV(self.Zs)

    def SetStep(self, spec, i):
        CapTrace.SetStep(self, spec, i)
        self.Set(self.Zs, i)

class SerInductTrace(InductTrace):
    desc = "Series Inductance (Ls)"
    name = "Ls"
    top = 1*uH
    bot = 0
    def __init__(self, spec, iScale):
        InductTrace.__init__(self, spec, iScale)
        self.SetV(self.Zs)

    def SetStep(self, spec, i):
        InductTrace.SetStep(self, spec, i)
        self.Set(self.Zs, i)

class ParResTrace(S11Trace):
    desc = "Parallel Resistance (Rp)"
    name = "Rp"
    units = "ohms"
    top = 200
    bot = 0
    def __init__(self, spec, iScale):
        S11Trace.__init__(self, spec, iScale)
        self.v = self.Zp.real

    def SetStep(self, spec, i):
        S11Trace.SetStep(self, spec, i)
        self.v[i] = self.Zp[i].real

class ParReactTrace(S11Trace):
    desc = "Parallel Reactance (Xp)"
    name = "Xp"
    units = "ohms"
    bot = -200
    top = 200
    def __init__(self, spec, iScale):
        S11Trace.__init__(self, spec, iScale)
        self.v = self.Zp.imag

    def SetStep(self, spec, i):
        S11Trace.SetStep(self, spec, i)
        self.v[i] = self.Zp[i].imag

class ParCapTrace(CapTrace):
    desc = "Parallel Capacitance (Cp)"
    name = "Cp"
    top = 1*uF
    bot = 0
    def __init__(self, spec, iScale):
        CapTrace.__init__(self, spec, iScale)
        self.SetV(self.Zp)

    def SetStep(self, spec, i):
        CapTrace.SetStep(self, spec, i)
        self.Set(self.Zp, i)

class ParInductTrace(InductTrace):
    desc = "Parallel Inductance (Lp)"
    name = "Lp"
    top = 1*uH
    bot = 0
    def __init__(self, spec, iScale):
        InductTrace.__init__(self, spec, iScale)
        self.SetV(self.Zp)

    def SetStep(self, spec, i):
        InductTrace.SetStep(self, spec, i)
        self.Set(self.Zp, i)

class ReturnLossTrace(S11Trace):
    desc = "Return Loss (db)"
    name = "RL"
    units = "dB"
    top = 60
    bot = 0
    def __init__(self, spec, iScale):
        S11Trace.__init__(self, spec, iScale)
        self.v = -self.Sdb

    def SetStep(self, spec, i):
        S11Trace.SetStep(self, spec, i)
        self.v[i] = -self.Sdb[i]

class ReflPwrTrace(S11Trace):
    desc = "Reflected Power (%)"
    name = "RefPwr"
    units = "%"
    top = 100
    bot = 0
    def __init__(self, spec, iScale):
        S11Trace.__init__(self, spec, iScale)
        self.v = 100 * 10**(self.Sdb/10)

    def SetStep(self, spec, i):
        S11Trace.SetStep(self, spec, i)
        self.v[i] = 100 * 10**(self.Sdb[i]/10)

class CompQTrace(S11Trace):
    desc = "Component Q"
    name = "Q"
    units = "Ratio"
    top = 0
    bot = 0
    def __init__(self, spec, iScale):
        S11Trace.__init__(self, spec, iScale)
        self.v = abs(self.Zs.imag) / self.Zs.real

    def SetStep(self, spec, i):
        S11Trace.SetStep(self, spec, i)
        self.v[i] = abs(self.Zs[i].imag) / self.Zs[i].real

class VSWRTrace(S11Trace):
    desc = "VSWR"
    name = "VSWR"
    units = "Ratio"
    top = 10
    bot = 0
    def __init__(self, spec, iScale):
        S11Trace.__init__(self, spec, iScale)
        rat = 10**(self.Sdb/20)
        self.v = (1+rat) / (1-rat)

    def SetStep(self, spec, i):
        S11Trace.SetStep(self, spec, i)
        rat = 10**(self.Sdb[i]/20)
        self.v[i] = (1+rat) / (1-rat)

traceTypesLists[MSA.MODE_VNARefl] = (
    NoTrace,
    S11MagTrace,
    S11PhaseTrace,
    RhoTrace,
    ThetaTrace,
    ZMagTrace,
    ZPhaseTrace,
    S21MagTrace,
    S21PhaseTrace,
    SerResTrace,
    SerReactTrace,
    SerCapTrace,
    SerInductTrace,
    ParResTrace,
    ParReactTrace,
    ParCapTrace,
    ParInductTrace,
    ReturnLossTrace,
    ReflPwrTrace,
    CompQTrace,
    VSWRTrace,
)


#==============================================================================
# A frequency marker for the spectrum frame.

class Marker:
    # marker mode, set in menu
    MODE_INDEP = 1      # Independent
    MODE_PbyLR = 2      # P+,P- bounded by L,R
    MODE_LRbyPp = 3     # L,R bounded by P+
    MODE_LRbyPm = 4     # L,R bounded by P-

    def __init__(self, name, traceName, mhz):
        self.name = name            # "L", "1", etc.
        self.traceName = traceName  # name of trace it's on
        self.mhz = mhz              # frequency (MHz)
        self.dbm = 0                # mangitude (dBm)
        self.deg = 0                # phase (degrees)

    #--------------------------------------------------------------------------
    # Find position of peak in given spectrum.
    #
    # data:     spectrum in dBm.
    # df:       freq bin spacing, in MHz.
    # iLogF:    True for log-frequency mode.
    # isPos:    True for P+, False for P-.
    # f0:       frequency of data[0]

    def FindPeak(self, data, df, isLogF, isPos=True, f0=0):
        if isLogF:
            f0 = log10(max(f0, 1e-6))
        n = len(data)
        if n > 0:
            mhz = f0 + (data.argmin(), data.argmax())[isPos] * df
            if isLogF:
                mhz = 10**mhz
            ##print ("FindPeak: mhz=", mhz, data
            self.mhz = round(mhz, 6)

    #--------------------------------------------------------------------------
    # Find position of peak in given spectrum by fitting a polygon near the
    # peak. This method is better suited for a smooth peak with few samples.
    #
    # data:     spectrum in dBm.
    # df:       freq bin spacing, in MHz.
    # isPos:    True for P+, False for P-.
    # f0:       frequency of data[0]
    # pdev:     how many elements to include on either side of the peak.

    def FindPeakPoly(self, data, df, isPos=True, f0=0, pdev=5):
        n = len(data)
        Pi = (data.argmin(), data.argmax())[isPos]
        if Pi < pdev:
            pdev = Pi
        elif Pi+pdev > n:
            pdev = n-Pi
        if pdev == 0:
            # no width to peak: use center
            self.mhz = round(f0 + Pi * df, 6)
            self.dbm = data[Pi]
        else:
            # fit peak data segment to a polynomial
            Li = Pi-pdev
            Ri = Pi+pdev
            peakPart = data[Li:Ri]
            indecies = arange(2*pdev)
            warnings.simplefilter("ignore", RankWarning)
            if len(indecies) != len(peakPart):
                # no width to peak: use center
                self.mhz = round(f0 + Pi * df, 6)
                self.dbm = data[Pi]
            else:
                if peakPart[0] < -1e6:
                    return
                p = polyfit(indecies, peakPart, 4)
                pp = poly1d(p)
                # peak is where slope is zero
                dpRoots = pp.deriv().roots
                self.dpRoots = dpRoots
                # must be at least one real root for a degree 3 poly
                pos = 0
                minj = 999.
                maxr = 2*pdev - 1
                for root in dpRoots:
                    rj = abs(root.imag)
                    if rj < minj and root.real >= 0 and root.real <= maxr:
                        pos = root.real
                        minj = rj
                self.poly = pp
                self.mhz = round(f0 + (Li + pos) * df, 6)
                self.dbm = pp(pos)

    #--------------------------------------------------------------------------
    # Find frequency corresponding to a given vValue in given trace's data.
    #
    # trace:    trace with v[] and Fmhz[].
    # jP:       index of peak, where to start search.
    # signP:    +1 for P+, -1 for P-.
    # searchR:  True to search to right.
    # value:    vValue to search for.
    # show:     print debug lines

    def FindValue(self, trace, jP, isLogF, signP, searchR, value, show=False):
        Fmhz = (trace.Fmhz, trace.LFmhz)[isLogF]

        # trim vals and Fmhz arrays to the subset of steps to search in
        if searchR:
            vals  = trace.v[jP:]
            Fmhz =       Fmhz[jP:]
        else:
            vals  = trace.v[jP::-1]
            Fmhz =       Fmhz[jP::-1]

        # using interpolation, locate exact freq where vals crosses value
        # (multiplied by slope to insure that vals are in increasing order)
        slope = -signP
        if show:
            print ("FindValue: jP=", jP, "signP=", signP, \
                "vals=", slope*vals[:10].round(3))
            print (self.name, "searchR=", searchR, "value=", slope*value, \
                "Fmhz=", Fmhz[:10].round(6))
        mhz = interp(slope*value, slope*vals, Fmhz)
        if isLogF:
            mhz = 10**mhz

        # round to Hz
        self.mhz = round(mhz, 6)
        if show:
            print ("FindValue got mhz=", self.mhz)

    #--------------------------------------------------------------------------
    # Get value of given trace at marker's frequency.

    def TraceValue(self, trace, isLogF):
        if not Trace:
            return None
        Fmhz = (trace.Fmhz, trace.LFmhz)[isLogF]
        mhz = (self.mhz, log10(max(self.mhz, 1e-6)))[isLogF]
        leftMHz = Fmhz[0]
        value = None
        if leftMHz == Fmhz[-1]:
            # if scan has zero span and marker is on center, use any value
            if mhz == leftMHz:
                value = trace.v[0]
        else:
            # normal span: interpolate between trace values
            value = interp(mhz, Fmhz, trace.v)
        return value

    #--------------------------------------------------------------------------
    # Set marker's mag (& phase) by reading given traces at marker's frequency.

    def SetFromTrace(self, trace, isLogF):
        traceP = trace.phaseTrace
        if not traceP and trace.magTrace:
            trace = trace.magTrace
            traceP = trace.phaseTrace
        Fmhz = (trace.Fmhz, trace.LFmhz)[isLogF]
        mhz = (self.mhz, log10(max(self.mhz, 1e-6)))[isLogF]
        leftMHz = Fmhz[0]
        if leftMHz == Fmhz[-1]:
            # if scan has zero span and marker is on center, use any value
            if mhz == leftMHz:
                self.dbm = trace.v[0]
                if traceP:
                    self.deg = traceP.v[0]
        else:
            # normal span: interpolate between trace values
            self.dbm = interp(mhz, Fmhz, trace.v)
            if traceP:
                self.deg = interp(mhz, Fmhz, traceP.v)

    #--------------------------------------------------------------------------
    # Save a marker's mhz and traceName preferences to p.

    def SavePrefs(self, p):
        print ("name=", self.name)
        name = re.sub("\+", "p", re.sub("-", "m", self.name))
        for attr in ("mhz", "traceName"):
            setattr(p, "markers_"+name+"_"+attr, getattr(self, attr))


#==============================================================================
# A graph of a set of traces.

class GraphPanel(wx.Panel):
    def __init__(self, parent, frame):
        self.frame = frame
        self.prefs = p = frame.prefs
        self._gridBitmap = None
        self._haveDrawnGrid = False
        self._isReady = False

        # settable parameters
        self.marginPix = 32         # minimum margin around graph (pixels)
        self.rtMarginPix = 180      # additional margin on right (pixels)
        self.botMarginPix = 80      # additional margin on bottom (pixels)
        self.gridHSize = 50         # target grid horizontal spacing (pixels)
        self.gridVSize = 50         # target grid vertical spacing (pixels)
        self.printData = False      # set to print debug data
        self.dotSize = 4            # dot size for low-rez scans (pixels)
        self.isLogF = True          # set for log frequency scale mode
        self.hUnit = "MHz"          # default horizontal scale label
        self.h0 = 1.                # horizontal start (MHz)
        self.h1 = 0.                # horizontal end (MHz)
        self.dh = 1.                # horizontal delta (MHz)
        # list of vertical scales
        self.vScales = [VScale(0, 0, 1, 0, ""), VScale(0, 0, 1, 0, "")]
        self.traces = {}            # traces to graph, by name
        self.cursorStep = 0         # step location of cursor
        self.eraseOldTrace = False  # set to erase previous trace first
        self.markers = {}           # markers to graph, by name
        self.tcWithFocus = None     # TextCtrl box that has input focus
        self.results = None         # results text box, if any
        self.showCursor = False     # enable cursor (small box) drawing
        self.markersActive = False  # enable marker position update
        self.dbDownBy = 3           # dB down-by level to put L, R markers
        self.isAbs = False          # set if dbDownBy is an absolute level
        self.bind = False # EON Jan 12 2014

        wx.Panel.__init__(self, parent, -1)
        self.SetBackgroundColour(p.theme.backColor)
        ##self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)

    #--------------------------------------------------------------------------
    # Enable graph events and update.

    def Enable(self):
            # Start EON Jan 12 2014
            if not self.bind:
                self.bind = True
                self.Bind(wx.EVT_PAINT,        self.OnPaint)
                self.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
                self.Bind(wx.EVT_KEY_DOWN,     self.OnKeyDown)
                self.Bind(wx.EVT_SIZE,         self.OnSizeChanged)
                self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
            # End EON Jan 12 2014
            self._isReady = True
            self.Refresh()

    #--------------------------------------------------------------------------
    # Force the grid and other parts to be redrawn on a resize of the frame.

    def FullRefresh(self):
        if debug:
            print ("FullRefresh")
        LogGUIEvent("FullRefresh hdg=%d" % self._haveDrawnGrid)
        self._haveDrawnGrid = False
        self.Refresh()
        smithDlg = self.frame.smithDlg
        if smithDlg:
            smithDlg.Refresh()

    #--------------------------------------------------------------------------
    # Handle a resize event.

    def OnSizeChanged(self, event):
        self.FullRefresh()
        event.Skip()   # (will continue handling event)

    #--------------------------------------------------------------------------
    # Repaint the waveform frame.
    # Do the actual drawing of the waveforms, including a grid and legend.

    def OnErase(self, event):
        pass

    def OnPaint(self, event):
        LogGUIEvent("OnPaint")
        ##assert wx.Thread_IsMain()

        # get current colors, pens, and brushes
        frame = self.frame
        p = self.prefs
        self.vColors = vColors = p.theme.vColors
        foreColor = p.theme.foreColor
        backColor = p.theme.backColor
        gridColor = p.theme.gridColor
        hColor = p.theme.hColor
        linePen = wx.Pen(foreColor, 1, wx.SOLID)
        backPen = wx.Pen(backColor, 1, wx.SOLID)
        ##gridPen = wx.Pen(foreColor, 1, wx.DOT)
        gridPen = wx.Pen(gridColor, 1, wx.SOLID)
        grid0Pen = wx.Pen(foreColor, 2, wx.SOLID)
        noFillBrush = wx.Brush("BLACK", wx.TRANSPARENT)
        dyText = fontSize + 5
        clientWid, clientHt = self.GetSize()

        # exit if any traces outside of graph: they may have not caught up yet
        h0 = self.h0
        h1 = self.h1
        dh = self.dh
        for tr in self.traces.values():
            margin = 0.000001
            if tr.Fmhz[0] < h0 - margin or tr.Fmhz[-1] > h1 + margin:
                print ("trace %s outside: [%5.6f, %5.6f] in [%5.6f, %5.6f]" % \
                    (tr.name, tr.Fmhz[0], tr.Fmhz[-1], h0, h1))
                return

        # left and right vertical scales, and their corresponding units
        vs0 = self.vScales[0]
        vs1 = self.vScales[1]
        vaUnits = vs0.dataType.units
        vbUnits = vs1.dataType.units

        # determine if axis traces are the prime traces, and which
        # trace belongs to which axis
        trA = trB = None
        axesArePrime = True
        if len(self.traces) == 2:
            # 2 traces: one axis for each
            trA, trB = self.traces.values()
            if trA.iScale != 0:
                # trace A not left axis: swap A and B
                trB, trA = self.traces.values()
                axesArePrime = trA.units == vs1.primeTraceUnits and \
                               trB.units == vs0.primeTraceUnits
            else:
                axesArePrime = trA.units == vs0.primeTraceUnits and \
                               trB.units == vs1.primeTraceUnits
        else:
            # 1 or more than 2 traces: see which axis each trace belongs to
            for tr in self.traces.values():
                if tr.units == vaUnits:
                    trA = tr
                    if trA.units != vs0.primeTraceUnits:
                        axesArePrime = False
                if tr.units == vbUnits:
                    trB = tr
                    if trB.units != vs1.primeTraceUnits:
                        axesArePrime = False

        # if log freq scale determine decade range if possible
        isLogF = p.isLogF
        if isLogF:
            try:
                lf0 = log10(h0)
                lf1 = log10(h1)
            except FloatingPointError:
                isLogF = False

        # draw the grid, axes, and legend if they're new or updated
        if not self._haveDrawnGrid:
            LogGUIEvent("OnPaint: redraw grid")
            # (GraphicsContext doesn't like AutoBufferedPaintDC, so we use:)
            if False:
##            if slowDisplay or self.IsDoubleBuffered():
                dc1 = wx.PaintDC(self)
            else:
                dc1 = wx.BufferedPaintDC(self)
                dc1.Clear()

            ##if clientWid != self.clientWid or clientHt != self.clientHt:
            ##self.clientWid = clientWid
            ##self.clientHt = clientHt
            self.graphWid = graphWid = clientWid - self.marginPix - \
                            self.rtMarginPix
            self.graphHt = graphHt = clientHt  - 2*self.marginPix - 20 - \
                            self.botMarginPix
            ##print ("OnPaint"

            # scale horz axis of graph to fit window
            hWid = h1 - h0
            dc1.SetFont(wx.Font(fontSize, wx.SWISS, wx.NORMAL,
                                p.theme.textWeight))
            wh0, hh0 = dc1.GetTextExtent(str(h0))
            wh1, hh1 = dc1.GetTextExtent(str(h1))
            gridHSize = max(self.gridHSize, 2*max(wh0, wh1)+10)
            if hWid == 0:
                isLogF = False
                dh = 0.     # h distance (in hUnits) between divisions
                hBase = h0  # h position of first div
                hFrac = 0.  # h distance from h0 to first div
                nXDiv = 2   # number of horizontal divisions
                xPixDiv = graphWid/2
                self.dx = dx = graphWid/2     # pixels/hUnit
                ##print ("dh=0"
            else:
                if isLogF:
                    self.dx = dx = graphWid / (lf1 - lf0)   # pixels/hUnit
                else:
                    dh, hBase, hFrac, nXDiv = \
                        StdScale(h0, h1, graphWid, gridHSize)

                    self.dx = dx = graphWid / (h1 - h0)   # pixels/hUnit
                xPixDiv = dx * dh
            self.dh = dh

            # scale vert axis of graph to fit window
            va1 = vs0.top
            va0 = vs0.bot
            vb1 = vs1.top
            vb0 = vs1.bot
            if vaUnits:
                v0, v1 = va0, va1
            else:
                v0, v1 = vb0, vb1

            dv, vBase, vFrac, nYDiv = \
                StdScale(v0, v1, graphHt, self.gridVSize)

            # calculate graph boundaries
            den = max(v1 - v0, 1e-20)
            yPixDiv = graphHt * dv / den
            self.x0 = x0 = self.marginPix + 10
            self.y0 = y0 = self.marginPix + 10
            self.x1 = x1 = x0 + graphWid
            self.y1 = y1 = y0 + graphHt

            self.dy = dy = yPixDiv / dv      # pixels/vUnit
            self.dya = dya = dy
            self.dyb = dyb = dy
            dvb = dv
            vbBase = vBase
            if vaUnits:
                vaBase = vBase
                den = max(va1 - va0, 1e-20)
                dvb = dv * (vb1 - vb0) / den
                self.dyb = dyb = yPixDiv / dvb
                vbBase = vb0 + vFrac

            # create a bitmap to store the grid in
            self.dc = dc = wx.MemoryDC()
            self._gridBitmap = wx.EmptyBitmap(clientWid, clientHt)
            dc.SelectObject(self._gridBitmap)
            dc.SetBackground(wx.Brush(backColor, wx.SOLID))
            dc.SetTextForeground(hColor)
            dc.Clear()
            dc.SetFont(wx.Font(fontSize, wx.SWISS, wx.NORMAL,
                                p.theme.textWeight))

            # ------ GRID ------

            # draw legend
            ntr = len(self.traces)
            y = y0 + 150
            x = x1 + 50
            for name, tr in sorted(self.traces.iteritems(), \
                                key=(lambda (k,v): v.name.upper())):
                if tr.displayed:
                    ##print("p.theme.vColors:", len(p.theme.vColors), "tr.iColor=", tr.iColor)
                    vColor = vColors[tr.iColor]
                    ##dc.SetPen(wx.Pen(vColor, 1, wx.SOLID))
                    dc.SetPen(wx.Pen(vColor, 5, wx.SOLID))
                    dc.DrawLine(x, y, x + 20, y)
                    dc.SetTextForeground(vColor)
                    unit = self.vScales[tr.iScale].dataType.units
                    ##text = "%s (%s)" % (name, unit)
                    text = name
                    (w, h) = dc.GetTextExtent(text)
                    dc.DrawText(text, x + 23, y - 6)
                    y += h + 4

            # draw graph axis labels
            vaColor = None
            if trA:
                vaColor = vColors[trA.iColor]
            vbColor = None
            if trB:
                vbColor = vColors[trB.iColor]
            if vaUnits:
                dc.SetTextForeground(vaColor)
                (w, h) = dc.GetTextExtent(vaUnits)
                dc.DrawText(vaUnits, x0 - w - 2, y0 - 2*h)
            if vbUnits:
                dc.SetTextForeground(vbColor)
                (w, h) = dc.GetTextExtent(vbUnits)
                dc.DrawText(vbUnits, x1 + 2, y0 - 2*h)

            dc.SetTextForeground(hColor)
            hUnit = self.hUnit
            if isLogF:
                hUnit = hUnit[1:]
            else:
                hUnit = hUnit + " (%sHz/div)" % si(dh*MHz)
            (w, h) = dc.GetTextExtent(hUnit)
            dc.DrawText(hUnit, (x1 + x0 - w) / 2, y1 + 20)

            # draw grid vert axis lines
            yDiv0 = y1 - vFrac * dy
            for vDiv in range(0, nYDiv+1):
                y = yDiv0 - vDiv * yPixDiv
                if y < (y0 - 0.01):
                    break
                if vaUnits:
                    va = vaBase + vDiv * dv
                    vaText = si(va, 3)
                    (w, h) = dc.GetTextExtent(vaText)
                    dc.SetTextForeground(vaColor)
                    dc.DrawText(vaText, x0 - w - 3, y - h/2)
                if vbUnits:
                    vb = vbBase + vDiv * dvb
                    vbText = si(vb, 3)
                    (w, h) = dc.GetTextExtent(vbText)
                    dc.SetTextForeground(vbColor)
                    dc.DrawText(vbText, x1 + 3, y - h/2)

                dc.SetPen(gridPen)
                dc.DrawLine(x0, y, x1, y)

            # draw grid h lines
            dc.SetTextForeground(hColor)
            if isLogF:
                ##print ("h0=", h0, "h1=", h1
                hName = si(h0 * MHz)
                (tw, th) = dc.GetTextExtent(hName)
                dc.DrawText(hName, x0 - tw/2, y1 + 6)
                df = 10**floor(lf0)
                f = floor(h0 / df) * df + df
                lf = log10(f)
                hDiv = 0
                lf1 -= 0.001
                textFrac = min(dx/200, 0.85)
                ##print ("lf=", lf, "f=", f, "df=", df
                while lf < lf1:
                    lfFrac = lf - floor(lf+0.001)
                    if abs(lfFrac) < 0.01:
                        df *= 10.
                        hDiv = 0
                    x = x0 + (lf - lf0) * dx
                    if f > 950 or (lfFrac < textFrac and \
                         (hDiv % 2) == 0 and x > x0+30 and x < x1-30):
                        hName = si(f * MHz)
                        (tw, th) = dc.GetTextExtent(hName)
                        dc.DrawText(hName, x - tw/2, y1 + 6)
                    dc.SetPen(gridPen)
                    dc.DrawLine(x, y0, x, y1)
                    hDiv += 1
                    f += df
                    lf = log10(f)
                hName = si(h1 * MHz)
                (tw, th) = dc.GetTextExtent(hName)
                dc.DrawText(hName, x1 - tw/2, y1 + 6)
            else:
                xDiv0 = x0 + hFrac * dx
                for hDiv in range(0, nXDiv+1):
                    x = xDiv0 + hDiv * xPixDiv
                    if x > (x1 + 0.01):
                        break
                    if dh == 0:
                        x = (x1 + x0)/2
                    h = hBase + hDiv * dh
                    if (hDiv % 2) == 0:
                        hName = str(h)
                        if len(hName) > 2 and hName[-2:] == ".0":
                            hName = hName[:-2]
                        (w, h) = dc.GetTextExtent(hName)
                        dc.DrawText(hName, x - w/2, y1 + 6)
                    dc.SetPen(gridPen)
                    dc.DrawLine(x, y0, x, y1)

            # draw border
            dc.SetPen(grid0Pen)
            dc.SetBrush(noFillBrush)
            dc.DrawRectangle(x0, y0, x1-x0, y1-y0)

            # ------ INFO ------

            # draw title
            dc.SetTextForeground(hColor)
            dc.SetFont(wx.Font(fontSize*1.2, wx.SWISS, wx.NORMAL, wx.NORMAL))
            (w, h) = dc.GetTextExtent(self.title)
            dc.DrawText(self.title, (x1 + x0 - w)/2, y0 - 10 - h)

            # draw right info panel
            xinfo = x1 + 50
            yinfo = y0 - 10
            modeName = msa.modeNames[p.mode]
            (w, h) = dc.GetTextExtent(modeName)
            dc.DrawText(modeName, clientWid - 10 - w, 5)
            dc.SetFont(wx.Font(fontSize, wx.SWISS, wx.NORMAL, wx.NORMAL))
            if p.calLevel <= 2 and p.mode > msa.MODE_SATG:
                calLevelName = ("None", "Base", "Band")[msa.calLevel]
                dc.SetTextForeground((red, blue, hColor)[p.calLevel])
                dc.DrawText("Cal=" + calLevelName, xinfo, yinfo + 0*dyText)
            dc.SetTextForeground(hColor)
            ##dc.DrawText("RBW=%sHz" % si(p.rbw * kHz), xinfo, yinfo + 1*dyText)
            ##dc.DrawText("RBW=%sHz" % (p.rbw * kHz), xinfo, yinfo + 1*dyText)
            dc.DrawText("RBW=%.1fkHz" % p.rbw, xinfo, yinfo + 1*dyText)
            dc.DrawText("Wait=%dms" % int(p.wait), xinfo, yinfo + 2*dyText)
            dc.DrawText("Steps=%d" % p.nSteps, xinfo, yinfo + 3*dyText)
            y = 4
            if not p.isLogF:
                df = (p.fStop - p.fStart) / p.nSteps
                dc.DrawText("%sHz/Step" % si(df * MHz), xinfo, yinfo+y*dyText)
                y += 1
            if p.mode >= msa.MODE_VNATran and p.planeExt[0] > 0:
                for i, planeExt in enumerate(p.planeExt):
                    dc.DrawText("Exten%dG=%ss" % (i, si(planeExt * ns)), xinfo,
                            yinfo + y*dyText)
                    y += 1
            if p.mode == msa.MODE_VNARefl:
                fixName = "Bridge"
                if p.isSeriesFix:
                    fixName = "Series"
                elif p.isShuntFix:
                    fixName = "Shunt"
                dc.DrawText("Fixture=%s" % fixName, xinfo, yinfo + y*dyText)
                y += 1
            dc.DrawText("Vers %s" % version, xinfo, yinfo + y*dyText)
            y += 1

            # draw optional results text box
            if self.results:
                lnsep = 4
                border = 10
                dc.SetTextForeground(hColor)
                dc.SetFont(wx.Font(fontSize, wx.SWISS, wx.NORMAL, wx.NORMAL))
                resultList = self.results.split("\n")
                wres = 0
                for result in resultList:
                    wid, ht = dc.GetTextExtent(result)
                    wres = max(wres, wid)
                wres += 2*lnsep
                xres0 = clientWid - border - wres
                yres0 = clientHt - border - lnsep - \
                            (ht+lnsep) * len(resultList)
                hres = clientHt - border - yres0
                dc.SetPen(wx.Pen(foreColor, 2, wx.SOLID))
                dc.SetBrush(noFillBrush)
                dc.DrawRectangle(xres0, yres0, wres, hres)
                for result in resultList:
                    dc.DrawText(result, xres0+lnsep, yres0+lnsep)
                    yres0 += ht + lnsep

            dc.SelectObject(wx.NullBitmap)
            self._haveDrawnGrid = True
            dc = dc1
            ##print ("Graph DoDrawing\n"
            dc.DrawBitmap(self._gridBitmap, 0, 0)

            ##dc.DestroyClippingRegion()

        else:
            # already have drawn grid, just retrieve parameters
            x0 = self.x0; y0 = self.y0
            x1 = self.x1; y1 = self.y1
            h0 = self.h0; h1 = self.h1
            dx = self.dx; dh = self.dh
            dya = self.dya; dyb = self.dyb ;dy = self.dy;
            va0 = self.vScales[0].bot
            vb0 = self.vScales[1].bot

            # (GraphicsContext doesn't like AutoBufferedPaintDC, so we use:)
            if False:
##            if slowDisplay or self.IsDoubleBuffered():
                dc = wx.PaintDC(self)
            else:
                dc = wx.BufferedPaintDC(self)
                dc.Clear()

            dc.DrawBitmap(self._gridBitmap, 0, 0)

        ##LogGUIEvent("OnPaint: have grid")

        ##dc.SetClippingRegion(x0, y0, x1-x0, y1-y0)
        if isLogF:
            h0 = log10(h0)
            h1 = log10(h1)

        # ------ TRACES ------

        # draw each trace in a different color
        for name, tr in sorted(self.traces.iteritems(), \
                     key=(lambda (k,v): -v.iScale)):
            LogGUIEvent("OnPaint: compute trace %s" % name)
            if not tr.displayed:
                continue
            fullLen = len(tr.v)
            isPhase = tr.units == "Deg"
            useFull = not tr.isMain or self.eraseOldTrace
            if useFull:
                nv = fullLen
            else:
                nv = min(self.cursorStep+1, fullLen)
            if nv < 2:
                break
            v = nan_to_num(tr.v[:nv])
            if isLogF:
                Fmhz = tr.LFmhz[:nv]
            else:
                Fmhz = tr.Fmhz[:nv]
            # jMin, jMax are limits of indices of v within the
            # displayed region, plus extra
            trh0 = Fmhz[0]
            trdh = Fmhz[1] - trh0    # hUnits/step
            if trdh == 0:
                jMin = 0
                jMax = nv-1
            else:
                jMin = max(min((int((h0 - trh0) / trdh) - 2), nv-2), 0)
                jMax = max(min((int((h1 - trh0) / trdh) + 2), nv-1), 1)
            jStep = max(int(1 / dx), 1)
            if self.printData:
                print (tr.name, "trh0=", trh0, "trdh=", trdh, "jMin/Max=", \
                        jMin, jMax, jStep, "nv=", nv)

            # h,v: coords of points to plot, in given units
            h = Fmhz[jMin:jMax+1]
            v = v[jMin:jMax+1]
            # x,y: window coords of those points
            if trdh == 0:
                # no span: draw straight line across
                x = array([x0, x1])
                v = v[0:2]
            else:
                ##print ("x0=", x0, "h=", h, "h0=", h0
                x = x0 + (h - h0) * dx
                if useFull:
                    x[-1] = x1
            if tr.iScale == 1:
                y = y1 - (v - vb0) * dyb
            else:
                y = y1 - (v - va0) * dya
            y = clip(y, y0+1, y1-1)
            if self.printData:
                print ("shape h=", h.shape, "shape v=", v.shape)
                print ("h[:5]=", h[:5])
                print ("v[:5]=", v[:5])
                print ("y[:5]=", y[:5])
                print ("x[:5]=", x[:5])
            # save coords for use by marker click searches
            self.xs = x.copy()
            tr.ys = y.copy()

            if True:
##            if not isWin:
                # GraphicsContext: faster and smoother (but broken in Windows?)
                gc = wx.GraphicsContext.Create(dc)
                eraseWidth = 0
                if tr.isMain and self.eraseOldTrace and trdh > 0:
                    # remove main line segs at the cursor to form a moving gap
                    eraseWidth = int(10./(trdh*dx)) + 1
                path = gc.CreatePath()
                path.MoveToPoint(x[0], y[0])
                for i in range(1, len(x)):
                    if tr.isMain and i > self.cursorStep and \
                                i <= self.cursorStep+eraseWidth:
                        path.MoveToPoint(x[i], y[i])
                    else:
                        path.AddLineToPoint(x[i], y[i])
                color = vColors[tr.iColor]
                gc.SetPen(wx.Pen(color, tr.dotSize, wx.SOLID))
                gc.StrokePath(path)

                if self.graphWid/fullLen > 20:
                    # draw larger dots at data points if X low-res
                    dsz = self.dotSize
                    path = gc.CreatePath()
                    for i in range(len(x)):
                        path.MoveToPoint(x[i], y[i])
                        path.AddLineToPoint(x[i], y[i])
                    gc.SetPen(wx.Pen(color, dsz, wx.SOLID))
                    gc.StrokePath(path)

            else:
                ##except NotImplementedError:
                # form an array of pairs of begin-end line coords tween points
                xy = concatenate((x.reshape(-1, 1), y.reshape(-1, 1)), axis=1)
                xpyp = concatenate(([[0,0]], xy[:-1]))
                lines = concatenate((xpyp, xy), axis=1)[1:]
                if tr.isMain and self.eraseOldTrace and trdh > 0:
                    # remove main line segs at the cursor to form a moving gap
                    eraseWidth = int(10./(trdh*dx)) + 1
                    lines = concatenate((lines[:self.cursorStep],
                                         lines[self.cursorStep+eraseWidth:]))
##                if isPhase:
##                    # remove phase line segments that wrap or have feeble mag
##                    linesY = lines[:,1]
##                    linesYP = lines[:,3]
##                    lines = lines[(abs((linesY - linesYP) < (y1 - y0)/2) *
##                                            (linesY < y1) * (linesYP < y1))]
##                    lines = lines.tolist()
                LogGUIEvent("OnPaint: draw trace %s" % name)
                # draw that list of lines
                color = vColors[tr.iColor]
                dc.SetPen(wx.Pen(color, tr.dotSize, wx.SOLID))
                dc.DrawLineList(lines, None)
                if self.graphWid/fullLen > 20:
                    ##dotEdge = [[self.dotSize/2+1, 0]]
                    dotEdge = [[0, 0]]
                    dots = concatenate((xy-dotEdge, xy+dotEdge),
                                        axis=1).tolist()
                    dc.SetPen(wx.Pen(color, self.dotSize, wx.SOLID))
                    dc.DrawLineList(dots, None)


        # ------ MARKERS ------

        markers = self.markers
        dc.SetTextForeground(hColor)
        dc.SetFont(wx.Font(fontSize, wx.SWISS, wx.NORMAL, wx.NORMAL))
        xminfo = x0 - 20
        yminfo = y1 + 40
        needHeader = True
        dc.SetBrush(wx.Brush(backColor, wx.SOLID))

        for name, m in sorted(markers.iteritems(), key=(lambda (k,v): v.name)):
            tr = self.traces.get(m.traceName)
            if tr:
                if needHeader:
                    dc.DrawText("Mark", xminfo, yminfo)
                    dc.DrawText(" Freq (MHz)", xminfo+55, yminfo)
                    if trA:
                        dc.DrawText(trA.name, xminfo+130, yminfo)
                    if trB:
                        dc.DrawText(trB.name, xminfo+190, yminfo)
                    yminfo += dyText
                    needHeader = False

                if p.markerMode == Marker.MODE_PbyLR:
                    if self.markersActive and m.name[0] == "P":
                        # markers P+,P- bounded by L,R
                        isPos = m.name[1] == "+"
                        mLeft = markers.get("L")
                        mRight = markers.get("R")
                        if mLeft and mRight:
                            jL, trh0, trdh = tr.Index(mLeft.mhz, isLogF, True)
                            jR, trh0, trdh = tr.Index(mRight.mhz, isLogF, True)
                            ##print m.name, isPos, trdh, h0, jL, jR
                            m.FindPeak(tr.v[jL:jR], trdh, isLogF, isPos,
                                mLeft.mhz)
                elif p.markerMode > Marker.MODE_PbyLR:
                    if self.markersActive and m.name in ("L", "R"):
                        # markers L,R bounded by P+ or P-
                        isPos = (p.markerMode == Marker.MODE_LRbyPp)
                        mPeak = markers.get(("P-", "P+")[isPos])
                        if mPeak:
                            signP = (-1, 1)[isPos]
                            if self.isAbs:
                                # dbDownBy taken as an absolute level
                                mag3dB = self.dbDownBy
                            else:
                                # normally dbDownBy==3 for -3dB from the peak
                                # or +3dB up from the notch
                                mag3dB = mPeak.dbm - self.dbDownBy * signP
                            jP = tr.Index(mPeak.mhz, isLogF)
                            ##print ("Marker", m.name, "finding", mPeak.name, \
                            ##    "mag3dB=", mag3dB, "jP=", jP
                            m.FindValue(tr, jP, isLogF, signP, m.name == "R",
                                mag3dB, show=0)

                if self.markersActive:
                    m.SetFromTrace(tr, isLogF)

                # draw marker's freq, mag, phase values with decimals aligned
                name = "%4s" % m.name
                ##if trA and tr.name != trA.name:
                ##    name = "%s-%s" % (m.name, tr.name)
                dc.DrawText(name, xminfo, yminfo)
                text = "%11.6f" % m.mhz
                (tw, th) = dc.GetTextExtent(text[:-6])
                dc.DrawText(text, xminfo+70-tw, yminfo)

                # draw axis trace values, or marker's mag & deg if axis
                # traces are the prime traces
                a = b = None
                if axesArePrime:
                    a = "%8.3f" % m.dbm
                    if m.deg > -190:
                        b = "%7.2f" % m.deg
                else:
                    if trA:
                        flags = 0
                        if trA.units in ("dB", "Deg"):
                            flags += SI_NO
                        a = si(m.TraceValue(trA, isLogF), flags=flags)
                    if trB:
                        flags = 0
                        if trB.units in ("dB", "Deg"):
                            flags += SI_NO
                        b = si(m.TraceValue(trB, isLogF), flags=flags)

                if a:
                    places = min(a[::-1].find("."), 3)
                    (tw, th) = dc.GetTextExtent(a[:-places])
                    dc.DrawText(a, xminfo+150-tw, yminfo)

                if b:
                    places = min(b[::-1].find("."), 3)
                    (tw, th) = dc.GetTextExtent(b[:-places])
                    dc.DrawText(b, xminfo+210-tw, yminfo)

                # draw triangle at marker position
                if m.name != "X":
                    if h1 == h0:
                        x = -1
                        if m.mhz == h0:
                            # a zero span: put mark in center
                            x = (x1 + x0) / 2
                    else:
                        if isLogF:
                            x = x0 + (log10(max(m.mhz, 1e-6)) - lf0) * dx
                            ##print ("marker", m.name, "mhz=", m.mhz, \
                            ##"log(mhz)=", log10(m.mhz), "lf0=", lf0, "x=", x
                        else:
                            x = x0 + (m.mhz - h0) * dx
                    if x >= x0 and x <= x1:
                        y = max(min(y1 - (m.dbm - va0) * dy, y1), y0)
                        q = 6
                        isPos = m.name != "P-"
                        ydir = 2*isPos - 1
                        yq =  ydir * q
                        dc.SetPen(linePen)
                        dc.DrawLine(x, y, x-q, y-yq)
                        dc.DrawLine(x-q, y-yq, x+q, y-yq)
                        dc.DrawLine(x+q, y-yq, x, y)
                        (tw, th) = dc.GetTextExtent(m.name)
                        tx = x-tw/2
                        ty = y-yq - (ydir+1)*(th+2)/2 + 1
                        dc.SetPen(backPen)
                        dc.DrawRectangle(tx, ty, tw, th)
                        dc.DrawText(m.name, tx, ty)

                # move to next info line
                yminfo += dyText
                if yminfo > clientHt - 20:
                    xminfo += 280
                    yminfo = y1 + 40
                    needHeader = True
            else:
                # marker missing its trace: remove it too
                markers.pop(name)

        # draw cursor, if present
        if self.showCursor:
            dc.SetPen(linePen)
            dc.SetBrush(noFillBrush)
            dc.DrawRectangle(self.cursorX-2, self.cursorY-2, 5, 5)

        LogGUIEvent("OnPaint: done")

    #--------------------------------------------------------------------------
    # Mouse event: holding mouse down in graph area puts a cursor on nearest
    # trace. Or a double-click adds the current marker.

    def OnMouse(self, event):
        frame = self.frame
        self.showCursor = False
        x, y = event.GetPosition()
        ##print ("Mouse", x, y

        LogGUIEvent("OnMouse")
        if event.LeftDClick():
            if y > self.y0 and y < self.y1:
                ymid = (self.y1 + self.y0) / 2
                if x < self.x0:
                    # left vert axis double-click
                    self.vScales[0].Set(frame, (10, ymid - 50))
                elif x < self.x1:
                    # graph body double-click
                    self.SetMarker(x, y)
                elif x < self.x1 + 40:
                    # right vert axis double-click
                    self.vScales[1].Set(frame, (self.x1+10, ymid - 50))
                else:
                    # right legend area
                    lgPos = wx.Point(self.x1+40, self.y0+100)
                    lgPos = self.ClientToScreen(lgPos)
                    LegendPopup(self, lgPos)

            elif x > self.x0 and x < self.x1:
                if y > self.y1 and y < self.y1 + 30:
                    # horiz axis double-click
                    frame.SetSweep()

        elif event.LeftDown() or event.Dragging():
            if x > self.x0 and x < self.x1 and y > self.y0 and y < self.y1:
                # in graph body:
                self.SetFocus()
                LogGUIEvent("OnMouse: SetFocus on graph")
                tr, mhz, y = self.FindNearestTrace(x, y)
                if tr:
                    # found nearest trace: will draw a small rectangle on it
                    self.showCursor = True
                    self.cursorX, self.cursorY = x, y
                    # and list a temporary 'X' marker there
                    mx = self.markers.get("X")
                    if mx:
                        mx.traceName = tr.name
                        mx.mhz = mhz
                    else:
                        self.markers["X"] = mx = Marker("X", tr.name, mhz)
                    mx.SetFromTrace(tr, self.isLogF)
                    self.cursorInfo = tr, mhz
                    self.markersActive = True
                    LogGUIEvent("OnMouse: cursor")
                    self.FullRefresh()

        if not self.showCursor and self.markers.has_key("X"):
            self.markers.pop("X")
            self.markersActive = True
            self.FullRefresh()
        LogGUIEvent("OnMouse: done")

    #--------------------------------------------------------------------------
    # Key pressed: if mouse is also down, add a marker at the cursor location.

    def OnKeyDown(self, event):
        ##print ("OnKeyDown"
        keycode = event.GetKeyCode()
        LogGUIEvent("OnKeyDown 0x%x cursor=%d" % (keycode, self.showCursor))
        if keycode >= 32 and keycode < 96:
            frame = self.frame
            p = self.prefs
            if self.showCursor:
                name = chr(keycode).upper()
                # when setting a marker currently auto-positioned, change mode
                if name in "+=":
                    name = "P+"
                    if p.markerMode == Marker.MODE_PbyLR:
                        frame.SetMarkers_Indep()
                elif name in "_-":
                    name = "P-"
                    if p.markerMode == Marker.MODE_PbyLR:
                        frame.SetMarkers_Indep()
                elif name in "LR":
                    if p.markerMode in (Marker.MODE_LRbyPp, Marker.MODE_LRbyPm):
                        frame.SetMarkers_Indep()
                elif not (name in "123456789"):
                    event.Skip()
                    return
                frame = self.frame
                tr, mhz = self.cursorInfo
                frame.markerCB.SetValue(name)
                m = Marker(name, tr.name, mhz)
                self.markers[name] = m
                m.SetFromTrace(tr, self.isLogF)
                frame.mhzT.ChangeValue(str(mhz))
                frame.markMHz = mhz
                self.markersActive = True
                self.FullRefresh()

    #--------------------------------------------------------------------------
    # Find the closest trace to given mouse coordintates.
    # Returns (trace, mhz, y), or 3 Nones if not found.

    def FindNearestTrace(self, x, y):
        traces = self.traces
        if len(traces) > 0:
            i = self.xs.searchsorted(x)
            if i >= 0 and i < len(self.xs):
                ysatx = [(abs(tr.ys[i] - y), name, tr) for name, tr in \
                         traces.items() if tr.ys != None]
                if len(ysatx) > 0:
                    ysatx.sort()
                    # found closest trace to click location
                    dist, traceName, tr = ysatx[0]
                    if dist < 200:
                        # interpolate between points to get freq at x
                        xi0, xi1 = self.xs[i-1:i+1]
                        hi0, hi1 = tr.Fmhz[i-1:i+1]
                        m = (x - xi0) / (xi1 - xi0)
                        mhz = round(hi0 + (hi1 - hi0)*m, 6)
                        y = 0
                        if tr.ys != None:
                            yi0, yi1 = tr.ys[i-1:i+1]
                            y = int(yi0 + (yi1 - yi0)*m)
                        return tr, mhz, y
        return None, None, None

    #--------------------------------------------------------------------------
    # Find the closest trace to given mouse coords and set a marker on it.

    def SetMarker(self, x, y):
        #traces = self.traces # JGH 2/10/14
        frame = self.frame
        tr, mhz, y = self.FindNearestTrace(x, y)
        if tr:
            # found closest trace to click location
            markName = frame.markerCB.GetValue()
            if markName == "None":
                markName = "L"
            frame.markerCB.SetValue(markName)
            m = Marker(markName, tr.name, mhz)
            self.markers[markName] = m
            m.SetFromTrace(tr, self.isLogF)
            frame.mhzT.ChangeValue(str(mhz))
            frame.markMHz = mhz
            self.FullRefresh()

    #--------------------------------------------------------------------------
    # Write graph data to a text file.

    def WriteGraph(self, fileName, p):
        traces = self.traces
        f = open(fileName, "w")
        f.write("!MSA, msapy %s\n" % version)
        f.write("!Date: %s\n" % time.ctime())
        f.write("!Graph Data\n")
        f.write("!Freq(MHz)  %s\n" % string.join(["%16s" % k \
                    for k in traces.keys()]))

        Fmhz = traces.values()[0].Fmhz
        for i in range(len(Fmhz)):
            f.write("%11.6f %s\n" % \
                (Fmhz[i],
                 string.join(["%16.8f" % tr.v[i] \
                                for tr in traces.values()])))
        f.close()


#==============================================================================
# A Line legend pop-up window for enabling graph lines.

class LegendPopup(wx.Dialog):
    def __init__(self, specP, pos):
        self.specP = specP
        frame = specP.frame
        self.prefs = frame.prefs
        wx.Dialog.__init__(self, specP, -1, "Lines", pos, (1, 1))
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizerGB = wx.GridBagSizer(2, 2)
        c = wx.ALIGN_CENTER
        cl = wx.ALIGN_LEFT
        self.traces = []

        # add an enabling checkbox for each possible trace line
        for name, tr in specP.traces.iteritems():
            print ("name=", name, "tr.name=", tr.name, "tr.i=", tr.iScale)
        for i, (name, tr) in enumerate(sorted(specP.traces.iteritems(), \
                        key=(lambda (k,v): v.name.upper()))): # JGH mod4P3
            self.traces.append(tr)
            chk = wx.CheckBox(self, -1, name)
            chk.SetValue(tr.displayed)
            self.Bind(wx.EVT_CHECKBOX, self.OnCheckBox, chk)
            sizerGB.Add(chk, (i, 0), flag=cl|wx.ALL, border=2)
            # trace color entry
            color = specP.vColors[tr.iColor]
            cs = csel.ColourSelect(self, -1, "", color, size=(35, -1))
            cs.trace = tr
            cs.Bind(csel.EVT_COLOURSELECT, self.OnSelectColor)
            sizerGB.Add(cs, (i, 1), flag=c)

        sizer.Add(sizerGB, 0, wx.ALL, 10)
        sizer.Add((1, 20), 0)
        sizer.Layout()
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Show()

    #--------------------------------------------------------------------------
    # Event handlers.

    def OnCheckBox(self, event):
        specP = self.specP
        chk = event.GetEventObject()
        name = chk.GetLabel()
        trace = specP.traces.get(name)
        ##print ("Check: name=", name, trace
        if trace:
            trace.displayed = chk.GetValue()
            self.specP.FullRefresh()

    def OnSelectColor(self, event):
        print ("OnSelectColor")
        specP = self.specP
        cs = event.GetEventObject()
        tr = cs.trace
        specP.prefs.theme.vColors[tr.iColor] = wx.Colour(*event.GetValue())
        specP.FullRefresh()


#==============================================================================
# A window showing important variables.

class VarDialog(wx.Dialog):
    def __init__(self, frame):
        self.frame = frame
        self.prefs = p = frame.prefs
        framePos = frame.GetPosition()
        frameSize = frame.GetSize()
        pos = p.get("varWinPos", (framePos.x + frameSize.x - 200, framePos.y))
        textList = msa.GetVarsTextList()
        size = (200, 40 + (fontSize+6)*(len(textList)))
        wx.Dialog.__init__(self, frame, -1, "Variables", pos,
                            size, wx.DEFAULT_DIALOG_STYLE)
        self.Bind(wx.EVT_PAINT,     self.OnPaint)
        self.Bind(wx.EVT_MOVE,     self.OnMove)
        self.SetBackgroundColour(p.theme.backColor)
        self.Show()

    def OnPaint(self, event):
        dc = wx.PaintDC(self)
        p = self.prefs
        textList = msa.GetVarsTextList()
        coords = [(10, 5+(fontSize+6)*i) for i in range(len(textList))]
        dc.SetTextForeground(p.theme.foreColor)
        dc.SetFont(wx.Font(fontSize-1, wx.SWISS, wx.NORMAL, wx.NORMAL))
        dc.DrawTextList(textList, coords)

    def OnMove(self, event):
        self.prefs.varWinPos = self.GetPosition().Get()

    def OnClose(self, event):
        self.Destroy()
        self.frame.varDlg = None


#==============================================================================
# Base class for main dialog boxes.

class MainDialog(wx.Dialog):

    # Add a test-fixture settings box to the dialog. Returns its sizer.

    def FixtureBox(self, isSeriesFix=True, isShuntFix=False):
        p = self.frame.prefs
        c = wx.ALIGN_CENTER
        chb = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM
        self.R0 = p.get("R0", 50.)
        titleBox = wx.StaticBox(self, -1, "Test Fixture")
        sizerHF = wx.StaticBoxSizer(titleBox, wx.HORIZONTAL)
        sizerVF1 = wx.BoxSizer(wx.VERTICAL)
        rb = wx.RadioButton(self, -1, "Series", style= wx.RB_GROUP)
        self.seriesRB = rb
        rb.SetValue(isSeriesFix)
        sizerVF1.Add(rb, 0, wx.ALL, 2)
        self.shuntRB = rb = wx.RadioButton(self, -1, "Shunt")
        rb.SetValue(isShuntFix)
        sizerVF1.Add(rb, 0, wx.ALL, 2)
        if msa.mode == MSA.MODE_VNARefl:
            self.bridgeRB = rb = wx.RadioButton(self, -1, "Bridge")
            rb.SetValue(not (isSeriesFix or isShuntFix))
            sizerVF1.Add(rb, 0, wx.ALL, 2)
        sizerHF.Add(sizerVF1, 0, c|wx.RIGHT, 10)
        sizerVG2 = wx.GridBagSizer()
        sizerVG2.Add(wx.StaticText(self, -1, "R0"), (0, 0), flag=chb)
        self.R0Box = tc = wx.TextCtrl(self, -1, gstr(self.R0), size=(40, -1))
        sizerVG2.Add(tc, (1, 0), flag=c)
        sizerVG2.Add(wx.StaticText(self, -1, Ohms), (1, 1),
                flag=c|wx.LEFT, border=4)
        sizerHF.Add(sizerVG2, 0, c)
        return sizerHF


#==============================================================================
# A Help modal dialog for  dialog. # JGH

class ConfigHelpDialog(wx.Dialog):
    def __init__(self, frame):
        p = frame.prefs
        pos = p.get("configHelpWinPos", wx.DefaultPosition)
        title = "Configuration Manager Help"
        wx.Dialog.__init__(self, frame, -1, title, pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        sizerV = wx.BoxSizer(wx.VERTICAL)
        self.SetBackgroundColour("WHITE")
        text = "Enter configuration data for your machine. "\
        "With a standard SLIM build, the items in WHITE likely need no "\
        "change. CYAN items and Auto Switch checkboxes generally must be "\
        "customized."
        self.st = st = wx.StaticText(self, -1, text, pos=(10, 10))

        st.Wrap(600)
        sizerV.Add(st, 0, wx.ALL, 5)

        # OK button
        butSizer = wx.BoxSizer(wx.HORIZONTAL)
        butSizer.Add((0, 0), 0, wx.EXPAND)
        btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        butSizer.Add(btn, 0, wx.ALL, 5)
        sizerV.Add(butSizer, 0, wx.ALIGN_RIGHT)

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if pos == wx.DefaultPosition:
            self.Center()

#==============================================================================
# The MSA/VNA Configuration Manager dialog box (also modal) # JGH

class ConfigDialog(wx.Dialog): # JGH Heavily modified 1/20/14
    def __init__(self, frame):
        self.frame = frame
        self.prefs = p = frame.prefs
        pos = p.get("configWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, "MSA/VNA Configuration Manager",
                             pos, wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)

        c = wx.ALIGN_CENTER
        cv = wx.ALIGN_CENTER_VERTICAL
        chbt = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM|wx.TOP
        bigFont = wx.Font(16, wx.SWISS, wx.NORMAL, wx.NORMAL)
        sizerV0 = wx.BoxSizer(wx.VERTICAL)
        text = wx.StaticText(self, -1, "ENTER CONFIGURATION DATA FOR YOUR MSA")
        text.SetFont(bigFont)
        sizerV0.Add(text, 0, flag=c)
        sizerH0 = wx.BoxSizer(wx.HORIZONTAL)

        # JGH added PLL hardware types, polarity, reference and mode
        pllTypeChoices = ("2325", "2326", "2350", "2353",\
                      "4112", "4113", "4118")
        pllPolInvChoices = (" 0 : No", " 1 : Yes")
        #pllPhafreqChoices = ("0.974","4.000")    # JGH 2/10/14
##        pllModeChoices = ("0: Integ", "1: Fract") # JGH 2/7/14
        # JGH addition end

        # PLL and DDS config
        # JGH: DEFINE FIRST COLUMN SIZER
        sizerG1 = wx.GridBagSizer(hgap=10, vgap=2)
        st = wx.StaticText(self, -1,  "-------------Type--------------" )
        sizerG1.Add(st, (1, 0), (1, 3), chbt, 5)
        st = wx.StaticText(self, -1, "---Is this a passive PLL Loop?---")
        sizerG1.Add(st, (3, 0), (1, 3), chbt, 5)
        st = wx.StaticText(self, -1, "------Phase frequency (MHz)------")
        sizerG1.Add(st, (5, 0), (1, 3), chbt, 5)
##        st = wx.StaticText(self, -1, "---Mode  (Integer/Fractional)---" ) # JGH 2/7/14 Fractional mode not used
##        sizerG1.Add(st, (7, 0), (1, 3), chbt, 5)
        st = wx.StaticText(self, -1, "--------Center Freq (MHz)--------")
        sizerG1.Add(st, (10, 0), (1, 3), chbt, 5)
        st = wx.StaticText(self, -1, "---------Bandwidth (MHz)---------")
        sizerG1.Add(st, (12, 0), (1, 3), chbt, 5)

        # JGH Following conditional moved here for aesthetic reasons
        for i in range(3):
            text = wx.StaticText(self, -1, "PLL%d" % (i+1))
            text.SetFont(bigFont)
            sizerG1.Add(text, (0, i), flag=c)

            if i != 1:
                text = wx.StaticText(self, -1, "DDS%d" % (i+1))
                text.SetFont(bigFont)
                sizerG1.Add(text, (9, i), flag=c)

        csz = (95, -1) # JGH
        tsz = (95, -1) # JGH

        #JGH added . Modified 1/14/14
        s = p.get("PLL1type", "4112")
        cmPLL1 = wx.ComboBox(self, -1, s, (0, 0), csz, choices=pllTypeChoices,
                             style=wx.CB_READONLY)
        sizerG1.Add(cmPLL1, (2, 0), flag=c)
        self.cmPLL1 = cmPLL1

        s = p.get("PLL2type", "4112")
        cmPLL2 = wx.ComboBox(self, -1, s, (0, 0), csz, choices=pllTypeChoices,
                             style=wx.CB_READONLY)
        sizerG1.Add(cmPLL2, (2, 1), flag=c)
        self.cmPLL2 = cmPLL2

        s = p.get("PLL3type", "4112")
        cmPLL3 = wx.ComboBox(self, -1, s, (0, 0), csz, choices=pllTypeChoices,
                             style=wx.CB_READONLY)
        sizerG1.Add(cmPLL3, (2, 2), flag=c)
        self.cmPLL3 =cmPLL3

        s = p.get("PLL1phasepol", " 0 : No")
        if s == 0:
            s = " 0 : No"
        if s == 1:
            s = " 1 : Yes"
        cmPOL1 = wx.ComboBox(self, -1, s, (0, 0), csz,
                             choices=pllPolInvChoices, style=wx.CB_READONLY)
        sizerG1.Add(cmPOL1, (4, 0), flag=c)
        self.cmPOL1 = cmPOL1

        s = p.get("PLL2phasepol", " 1 : Yes")
        if s == 0:
            s = " 0 : No"
        if s == 1:
            s = " 1 : Yes"
        cmPOL2 = wx.ComboBox(self, -1, s, (0, 0), csz,
                             choices=pllPolInvChoices, style=wx.CB_READONLY)
        sizerG1.Add(cmPOL2, (4, 1), flag=c)
        self.cmPOL2 = cmPOL2

        s = p.get("PLL3phasepol", " 0 : No")
        if s == 0:
            s = " 0 : No"
        if s == 1:
            s = " 1 : Yes"
        cmPOL3 = wx.ComboBox(self, -1, s, (0, 0), csz,
                             choices=pllPolInvChoices, style=wx.CB_READONLY)
        sizerG1.Add(cmPOL3, (4, 2), flag=c)
        self.cmPOL3 = cmPOL3

        s = p.get("PLL1phasefreq", 0.974)
        tcPhF1 = wx.TextCtrl(self, -1, gstr(s), size=tsz)
        tcPhF1.Enable(False)
        sizerG1.Add(tcPhF1, (6, 0), flag=c)
        self.tcPhF1 = tcPhF1

        s = p.get("PLL2phasefreq", 4.)
        tcPhF2 = wx.TextCtrl(self, -1, gstr(s), size=tsz)
        tcPhF2.Enable(False)
        sizerG1.Add(tcPhF2, (6, 1), flag=c)
        self.tcPhF2 = tcPhF2

        s = p.get("PLL3phasefreq", 0.974)
        tcPhF3 = wx.TextCtrl(self, -1, gstr(s), size=tsz)
        tcPhF3.Enable(False)
        sizerG1.Add(tcPhF3, (6, 2), flag=c)
        self.tcPhF3 = tcPhF3

##        s = p.get("PLL1mode", 0)  # JGH 2/7/14 Fractional mode not used
##        if s == 0:
##            s = "0: Integ"
##        if s== 1:
##            s = "1: Fract"
##        cmMOD1 = wx.ComboBox(self, -1, s, (0, 0), csz,
##                             choices=pllModeChoices, style=wx.CB_READONLY)
##        sizerG1.Add(cmMOD1, (8, 0), flag=c)
##        self.cmMOD1 = cmMOD1
##
##        s = p.get("PLL3mode", 0)
##        if s == 0:
##            s = "0: Integ"
##        if s== 1:
##            s = "1: Fract"
##        cmMOD3 = wx.ComboBox(self, -1, s, (0, 0), csz,
##                             choices=pllModeChoices, style=wx.CB_READONLY)
##        sizerG1.Add(cmMOD3, (8, 2), flag=c)
##        self.cmMOD3 = cmMOD3

        cvl = wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_LEFT
        cvr = wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT
        # JGH addition end

        tc = wx.TextCtrl(self, -1, gstr(LO1.appxdds), size=tsz) # JGH 2/2/14
##        tc.SetBackgroundColour(wx.CYAN) #JGH 2/3/14
        self.dds1CentFreqBox = tc
        tc.Enable(False)
        sizerG1.Add(tc, (11, 0), flag=c)

        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        tc = wx.TextCtrl(self, -1, gstr(LO3.appxdds), size=tsz) # JGH 2/2/14
##        tc.SetBackgroundColour(wx.CYAN) #JGH 2/3/14
        self.dds3CentFreqBox = tc
        tc.Enable(False)
        sizerG1.Add(tc, (11, 2), flag=c)
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        tc = wx.TextCtrl(self, -1, gstr(LO1.ddsfilbw), size=tsz) # JGH 2/2/14
##        tc.SetBackgroundColour(wx.CYAN) #JGH 2/3/14
        self.dds1BWBox = tc
        tc.Enable(False)
        sizerG1.Add(tc, (13, 0), flag=c)
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        tc = wx.TextCtrl(self, -1, gstr(LO3.ddsfilbw), size=tsz) # JGH 2/2/14
##        tc.SetBackgroundColour(wx.CYAN) #JGH 2/3/14
        self.dds3BWBox = tc
        tc.Enable(False)
        sizerG1.Add(tc, (13, 2), flag=c)
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)

        st = wx.StaticText(self, -1, "DDS1 Parser")
        sizerG1.Add(st, (14, 0), (1, 1), chbt, 10)
        s = "1:serial"
        cmPAR1 = wx.ComboBox(self, -1, s, (0, 0), csz, [s])
        cmPAR1.Enable(False) # JGH changed to False
        sizerG1.Add(cmPAR1, (15, 0), flag=c)

        st = wx.StaticText(self, -1, "LO2 (MHz)")
        sizerG1.Add(st, (14, 1), (1, 1), chbt, 10)
        tc = wx.TextCtrl(self, -1, gstr(msa.appxLO2), size=tsz) # JGH 2/2/14
        tc.Enable(False) # JGH changed to False
        sizerG1.Add(tc, (15, 1), flag=c)

        st = wx.StaticText(self, -1, "Mast Clk (MHz)")
        sizerG1.Add(st, (14, 2), (1, 1), chbt, 10)
        mastClkBox = wx.TextCtrl(self, -1, gstr(msa.masterclock), size=tsz) # JGH 2/2/14
##        tc.SetBackgroundColour(wx.CYAN)
        self.mastClkBox = mastClkBox
        mastClkBox.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        self.mastClkBox = mastClkBox
        sizerG1.Add(mastClkBox, (15, 2), flag=c)

        # Phase config JGH This section of code moved here
        st = wx.StaticText(self, -1,  "Max PDM out" )
        sizerG1.Add(st, (16, 0), (1, 1), chbt, 10)
        tc = wx.TextCtrl(self, -1, gstr(2**16-1), size=tsz) # JGH 2/2/14
        tc.Enable(False) # JGH changed to False
        sizerG1.Add(tc, (17, 0), flag=c)

        st = wx.StaticText(self, -1,  "Inv Deg" )
        sizerG1.Add(st, (16, 2), (1, 1), chbt, 10)
        InvDegBox = wx.TextCtrl(self, -1, gstr(p.invDeg), size=tsz) # JGH 2/2/14
        InvDegBox.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        self.InvDegBox = InvDegBox
##        tc.SetBackgroundColour(wx.CYAN)

        sizerG1.Add(InvDegBox, (17, 2), flag=c)

        lk1 = wx.CheckBox(self, label='HW Lock')
        lk1.Bind(wx.EVT_CHECKBOX, self.LockHW)
        sizerG1.Add(lk1, (8, 1), flag=c)
        lk1.SetValue(True)
        if lk1.GetValue() == True:
            self.cmPLL1.Enable(False); self.cmPLL2.Enable(False); self.cmPLL3.Enable(False)
            self.cmPOL1.Enable(False); self.cmPOL2.Enable(False); self.cmPOL3.Enable(False)
            self.tcPhF1.Enable(False); self.tcPhF2.Enable(False); self.tcPhF3.Enable(False)
##            self.cmMOD1.Enable(False); self.cmMOD3.Enable(False)
##            tc.Enable(False)
            self.mastClkBox.Enable(False); self.InvDegBox.Enable(False)
        else:
            self.cmPLL1.Enable(True); self.cmPLL2.Enable(True); self.cmPLL3.Enable(True)
            self.cmPOL1.Enable(True); self.cmPOL2.Enable(True); self.cmPOL3.Enable(True)
            self.tcPhF1.Enable(True); self.tcPhF2.Enable(True); self.tcPhF3.Enable(True)
##            self.cmMOD1.Enable(True); self.cmMOD3.Enable(True)
##            tc.Enable(True)
            self.mastClkBox.Enable(True); self.InvDegBo.Enable(True)

        sizerH0.Add(sizerG1, 0, wx.ALL, 10)

        sizerV2 = wx.BoxSizer(wx.VERTICAL) # DEFINE SECOND COLUMN SIZER
#       JGH: all of the following code is new on 1/20/14
######## USING A RBW GRID TABLE FOR THE HECK OF IT (looks nice too)

        # Final RBW Filter config
        self.rbwFiltersTitle = \
                wx.StaticBox(self, -1, "Final RBW Filters" ) #JGH 12/25/13
        sizerV2A = wx.StaticBoxSizer(self.rbwFiltersTitle, wx.VERTICAL)

        colLabels = ["Freq(MHz)", "BW(kHz)"]
        self.gridRBW = gr = wx.grid.Grid(self)
        gr.CreateGrid(4,2)
        for col in range(2):
            gr.SetColLabelValue(col, colLabels[col])
        gr.SetRowLabelSize(35)
        for i, (freq, bw) in enumerate(msa.RBWFilters):
            gr.SetCellValue(i, 0, "%2.6f" % freq) # Jgh 1/28/14
            gr.SetCellValue(i, 1, "%3.1f" % bw)
        gr.SetDefaultCellAlignment(wx.ALIGN_RIGHT, wx.ALIGN_CENTRE)
        sizerV2A.Add(gr, 0, wx.ALIGN_CENTER) # JGH 1/28/14
##      The next two lines might be needed later
##        gr.Bind(wx.grid.EVT_GRID_SELECT_CELL, self.OnRBWCellSel)
##        gr.Bind(wx.grid.EVT_GRID_LABEL_LEFT_CLICK, self.OnRBWLabelSel)

        lk2 = wx.CheckBox(self, label='RBW Lock')
        sizerV2A.Add(lk2, 0, flag=c)
        sizerV2.Add(sizerV2A, 0, wx.ALL|wx.EXPAND, 5)
        lk2.Bind(wx.EVT_CHECKBOX, self.LockRBWs)
        lk2.SetValue(True)
        if lk2.GetValue() == True:
            gr.EnableEditing(0)
        else:
            gr.EnableEditing(1)

        # Video Filters config

        self.vidFiltBoxTitle = \
            wx.StaticBox(self, -1, "Video Filters (%sF)" % mu)
        sizerV2B = wx.StaticBoxSizer(self.vidFiltBoxTitle, wx.VERTICAL)
##        st = wx.StaticText(self, -1, "(Use 0 for non-existent filter)")
##        sizerV2B.Add(st, 0, flag=cv)
        colLabels = ["Mag", "Phase"]
        rowLabels = msa.videoFilterNames
        uFMagDefaults = [0.001, 0.2, 10.0, 100] # JGH Mag defaults
        uFPhaDefaults = [0.001, 0.2, 2.2, 10] # JGH Phase defaults
        self.gridVF = gv = wx.grid.Grid(self)
        gv.CreateGrid(4,2)
        for i in range(4):
            gv.SetCellValue(i, 0, "%6.3f" % uFMagDefaults[i])
            gv.SetCellValue(i, 1, "%4.3f" % uFPhaDefaults[i])
        gv.SetRowLabelSize(72)
        gv.SetDefaultColSize(64)
        for col in range(2):
            gv.SetColLabelValue(col, colLabels[col])
        for row in range(4):
            gv.SetRowLabelValue(row, rowLabels[row])
        gv.SetDefaultCellAlignment(wx.ALIGN_RIGHT, wx.ALIGN_CENTRE)
        sizerV2B.Add(gv, 1, flag=cv)

        lk3 = wx.CheckBox(self, label='VF Lock')
        sizerV2B.Add(lk3, 0, flag=c)
        sizerV2.Add(sizerV2B, 0, wx.ALL|wx.EXPAND, 4)
        lk3.Bind(wx.EVT_CHECKBOX, self.LockVFs)
        lk3.SetValue(True)
        if lk3.GetValue() == True:
            gv.EnableEditing(0)
        else:
            gv.EnableEditing(1)

        # TOPOLOGY

        self.topologyBoxTitle = wx.StaticBox(self, -1, "Topology")
        sizerV2C = wx.StaticBoxSizer(self.topologyBoxTitle, wx.VERTICAL)

        sizerG2B = wx.GridBagSizer(hgap=4, vgap=2)
        cwsz = (120, -1)
        sizerG2B.Add(wx.StaticText(self, -1,  "ADC type" ), (0, 0), flag=cvl)
        s = "Serial 16bit"
        cm = wx.ComboBox(self, -1, s, (0, 0), cwsz, [s])
        cm.Enable(True) # JGH changed to True from false
        sizerG2B.Add(cm, (0, 1), flag=cv)

        st = wx.StaticText(self, -1,  "Track Gen" )
        sizerG2B.Add(st, (1, 0), flag=cvl)
        s = "DDS3/PLL3"
        cm = wx.ComboBox(self, -1, s, (0, 0), cwsz, [s])
        cm.Enable(True) # JGH changed to True from false
        sizerG2B.Add(cm, (1, 1), flag=cv)

        st = wx.StaticText(self, -1,  "Control Brd" )
        sizerG2B.Add(st, (2, 0), flag=cvl)
        CBoptions = ('0-Old', 'LPT to CB', \
                     'USB to CB', 'RPi to CB', 'BBB to CB') # JGH 1/16/14

        s = p.get("CBoption", CBoptions[2])
        cm = wx.ComboBox(self, -1, s, (0, 0), cwsz, choices=CBoptions,
                         style=wx.CB_READONLY)
        cm.Enable(True)
        sizerG2B.Add(cm, (2, 1), flag=cv)
        self.CBoptCM = cm
        sizerV2C.Add(sizerG2B, 0, wx.ALL, 5)

        sizerV2.Add(sizerV2C, 0, wx.ALL|wx.EXPAND, 4)
        sizerH0.Add(sizerV2, 0, wx.ALIGN_TOP)

        sizerV3 = wx.BoxSizer(wx.VERTICAL|wx.ALIGN_TOP)

        # Auto Switches config
        self.autoSwBoxTitle = wx.StaticBox(self, -1, "Auto Switches")
        sizerV3A = wx.StaticBoxSizer(self.autoSwBoxTitle, wx.VERTICAL)
        sizerG3A = wx.GridBagSizer(5, 2)
        #autoSwEn = p.get("autoSwEn", {})
        ## autoSwBit = p.get("autoSwBit", {})    #JGH commented out
        # self.autoSwEnCB = {}
        autoSw = ("RBW", "Video", "xG Band", "Trans/Reflect", "Fwd/Rev")
        ## autoSwDefaults = (0x00, 0x03, 0x0c, 0x20, 0x10)  #JGH commented out

        for i, sw in enumerate(autoSw):

            # JGH The following may be useful in the future
            #self.autoSwEnCB[sw] = chk = wx.CheckBox(self, -1, sw)
            #chk.Enable(autoSwEn.get(sw, True)) # JGH, original was False
            #sizerG2A.Add(chk, (i, 0), flag=wx.ALIGN_CENTER_VERTICAL)
            ## n = autoSwBit.get(sw, autoSwDefaults[i]) #JGH commented out
            # binary-to-string in python 2.5 is tricky:
            ## s = "".join([["0", "1"][(n >> j) & 1] for j in reversed(range(8))]) #JGH commented out
            ##tc = wx.TextCtrl(self, -1, s, size=(72, -1))  #JGH commented out
            ##sizerG2A.Add(tc, (i, 1), flag=cvr)    #JGH commented out

            if i == 0:
                rbwCheckBox = wx.CheckBox(self, -1, label=sw)
                sizerG3A.Add(rbwCheckBox, (i, 0), flag=wx.ALIGN_CENTER_VERTICAL)
                rbwCheckBox.Bind(wx.EVT_CHECKBOX, self.autoSwitchRBW)
                s = p.get("SwRBW", True)
                rbwCheckBox.SetValue(s)
                p.SwRBW = rbwCheckBox.GetValue()
            if i == 1:
                videoCheckBox = wx.CheckBox(self, -1, label=sw)
                sizerG3A.Add(videoCheckBox, (i, 0), flag=wx.ALIGN_CENTER_VERTICAL)
                videoCheckBox.Bind(wx.EVT_CHECKBOX, self.autoSwitchVideo)
                s = p.get("SwVideo", True)
                videoCheckBox.SetValue(s)
                p.SwVideo = videoCheckBox.GetValue()
            if i == 2:
                bandCheckBox = wx.CheckBox(self, -1, label=sw)
                sizerG3A.Add(bandCheckBox, (i, 0), flag=wx.ALIGN_CENTER_VERTICAL)
                bandCheckBox.Bind(wx.EVT_CHECKBOX, self.autoSwitchBand)
                s = p.get("SwBand", False)
                bandCheckBox.SetValue(s)
                p.SwBand = bandCheckBox.GetValue()
            if i == 3:
                trCheckBox = wx.CheckBox(self, -1, label=sw)
                sizerG3A.Add(trCheckBox, (i, 0), flag=wx.ALIGN_CENTER_VERTICAL)
                trCheckBox.Bind(wx.EVT_CHECKBOX, self.autoSwitchTR)
                s = p.get("SwTR", False)
                trCheckBox.SetValue(s)
                p.SwTR = trCheckBox.GetValue()
            if i == 4:
                frCheckBox = wx.CheckBox(self, -1, label=sw)
                sizerG3A.Add(frCheckBox, (i, 0), flag=wx.ALIGN_CENTER_VERTICAL)
                frCheckBox.Bind(wx.EVT_CHECKBOX, self.autoSwitchFR)
                s = p.get("SwFR", False)
                frCheckBox.SetValue(s)
                p.SwFR = frCheckBox.GetValue()

        if debug:
            print ("SwRBW = " + str(p.SwRBW))
            print ("SwVideo = " + str(p.SwVideo))
            print ("SwBand = " + str(p.SwBand))
            print ("SwTR = " + str(p.SwTR))
            print ("SwFR = " + str(p.SwFR))

        sizerV3A.Add(sizerG3A, 0)
        sizerV3.Add(sizerV3A, 0)

        # JGH add end

        # Cancel and OK buttons
        butSizer = wx.BoxSizer(wx.HORIZONTAL)
        butSizer.Add((0, 0), 0, wx.EXPAND)
        self.helpBtn = btn = wx.Button(self, -1, "Help")
        btn.Bind(wx.EVT_BUTTON, self.OnHelp)
        butSizer.Add(btn, 0, wx.ALL, 5)
        btn = wx.Button(self, wx.ID_CANCEL)
        butSizer.Add(btn, 0, wx.ALL, 5)
        btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        butSizer.Add(btn, 0, wx.ALL, 5)
        sizerV3.Add(butSizer, 0, wx.ALIGN_RIGHT|wx.ALIGN_TOP)
        sizerH0.Add(sizerV3, 0, wx.ALIGN_TOP|wx.EXPAND)
        sizerV0.Add(sizerH0, 0, wx.ALL, 10)

        self.SetSizer(sizerV0)
        sizerV0.Fit(self)
        if pos == wx.DefaultPosition:
            self.Center()

    #--------------------------------------------------------------------------
    def LockHW(self, event):  # JGH 2/3/14 Modified
        sender = event.GetEventObject()
        isChecked = sender.GetValue()
        if isChecked == True:
            self.cmPLL1.Enable(False); self.cmPLL2.Enable(False); self.cmPLL3.Enable(False)
            self.cmPOL1.Enable(False); self.cmPOL2.Enable(False); self.cmPOL3.Enable(False)
            self.tcPhF1.Enable(False); self.tcPhF2.Enable(False); self.tcPhF3.Enable(False)
            self.cmMOD1.Enable(False); self.cmMOD3.Enable(False)
##            tc.Enable(False)
            self.mastClkBox.Enable(False); self.InvDegBo.Enable(False)
        else:
            self.cmPLL1.Enable(True); self.cmPLL2.Enable(True); self.cmPLL3.Enable(True)
            self.cmPOL1.Enable(True); self.cmPOL2.Enable(True); self.cmPOL3.Enable(True)
            self.tcPhF1.Enable(True); self.tcPhF2.Enable(True); self.tcPhF3.Enable(True)
            self.cmMOD1.Enable(True); self.cmMOD3.Enable(True)
##            tc.Enable(True)
            self.mastClkBox.Enable(True); self.InvDegBox.Enable(True)
        event.Skip() # JGH 1/20/14

    #--------------------------------------------------------------------------
    # JGH addition starts here 1/18/14
    # Handle Configuration locks

    def LockRBWs(self, event): # JGH New on 1/18/14
        gr = self.gridRBW
        sender = event.GetEventObject()
        isChecked = sender.GetValue()
        if isChecked == True:
            gr.EnableEditing(0)
        else:
            gr.EnableEditing(1)
        event.Skip() # JGH 1/20/14

    def LockVFs(self, event): # JGH New on 1/18/14
        gv = self.gridVF
        sender = event.GetEventObject()
        isChecked = sender.GetValue()
        if isChecked == True:
            gv.EnableEditing(0)
        else:
            gv.EnableEditing(1)
        event.Skip() # JGH 1/20/14
    # JGH addition ends here 1/18/14
    #--------------------------------------------------------------------------
    def autoSwitchRBW(self, event):  # JGH added this method
        sender = event.GetEventObject()
        p = self.frame.prefs
        p.SwRBW = sender.GetValue()
##        print ("p.SwRBW:   " + str(p.SwRBW))

    def autoSwitchVideo(self, event):  # JGH added this method
        sender = event.GetEventObject()
        p = self.frame.prefs
        p.SwVideo = sender.GetValue()
##        print ("p.SwVideo:   " + str(p.SwVideo))

    def autoSwitchBand(self, event):  # JGH added this method
        sender = event.GetEventObject()
        p = self.frame.prefs
        p.SwBand = sender.GetValue()
##        print ("p.SwBand:   " + str(p.SwBand))

    def autoSwitchTR(self, event):  # JGH added this method
        sender = event.GetEventObject()
        p = self.frame.prefs
        p.SwTR = sender.GetValue()
##        print ("p.SwTR:   " + str(p.SwTR))

    def autoSwitchFR(self, event):  # JGH added this method
        sender = event.GetEventObject()
        p = self.frame.prefs
        p.SwFR = sender.GetValue()
##        print ("p.SwFR:   " + str(p.SwFR))

    #--------------------------------------------------------------------------
    # Present Help dialog.

    def OnHelp(self, event):
        self.helpDlg = dlg = ConfigHelpDialog(self)
        dlg.Show()
        # JGH added 1/21/14
        result = dlg.ShowModal()
        if (result == wx.ID_OK):
            dlg.Close()
        # JGH ends 1/21/14

    #--------------------------------------------------------------------------
    # Cancel actions
    def OnCancel(self, event):
        pass

    #--------------------------------------------------------------------------
    # Focus on a text box: select contents when tabbed to for easy replacement.

    def OnSetFocus(self, event):
        if isMac:
            tc = event.GetEventObject()
            tc.SelectAll()
        event.Skip()

    #--------------------------------------------------------------------------
    # Handle Final Filter ListCtrl item addition/deletion.
    # JGH This section deleted on its entirety 1/21/14

#==============================================================================
# Calibration File Utilities.

# Make a calibration file name from a path number, returning (directory, fileName).
# Also creates the MSA_Info/MSA_Cal dirs if needed.

def CalFileName(pathNum):
    if pathNum == 0:
        fileName = "MSA_CalFreq.txt"
    else:
        fileName = "MSA_CalPath%d.txt" % pathNum
    directory = os.path.join(appdir, "MSA_Info", "MSA_Cal")
    if not os.path.exists(directory):
        os.makedirs(directory)
    return directory, fileName

# Check the version of a calibration file.

def CalCheckVersion(fName): # JGH 2/9/14
    f = open(fName, "Ur")   # JGH 2/9/14
    for i in range(3):
        line = f.readline()
    if line.strip() != "CalVersion= %s" % CalVersion:
        raise ValueError("File %s is the wrong version. Need %s" % \
                    (fName, CalVersion))    # JGH 2/9/14

# Parse a Mag calibration file, returning adc, Sdb, Sdeg arrays.

def CalParseMagFile(fName): # JGH 2/9/14
    for i in range(5):
        fName.readline()    # JGH 2/9/14
    Madc = []; Sdb = []; Sdeg = []
    for line in fName.readlines():  # JGH 2/9/14
        words = map(string.strip, line.split())
        if len(words) == 3:
            Madc.append(int(words[0]))
            Sdb.append(float(words[1]))
            Sdeg.append(float(words[2]))
    return Madc, Sdb, Sdeg

# Parse a Freq calibration file, returning freq, db arrays.

def CalParseFreqFile(fName):    # JGH 2/9/14
    # (genfromtxt in Python2.6 only)
    ##data = genfromtxt(file, dtype=[("freq", "f8"), ("db", "f8")], \
    ##        comments="*", skip_header=5)
    ##return data["freq"], data["db"]
    for i in range(5):
        fName.readline()    # JGH 2/9/14
    Fmhz = []; dbs = []
    for line in fName.readlines():  # JGH 2/9/14
        words = map(string.strip, line.split())
        if len(words) == 2:
            Fmhz.append(float(words[0]))
            dbs.append(float(words[1]))
    return Fmhz, dbs

# Generate a Mag calibration file.

def CalGenMagFile(fName, Madc, Sdb, Sdeg, pathNum, freq, bw, calFreq):  # JGH 2/9/14
    fName.write( \
        "*Filter Path %d: CenterFreq=%8.6f MHz; Bandwidth=%8.6f KHz\n"\
        "*Calibrated %s at %8.6f MHz.\n"\
        "CalVersion= %s\n"\
        "MagTable=\n"\
        "*  ADC      dbm      Phase   in increasing order of ADC\n" % \
        (pathNum, freq, bw, time.strftime("%D"), calFreq, CalVersion))
    for fset in sorted(zip(Madc, Sdb, Sdeg)):
        fName.write("%6i %9.3f %8.2f\n" % fset)  # JGH 2/9/14
    fName.close()   # JGH 2/9/14

# Generate a Freq calibration file.

def CalGenFreqFile(fName, Fmhz, dbs, calDbm):   # JGH 2/9/14
    fName.write( \
        "*Calibration over frequency\n"\
        "*Calibrated %s at %8.3f dbm.\n"\
        "CalVersion= %s\n"\
        "FreqTable=\n"\
        "*    MHz        db   in increasing order of MHz\n" % \
        (time.strftime("%D"), calDbm, CalVersion))
    for fset in sorted(zip(Fmhz, dbs)):
        fName.write("%11.6f %9.3f\n" % fset) # JGH 2/9/14
    fName.close()


#==============================================================================
# The Calibration File Manager dialog box.

class CalManDialog(wx.Dialog):
    def __init__(self, frame):
        self.frame = frame
        if msa.IsScanning():
            msa.StopScan()
        self.prefs = p = frame.prefs
        pos = p.get("calManWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, "Calibration File Manager", pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        c = wx.ALIGN_CENTER
        self.sizerV = sizerV = wx.BoxSizer(wx.VERTICAL)
        sizerH1 = wx.BoxSizer(wx.HORIZONTAL)

        # file editor box
        sizerV2 = wx.BoxSizer(wx.VERTICAL)
        st = wx.StaticText(self, -1, "Path Calibration Table" )
        sizerV2.Add(st, 0, flag=c)
        self.editBox = tc = wx.TextCtrl(self, -1, "", size=(350, 300), \
                style=wx.TE_MULTILINE|wx.HSCROLL|wx.VSCROLL) # JGH 1/31/14
        tc.SetFont(wx.Font(fontSize*1.2, wx.TELETYPE, wx.NORMAL, wx.NORMAL))
        tc.Bind(wx.EVT_CHAR, self.OnTextEdit)
        sizerV2.Add(tc, 0, c|wx.ALL, 5)

        butSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.cleanupBtn = btn = wx.Button(self, -1, "Clean Up")
        btn.Bind(wx.EVT_BUTTON, self.OnCleanUp)
        butSizer.Add(btn, 0, wx.ALL, 5)
        self.defaultsBtn = btn = wx.Button(self, -1, "Display Defaults")
        btn.Bind(wx.EVT_BUTTON, self.OnSetDefaults)
        butSizer.Add(btn, 0, wx.ALL, 5)
        sizerV2.Add(butSizer, 0, c)
        sizerH1.Add(sizerV2, 0, wx.EXPAND|wx.ALL, 20)

        # files chooser
        sizerV3 = wx.BoxSizer(wx.VERTICAL)
        sizerV3.Add(wx.StaticText(self, -1,  "Available Files" ), 0, flag=c)
        self.filesListCtrl = lc = wx.ListCtrl(self, -1, (0, 0), (180, 160),
            wx.LC_REPORT|wx.LC_SINGLE_SEL)
        lc.InsertColumn(0, "File")
        lc.InsertColumn(1, "Freq")
        lc.InsertColumn(2, "BW")
        lc.SetColumnWidth(0, 35)
        lc.SetColumnWidth(1, 90)
        lc.SetColumnWidth(2, 40)
        lc.InsertStringItem(0, "")
        lc.SetStringItem(0, 0, gstr(0))
        lc.SetStringItem(0, 1, "(Frequency)")

        i = 1
        for freq, bw in msa.RBWFilters:
            lc.InsertStringItem(i, "")
            lc.SetStringItem(i, 0, gstr(i))
            lc.SetStringItem(i, 1, gstr(freq))
            lc.SetStringItem(i, 2, gstr(bw))
            i += 1

        self.pathNum = None
        lc.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnFileItemSel)
        lc.MoveBeforeInTabOrder(self.editBox)
        sizerV3.Add(lc, 0, c|wx.ALL, 5)
        sizerH1.Add(sizerV3, 1, wx.EXPAND|wx.ALL, 20)
        sizerV.Add(sizerH1, 0, c)

        # instructions and measurement controls
        self.sizerG1 = sizerG1 = wx.GridBagSizer(hgap=10, vgap=2)
        self.startBtn = btn = wx.Button(self, -1, "Start Data Entry")
        btn.Bind(wx.EVT_BUTTON, self.OnStartBtn)
        sizerG1.Add(btn, (0, 0), flag=c)
        sizerV.Add(sizerG1, 0, c|wx.ALL, 5)

        self.beginText = \
            "To begin entry of calibration data, click Start Entry.\n"\
            "Alternatively, you may enter, alter and delete data in "\
            "the text editor.\n"
        self.instructBox = text = wx.TextCtrl(self, -1, self.beginText,
            size=(600, 180),
            style=wx.TE_READONLY|wx.NO_BORDER|wx.TE_MULTILINE)
        text.SetBackgroundColour(wx.WHITE)
        sizerV.Add(text, 1, c|wx.ALL, 5)

        # Cancel and OK buttons
        butSizer = wx.BoxSizer(wx.HORIZONTAL)
        butSizer.Add((0, 0), 0, wx.EXPAND)
        btn = wx.Button(self, wx.ID_CANCEL)
        butSizer.Add(btn, 0, wx.ALL, 5)
        btn = wx.Button(self, wx.ID_OK)
        butSizer.Add(btn, 0, wx.ALL, 5)
        sizerV.Add(butSizer, 0, wx.ALIGN_RIGHT|wx.ALIGN_BOTTOM)

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if pos == wx.DefaultPosition:
            self.Center()

        self.calDbm = 0.
        self.dirty = False
        self.cancelling = False
        self.refPhase = 0.
        self.refFreq = msa._fStart
        lc.SetItemState(0, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED)

    #--------------------------------------------------------------------------
    # A character was typed in the text edit box. Say it's now modified.

    def OnTextEdit(self, event):
        self.dirty = True
        self.cleanupBtn.Enable(True)
        self.defaultsBtn.Enable(True)
        event.Skip()

    #--------------------------------------------------------------------------
    # Clean up the formatting of the current calibration text by parsing and
    # then re-generating it.

    def OnCleanUp(self, event):
        lc = self.filesListCtrl
        i = self.pathNum
        tc = self.editBox
        fin = StringIO(tc.GetValue())
        fout = StringIO("")
        if i == 0:
            pass
            ##Fmhz, dbs = CalParseFreqFile(fin)
            ##CalGenFreqFile(fout, Fmhz, dbs, self.calDbm)
        else:
            centerFreq = float(lc.GetItem(i, 1).GetText())
            bw =         float(lc.GetItem(i, 2).GetText())
            Madc, Sdb, Sdeg = CalParseMagFile(fin)
            CalGenMagFile(fout, Madc, Sdb, Sdeg, i, centerFreq, bw,
                            self.refFreq)
        tc.SetValue(string.join(fout.buflist))
        self.dirty = True
        self.cleanupBtn.Enable(False)

    #--------------------------------------------------------------------------
    # Set the calibration table to default values.

    def OnSetDefaults(self, event):
        if self.dirty:
            if self.SaveIfAllowed(self) == wx.ID_CANCEL:
                return
        lc = self.filesListCtrl
        i = self.pathNum
        tc = self.editBox
        fout = StringIO("")
        if i == 0:
            Fmhz = [0., 1000.]
            dbs = [0., 0.]
            CalGenFreqFile(fout, Fmhz, dbs, self.calDbm)
        else:
            Madc = [0, 32767]
            Sdb = [-120., 0.]
            Sdeg = [0., 0.]
            CalGenMagFile(fout, Madc, Sdb, Sdeg, i, 10.7, 8, self.refFreq)
        tc.SetValue(string.join(fout.buflist))
        self.dirty = True
        self.cleanupBtn.Enable(False)

    #--------------------------------------------------------------------------
    # Save the modified text to the file, if confirmed. May return
    # wx.ID_CANCEL.

    def SaveIfAllowed(self, parent):
        dlg = wx.MessageDialog(parent, "Unsaved calibration changes will be "\
                "lost. Do you want to SAVE first?", \
                "Warning", style=wx.YES_NO|wx.CANCEL|wx.CENTER)
        answer = dlg.ShowModal()
        if answer == wx.ID_YES:
            directory, fileName = CalFileName(self.pathNum)   # JGH 2/9/14
            wildcard = "Text (*.txt)|*.txt"
            while True:
                dlg = wx.FileDialog(self, "Save file as...", defaultDir=directory,
                        defaultFile=fileName, wildcard=wildcard, style=wx.SAVE) # JGH 2/9/14
                answer = dlg.ShowModal()
                if answer != wx.ID_OK:
                    break
                path = dlg.GetPath()
                if ShouldntOverwrite(path, parent):
                    continue
                f = open(path, "w")
                f.write(self.editBox.GetValue())
                f.close()
                print ("Wrote configuration to", path)
                self.dirty = False
                break
        return answer

    #--------------------------------------------------------------------------
    # Handle a calibration file selection.

    def OnFileItemSel(self, event):
        if self.cancelling:
            self.cancelling = False
            return
        i = event.m_itemIndex

        # save current file first, if it needs it
        if self.dirty and i != self.pathNum:
            if self.SaveIfAllowed(self) == wx.ID_CANCEL:
                # canelled: undo selection change
                self.cancelling = True
                lc = self.filesListCtrl
                lc.SetItemState(i, 0, wx.LIST_STATE_SELECTED)
                lc.SetItemState(self.pathNum, wx.LIST_STATE_SELECTED,
                    wx.LIST_STATE_SELECTED)
                return

        # open newly selected file
        self.pathNum = i
        try:
            directory, fileName = CalFileName(i)    # JGH 2/9/14
            text = open(os.path.join(directory, fileName), "Ur").read() # JGH 2/9/14
            self.editBox.SetValue(text)
            self.dirty = False
            self.cleanupBtn.Enable(False)
        except IOError:
            print ("File %s not found, using defaults." % fileName)
            self.OnSetDefaults(0)
        self.instructBox.SetValue(self.beginText)

    #--------------------------------------------------------------------------
    # Start Data Entry button.

    def OnStartBtn(self, event):
        self.instructBox.SetValue( \
        "The Spectrum Analyzer must be configured for zero sweep width. "\
        "Center Frequency must be higher than 0 MHz. The first data Point "\
        "will become the Reference data for all other data Points. Click "\
        "Measure button to display the data measurements for ADC value and "\
        "Phase. Manually, enter the Known Power Level into the Input (dBm) "\
        "box. Click the Enter button to insert the data into the Path "\
        "Calibration Table. Subsequent Data may be entered in any order, and "\
        "sorted by clicking Clean Up. ADC bits MUST increase in order and no "\
        "two can be the same. You may alter the Data in the table, or boxes, "\
        "by highlighting and retyping. The Phase Data (Phase Error vs Input "\
        "Power) = Measured Phase - Ref Phase, is Correction Factor used in "\
        "VNA. Phase is meaningless for the Basic MSA, or MSA with TG. ")
        sizerG1 = self.sizerG1
        self.startBtn.Destroy()

        c = wx.ALIGN_CENTER
        chb = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM
        tsz = (90, -1)
        st = wx.StaticText(self, -1, "Input (dbm)")
        sizerG1.Add(st, (2, 0), (1, 1), chb, 0)
        self.inputBox = tc = wx.TextCtrl(self, -1, "", size=tsz)
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        sizerG1.Add(tc, (3, 0), flag=c)

        st = wx.StaticText(self, -1, "ADC value")
        sizerG1.Add(st, (2, 1), (1, 1), chb, 0)
        self.adcBox = tc = wx.TextCtrl(self, -1, "", size=tsz)
        sizerG1.Add(tc, (3, 1), flag=c)

        st = wx.StaticText(self, -1, "Phase")
        sizerG1.Add(st, (1, 2), (1, 1), chb, 0)
        st = wx.StaticText(self, -1, "(degrees)")
        sizerG1.Add(st, (2, 2), (1, 1), chb, 0)
        self.phaseBox = tc = wx.TextCtrl(self, -1, "", size=tsz)
        sizerG1.Add(tc, (3, 2), flag=c)

        btn = wx.Button(self, -1, "Measure")
        btn.Bind(wx.EVT_BUTTON, self.OnMeasure)
        btn.SetDefault()
        sizerG1.Add(btn, (3, 3), flag=c)

        btn = wx.Button(self, -1, "Enter")
        btn.Bind(wx.EVT_BUTTON, self.OnEnter)
        sizerG1.Add(btn, (3, 4), flag=c)

        st = wx.StaticText(self, -1, "Ref Freq (MHz)")
        sizerG1.Add(st, (2, 5), (1, 1), chb, 0)
        self.refFreqBox = tc = wx.TextCtrl(self, -1, "", size=tsz)
        self.refFreqBox.SetValue(gstr(self.refFreq))
        sizerG1.Add(tc, (3, 5), flag=c)
        self.sizerV.Fit(self)

        self.haveRefMeas = False
        self.inputBox.SetFocus()

    #--------------------------------------------------------------------------
    # Key focus changed.

    def OnSetFocus(self, event):
        tc = event.GetEventObject()
        if isMac:
            tc.SelectAll()
        self.tcWithFocus = tc
        event.Skip()

    #--------------------------------------------------------------------------
    # Make a measurement and update ADC and phase value boxes.

    def OnMeasure(self, event):
        msa.WrapStep()
        freq, adc, Sdb, Sdeg = msa.CaptureOneStep(post=False, useCal=False)
        self.adcBox.SetValue(gstr(adc))
        if isnan(Sdeg):
            Sdeg = 0
        self.phaseBox.SetValue("%7g" % (Sdeg - self.refPhase))
        self.refFreqBox.SetValue(gstr(freq))
        self.inputBox.SetFocus()
        if isMac:
            self.inputBox.SelectAll()

    #--------------------------------------------------------------------------
    # Enter the measurement values into the calibration table.

    def OnEnter(self, event):
        adc = int(self.adcBox.GetValue())
        Sdb = float(self.inputBox.GetValue())
        Sdeg = float(self.phaseBox.GetValue())

        # if first one, make it the reference measurement
        if not self.haveRefMeas:
            self.haveRefMeas = True
            self.refMag = Sdb
            self.refPhase = Sdeg

            sizerG1 = self.sizerG1
            c = wx.ALIGN_CENTER
            chb = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM
            tsz = (90, -1)
            st = wx.StaticText(self, -1, "Ref Input (dbm)")
            sizerG1.Add(st, (0, 0), (1, 1), chb, 0)
            tc = wx.TextCtrl(self, -1, "%7g" % Sdb, size=tsz)
            self.refInputBox = tc
            tc.MoveBeforeInTabOrder(self.inputBox)
            sizerG1.Add(tc, (1, 0), flag=c)

            st = wx.StaticText(self, -1, "Ref Phase (deg)")
            sizerG1.Add(st, (0, 5), (1, 1), chb, 0)
            tc = wx.TextCtrl(self, -1, "%7g" % Sdeg, size=tsz)
            self.refPhaseBox = tc
            sizerG1.Add(tc, (1, 5), flag=c)
            self.sizerV.Fit(self)
            Sdeg = 0.
        else:
            Sdb += float(self.refInputBox.GetValue())

        # append values to calibration table text
        self.editBox.AppendText("\n%d %7g %7g" % (adc, Sdb, Sdeg))
        self.OnCleanUp(0)


#==============================================================================
# The PDM Calibration dialog box.

class PDMCalDialog(wx.Dialog):
    def __init__(self, frame):
        self.frame = frame
        p = frame.prefs
        if msa.IsScanning():
            msa.StopScan()
        pos = p.get("pdmCalWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, "PDM Calibration", pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        c = wx.ALIGN_CENTER
        sizerV = wx.BoxSizer(wx.VERTICAL)
        st = wx.StaticText(self, -1, \
        "The actual phase shift caused by PDM inversion will differ from "\
        "the theoretical 180 degrees. A one-time calibration is required to "\
        "determine the actual phase shift. This value will be used "\
        "internally, and you will not directly need to know or use the "\
        "value. To perform this calibration you first need to do the "\
        "following, which will require that you close this window and return "\
        "to the Graph Window:\n\n"\
        "    * Set Video Filter to NARROW bandwidth.\n"\
        "    * Connect Tracking Generator output to MSA input with 1-2 foot "\
                "cable.\n"\
        "    * In menu Operating Cal->Transmission, set Transmission "\
                "Reference to No Reference.\n"\
        "    * Sweeping 0-200 MHz, find a frequency with a phase shift near "\
                "90 or 270 deg.\n"\
        "    * Center the sweep at that frequency, with zero sweep width.\n"\
        "    * Return to this window and click the PDM Inversion Cal button.")
        st.Wrap(600)
        sizerV.Add(st, 0, c|wx.ALL, 10)

        btn = wx.Button(self, -1, "Set Up")
        btn.Bind(wx.EVT_BUTTON, self.OnCalSetup)
        sizerV.Add(btn, 0, c|wx.ALL, 5)
        btn = wx.Button(self, -1, "PDM Inversion Cal")
        btn.Bind(wx.EVT_BUTTON, self.OnPDMInversionCal)
        sizerV.Add(btn, 0, c|wx.ALL, 5)
        self.invDeg = p.invDeg
        self.invBox =tb = wx.StaticText(self, -1,
                                "Current Inversion= %g deg" % self.invDeg)
        sizerV.Add(tb, 0, c)

        # Cancel and OK buttons
        butSizer = wx.BoxSizer(wx.HORIZONTAL)
        butSizer.Add((0, 0), 0, wx.EXPAND)
        btn = wx.Button(self, wx.ID_CANCEL)
        butSizer.Add(btn, 0, wx.ALL, 5)
        btn = wx.Button(self, wx.ID_OK)
        butSizer.Add(btn, 0, wx.ALL, 5)
        sizerV.Add(butSizer, 0, wx.ALIGN_RIGHT|wx.ALIGN_BOTTOM|wx.ALL, 10)

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if pos == wx.DefaultPosition:
            self.Center()

    #--------------------------------------------------------------------------
    # Set up for a PDM calibration.

    def OnCalSetup(self, event):
        frame = self.frame
        p = frame.prefs
        if frame.sweepDlg:
            frame.sweepDlg.OnClose()
        p.fStart = 0.
        p.fStop = 200.
        p.nSteps = 100
        p.planeExt = 3*[0.]
        p.isLogF = False
        frame.SetCalLevel(0)
        frame.SetMode(msa.MODE_VNATran)
        frame.StartScan(True)

    #--------------------------------------------------------------------------
    # Find the amount of phase shift when the PDM state is inverted.
    # invDeg is a calibration value used in CaptureOneStep(),
    # (phase of inverted PDM) - (invDeg) = real phase of PDM.
    # The VNA must be in "0" sweepwidth, freq close to the transition point.

    def OnPDMInversionCal(self, event):
        frame = self.frame
        p = frame.prefs
        print ("Calibrating PDM Inversion")
        msa.wait = 250
        msa.invDeg = 192.
        msa.invPhase = 0
        msa.WrapStep()
        freq, adc, Sdb, phase0 = \
            msa.CaptureOneStep(post=False, useCal=False, bypassPDM=True)
        print ("phase0= %8.3f freq= %8.6f adc=%5d" % (phase0, freq, msa._phasedata))
        msa.invPhase = 1
        msa.WrapStep()
        freq, adc, Sdb, phase1 = \
            msa.CaptureOneStep(post=False, useCal=False, bypassPDM=True)
        print ("phase0= %8.3f freq= %8.6f adc=%5d" % (phase1, freq, msa._phasedata))
        msa.wait = p.wait
        self.invDeg = round(mod(phase1 - phase0, 360), 2)
        self.invBox.SetLabel("Current Inversion= %g deg" % self.invDeg)


#==============================================================================
# The Test Setups dialog box.

class TestSetupsDialog(wx.Dialog):
    def __init__(self, frame):
        self.frame = frame
        self.prefs = p = frame.prefs
        pos = p.get("testSetupsWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, "Test Setups", pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)

        # the subset of prefs variables that define a test setup
        self.setupVars = ("calLevel", "calThruDelay", "dataMode", "fStart",
            "fStop", "indexRBWSel", "isCentSpan", "isLogF", "continuous",
            "markerMode", "mode", "nSteps", "normRev", "planeExt", "rbw",
            "sigGenFreq", "spurTest", "sweepDir", "sweepRefresh", "tgOffset",
            "va0", "va1", "vb0", "vb1", "nameVideoSel", "wait")

        # get a list of saved-test-setup files
        self.setupsDir = directory = os.path.join(appdir, "MSA_Info", "TestSetups")
        if not os.path.exists(directory):
            os.makedirs(directory)
        # get descriptions from first line in files (minus leading '|')
        names = ["Empty"] * 16
        for fn in os.listdir(directory):
            if len(fn) > 11 and fn[:9] == "TestSetup":
                i = int(fn[9:11]) - 1
                path = os.path.join(self.setupsDir, fn)
                names[i] = open(path).readline().strip()[1:]
        self.setupNames = names

        # instructions text
        c = wx.ALIGN_CENTER
        sizerV = wx.BoxSizer(wx.VERTICAL)
        sizerV.Add(wx.StaticText(self, -1, \
        "To save a test setup consisting of the current sweep settings and "\
        "calibration data,\nselect a slot, change the name if desired, and "\
        "click Save.\nTo load a test setup, select it and click Load."), \
        0, c|wx.ALL, 10)

        # setup chooser box
        self.setupsListCtrl = lc = wx.ListCtrl(self, -1, (0, 0), (450, 250),
            wx.LC_REPORT|wx.LC_SINGLE_SEL)
        lc.InsertColumn(0, "#")
        lc.InsertColumn(1, "Name")
        lc.SetColumnWidth(0, 30)
        lc.SetColumnWidth(1, 400)

        for i, name in enumerate(names):
            lc.InsertStringItem(i, "")
            lc.SetStringItem(i, 0, gstr(i+1))
            lc.SetStringItem(i, 1, name)

        lc.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnSetupItemSel)
        lc.Bind(wx.EVT_LEFT_DCLICK,  self.OnListDClick)
        sizerV.Add(lc, 0, c|wx.ALL, 5)

        sizerH1 = wx.BoxSizer(wx.HORIZONTAL)
        sizerH1.Add(wx.StaticText(self, -1, "Name:"), 0, c)
        self.nameBox = tc = wx.TextCtrl(self, -1, "", size=(300, -1))
        sizerH1.Add(tc, 0, c|wx.ALL, 5)
        btn = wx.Button(self, -1, "Create Name")
        btn.Bind(wx.EVT_BUTTON, self.CreateName)
        sizerH1.Add(btn, 0, c)
        sizerV.Add(sizerH1, 0, c)

        # Cancel and OK buttons
        sizerH2 = wx.BoxSizer(wx.HORIZONTAL)
        sizerH2.Add((0, 0), 0, wx.EXPAND)
        self.saveBtn = btn = wx.Button(self, -1, "Save")
        btn.Bind(wx.EVT_BUTTON, self.OnSave)
        btn.Enable(False)
        sizerH2.Add(btn, 0, wx.ALL, 5)
        self.loadBtn = btn = wx.Button(self, -1, "Load")
        btn.Bind(wx.EVT_BUTTON, self.OnLoad)
        btn.Enable(False)
        sizerH2.Add(btn, 0, wx.ALL, 5)
        self.loadWithCalBtn = btn = wx.Button(self, -1, "Load with Cal")
        btn.Bind(wx.EVT_BUTTON, self.OnLoadWithCal)
        btn.Enable(False)
        sizerH2.Add(btn, 0, wx.ALL, 5)
        self.deleteBtn = btn = wx.Button(self, -1, "Delete")
        btn.Bind(wx.EVT_BUTTON, self.OnDelete)
        btn.Enable(False)
        sizerH2.Add(btn, 0, wx.ALL, 5)
        sizerH2.Add((0, 0), 0, wx.EXPAND)
        btn = wx.Button(self, wx.ID_OK)
        sizerH2.Add(btn, 0, wx.ALL, 5)
        sizerV.Add(sizerH2, 0, wx.ALIGN_RIGHT|wx.ALIGN_BOTTOM|wx.ALL, 10)

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if pos == wx.DefaultPosition:
            self.Center()

    #--------------------------------------------------------------------------
    # Create-Name button was pressed, or we need a new name. Build it out of
    # a shorthand for the current scan mode.

    def CreateName(self, event=None):
        p = self.prefs
        name = "%s/%s/%g to %g/Path %d" % \
            (msa.shortModeNames[p.mode], ("Linear", "Log")[p.isLogF],
            p.fStart, p.fStop, p.indexRBWSel+1)
        self.nameBox.SetValue(name)

    #--------------------------------------------------------------------------
    # A double-click in the list loads that setup file.

    def OnListDClick(self, event):
        self.OnLoadWithCal(event)
        self.Close()

    #--------------------------------------------------------------------------
    # An item in list selected- change name and button enables.

    def OnSetupItemSel(self, event):
        self.setupSel = i = event.m_itemIndex
        self.saveBtn.Enable(True)
        notEmpty = self.setupNames[i] != "Empty"
        self.loadBtn.Enable(notEmpty)
        self.loadWithCalBtn.Enable(notEmpty)
        self.deleteBtn.Enable(notEmpty)
        if notEmpty:
            self.nameBox.SetValue(self.setupNames[i])
        else:
            self.CreateName()

    #--------------------------------------------------------------------------
    # Return a TestSetup file name for the current slot.

    def SetupFileName(self):
        i = self.setupSel
        return os.path.join(self.setupsDir,"TestSetup%02d.txt" % (i+1))

    #--------------------------------------------------------------------------
    # Save pressed- write setup vars to a file as a list of
    # 'variable=value' lines.

    def OnSave(self, event):
        frame = self.frame
        i = self.setupSel
        setup = Prefs()
        p = self.prefs
        for attr in self.setupVars:
            if hasattr(p, attr):
                setattr(setup, attr, getattr(p, attr))
        name = self.nameBox.GetValue()
        self.setupNames[i] = name
        setup.save(self.SetupFileName(), header=name)
        ident = "%02d.s1p" % (self.setupSel+1)
        frame.SaveCal(msa.bandCal, frame.bandCalFileName[:-4] + ident)
        frame.SaveCal(msa.baseCal, frame.baseCalFileName[:-4] + ident)
        self.setupsListCtrl.SetStringItem(i, 1, name)
        self.loadBtn.Enable(True)
        self.loadWithCalBtn.Enable(True)
        self.deleteBtn.Enable(True)

    #--------------------------------------------------------------------------
    # Load pressed- read TestSetup file and update prefs from it.

    def OnLoad(self, event):
        frame = self.frame
        p = self.prefs
        setup = Prefs.FromFile(self.SetupFileName())
        for attr in self.setupVars:
            if hasattr(setup, attr):
                setattr(p, attr, getattr(setup, attr))
        frame.SetCalLevel(p.calLevel)
        self.CreateName()
        frame.RefreshAllParms()

    #--------------------------------------------------------------------------
    # Load with Cal pressed- additionaly load calibration files.

    def OnLoadWithCal(self, event):
        frame = self.frame
        ident = "%02d.s1p" % (self.setupSel+1)
        msa.bandCal = frame.LoadCal(frame.bandCalFileName[:-4] + ident)
        msa.baseCal = frame.LoadCal(frame.baseCalFileName[:-4] + ident)
        self.OnLoad(event)

    #--------------------------------------------------------------------------
    # Delete presed- delete the slot's TestSetup file and mark slot empty.

    def OnDelete(self, event):
        i = self.setupSel
        os.unlink(self.SetupFileName())
        self.setupNames[i] = name = "Empty"
        self.setupsListCtrl.SetStringItem(i, 1, name)
        self.CreateName()
        self.loadBtn.Enable(False)
        self.loadWithCalBtn.Enable(False)
        self.deleteBtn.Enable(False)


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


#==============================================================================
# The Sweep Parameters modeless dialog window.

class SweepDialog(wx.Dialog):
    def __init__(self, frame):
        self.frame = frame
        self.mode = None
        self.modeCtrls = []   # JGH modeCtrls does not exist anywhere
        self.prefs = p = frame.prefs
        pos = p.get("sweepWinPos", (20, 720))
        wx.Dialog.__init__(self, frame, -1, "Sweep Parameters", pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        c = wx.ALIGN_CENTER

        # Mode selection
        self.sizerH = sizerH = wx.BoxSizer(wx.HORIZONTAL)
        sizerV1 = wx.BoxSizer(wx.VERTICAL)
        sizerV1.Add(wx.StaticText(self, -1, "Data Mode"), 0)
        samples = ["0(Normal Operation)", "1(Graph Mag Cal)",
                   "2(Graph Freq Cal)", "3(Graph Noisy Sine)",
                   "4(Graph 1MHz Peak)"]
        cm = wx.ComboBox(self, -1, samples[0], (0, 0), (160, -1), samples)
        self.dataModeCM = cm
        cm.Enable(False)
        sizerV1.Add(cm, 0, 0)

        # Create list of Final RBW Filters
        self.finFiltSamples = samples = []
        i = 1
        for freq, bw in msa.RBWFilters:
            samples.append("F%d-%s-%s" % (i, gstr(freq), gstr(bw))) # JGH 1/30/14
            i += 1

        sizerV1.Add(wx.StaticText(self, -1, "Final RBW Filter Path:"), 0)
        ##s = p.indexRBWSel  # JGH added Oct24
        ##cm = wx.ComboBox(self, -1, samples[s], (0, 0), (160, -1), samples) # JGH changed to samples[s] from samples[0]
        cm = wx.ComboBox(self, -1, samples[0], (0, 0), (160, -1), samples)
        self.RBWPathCM = cm
        sizerV1.Add(cm, 0, 0)

        # Video Filters
        sizerV1.Add(wx.StaticText(self, -1, "Video Filter / BW"), 0)
##        samples = ["Wide", "Medium", "Narrow", "XNarrow"]  # JGH added XNarrow
        samples = msa.videoFilterNames
        cm = wx.ComboBox(self, -1, samples[1], (0, 0), (120, -1), samples)
        cm.Enable(True) # JGH set True instead of false
        cm.SetSelection(p.indexVideoSel)
        self.Bind(wx.EVT_COMBOBOX, self.AdjAutoWait, cm)
        self.videoFiltCM = cm
        sizerV1.Add(cm, 0, 0)

        sizerV1.Add(wx.StaticText(self, -1, "Graph Appearance"), 0)
        samples = ["Dark", "Light"]
        cm = wx.ComboBox(self, -1, samples[0], (0, 0), (120, -1), samples)
        self.graphAppearCM = cm
        sizerV1.Add(cm, 0, 0)
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

        ##self.atten5CB = cb = wx.CheckBox(self, -1, "Attenuate 5dB")
        ##sizerV2.Add(cb, 0, wx.BOTTOM, 10)

        st = wx.StaticText(self, -1, "Step Attenuator")
        sizerV2.Add(st, 0, c|wx.TOP, 4)

        sizerH2 = wx.BoxSizer(wx.HORIZONTAL)
        sizerH2.Add(wx.StaticText(self, -1, "  "), 0, c|wx.RIGHT, 2)
        tc2 = wx.TextCtrl(self, -1, str(p.stepAttenDB), size=(40, -1))
        self.stepAttenBox = tc2
        sizerH2.Add(tc2, 0, 0)
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
        freqSizer = wx.GridBagSizer(0, 0)
        self.centSpanRB = rb = wx.RadioButton(self, -1, "", style= wx.RB_GROUP)
        self.Bind(wx.EVT_RADIOBUTTON, self.AdjFreqTextBoxes, rb)
        freqSizer.Add(rb, (0, 0), (2, 1), 0, 0)
        cl = wx.ALIGN_CENTER|wx.LEFT
        cr = wx.ALIGN_CENTER|wx.RIGHT
        freqSizer.Add(wx.StaticText(self, -1, "Cent"), (0, 1), (1, 1), 0, cr,2)
        self.centBox = tc = wx.TextCtrl(self, -1, "", size=(80, -1))
        freqSizer.Add(tc, (0, 2), (1, 1), 0, 0)
        self.Bind(wx.EVT_TEXT, self.AdjFreqTextBoxes, tc)
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        freqSizer.Add(wx.StaticText(self, -1, "MHz"), (0, 3), (1, 1), 0, cl,2)
        freqSizer.Add(wx.StaticText(self, -1, "Span"), (1, 1), (1, 1), cr, 2)
        self.spanBox = tc = wx.TextCtrl(self, -1, "", size=(80, -1))
        freqSizer.Add(tc, (1, 2), (1, 1), 0, 0)
        self.Bind(wx.EVT_TEXT, self.AdjFreqTextBoxes, tc)
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        freqSizer.Add(wx.StaticText(self, -1, "MHz"), (1, 3), (1, 1), cl, 2)
        self.startstopRB = rb = wx.RadioButton(self, -1, "")
        self.Bind(wx.EVT_RADIOBUTTON, self.AdjFreqTextBoxes, rb)
        freqSizer.Add(rb, (0, 4), (2, 1), wx.LEFT, 5)
        freqSizer.Add(wx.StaticText(self, -1, "Start"), (0, 5), (1, 1), 0,cr,2)
        self.startBox = tc = wx.TextCtrl(self, -1, "", size=(80, -1))
        freqSizer.Add(tc, (0, 6), (1, 1), 0, 0)
        self.Bind(wx.EVT_TEXT, self.AdjFreqTextBoxes, tc)
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        freqSizer.Add(wx.StaticText(self, -1, "MHz"), (0, 7), (1, 1), 0, cl, 2)
        freqSizer.Add(wx.StaticText(self, -1, "Stop"), (1, 5), (1, 1), 0, cr,2)
        self.stopBox = tc = wx.TextCtrl(self, -1, "", size=(80, -1))
        freqSizer.Add(tc, (1, 6), (1, 1), 0, 0)
        self.Bind(wx.EVT_TEXT, self.AdjFreqTextBoxes, tc)
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        freqSizer.Add(wx.StaticText(self, -1, "MHz"), (1, 7), (1, 1), 0, cl, 2)
        freqBox.Add(freqSizer, 0, wx.ALL, 2)
        sizerV3.Add(freqBox, 0, wx.EXPAND)

        # other sweep parameters
        sizerH3 = wx.BoxSizer(wx.HORIZONTAL)
        self.sizerH3V1 = wx.BoxSizer(wx.VERTICAL)
        self.sizerH3V1.Add(wx.StaticText(self, -1, "Steps/Sweep"), 0, wx.TOP, 5)
        sizerH3V1H1 = wx.BoxSizer(wx.HORIZONTAL)
        tc = wx.TextCtrl(self, -1, str(p.nSteps), size=(50, -1))
        self.stepsBox = tc
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        sizerH3V1H1.Add(tc, 0, c)
        self.continCB = chk = wx.CheckBox(self, -1, "Continuous")
        sizerH3V1H1.Add(chk, 0, c|wx.LEFT, 10)
        self.sizerH3V1.Add(sizerH3V1H1, 0, 0)
        self.sizerH3V1.Add(wx.StaticText(self, -1, "Wait (ms)"), 0, wx.TOP, 5)
        sizerH3V1H2 = wx.BoxSizer(wx.HORIZONTAL)
        self.waitBox = tc = wx.TextCtrl(self, -1, str(p.wait), size=(50, -1))
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        sizerH3V1H2.Add(tc, 0, c)
        self.autoWaitCB = chk = wx.CheckBox(self, -1, "Auto Wait")
        chk.Enable(True)
        chk.Bind(wx.EVT_CHECKBOX, self.configAutoWait)
        sizerH3V1H2.Add(chk, 0, c|wx.LEFT, 10)
        self.sizerH3V1.Add(sizerH3V1H2, 0, 0)
        sizerH3.Add(self.sizerH3V1, 0, 0)

        self.sizerH3V2 = wx.BoxSizer(wx.VERTICAL) # JGH 11/25/2013
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
        sweepSizer.Add(sweepH2Sizer, 0, 0)
##        sizerH3.Add(sweepSizer, 0, wx.LEFT|wx.TOP, 10)
        self.sizerH3V2.Add(sweepSizer, 0, wx.LEFT|wx.TOP, 10) # JGH 11/25/2013
        sizerH3.Add(self.sizerH3V2, 0, 0) # JGH 11/25/2013
        sizerV3.Add(sizerH3, 0, 0)

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
            accTbl = wx.AcceleratorTable([(wx.ACCEL_CTRL, ord('W'),
                                        wx.ID_CLOSE)])
            self.SetAcceleratorTable(accTbl)
            self.Connect(wx.ID_CLOSE, -1, wx.wxEVT_COMMAND_MENU_SELECTED,
                         self.OnClose)

        # get current parameters from prefs
        self.SetSizer(sizerH)
        if debug:
            print (">>>>6610<<<< SweepDialog goes to UpdateFromPrefs")
        self.UpdateFromPrefs()
        (self.startBox, self.centBox)[p.isCentSpan].SetFocus()
        if debug:
            print (">>>>6614<<<< SweepDialog complete")

    #--------------------------------------------------------------------------
    # Update all controls to current prefs.

    def UpdateFromPrefs(self):
        p = self.prefs
        LogGUIEvent("UpdateFromPrefs start=%g stop=%g" % (p.fStart, p.fStop))
        if p.fStop < p.fStart:
            p.fStop = p.fStart

        self.dataModeCM.SetValue(p.get("dataMode", "0(Normal Operation)"))

        self.RBWPathCM.SetValue(self.finFiltSamples[p.indexRBWSel])
        # JGH: Get RBW switch bits (Correspond directly to msa.indexRBWSel)
        self.switchRBW = p.indexRBWSel

        # JGH: Get Video switch bits  (= indexVideoSel)
        self.nameVideoSel = p.nameVideoSel = self.videoFiltCM.GetValue()
        self.indexVideoSel = p.indexVideoSel = msa.videoFilterNames.index(p.nameVideoSel)

        self.switchBand = p.get("switchBand", 1)

        self.switchTR = p.get("switchTR", 0)

        self.switchFR = p.get("switchFR", 0)

        self.switchPulse = p.get("switchPulse", 0)

        self.graphAppearCM.SetValue(p.get("graphAppear", "Light"))

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

            # create new mode-dependent controls
            c = wx.ALIGN_CENTER
            ch = wx.ALIGN_CENTER_HORIZONTAL
            if newMode == msa.MODE_SA:
                # Spectrum Analyzer mode
                self.modeBoxTitle.SetLabel("Signal Generator")
                sizerVM.Add(wx.StaticText(self, -1, "Sig Gen Freq"), ch, 0)
                sizerH = wx.BoxSizer(wx.HORIZONTAL)
                tc = wx.TextCtrl(self, -1, str(p.sigGenFreq), size=(80, -1))
                self.sigGenFreqBox = tc
                sizerH.Add(tc, 0, 0)
                sizerH.Add(wx.StaticText(self, -1, "MHz"), 0, c|wx.LEFT, 2)
                sizerVM.Add(sizerH, 0, 0)

            elif newMode == msa.MODE_SATG:
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

                # For reflection only, Graph R()
                if newMode == msa.MODE_VNARefl:
                    self.sizerH3V1.Add(wx.StaticText(self, -1, "Graph R()"), 0, wx.TOP, 7)
                    sizerH3V1H3 = wx.BoxSizer(wx.HORIZONTAL)
                    p.graphR = p.get("graphR", 50)
                    self.graphRBox = tc = wx.TextCtrl(self, -1, str(p.graphR), size=(50, -1))
                    tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
                    tc.Enable(True)
                    sizerH3V1H3.Add(tc, 0, wx.ALIGN_LEFT)
                    sizerH3V1H3.Add(wx.StaticText(self, -1, "  ohms"), 0, c|wx.LEFT, 2)
                    self.sizerH3V1.Add(sizerH3V1H3, 0, wx.ALIGN_LEFT)

                # DUT Forward/Reverse
                fwdrevBoxTitle = wx.StaticBox(self, -1, "DUT Fwd/Rev")
                fwdrevSizer = wx.StaticBoxSizer(fwdrevBoxTitle, wx.VERTICAL)
                fwdrevH1Sizer = wx.BoxSizer(wx.HORIZONTAL)
                rb = wx.RadioButton(self, -1, "Forward", style= wx.RB_GROUP)
                self.forwardFR = rb
                self.Bind(wx.EVT_RADIOBUTTON, self.SetDUTfwdrev, rb)
                fwdrevH1Sizer.Add(rb, 0, wx.RIGHT, 10)
                self.reverseFR = rb = wx.RadioButton(self, -1, "Reverse")
                self.Bind(wx.EVT_RADIOBUTTON, self.SetDUTfwdrev, rb)
                fwdrevH1Sizer.Add(rb, 4, 0)
                fwdrevSizer.Add(fwdrevH1Sizer, 4, 0)
                self.sizerH3V2.Add(fwdrevSizer, 0, wx.LEFT|wx.TOP|wx.EXPAND, 12)

            self.mode = newMode
            sizerVM.Layout()

        # Cent-Span or Start-Stop frequency entry
        isCentSpan = p.get("isCentSpan", True)
        self.centSpanRB.SetValue(isCentSpan)
        fCent, fSpan = StartStopToCentSpan(p.fStart, p.fStop, p.isLogF)
        self.centBox.SetValue(mhzStr(fCent))
        self.spanBox.SetValue(mhzStr(fSpan))
        self.startstopRB.SetValue(not isCentSpan)
        self.startBox.SetValue(str(p.fStart))
        self.stopBox.SetValue(str(p.fStop))

        # other sweep parameters
        self.stepsBox.SetValue(str(p.nSteps))
        self.continCB.SetValue(p.get("continuous", False))
        #self.waitBox.SetValue(str(p.wait))
        if self.autoWaitCB.GetValue() == False: # JGH 12/18/13
            self.waitBox.SetValue(str(p.get("wait", 10)))
        else:
            self.calculateWait
            self.waitBox.SetValue(str(p.wait))

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

    def SwitchLatchBits(self, indexVideoSel, switchFR, switchTR, switchPulse):
        # JGH not implemented yet, for reference only so far
        if debug:
            print (">>>>6760<<<< Set Port 4 on the SLIM Control Board")
        # Video Switches: 00 Wide, 01 Medium, 10 Narrow, 11 XNarrow
        #bit 0  VS0 Video Filter Address, low order bit
        #bit 1  VS1                       high order bit
        #bit 2  A0 RBW Final Filter, low order bit
        #bit 3  A1 RBW Final Filter, high order bit
        #bit 4  FR  DUT Direct, Fwd (0), Rev (1)
        #bit 5  TR  VNA Select, Trans (0), Refl (1)
        #bit 6  Band seelction 0 for band 2, 1 for bands 1 and 3
        #bit 7  PS  Latch Pulse start (for all latching relays, adjustable)
        #           Normally high, pulsed low (2-200 ms) to trigger relay latching.

        SwitchLatchBits = indexVideoSel + 4 * self.switchRBW + 16 * self.switchFR + \
                          32 * self.switchTR + 64 * self.switchBand + 128 * self.switchPulse
        if debug:
            print (">>>>7169<<<< SwitchLatchBits: " + str(SwitchLatchBits) + " <<<<<")

        #--------------------------------------------------------------------------

    def configAutoWait(self, event):  # JGH added this method
        sender = event.GetEventObject()
        p = self.frame.prefs
        if sender.GetValue() == True:
            # Set the wait time to 10 x time constant of video filter
            # With R=10K and C in uF, RC = C/100 secs and wait=C/10 secs = 100C msecs
            self.calculateWait()
        else:
            # Set value = Leave in Wait box
            p.wait = int(self.waitBox.GetValue())

        #--------------------------------------------------------------------------

    def calculateWait(self):    # JGH added this  method
        p = self.frame.prefs
        p.nameVideoSel = self.videoFiltCM.GetValue()
        p.indexVideoSel = msa.videoFilterNames.index(p.nameVideoSel)
        p.wait = int(10 + 67 *(float(p.VideoFilters[p.indexVideoSel][p.nameVideoSel][0])) ** 0.32)
        self.waitBox.SetValue(str(p.wait))

        #--------------------------------------------------------------------------

    def AdjAutoWait(self, name):
        if self.autoWaitCB.GetValue() == True:
            self.calculateWait()
        else:
            pass

        #--------------------------------------------------------------------------

    def SetDUTfwdrev(self, event):  # JGH added this method
        sender = event.GetEventObject()
        p = self.frame.prefs
        p.DUTfwdrev = sender.GetValue()
        # if sender.GetValue() == fwd on:
            # set the bits for fwd (=0)
            # else set the bits for rev (=1)
        pass

    #--------------------------------------------------------------------------
    # One Scan pressed- apply before scanning.

    def DoOneScan(self, event):
        self.Apply()
        self.frame.DoExactlyOneScan()

    #--------------------------------------------------------------------------
    # Only enable selected freq text-entry boxes, and make other values track.

    def AdjFreqTextBoxes(self, event=None, final=False):
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
                    fStop = fStart
                    self.stopBox.ChangeValue(mhzStr(fStop))
                else:
                    fStart = fStop
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
    # Grab new values from dialog box and update preferences.

    def Apply(self, event=None):
        if debug:
            print (">>>6948<<< Entering Apply") # JGH
        frame = self.frame
        specP = frame.specP
        p = self.prefs
        LogGUIEvent("Apply")
        p.dataMode = self.dataModeCM.GetValue()

        i = self.RBWPathCM.GetSelection()
        # JGH added in case the SweepDialog is opened and closed with no action
        if i >= 0:
            msa.indexRBWSel = p.indexRBWSel = i
        # JGH end
        (msa.finalfreq, msa.finalbw) = p.RBWFilters[p.indexRBWSel]
        p.rbw = msa.finalbw # JGH added
        p.switchRBW = p.indexRBWSel
        msa.bitsRBW = self.bitsRBW = 4 * p.switchRBW
        if debug: # JGH Same prints, different location. Will be removed
            print (">>>6965<<< p.RBWFilters[p.indexRBWSel]: ", \
                   p.RBWFilters[p.indexRBWSel])
            print (">>> 6967 <<<< p.rbw: ", p.rbw)
            print (">>>6968<<< bitsRBW: ", msa.bitsRBW)

        self.calculateWait

        i = self.videoFiltCM.GetSelection()
        if i>= 0:
            msa.indexVideoSel = p.indexVideoSel = i

        p.indexVideoSel = self.indexVideoSel
        p.nameVideoSel = self.nameVideoSel
        msa.bitsVideo = self.bitsVideo = 1 * p.indexVideoSel
        if debug:
            print (">>>6980<<< bitsVideo: ", msa.bitsVideo)

        msa.bitsBand = 64 * self.switchBand

        msa.bitsFR = 16 * self.switchFR

        msa.bitsTR = 32 * self.switchTR

        msa.bitsPulse = 128 * self.switchPulse

        p.graphAppear = self.graphAppearCM.GetValue()
        p.theme = (DarkTheme, LightTheme)[p.graphAppear == "Light"]
        if 0:
            # these aren't implemented yet
            p.sweepRefresh = self.refreshCB.IsChecked()
            p.dispSweepTime = self.dispSweepTimeCB.IsChecked()
            p.spurTest = self.spurTestCB.IsChecked()
        ##p.atten5 = self.atten5CB.IsChecked()
        p.atten5 = False
        p.stepAttenDB = floatOrEmpty(self.stepAttenBox.GetValue())
        if self.mode == msa.MODE_SA:
            p.sigGenFreq = floatOrEmpty(self.sigGenFreqBox.GetValue())
        elif self.mode == msa.MODE_SATG:
            p.normRev = self.tgReversedChk.GetValue()
            p.tgOffset = floatOrEmpty(self.tgOffsetBox.GetValue())
        else:
            p.invDeg = floatOrEmpty(self.invDegBox.GetValue())
            p.planeExt = [floatOrEmpty(self.planeExtBox.GetValue())]
            p.planeExt += [floatOrEmpty(box.GetValue()) + p.planeExt[0] \
                           for box in self.planeExt2G3GBox]
        p.isCentSpan = self.centSpanRB.GetValue()
        p.nSteps = int(self.stepsBox.GetValue())
        p.continuous = self.continCB.GetValue()


        if self.autoWaitCB.GetValue() == True:   # JGH 11/27/13
            self.calculateWait()
            self.waitBox.SetValue(str(p.wait))
            if debug:
                print ("waitBox: ", self.waitBox.GetValue())
        else:
            p.wait = int(self.waitBox.GetValue())
        if p.wait > 255:
            p.wait = 255
            self.waitBox.SetValue(str(p.wait))
        if p.wait < 0:
            p.wait = 0
            self.waitBox.SetValue(str(p.wait))
##        p.autoWait = self.autoWaitCB.GetValue() #JGH 11/27/13 remmed out

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

        frame.StopScanAndWait()
        cb.SetP(4, msa.bitsVideo + msa.bitsRBW + msa.bitsFR +
                msa.bitsTR + msa.bitsBand + msa.bitsPulse)

        msa.NewScan(p)
        frame.spectrum = None
        specP.results = None

        LogGUIEvent("Apply: new spectrum")
        frame.ReadCalPath()
        frame.ReadCalFreq()
        specP.FullRefresh()

    #--------------------------------------------------------------------------
    # Key focus changed.

    def OnSetFocus(self, event):
        tc = event.GetEventObject()
        if isMac:
            tc.SelectAll()
        self.tcWithFocus = tc
        event.Skip()

    #--------------------------------------------------------------------------
    # Close pressed- save parameters back in prefs and close window.

    def OnClose(self, event=None):
        frame = self.frame
        frame.closeMenuItem.Enable(False)
        self.prefs.sweepWinPos = self.GetPosition().Get()
        self.Destroy()
        frame.sweepDlg = None

    def OnOK(self, event):
        self.Apply()
        self.OnClose()


#==============================================================================
# The Vertical Scale Parameters dialog window.

class VScaleDialog(wx.Dialog):
    def __init__(self, specP, vScale, pos):
        self.specP = specP
        self.vScale = vScale
        self.prefs = p = specP.prefs
        units = vScale.dataType.units
        wx.Dialog.__init__(self, specP, -1, "Vert %s Scale" % units,
                            pos, wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        c = wx.ALIGN_CENTER
        chb = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM
        cvr = wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT

        # limits entry
        sizerV = wx.BoxSizer(wx.VERTICAL)
        sizerGB = wx.GridBagSizer(10, 8)
        st = wx.StaticText(self, -1, "Top Ref")
        sizerGB.Add(st, (0, 1), flag=cvr)
        self.topRefTC = tc = wx.TextCtrl(self, -1,
                            si(vScale.top, flags=SI_ASCII), size=(80, -1))
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        tc.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        sizerGB.Add(tc, (0, 2), flag=c)
        st = wx.StaticText(self, -1, "Bot Ref")
        sizerGB.Add(st, (1, 1), flag=cvr)
        self.botRefTC = tc = wx.TextCtrl(self, -1,
                            si(vScale.bot, flags=SI_ASCII), size=(80, -1))
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        tc.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        sizerGB.Add(tc, (1, 2), flag=c)
        btn = wx.Button(self, -1, "Auto Scale")
        btn.Bind(wx.EVT_BUTTON, self.OnAutoScale)
        sizerGB.Add(btn, (2, 2), flag=c)

        # graph data select
        st = wx.StaticText(self, -1, "Graph Data")
        sizerGB.Add(st, (0, 4), flag=chb)
        typeList = traceTypesLists[msa.mode]
        choices = [ty.desc for ty in typeList]
        i = min(vScale.typeIndex, len(choices)-1)
        cbox = wx.ComboBox(self, -1, choices[i], (0, 0), (200, -1), choices)
        cbox.SetStringSelection(choices[i])
        self.typeSelCB = cbox
        self.Bind(wx.EVT_COMBOBOX, self.OnSelectType, cbox)
        sizerGB.Add(cbox, (1, 4), flag=c)
        self.MaxHoldChk = chk = wx.CheckBox(self, -1, "Max Hold")
        chk.SetValue(vScale.maxHold)
        chk.Bind(wx.EVT_CHECKBOX ,self.OnMaxHold)
        sizerGB.Add(chk, (2, 4), flag=c)
        sizerGB.AddGrowableCol(3)

        # TODO: VScale primary trace entry
        # TODO: VScale priority entry
        sizerV.Add(sizerGB, 0, wx.EXPAND|wx.ALL, 20)

        # Cancel and OK buttons
        butSizer = wx.BoxSizer(wx.HORIZONTAL)
        butSizer.Add((0, 0), 0, wx.EXPAND)
        btn = wx.Button(self, wx.ID_CANCEL)
        butSizer.Add(btn, 0, wx.ALL, 5)
        btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        butSizer.Add(btn, 0, wx.ALL, 5)
        sizerV.Add(butSizer, 0, wx.ALIGN_RIGHT)

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if pos == wx.DefaultPosition:
            self.Center()

    #--------------------------------------------------------------------------
    # Update vert scale parameters from dialog.

    def Update(self):
        specP = self.specP
        vScale = self.vScale
        vScale.top = floatSI(self.topRefTC.GetValue())
        vScale.bot = floatSI(self.botRefTC.GetValue())
        specP.frame.DrawTraces()
        specP.FullRefresh()

    #--------------------------------------------------------------------------
    # Key focus changed.

    def OnSetFocus(self, event):
        if isMac:
            tc = event.GetEventObject()
            tc.SelectAll()
        event.Skip()

    def OnKillFocus(self, event):
        self.Update()
        event.Skip()

    #--------------------------------------------------------------------------
    # Auto Scale pressed- calculate new top, bottom values.

    def OnAutoScale(self, event):
        specP = self.specP
        vScale = self.vScale
        vScale.AutoScale(self.specP.frame)
        self.topRefTC.SetValue(si(vScale.top, flags=SI_ASCII))
        self.botRefTC.SetValue(si(vScale.bot, flags=SI_ASCII))
        specP.frame.DrawTraces()
        specP.FullRefresh()

    def OnMaxHold(self, event):
        specP = self.specP
        vScale = self.vScale
        vScale.maxHold = hold = self.MaxHoldChk.GetValue()
        name = vScale.dataType.name
        trace = specP.traces[name]
        trace.maxHold = hold
        trace.max = False

    #--------------------------------------------------------------------------
    # A graph data type selected- if new, remember it and run auto scale.

    def OnSelectType(self, event):
        vScale = self.vScale
        i = self.typeSelCB.GetSelection()

        if i != vScale.typeIndex:
            # have chosen a new data type: perform auto-scale
            vScale.typeIndex = i
            vScale.dataType = dataType = traceTypesLists[msa.mode][i]
            vScale.top = self.top = dataType.top
            vScale.bot = self.bot = dataType.bot
            if self.top == 0 and self.bot == 0:
                self.OnAutoScale(event)
            else:
                self.topRefTC.SetValue(si(self.top, flags=SI_ASCII))
                self.botRefTC.SetValue(si(self.bot, flags=SI_ASCII))
                self.Update()
        else:
            self.Update()


#==============================================================================
# A Reference line. Created by copying another spectrum.

class Ref(Spectrum):
    def __init__(self, refNum):
        self.refNum = refNum
        self.aColor = None
        self.bColor = None
        self.aWidth = 1
        self.bWidth = 1
        self.mathMode = 0

    @classmethod
    def FromSpectrum(cls, refNum, spectrum, vScale):
        this = cls(refNum)
        this.spectrum = dcopy.deepcopy(spectrum)
        this.vScale = vScale
        ##this.aColor = vColors[refNum]
        return this


#==============================================================================
# The Reference Line dialog box.

class RefDialog(wx.Dialog):
    def __init__(self, frame, refNum):
        self.frame = frame
        self.refNum = refNum
        self.prefs = p = frame.prefs
        self.ref = ref = frame.refs.get(refNum)
        pos = p.get("refWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1,
                            "Reference Line %d Specification" % refNum, pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        sizerV = wx.BoxSizer(wx.VERTICAL)
        c = wx.ALIGN_CENTER
        chb = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM

        # instructions
        st = wx.StaticText(self, -1, \
        "You may create reference lines from fixed values, the current "\
        "data, or by simulating an RLC circuit. You may select to graph the "\
        "reference and the input data, or to graph the result of adding or "\
        "subtracting them.")
        st.Wrap(600)
        sizerV.Add(st, 0, c|wx.ALL|wx.EXPAND, 10)

        # reference label box
        sizerH1 = wx.BoxSizer(wx.HORIZONTAL)
        sizerH1.Add(wx.StaticText(self, -1, "Name:"), 0, c|wx.RIGHT, 4)
        name = "R%d" % refNum
        if ref:
            name = ref.name
        self.nameBox = tc = wx.TextCtrl(self, -1, name, size=(80, -1))
        tc.SetFocus()
        tc.SetInsertionPoint(len(name))
        sizerH1.Add(tc, 0, c)
        sizerV.Add(sizerH1, 0, c|wx.ALL, 5)

        # reference mode
        self.mode = 1
        choices = ["No Reference Lines", "Use Current Data", "Use Fixed Value"]
        if msa.mode >= msa.MODE_VNATran:
            choices += ["Use RLC Circuit"]
        self.modeRB = rb = wx.RadioBox(self, -1, choices=choices,
                        majorDimension=3, style=wx.RA_HORIZONTAL)
        rb.SetSelection(self.mode)
        self.Bind(wx.EVT_RADIOBOX, self.SetMode, rb)
        sizerV.Add(rb, 0, c|wx.ALL, 10)

        # right trace
        self.traceEns = [False, False]
        sizerG1 = wx.GridBagSizer()
        self.traceEns[0] = chk = wx.CheckBox(self, -1, "Do Trace for Right Axis")
        chk.SetValue(True)
        sizerG1.Add(chk, (0, 0), (1, 3), c|wx.BOTTOM, 5)
        sizerG1.Add(wx.StaticText(self, -1, "Color"), (1, 0), flag=chb)
        nColors = len(p.theme.vColors)
        color = p.theme.vColors[(2*refNum) % nColors].Get(False)
        cs = csel.ColourSelect(self, -1, "", color, size=(45, 25))
        self.colSelA = cs
        cs.Bind(csel.EVT_COLOURSELECT, self.OnSelectColorA)
        sizerG1.Add(cs, (2, 0), flag=c)
        sizerG1.Add(wx.StaticText(self, -1, "Width"), (1, 1), flag=chb)
        choices = [str(i) for i in range(1, 7)]
        cbox = wx.ComboBox(self, -1, "1", (0, 0), (50, -1), choices)
        self.widthACB = cbox
        if ref:
            cbox.SetValue(str(ref.aWidth))
        sizerG1.Add(cbox, (2, 1), (1, 1), c|wx.LEFT|wx.RIGHT, 10)
        sizerG1.Add(wx.StaticText(self, -1, "Value"), (1, 2), flag=chb)
        self.valueABox = tc = wx.TextCtrl(self, -1, "", size=(80, -1))
        tc.Enable(False)
        sizerG1.Add(tc, (2, 2), flag=c)
        sizerG1.Add((1, 10), (3, 0))

        if msa.mode >= msa.MODE_VNATran:
            # left trace
            chk = wx.CheckBox(self, -1, "Do Trace for Left Axis")
            self.traceEns[1] = chk
            chk.SetValue(True)
            sizerG1.Add(chk, (4, 0), (1, 3), c|wx.BOTTOM|wx.TOP, 5)
            sizerG1.Add(wx.StaticText(self, -1, "Color"), (5, 0), flag=chb)
            color = p.theme.vColors[(2*refNum+1) % nColors].Get(False)
            cs = csel.ColourSelect(self, -1, "", color, size=(45, 25))
            self.colSelB = cs
            cs.Bind(csel.EVT_COLOURSELECT, self.OnSelectColorB)
            sizerG1.Add(cs, (6, 0), flag=c)
            sizerG1.Add(wx.StaticText(self, -1, "Width"), (5, 1), flag=chb)
            choices = [str(i) for i in range(1, 7)]
            cbox = wx.ComboBox(self, -1, "1", (0, 0), (50, -1), choices)
            self.widthBCB = cbox
            if ref:
                cbox.SetValue(str(ref.bWidth))
            sizerG1.Add(cbox, (6, 1), (1, 1), c|wx.LEFT|wx.RIGHT, 10)
            sizerG1.Add(wx.StaticText(self, -1, "Value"), (5, 2), flag=chb)
            self.valueBBox = tc = wx.TextCtrl(self, -1, "", size=(80, -1))
            tc.Enable(False)
            sizerG1.Add(tc, (6, 2), flag=c)

        # graph options
        if refNum == 1:
            choices = ["Data and Ref", "Data + Ref", "Data - Ref",
                       "Ref - Data"]
            self.graphOptRB = rb = wx.RadioBox(self, -1, "Graph Options",
                            choices=choices, style=wx.RA_VERTICAL)
            if ref:
                rb.SetSelection(ref.mathMode)
            sizerG1.Add(rb, (0, 4), (6, 1), c)
            sizerG1.AddGrowableCol(3)
        sizerV.Add(sizerG1, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 30)

        # Cancel and OK buttons
        butSizer = wx.BoxSizer(wx.HORIZONTAL)
        butSizer.Add((0, 0), 0, wx.EXPAND)
        btn = wx.Button(self, wx.ID_CANCEL)
        butSizer.Add(btn, 0, wx.ALL, 5)
        btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        butSizer.Add(btn, 0, wx.ALL, 5)
        sizerV.Add(butSizer, 0, wx.ALIGN_RIGHT|wx.ALL, 10)

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if pos == wx.DefaultPosition:
            self.Center()

    #--------------------------------------------------------------------------
    # Set mode: 0=No Ref Lines, 1=Current Data, 2=Fixed Value.

    def SetMode(self, event):
        self.mode = mode = event.GetInt()
        self.nameBox.Enable(mode > 0)
        self.traceEns[0].Enable(mode > 0)
        self.colSelA.Enable(mode > 0)
        self.widthACB.Enable(mode > 0)
        self.valueABox.Enable(mode > 1)
        if msa.mode >= msa.MODE_VNATran:
            self.traceEns[1].Enable(mode > 0)
            self.colSelB.Enable(mode > 0)
            self.widthBCB.Enable(mode > 0)
            self.valueBBox.Enable(mode > 1)
        if self.refNum == 1:
            self.graphOptRB.Enable(mode > 0)

    #--------------------------------------------------------------------------
    # Got a result from color chooser- change corresponding vColor preference.

    def OnSelectColorA(self, event):
        vColors = self.prefs.theme.vColors
        nColors = len(vColors)
        #ref = self.refs.get(self.refNum).iColor #JGH 2/10/14 (ref not used)
        vColors[(2*self.refNum) % nColors] = wx.Colour(*event.GetValue())

    def OnSelectColorB(self, event):
        vColors = self.prefs.theme.vColors
        nColors = len(vColors)
        vColors[(2*self.refNum+1) % nColors] = wx.Colour(*event.GetValue())

    def OnHelp(self, event):
        pass


#==============================================================================
# The Perform Calibration dialog box.

class PerformCalDialog(MainDialog):
    def __init__(self, frame):
        self.frame = frame
        p = frame.prefs
        pos = p.get("perfCalWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, "Perform Calibration", pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        self.sizerV = sizerV = wx.BoxSizer(wx.VERTICAL)
        c = wx.ALIGN_CENTER

        # text box, filled in by Update()
        self.textBox = wx.StaticText(self, -1, "")
        sizerV.Add(self.textBox, 0, wx.TOP|wx.LEFT|wx.RIGHT, 10)

        # optional thru delay
        self.calThruBox = None
        # DISABLED- expected to be set up beforehand in Sweep dialog
        if msa.mode == msa.MODE_VNATran: # EON Jan 10 2014
            sizerH = wx.BoxSizer(wx.HORIZONTAL)
            st = wx.StaticText(self, -1,
                    "Delay of Calibration Through Connection:")
            sizerH.Add(st, 0, c|wx.RIGHT, 8)
            delText = "%g" % p.get("calThruDelay", 0)
            tc = wx.TextCtrl(self, -1, delText, size=(40, -1))
            self.calThruBox = tc
            tc.SetInsertionPoint(len(delText))
            sizerH.Add(tc, 0, c)
            sizerH.Add(wx.StaticText(self, -1, "ns"), 0, c|wx.LEFT, 5)
            sizerV.Add(sizerH, 0, wx.LEFT, 20)

        if 0 and msa.mode == MSA.MODE_VNARefl: #EON add 0 to disable 12/24/2013
            # test fixture
            sizerH1 = wx.BoxSizer(wx.HORIZONTAL)
            sizerH1.Add((1, 1), 1, wx.EXPAND)
            series = p.get("isSeriesFix", True)
            shunt = p.get("isShuntFix", False)
            sizerH1.Add(self.FixtureBox(series, shunt), 0, wx.ALIGN_TOP)
            sizerH1.Add((1, 1), 1, wx.EXPAND)
            sizerV.Add(sizerH1, 0, c)

        #  buttons
        sizerG1 = wx.GridBagSizer(10, 10)
        self.perfBandCalBtn = btn = wx.Button(self, -1, "Perform Band Cal")
        # Start EON Jan 10 2014
        if msa.mode == msa.MODE_VNATran:
            btn.Bind(wx.EVT_BUTTON, self.OnPerformBandCal)
        else:
            btn.Bind(wx.EVT_BUTTON, self.ReflBandCalDialog)
        # End EON Jan 10 2014
        sizerG1.Add(btn, (0, 0), flag=c)
        self.saveAsBaseBtn = btn = wx.Button(self, -1, "Save As Base")
        btn.Bind(wx.EVT_BUTTON, self.OnSaveAsBase)
        sizerG1.Add(btn, (1, 0), flag=c)
        self.clearBandBtn = btn = wx.Button(self, -1, "Clear Band Cal")
        btn.Bind(wx.EVT_BUTTON, self.OnClearBandCal)
        sizerG1.Add(btn, (0, 1), flag=c)
        self.clearBaseBtn =  btn = wx.Button(self, -1, "Clear Base Cal")
        btn.Bind(wx.EVT_BUTTON, self.OnClearBaseCal)
        sizerG1.Add(btn, (1, 1), flag=c)
        self.helpBtn = btn = wx.Button(self, -1, "Help")
        btn.Bind(wx.EVT_BUTTON, self.OnHelp)
        sizerG1.Add(btn, (0, 3)) # EON Jan 22, 2014
        self.okBtn = btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        sizerG1.Add(btn, (1, 3)) # EON Jan 22, 2014
        sizerV.Add(sizerG1, 0, wx.EXPAND|wx.ALL, 10)
        sizerG1.AddGrowableCol(2) # EON Jan 22, 2014

        self.SetSizer(sizerV)
        self.Update()
        if pos == wx.DefaultPosition:
            self.Center()
        self.Bind(wx.EVT_CLOSE, self.OnClose)

    #--------------------------------------------------------------------------
    # Update help and info text and button enables after a change.

    def Update(self):
        frame = self.frame
        p = frame.prefs
        msg = "Connect TG output and MSA input to test fixture and attach "\
                "proper cal standards."
        if msa.mode == msa.MODE_VNATran:
            msg = "TG output must have THROUGH connection to MSA input."
        bandCalInfo = "(none)"
        spec = msa.bandCal
        # Start EON Jan 10 2014
        if spec:
            bandCalInfo = "Performed %s" % spec.desc
        baseCalInfo = "(none)"
        spec = msa.baseCal
        if spec:
            baseCalInfo = "Performed %s" % spec.desc
        # End EON Jan 10 2014
        self.textBox.SetLabel( \
        "            The MSA is currently in Path %d.\n\n"\
        "MSA calibrations are not saved separately for different paths. If "\
        "the current path is not the one for which the calibration will be "\
        "used, close this window and change the path selection. VIDEO FILTER "\
        "should be set to NARROW bandwidth for maximum smoothing. %s\n\n"\
        "Band Sweep calibration is run at the same frequency points at which "\
        "it will be used.\n\n"\
        "   Band: %s\n\n"\
        "You may save the current Band calibration as a Base calibration, to "\
        "be used as a coarse reference when the Band calibration is not "\
        "current.\n\n"\
        "   Base: %s \n\n"\
        % (p.indexRBWSel + 1, msg, bandCalInfo, baseCalInfo))
        self.textBox.Wrap(600)

        self.sizerV.Fit(self)
        frame.RefreshAllParms()

    #--------------------------------------------------------------------------
    # Perform Band Cal pressed- do a scan in calibration mode.

    def OnPerformBandCal(self, event):
        frame = self.frame
        p = frame.prefs
        if msa.IsScanning():
            msa.StopScan()
        else:
## Start EON Jan 10 2014
##            if msa.mode == MSA.MODE_VNARefl:
##                spec = frame.spectrum
##                p.isSeriesFix = self.seriesRB.GetValue()
##                p.isShuntFix = self.shuntRB.GetValue()
##                if spec:
##                    spec.isSeriesFix = p.isSeriesFix
##                    spec.isShuntFix = p.isShuntFix
## End EON Jan 10 2014
            msa.calibrating = True
            ##savePlaneExt = p.planeExt
            if self.calThruBox:
                p.calThruDelay = floatOrEmpty(self.calThruBox.GetValue())
                p.planeExt = 3*[p.calThruDelay]
            self.perfBandCalBtn.SetLabel("Cancel")
            self.EnableButtons(False)
            frame.DoExactlyOneScan()
            frame.WaitForStop()
            self.perfBandCalBtn.SetLabel("Perform Band Cal")
            self.EnableButtons(True)
            msa.calibrating = False
            ##p.planeExt = savePlaneExt
            frame.SetBandCal(dcopy.deepcopy(frame.spectrum))
            frame.SetCalLevel(2)
            self.Update()

    # Start EON Jan 10 2014
    #--------------------------------------------------------------------------
    # Reflection Band Cal

    def ReflBandCalDialog(self, event):
        p = self.frame.prefs
        dlg = PerformReflCalDialog(self.frame, self)
        if dlg.ShowModal() == wx.ID_OK:
            p.perfReflCalpWinPos = dlg.GetPosition().Get()
    # End EON Jan 10 2014

    #--------------------------------------------------------------------------
    # Save As Base pressed- copy band cal data to base.

    def OnSaveAsBase(self, event):
        self.frame.CopyBandToBase()
        self.Update()

    #--------------------------------------------------------------------------
    # Clear Band or Clear Base Cal pressed- clear corresponding data.

    def OnClearBandCal(self, event):
        frame = self.frame
        if msa.bandCal:
            frame.SetBandCal(None)
            if msa.baseCal:
                frame.SetCalLevel(1)
            else:
                frame.SetCalLevel(0)
            self.Update()

    def OnClearBaseCal(self, event):
        frame = self.frame
        if msa.baseCal:
            msa.baseCal = None
            # Start EON Jan 10 2014
            try:
                os.unlink(frame.baseCalFileName)
            except:
                pass
            # End EON Jan 10 2014
            if not msa.bandCal:
                frame.SetCalLevel(0)
            self.Update()

    #--------------------------------------------------------------------------
    # Help pressed- bring up help.

    def OnHelp(self, event):
        p = self.frame.prefs
        dlg = OperCalHelpDialog(self.frame)
        if dlg.ShowModal() == wx.ID_OK:
            p.operCalHelpWinPos = dlg.GetPosition().Get()

    #--------------------------------------------------------------------------
    # Disable buttons while running calibration.

    def EnableButtons(self, enable):
        self.saveAsBaseBtn.Enable(enable)
        self.clearBandBtn.Enable(enable)
        self.clearBaseBtn.Enable(enable)
        self.okBtn.Enable(enable)

    #--------------------------------------------------------------------------
    # Close- quit any running calibration.

    def OnClose(self, event):
        if msa.IsScanning():
            msa.StopScan()
            event.Skip()

#==============================================================================
# A Help dialog for Operating Cal dialog.

class OperCalHelpDialog(wx.Dialog):
    def __init__(self, frame):
        p = frame.prefs
        pos = p.get("operCalHelpWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, "Perform Calibration Help", pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        sizerV = wx.BoxSizer(wx.VERTICAL)
        self.SetBackgroundColour("WHITE")
        st = wx.StaticText(self, -1, "Band calibration is performed at the "\
        "frequency points of immediate interest and is used only as long as "\
        "the sweep matches those points. Base calibration is performed over "\
        "a broad frequency range, to be interpolated to the current sweep "\
        "frequencies when there is no current band calibration. To create a "\
        "Base calibration you perform a Band calibration and save it as a "\
        "Base calibration. It is intended as a convenient coarse reference, "\
        "especially when phase precision is not required. In Transmission "\
        "Mode, Base calibrations are saved in a file for use in future "\
        "sessions. In Transmision Mode you also specify the time delay of "\
        "the calibration Through connection, which is ideally zero but may "\
        "be greater if you need to use an adapter.", pos=(10, 10))
        st.Wrap(600)
        sizerV.Add(st, 0, wx.ALL, 5)

        # OK button
        butSizer = wx.BoxSizer(wx.HORIZONTAL)
        butSizer.Add((0, 0), 0, wx.EXPAND)
        btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        butSizer.Add(btn, 0, wx.ALL, 5)
        sizerV.Add(butSizer, 0, wx.ALIGN_RIGHT)

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if pos == wx.DefaultPosition:
            self.Center()

# Start EON Jan 10 2014
#==============================================================================
# The Perform Reflection Calibration dialog box.

class PerformReflCalDialog(wx.Dialog):
    def __init__(self, frame, calDialog):
        self.frame = frame
        self.readSpectrum = False
        self.saveSpectrum = False
        self.calDialog = calDialog
        p = frame.prefs
        self.prefs = p
        pos = p.get("perfReflCalWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, "Reflection Calibration", pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        self.sizerH = sizerH = wx.BoxSizer(wx.HORIZONTAL)
        c = wx.ALIGN_CENTER

        self.isSeriesFix = p.get("isSeriesFix", False)
        self.isShuntFix = p.get("isShuntFix", False)
        self.isReflBridge = (not self.isSeriesFix) and (not self.isShuntFix)
        self.isRefCal = p.get("isRefCal", True)
        self.isOslCal = not self.isRefCal
        self.oslCal = None
        self.btnList = []
        p.get("openSpec", "RLC[S,C0,D0]")
        p.get("shortSpec", "RLC[P,R0,L0,D0]")
        p.get("loadSpec", "RLC[P,R50,C0]")

        self.sizerV1 = sizerV = wx.BoxSizer(wx.VERTICAL)
        txt = "Specify the fixture used. For a\n"\
              "Shunt fixture, you may specify a\n"\
              "a delay time."
        self.textBox1 = wx.StaticText(self, -1, txt)
        sizerV.Add(self.textBox1, 0, wx.TOP|wx.LEFT|wx.RIGHT, 10)

        btn = wx.Button(self, -1, "Help")
        self.btnList.append(btn)
        btn.Bind(wx.EVT_BUTTON, self.onReflFixHelp)
        sizerV.Add(btn, 0, c|wx.ALL, 5)

        sizerH0 = wx.BoxSizer(wx.HORIZONTAL)
        txt = wx.StaticText(self, -1, "Fixture R0 (ohms)")
        sizerH0.Add(txt, 0, wx.EXPAND|wx.ALL|wx.ALIGN_CENTER_VERTICAL, 10)
        self.fixtureR0Box = tc = wx.TextCtrl(self, -1, p.get("fixtureR0", "50"), size=(40, -1))
        sizerH0.Add(tc, 0, wx.EXPAND|wx.ALL|wx.ALIGN_CENTER_VERTICAL, 10)
        sizerV.Add(sizerH0, 0, c|wx.ALL, 5)

        fixTypeTitle = wx.StaticBox(self, -1, "Fixture Type")
        self.fixTypeSizer = wx.StaticBoxSizer(fixTypeTitle, wx.VERTICAL)
        fixTypeBoxSizer = wx.BoxSizer(wx.VERTICAL)

        self.bridgeRb = rb = wx.RadioButton(self, -1, "Reflection Bridge", style=wx.RB_SINGLE)
        self.btnList.append(rb)
        rb.Bind(wx.EVT_RADIOBUTTON, self.BridgeUpd)
        fixTypeBoxSizer.Add(rb, 0, wx.ALL, 2)

        self.seriesRb = rb = wx.RadioButton(self, -1, "Series", style=wx.RB_SINGLE)
        self.btnList.append(rb)
        rb.Bind(wx.EVT_RADIOBUTTON, self.SeriesUpd)
        fixTypeBoxSizer.Add(rb, 0, wx.ALL, 2)

        self.shuntRb = rb = wx.RadioButton(self, -1, "Shunt", style=wx.RB_SINGLE)
        self.btnList.append(rb)
        rb.Bind(wx.EVT_RADIOBUTTON, self.ShuntUpd)
        fixTypeBoxSizer.Add(rb, 0, wx.ALL, 2)

        self.conDelayText = txt = wx.StaticText(self, -1, "Connect Delay (ns)")
        fixTypeBoxSizer.Add(txt, 0, c|wx.ALL, 2)
        self.conDelay = tc = wx.TextCtrl(self, -1, p.get("shuntConDelay", "0"), size=(60, -1))
        fixTypeBoxSizer.Add(tc, 0, c|wx.ALL, 2)

        self.fixTypeSizer.Add(fixTypeBoxSizer, 0, c|wx.ALL, 5)
        sizerV.Add(self.fixTypeSizer, 0, c|wx.ALL, 5)

        sizerH1 = wx.BoxSizer(wx.HORIZONTAL)

        self.doneBtn = btn = wx.Button(self, -1, "Done")
        self.btnList.append(btn)
        btn.Bind(wx.EVT_BUTTON, self.onDone)
        sizerH1.Add(btn, 0, c|wx.ALL, 5)

        self.cancelBtn = btn = wx.Button(self, -1, "Cancel")
        self.btnList.append(btn)
        btn.Bind(wx.EVT_BUTTON, self.OnClose)
        sizerH1.Add(btn, 0, c|wx.ALL, 5)

        sizerV.Add(sizerH1, 0, c|wx.ALL, 5)

        sizerH.Add(sizerV, 0, wx.EXPAND|wx.ALL, 10)

        self.sizerV2 = sizerV = wx.BoxSizer(wx.VERTICAL)
        txt = "Specify the desired calibration.\n"\
              "For OSL, specify characteristics\n"\
               "of the standards."
        self.textBox2 = wx.StaticText(self, -1, txt)
        sizerV.Add(self.textBox2, 0, wx.TOP|wx.LEFT|wx.RIGHT, 10)
        btn = wx.Button(self, -1, "Help")
        self.btnList.append(btn)
        btn.Bind(wx.EVT_BUTTON, self.onReflCalHelp)
        sizerV.Add(btn, 0, c|wx.ALL, 5)

        sizerV.AddSpacer(10)
        self.OslCalRb = rb = wx.RadioButton(self, -1, "Full OSL")
        self.btnList.append(rb)
        rb.Bind(wx.EVT_RADIOBUTTON, self.OslUpd)
        sizerV.Add(rb, 0, wx.ALL, 2)

        self.RefCalRb = rb = wx.RadioButton(self, -1, "Reference Cal")
        self.btnList.append(rb)
        rb.Bind(wx.EVT_RADIOBUTTON, self.RefUpd)
        sizerV.Add(rb, 0, wx.ALL, 2)
        sizerV.AddSpacer(10)

        c = wx.ALIGN_CENTER_VERTICAL
        sizerGb = wx.GridBagSizer(20, 10)
        doneSize = (30,-1)
        self.openDone = txt = wx.StaticText(self, -1, "", size=doneSize)
        sizerGb.Add(txt, (0, 0), flag=c)
        self.openBtn = btn = wx.Button(self, -1, "Perform Open")
        self.btnList.append(btn)
        btn.Bind(wx.EVT_BUTTON, self.OnOpen)
        sizerGb.Add(btn, (0, 1))
        self.openSpecTxt = txt = wx.TextCtrl(self, -1, "")
        txt.SetEditable(True)
        txt.Enable()
        txt.SetBackgroundColour(wx.WHITE)
        sizerGb.Add(txt, (0, 2))

        self.shortDone = txt = wx.StaticText(self, -1, "", size=doneSize)
        sizerGb.Add(txt, (1, 0), flag=c)
        self.shortBtn = btn = wx.Button(self, -1, "Perform Short")
        self.btnList.append(btn)
        btn.Bind(wx.EVT_BUTTON, self.OnShort)
        sizerGb.Add(btn, (1, 1))
        self.shortSpecTxt = txt = wx.TextCtrl(self, -1, "")
        txt.SetEditable(False)
        txt.Disable()
        txt.SetBackgroundColour(wx.WHITE)
        sizerGb.Add(txt, (1, 2))

        self.loadDone = txt = wx.StaticText(self, -1, "", size=doneSize)
        sizerGb.Add(txt, (2, 0), flag=c)
        self.loadBtn = btn = wx.Button(self, -1, "Perform Load")
        self.btnList.append(btn)
        btn.Bind(wx.EVT_BUTTON, self.OnLoad)
        sizerGb.Add(btn, (2, 1))
        self.loadSpecTxt = txt = wx.TextCtrl(self, -1, "")
        txt.SetEditable(True)
        txt.Disable()
        txt.SetBackgroundColour(wx.WHITE)
        sizerGb.Add(txt, (2, 2))
        sizerV.Add(sizerGb, 0, wx.ALL, 2)

        st = wx.StaticText(self, -1, "Calibrations Standards")
        sizerV.Add(st, 0, wx.ALL|wx.ALIGN_CENTER, 5)
        self.sizerV1 = sizerV

        loads = ['Ideal 50 ohms','Custom']
        self.loadBox = cb = wx.ComboBox(self, -1, choices=loads, style=wx.CB_READONLY)
        cb.Bind(wx.EVT_COMBOBOX, self.OnLoadBox)
        calStd = p.get("calStandard", 0)
        cb.SetSelection(calStd)
        if calStd != 0:
            self.openSpecTxt.SetValue(p.get("openSpec", ""))
            self.shortSpecTxt.SetValue(p.get("shortSpec", ""))
            self.loadSpecTxt.SetValue(p.get("loadSpec", ""))
        cb.SetBackgroundColour(wx.WHITE)
        sizerV.Add(cb, 0, wx.ALL|wx.ALIGN_CENTER, 5)

        txt = "50 ohms, good for cal plane\n"\
              "on back of SMA connectors."
        st = wx.StaticText(self, -1, txt)
        sizerV.Add(st, 0, wx.ALL|wx.ALIGN_CENTER, 5)

        sizerH.Add(sizerV, 0, wx.EXPAND|wx.ALL, 10)

        self.SetSizer(sizerH)
        self.Update()
        if pos == wx.DefaultPosition:
            self.Center()
        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def OnLoadBox(self,event):
        self.Update()

    def BridgeUpd(self, event):
        if self.bridgeRb.GetValue():
            self.isReflBridge = True
            self.isSeriesFix = False
            self.isShuntFix = False
        self.Update()

    def SeriesUpd(self, event):
        if self.seriesRb.GetValue():
            self.isSeriesFix = True
            self.isShuntFix = False
            self.isReflBridge = False
        self.Update()

    def ShuntUpd(self, event):
        if self.shuntRb.GetValue():
            self.isShuntFix = True
            self.isReflBridge = False
            self.isSeriesFix = False
        self.Update()

    def OslUpd(self, event):
        if self.OslCalRb.GetValue():
            self.isOslCal = True
            self.isRefCal = False
        self.Update()

    def RefUpd(self, event):
        if self.RefCalRb.GetValue():
            self.isRefCal = True
            self.isOslCal = False
        self.Update()

    def OslCal(self, spectrum):
        oslCal = self.oslCal
        isLogF = self.frame.prefs.isLogF
        upd = False
        if oslCal == None:
            oslCal = OslCal(self.frame.specP.title, msa.indexRBWSel + 1, isLogF,
                            msa._fStart, msa._fStop, msa._nSteps, msa._freqs)
            upd = True
        else:
            if oslCal.Changed(isLogF, msa._fStart, msa._fStop, msa._nSteps):
                oslCal = OslCal(self.frame.specP.title, msa.indexRBWSel + 1, isLogF,
                                msa._fStart, msa._fStop, msa._nSteps, msa._freqs)
                upd = True
        if upd:
            self.oslCal = oslCal
            msa.oslCal = oslCal
        return oslCal

    def CalScan(self):
        frame = self.frame
        p = self.prefs
        spectrum = frame.spectrum
        if spectrum:
            spectrum.isSeriesFix = p.isSeriesFix
            spectrum.isShuntFix = p.isShuntFix
        msa.calibrating = True
        wait = p.wait
        p.wait = calWait # EON Jan 29, 2014
        frame.DoExactlyOneScan()
        frame.WaitForStop()
        p.wait = wait
        msa.calibrating = False
        ##p.planeExt = savePlaneExt
        return frame.spectrum

    def ReadSpectrum(self, fileName):
        frame = self.frame
        p = self.prefs
        frame.spectrum = spectrum = Spectrum.FromS1PFile(fileName + ".s1p")
        specP = frame.specP
        specP.h0 = p.fStart = spectrum.Fmhz[0]
        specP.h1 = p.fStop  = spectrum.Fmhz[-1]
        p.nSteps = spectrum.nSteps
        frame.RefreshAllParms()
        frame.DrawTraces()
        f = open(fileName + ".txt", "r")
        f.readline()
        f.readline()
        for line in f:
            line = line.strip()
            (i, Fmhz, Sdb, magdata, tmp, Sdeg, phasedata) = re.split(" +", line)
            i = int(i)
            spectrum.magdata[i] = int(magdata)
            spectrum.phasedata[i] = int(phasedata)
#            spectrum.Fmhz[i] = float(Fmhz)
#            spectrum.Mdb[i] = float(Mdb)
#            spectrum.Mdeg[i] = float(Mdeg)
        f.close()
        return spectrum

    def OnOpen(self, event):
        if msa.IsScanning():
            msa.StopScan()
        else:
            self.EnableButtons(False)
            self.openBtn.SetLabel("Abort Cal")
            self.openBtn.Enable(True)
            if self.readSpectrum:
                spectrum = self.ReadSpectrum('open')
            else:
                spectrum = self.CalScan()
            oslCal = self.OslCal(spectrum)
            if self.saveSpectrum:
                spectrum.WriteInput("open.txt",self.prefs)
                spectrum.WriteS1P("open.s1p",self.prefs)
            for i in range (0, spectrum.nSteps + 1):
                oslCal.OSLcalOpen[i] = (spectrum.Sdb[i], spectrum.Sdeg[i])
            oslCal.OSLdoneO = True
            self.openBtn.SetLabel("Perform Open")
            self.openDone.SetLabel("Done");
            self.EnableButtons(True)
            if self.isRefCal:
                self.onDone(event)
            else:
                self.Update()

    def OnShort(self, event):
        if msa.IsScanning():
            msa.StopScan()
        else:
            self.EnableButtons(False)
            self.shortBtn.SetLabel("Abort Cal")
            self.shortBtn.Enable(True)
            msa.calibrating = True
            if self.readSpectrum:
                spectrum = self.ReadSpectrum('short')
            else:
                spectrum = self.CalScan()
            oslCal = self.OslCal(spectrum)
            if self.saveSpectrum:
                spectrum.WriteInput("short.txt",self.prefs)
                spectrum.WriteS1P("short.s1p",self.prefs)
            for i in range (0, spectrum.nSteps + 1):
                oslCal.OSLcalShort[i] = (spectrum.Mdb[i], spectrum.Mdeg[i])
            oslCal.OSLdoneS = True
            self.shortBtn.SetLabel("Perform Short")
            self.shortDone.SetLabel("Done");
            self.EnableButtons(True)
            if self.isRefCal:
                self.onDone(event)
            else:
                self.Update()

    def OnLoad(self, event):
        if msa.IsScanning():
            msa.StopScan()
        else:
            self.EnableButtons(False)
            self.loadBtn.SetLabel("Abort Cal")
            self.loadBtn.Enable(True)
            if self.readSpectrum:
                spectrum = self.ReadSpectrum('load')
            else:
                spectrum = self.CalScan()
            oslCal = self.OslCal(spectrum)
            if self.saveSpectrum:
                spectrum.WriteInput("load.txt",self.prefs)
                spectrum.WriteS1P("load.s1p",self.prefs)
            for i in range (0, spectrum.nSteps + 1):
                oslCal.OSLcalLoad[i] = (spectrum.Mdb[i], spectrum.Mdeg[i])
            oslCal.OSLdoneL = True
            self.loadBtn.SetLabel("Perform Load")
            self.loadDone.SetLabel("Done");
            self.EnableButtons(True)
            self.Update()

    def onDone(self, event):
        # User has performed the desired calibrations.  The caller must now
        # calculate/set up the calibration data.  But either the Open or
        # Short must have been performed.  We know what was done based on
        # OSLdoneO, OSLdoneS and OSdoneL
        # Retrieve test fixture info

#     #OSLcal.Full, "value? OSLFullval$"  'ver116-4k
        OSLFull = self.OslCalRb.GetValue()
# if doing full OSL, we treat all fixtures as bridges
#     if OSLFullval$="set" then #OSLcal.Bridge, "set" : #OSLcal.Series, "reset" : #OSLcal.Shunt, "reset"

        oslCal = self.oslCal
        if oslCal == None:
            message ("No Calibration Done") # EON Jan 29, 2014
            return

        if OSLFull:
            self.bridgeRb.SetValue(True)
            self.seriesRb.SetValue(False)
            self.shuntRb.SetValue(False)

#     #OSLcal.Bridge, "value? bridgeVal$"
#     isBridge=0
#     isSeries=0
#     if bridgeVal$="set" then
#         isBridge=1
#         S11JigType$="Reflect"   'bridge
#     else    'must be series or shunt
#         #OSLcal.Series, "value? attachVal$"
#         if attachVal$="set" then
#             S21JigAttach$="Series"
#             isSeries=1
#         else
#             S21JigAttach$="Shunt"
#             #OSLcal.ShuntDelay, "!contents? delayVal$"  'connector delay (ns)
#             S21JigShuntDelay=val(uCompact$(delayVal$))
#         end if
#         S11JigType$="Trans"
#     end if

        isBridge = False
        isSeries = False
        if self.bridgeRb.GetValue():
            isBridge = True
            oslCal.S11JigType = "Reflect"
        else:
            if self.seriesRb.GetValue():
                isSeries = True
                oslCal.S21JigAttach = "Series"
            else:
                oslCal.S21JigAttach = "Shunt"
                oslCal.ShuntDelay = self.conDelay.GetValue()
            oslCal.S11JigType = "Trans"

#     #OSLcal.R0, "!contents? R0$"
#     S11BridgeR0=uValWithMult(R0$) : if S11BridgeR0<=0 then S11BridgeR0=50 : notice "Invalid R0. 50 ohms used."
#         'We now set both S11BridgeR0 and S21JigR0 to the same value. When doing full OSL, the user does not choose the
#         'fixture type so we wouldn't know which one to set if we didn't set both. Certain routines refer to one or the other,
#         'depending on fixture type, but they will get the same value either way. ver116-4j
#     S21JigR0=S11BridgeR0

        S11BridgeR0 = floatSI(self.fixtureR0Box.GetValue())
        if S11BridgeR0 <= 0:
            S11BridgeR0 = 50
            message("Invalid R0. 50 ohms used") # EON Jan 29, 2014
        oslCal.S11BridgeR0 = S11BridgeR0
        oslCal.S21JigR0 = S11BridgeR0

#
#     'Note S11GraphR0 is set in the sweep parameters window
#     OSLcalSum=OSLdoneO+OSLdoneL+OSLdoneS

        calSum = 0
        self.OSLError = False
        if oslCal.OSLdoneO:
            calSum += 1
        if oslCal.OSLdoneS:
            calSum += 1
        if oslCal.OSLdoneL:
            calSum += 1
#
#     'If full OSL, we require all 3 cals to be done. If reference, we quit as soon as one is done. This means
#     'we never leave with 2 cals done.
#     if OSLFullval$="set" then   'set means full OSL. Note if not full we quit as soon as one is done.
#         if OSLcalSum<>3 then notice "You are missing one of the necessary calibrations for full OSL." : wait
#     else
#         if isBridge then    'Be sure reference cal was done
#             didRef=(OSLdoneO or OSLdoneS)
#         else
#             if isSeries then didRef=OSLdoneS else didRef=OSLdoneO
#         end if
#         if didRef=0 then notice "You have not performed the necessary calibration" : wait
#     end if

        didRef = False
        if self.OslCalRb.GetValue():
            if calSum != 3:
                message("For full OSL all references must be scanned.") # EON Jan 29, 2014
                return # EON Jan 29, 2014
        else:
            if isBridge:
                didRef = oslCal.OSLdoneO or oslCal.OSLdoneS
            else:
                if isSeries:
                    didRef = oslCal.OSLdoneS
                else:
                    didRef = oslCal.OSLdoneO
                if not didRef:
                    message("You have not performed the necessary calibration.") # EON Jan 29, 2014
                    return # EON Jan 29, 2014

#         'ver115-3f moved the disables to here, after a possible wait occurs
#     call SetOSLCalCheckboxStatus "disable"    'So nothing gets clicked before dialog closes ver115-3a
#     call SetOSLCalButtonStatus "!disable"
#
#     #OSLcal.stdSet, "selectionindex? OSLLastSelectedCalSet"
#     #OSLcal.OpenSpecs, "!contents? OSLOpenSpec$"
#     #OSLcal.ShortSpecs, "!contents? OSLShortSpec$"
#     #OSLcal.LoadSpecs, "!contents? OSLLoadSpec$"

        oslCal.OslOpenSpec = self.openSpecTxt.GetValue()
        oslCal.OslShortSpec = self.shortSpecTxt.GetValue()
        oslCal.OslLoadSpec = self.loadSpecTxt.GetValue()

#
#     if OSLError then OSLBandNumSteps=-1 'Invalid cal data if math error occurred 'ver116-4b
#     call SignalNoCalInstalled   'ver116-4b 'So new cal will get installed on Restart
#     desiredCalLevel=2   'desire Band Sweep since we just did it
#     call RequireRestart 'So cal gets installed before user proceeds, but we don't install it here
#          'In earlier versions this line was put here.
#         'because we sometimes returned to a strange place. Doesn't seem to happen now.
#     cursor hourglass    'ver116-4b
#     gosub [ProcessOSLBandCal]   'ver115-1g

# [ProcessOSLBandCal]   'Process already gathered band cal data
#     call ProcessOSLCal
#     desiredCalLevel=2   'opt for using band cal since we just did it

        oslCal.ProcessOSLCal()

#     if OSLError then BandSweepCalDone=0 : OSLBandNumSteps=-1 : return    'If error, nullify the cal and return
#                 'Save the conditions under which the cal was done
#     OSLBandStartFreq=startfreq
#     OSLBandEndFreq=endfreq
#     OSLBandNumSteps=steps
#     OSLBandLinear=gGetXIsLinear()
#     OSLBandPath$=path$
#     OSLBandS11JigType$=S11JigType$
#     OSLBandS21JigAttach$=S21JigAttach$
#     OSLBandS11BridgeR0=S11BridgeR0
#     OSLBandS21JigR0=S21JigR0
#     OSLBandTimeStamp$=date$("mm/dd/yy"); "; ";time$()
#     BandSweepCalDone=1
#     return

#     cursor normal   'ver116-4b
#     close #OSLcal
#     'ver115-5b moved update of band cal display to the routines for the basic cal window
#     return 'we will be back in the basic cal window, or whoever called us

        frame = self.frame
        frame.SetBandCal(self.oslCal)
        frame.SetCalLevel(2)
        self.calDialog.Update()
        frame.RefreshAllParms()
        self.Destroy()

    def EnableButtons(self, enable):
        for btn in self.btnList:
            btn.Enable(enable)

    #--------------------------------------------------------------------------
    # Close or Cancel - quit any running calibration.

    def OnClose(self, event):
        if msa.IsScanning():
            msa.StopScan()
            event.Skip()
        self.Destroy()

    #--------------------------------------------------------------------------
    # Update button enables after a change.

    def Update(self):
        frame = self.frame
        p = self.prefs
        p.isSeriesFix = self.isSeriesFix
        p.isShuntFix = self.isShuntFix
        p.isRefCal = self.isRefCal
        p.fixtureR0 = self.fixtureR0Box.GetValue()
        p.shuntConDelay = self.conDelay.GetValue()

        spectrum = frame.spectrum
        if spectrum:
            spectrum.isSeriesFix = self.isSeriesFix
            spectrum.isShuntFix = self.isShuntFix

        self.bridgeRb.SetValue(self.isReflBridge)
        self.seriesRb.SetValue(self.isSeriesFix)
        self.shuntRb.SetValue(self.isShuntFix)

        self.RefCalRb.SetValue(self.isRefCal)
        self.OslCalRb.SetValue(self.isOslCal)

        self.fixTypeSizer.ShowItems(self.isRefCal)

        self.conDelayText.Show(self.isShuntFix)
        self.conDelay.Show(self.isShuntFix)

        show = self.isOslCal or (self.isRefCal and (self.isReflBridge or self.isShuntFix))
        self.openBtn.Show(show)
        self.openSpecTxt.Show(show)

        show = self.isOslCal or (self.isRefCal and (self.isReflBridge or self.isSeriesFix))
        self.shortBtn.Show(show)
        self.shortSpecTxt.Show(show)

        self.loadBtn.Show(self.isOslCal)
        self.loadSpecTxt.Show(self.isOslCal)

        calStd = self.loadBox.GetCurrentSelection()
        p.calStandard = calStd
        if calStd == 0:
            self.openSpecTxt.Disable()
            self.shortSpecTxt.Disable()
            self.loadSpecTxt.Disable()
            self.openSpecTxt.SetValue("RLC[S,C0,D0]")
            self.shortSpecTxt.SetValue("RLC[P,R0,L0,D0]")
            self.loadSpecTxt.SetValue("RLC[P,R50,C0]")
        else:
            self.openSpecTxt.Enable()
            self.shortSpecTxt.Enable()
            self.loadSpecTxt.Enable()
            p.openSpec = self.openSpecTxt.GetValue()
            p.shortSpec = self.shortSpecTxt.GetValue()
            p.loadSpec = self.loadSpecTxt.GetValue()

        frame.RefreshAllParms()
        self.sizerV1.Fit(self)
        self.sizerH.Fit(self)

    def onReflFixHelp(self, event):
        dlg = ReflFixHelpDialog(self.frame)
        if dlg.ShowModal() == wx.ID_OK:
            self.p.ReflFixHelpWinPos = dlg.GetPosition().Get()

    def onReflCalHelp(self, event):
        dlg = ReflCalHelpDialog(self.frame)
        if dlg.ShowModal() == wx.ID_OK:
            self.p.ReflCalHelpWinPos = dlg.GetPosition().Get()

#==============================================================================
# Help dialog for Reflection Fixtures.

class ReflFixHelpDialog(wx.Dialog):
    def __init__(self, frame):
        p = frame.prefs
        pos = p.get("ReflFixHelpWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, "Reflection Fixture Help", pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        sizerV = wx.BoxSizer(wx.VERTICAL)
        self.SetBackgroundColour("WHITE")
        txt = "Reflection measurements use one of several types of test fixtures "\
              "to which the device under test (DUT) is attached. Many fixtures "\
              "are Reflection Bridges, which make an attempt to make their "\
              "output signal correspond closely to the actual reflection from "\
              "the DUT. Such fixtures can use Reference Calibration with either "\
              "the Open or Short, or for better accuracy can use full OSL "\
              "calibration.\n\n"\
              "Other fixtures produce an output which does not directly "\
              "correspond to the DUT reflection, but can be mathematically "\
              "transformed into a reflection measurement. These test fixtures "\
              "typically consist of an attenuator, then the component, then "\
              "another attenuator. The component may be connected in Series "\
              "between the attenuators, or may be Shunt to ground, which "\
              "accounts for the two different fixture types. The component will "\
              "see a certain resistance R0 looking at the incoming signal and "\
              "the outgoing signal. You must specify that R0, usually 50 "\
              "ohms. The Series fixture is calibrated with just the Short or "\
              "with full OSL. The Shunt fixture is calibrated with just the Open "\
              "or with full OSL.\n\n"\
              "If you specify the Shunt Fixture, then you may also specify the "\
              "one-way connection delay time, which is used for compensation "\
              "when you do not use full OSL. A delay of 0.115 ns is typical. "\
              "For low frequencies a delay of 0 ns may be adequate."
        st = wx.StaticText(self, -1, txt, pos=(10, 10))
        st.Wrap(600)
        sizerV.Add(st, 0, wx.ALL, 5)

        # OK button
        butSizer = wx.BoxSizer(wx.HORIZONTAL)
        butSizer.Add((0, 0), 0, wx.EXPAND)
        btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        butSizer.Add(btn, 0, wx.ALL, 5)
        sizerV.Add(butSizer, 0, wx.ALIGN_RIGHT)

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if pos == wx.DefaultPosition:
            self.Center()

#==============================================================================
# Help dialog for Reflection Calibration.

class ReflCalHelpDialog(wx.Dialog):
    def __init__(self, frame):
        p = frame.prefs
        pos = p.get("ReflCalHelpWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, "Reflection Calibration Help", pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        sizerV = wx.BoxSizer(wx.VERTICAL)
        self.SetBackgroundColour("WHITE")
        txt = "All measurements in Reflection mode require some form of "\
              "calibration. The simplest calibration is Reference Calibration, which "\
              "uses either an Open or a Short calibration standard, which essentially "\
              "allows the MSA to adjust to set a reference signal level. This works "\
              "well for precise fixtures at relatively low frequencies. OSL "\
              "Calibration involves more steps but is more accurate. OSL involves "\
              "sequentially measuring Open, Short and Load calibration standards, in "\
              "any order.  For OSL Calibration, you generally specify the electrical "\
              "characteristics of each of the standards.  At low frequencies it may "\
              "work well just to treat them as Ideal."
        st = wx.StaticText(self, -1, txt, pos=(10, 10))
        st.Wrap(600)
        sizerV.Add(st, 0, wx.ALL, 5)

        # OK button
        butSizer = wx.BoxSizer(wx.HORIZONTAL)
        butSizer.Add((0, 0), 0, wx.EXPAND)
        btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        butSizer.Add(btn, 0, wx.ALL, 5)
        sizerV.Add(butSizer, 0, wx.ALIGN_RIGHT)

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if pos == wx.DefaultPosition:
            self.Center()

#==============================================================================
# The Perform Calibration Update dialog box.

class PerformCalUpdDialog(wx.Dialog): # EON Jan 29, 2014
    def __init__(self, frame):
        self.frame = frame
        p = frame.prefs
        self.error = False # EON Jan 29, 2014
        if msa.calLevel != 2:
            message("Calibration Level must be Reference to Band to update.") # EON Jan 29, 2014
            self.error = True # EON Jan 29, 2014
            return
        mode = p.mode
        if mode == MSA.MODE_VNARefl:
            oslCal = msa.oslCal
            if oslCal != None:
                stdType = msa.oslCal.OSLBandRefType
            else:
                message("No OSL Calibration.") # EON Jan 29, 2014
                self.error = True # EON Jan 29, 2014
                return
        else:
            stdType = "Through connection"

        self.btnList = []
        pos = p.get("perfCalUpdWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, "Calibration Update", pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        self.sizerV = sizerV = wx.BoxSizer(wx.VERTICAL)
        c = wx.ALIGN_CENTER

        text = "To update the currently band calibration, attach the " + stdType +\
                " and click Perform Update. This will update the currently installed "\
                "reference to partially adjust for drift occurring since the full "\
                "calibration was performed."
        st = wx.StaticText(self, -1, text, pos=(10, 10))
        st.Wrap(500)
        sizerV.Add(st, 0, wx.ALL|wx.EXPAND, 5)

        if mode == MSA.MODE_VNATran:
            sizerH0 = wx.BoxSizer(wx.HORIZONTAL)
            text = "Delay of Calibration Through Connection (ns):"
            txt = wx.StaticText(self, -1, text)
            sizerH0.Add(txt, 0, wx.EXPAND|wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
            delText = "%g" % p.get("calThruDelay", 0)
            self.calThruBox = tc = wx.TextCtrl(self, -1, delText, size=(40, -1))
            self.btnList.append(tc)
            sizerH0.Add(tc, 0, wx.EXPAND|wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
            sizerV.Add(sizerH0, 0, c|wx.ALL, 10)

##        text = ("Apply update to " + # EON Jan 29, 2014
##                ("Reflection","Transmission")[mode == MSA.MODE_VNARefl] +
##                " Cal as well.")
##        self.updateBoth = chk = wx.CheckBox(self, -1, text)
##        self.btnList.append(chk)
##        sizerV.Add(chk, 0, c|wx.ALL, 10)

        sizerH1 = wx.BoxSizer(wx.HORIZONTAL)
        self.calBtn = btn = wx.Button(self, -1, "Perform " + stdType)
        btn.Bind(wx.EVT_BUTTON, self.onCal)
        sizerH1.Add(btn, 0, c|wx.ALL, 5)

        self.doneBtn = btn = wx.Button(self, -1, "Done")
        self.btnList.append(btn)
        btn.Bind(wx.EVT_BUTTON, self.onDone)
        sizerH1.Add(btn, 0, c|wx.ALL, 5)
        sizerV.Add(sizerH1, 0, c|wx.ALL, 5)

        self.SetSizer(sizerV)
        sizerV.Fit(self)

#        self.Update()
        if pos == wx.DefaultPosition:
            self.Center()
#        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def EnableButtons(self, enable):
        for btn in self.btnList:
            btn.Enable(enable)

    def CalScan(self):
        frame = self.frame
        p = frame.prefs
        spectrum = frame.spectrum
        if spectrum:
            spectrum.isSeriesFix = p.isSeriesFix
            spectrum.isShuntFix = p.isShuntFix
        msa.calibrating = True
        wait = p.wait
        p.wait = calWait # EON Jan 29, 2014
        self.calBtn
        self.doneBtn
        frame.DoExactlyOneScan()
        frame.WaitForStop()
        p.wait = wait
        msa.calibrating = False
        ##p.planeExt = savePlaneExt
        return spectrum

    def onCal(self, wxEvent):
        if msa.IsScanning():
            msa.StopScan()
        else:
            self.EnableButtons(False)
            calBtn = self.calBtn
            label = calBtn.GetLabel()
            calBtn.SetLabel("Abort Cal")
            spectrum = self.CalScan()
            oslCal = msa.oslCal
            calBtn.SetLabel(label)
            self.EnableButtons(True)
            if msa.mode == MSA.MODE_VNARefl:
                for i in range (0, oslCal._nSteps):
                    Mdb = spectrum.Mdb[i]
                    Mdeg = spectrum.Mdeg[i]
                    (db, deg) = oslCal.bandRef[i]
                    oslCal.bandRef[i] = (Mdb, Mdeg)
            else:
                cal = msa.bandCal # EON Jan 29, 2014
                if cal != None:
                    cal.Mdb = dcopy.copy(spectrum.Mdb)
                    cal.deg = dcopy.copy(spectrum.Mdeg)

    def onDone(self, wxEvent):
        self.Destroy()

#  [RunCalUpdate]  'menu item to update calibration ver116-4b
#    if haltsweep=1 then gosub [FinishSweeping]
#     WindowWidth = 475 : WindowHeight = 235
#     call GetDialogPlacement 'set UpperLeftX and UpperLeftY ver115-1c
#     UpperLeftY=UpperLeftY-100
#     BackgroundColor$="buttonface"
#     ForegroundColor$="black"
#     TextboxColor$ = "white"
#     ComboboxColor$="white"
#         'We can update band cal if we have current cal, even if not yet installed.
#         'TO DO: For base cal, change the sweep settings to match the cal data. DO a scan and update the base cal data, and
#         'save it to file. Change desired cal level to 1 and install cal. For band cal, be sure it matches current sweep params,
#         'update the band cal data, change desired cal level to 2 and install cal.
#         'To update both reflection and transmission base cal, they must both exist but don't need matching freq range.
#         'Note: Currently only band cal update is implemented.
#     if msaMode$="Reflection" then bandUpdateIsCurrent=(desiredCalLevel=2 and BandOSLCalIsCurrent()) : baseUpdateIsCurrent=BaseOSLCalIsCurrent() _
#                         else bandUpdateIsCurrent=(desiredCalLevel=2 and BandLineCalIsCurrent()) : baseUpdateIsCurrent=BaseOSLCalIsCurrent()
#     if bandUpdateIsCurrent=0 then Notice "Must have current band calibration to update. Cannot update base cal." : wait 'ver116-4n
#         'update band cal
#     if msaMode$="Reflection" then stdType$=OSLBandRefType$;" standard" else stdType$="Through connection"
#     s$="To update the currently band calibration, attach the "; stdType$
#     s$=s$;" and click Perform Update. This will update the currently installed reference to partially adjust for drift "
#     s$=s$;"occurring since the full calibration was performed. "
#
#     statictext #OSLupdate.inst, s$,10,1,450, 70
#
#     updateCalsMatch=0   'Whether other VNA mode has matching calibration
#     if BandOSLCalIsCurrent() and BandLineCalIsCurrent() then updateCalsMatch=1
#
#     if msaMode$="VectorTrans" then
#         statictext #OSLupdate.DelayLabel, "Delay of Calibration Through Connection (ns):",10,90,270, 18
#         textbox #OSLupdate.Delay, 282,90,50, 20
#         checkbox #OSLupdate.applyAlso, "Apply update to Reflection Cal as well.",[updateNil], [updateNil],50,115,260, 18
#     else    'Reflection
#         checkbox #OSLupdate.applyAlso, "Apply update to Transmission Cal as well.",[updateNil], [updateNil],50,115,260, 18
#     end if
#
#     button #OSLupdate.Perform, "Perform Open",[PerformCalUpdate], UL, 75, 160, 120,25    'ver114-5f
#     button #OSLupdate.Done, "Done",[CalUpdateFinished], UL, 220, 160, 100,25
#
#     open "Update Calibration" for dialog_modal as #OSLupdate  'ver114-3g
#     print #OSLupdate, "trapclose [CalUpdateFinished]"   'goto [OSLCalUpdateFinished] if xit is clicked
#     print #OSLupdate, "font ms_sans_serif 10"
#     if msaMode$="VectorTrans" then #OSLupdate.Perform, "Perform Through" : #OSLupdate.Delay, lineCalThroughDelay  'Delay in ns
#     calUpdatePerformed=0
#     if updateCalsMatch=0 then #OSLupdate.applyAlso, "disable"   'gray it out in reset mode if not applicable
#     wait
#
# [updateNil] 'nil handler
#     wait
#
# [PerformCalUpdate]  'update button clicked
#         'We will re-scan the reference data, which should in theory match the current reference data. If a current
#         'reading minus the original is D dB @ A degrees, this means we need to subtract that extra
#         'amount from all future readings. Essentially, the new data becomes our new reference,
#         'which we need to transfer to lineCalArray. In addition, if we have Band cal, we should
#         'replace lineCalBandRef() or OSLBandRef(). For Base cal, it is not feasible to adust the Base cal array reference, so
#         'we can only adjust the currently installed data in lineCalArray.
#     if calInProgress then goto [CalUpdateAborted]   'Perform button is actually Abort while cal in progress
#     calUpdatePerformed=1    'set this even if we abort ver116-4b
#     #OSLupdate.Perform, "Abort Cal" : #OSLupdate.Done, "!disable" : #OSLupdate.applyAlso, "disable"
#     if msaMode$<>"Reflection" then gosub [PerformLineCalUpdate] else gosub [PerformOSLCalUpdate]
#     wait
#
# [PerformOSLCalUpdate]
#     cursor hourglass
#     calInProgress=1 : specialOneSweep=1
#     saveAlternate=alternateSweep : saveSweepDir=sweepDir : savePlaneAdj=planeadj : saveWate=wate
#     alternateSweep=0 : sweepDir=1
#     call FunctSetVideoAndAutoWait 1  'set video filter to narrow and autowait to Normal or Precise; 1 means save settings
#     planeadj=0  'So phase will not be affected
#         'Note with calInProgress=1, the cal installation routine will not install anything and sets applyCalLevel=0
#     gosub [Restart] 'Perform one sweep and fill datatable(,)
#     specialOneSweep=0
#     calInProgress=0
#     call FunctRestoreVideoAndAutoWait
#     sweepDir=saveSweepDir : alternateSweep=saveAlternate
#     planeadj=savePlaneAdj : wate=saveWate
#         'New Cal reference data is now in datatable
#     #OSLupdate.applyAlso, "value? applyAlso$"
#     for i=0 to steps
#         m=datatable(i,2) : p=datatable(i,3) 'get mag and phase; freq doesn't change
#         deltaM=m-OSLBandRef(i,1) : deltaP=p-OSLBandRef(i,2) 'change in mag and phase
#         OSLBandRef(i,1)=m : OSLBandRef(i,2)=p   'update OSLBandRef
#         if applyAlso$="set" then _        'update line cal data if required
#                 bandLineCal(i,1)=bandLineCal(i,1)+deltaM : bandLineCal(i,2)=gNormalizePhase(bandLineCal(i,2)+deltaP)
#     next i
#     desiredCalLevel=2 : installedOSLBandTimeStamp$=""   'so installation will occur
#     call InstallSelectedOSLCal 'So new data gets installed and installation variables get updated
#
#     OSLBandTimeStamp$=date$("mm/dd/yy"); "; ";time$()
#     if applyAlso$="set" then bandLineTimeStamp$=OSLBandTimeStamp$
#     cursor normal
#     beep
#     #OSLupdate.Perform, "Perform Update" : #OSLupdate.Done, "!enable"
#     if updateCalsMatch then #OSLupdate.applyAlso, "enable"
#     return
#
# [PerformLineCalUpdate]
#     cursor hourglass
#     if msaMode$="VectorTrans" then   'ver115-5a
#         #OSLupdate.Delay, "!contents? s$"
#         lineCalThroughDelay=val(uCompact$(s$))      'Store in ns; used by [BandLineCal]
#     else
#         lineCalThroughDelay=0
#     end if
#         'We use BandLineCal rather than just doing our own sweep because it adjusts for lineCalThroughDelay
#         'It will automatically update bandLineCal, so in order for us to have access to the old info
#         'we have to be sure it is saved into lineCalArray.
#         'lineCalArray data will not be disturbed (and will not be used) during the sweep conducted by [BandLineCal].
#     for i=0 to steps : lineCalArray(i,1)=bandLineCal(i,1) : lineCalArray(i,2)=bandLineCal(i,2) : next i
#     gosub [BandLineCal] 'Peforms sweep and loads into bandLineCal; saves/restores necessary settings
#         'new data is in datatable and bandLineCal; old data is still in lineCalArray
#     #OSLupdate.applyAlso, "value? applyAlso$"
#     if applyAlso$="set" then   'update OSL data if required
#         for i=0 to steps
#             m=bandLineCal(i,1) : p=bandLineCal(i,2) 'get mag and phase; freq doesn't change
#             deltaM=m-lineCalArray(i,1) : deltaP=p-lineCalArray(i,2) 'change in mag and phase
#             OSLBandRef(i,1)=OSLBandRef(i,1)+deltaM : OSLBandRef(i,2)=gNormalizePhase(OSLBandRef(i,2)+deltaP)
#         next i
#     end if
#     desiredCalLevel=2 : installedBandLineTimeStamp$=""   'so installation will occur
#     call InstallSelectedLineCal 'So new data gets installed and installation variables get updated
#         '[BandLineCal] updates bandLineTimeStamp$
#     if applyAlso$="set" then OSLBandTimeStamp$=bandLineTimeStamp$
#     #OSLupdate.Perform, "Perform Update" : #OSLupdate.Done, "!enable"
#     if updateCalsMatch then #OSLupdate.applyAlso, "enable"
#     cursor normal
#     return
#
# [CalUpdateAborted]    'abort calibration
#     gosub [FinishSweeping] 'Finish nicely
#     #OSLupdate.Perform, "Perform Update" : #OSLupdate.Done, "!enable"
#     if updateCalsMatch then #OSLupdate.applyAlso, "enable"
#     cursor normal
#     specialOneSweep=0 : calInProgress=0
#     sweepDir=saveSweepDir : alternateSweep=saveAlternate
#     planeadj=savePlaneAdj : wate=saveWate
#     wait
#
# [CalUpdateFinished]
#     if calInProgress=1 then goto [PostScan] 'Don't allow quit in middle of cal
#     'Note we do not update the time stamp of the base, band or installed cal. That is needed only to trigger a
#     're-install of cal info on Restart. We just installed what is necessary. If Base cal, on Restart no new install
#     'will be done so what we just did won't be overridden. If Band cal, it wouldn't matter if a re-install were done.
#     cursor normal
#     close #OSLupdate
#     if calUpdatePerformed then
#         call SignalNoCalInstalled   'ver116-4b
#         desiredCalLevel=2   'desire BandSweep since we just did it
#         call RequireRestart   'so cal will get installed before proceeding
#     end if
#     wait
# '--end of [RunCalUpdate]

#==============================================================================
# Class for OSL Calibration

class OslCal:
    def __init__(self, when, pathNo, isLogF, fStart, fStop, nSteps, Fmhz):
        self.desc = "%s, Path %d, %d %s steps, %g to %g MHz." % \
            (when, pathNo, nSteps, ("linear", "log")[isLogF], fStart, fStop)
        self.oslDbg = False
        self.when = when
        self.path = pathNo
        self.oslCal = True
        self.isLogF = isLogF
        self._fStart = fStart
        self._fStop = fStop
        self.nSteps = nSteps
        self._nSteps = self.nSteps + 1
        n = self._nSteps
        self.Fmhz = dcopy.copy(Fmhz)
        self.OSLcalOpen = [None] * n
        self.OSLcalShort = [None] * n
        self.OSLcalLoad = [None] * n
        self.OSLstdOpen = zeros(n, dtype=complex)
        self.OSLstdShort = zeros(n, dtype=complex)
        self.OSLstdLoad = zeros(n, dtype=complex)
        self.comboResp = [None] * n
        self.OSLdoneO = False
        self.OSLdoneS = False
        self.OSLdoneL = False
        self.OSLError = False
        self.OSLShortSpec = ""
        self.OSLOpenSpec = ""
        self.OSLLoadSpec = ""
        self.S11JigType = ""
        self.S11BridgeR0 = 0
        self.S11FixR0 = 0
        self.S21JigAttach = ""
        self.S21JigShuntDelay = 0
        self.OSLBandRefType = ""
        self.OSLBandRef = [None] * n
        self.OSLBandA = zeros(n, dtype=complex)
        self.OSLBandB = zeros(n, dtype=complex)
        self.OSLBandC = zeros(n, dtype=complex)
        self.bandFmhz = []
        self.bandRef = []
        self.bandA = []
        self.bandB = []
        self.bandC = []

    # OSLCal[i] returns the tuple (Sdb, Sdeg) for step i

    def __getitem__(self, i):
        return self.bandRef[i]

    def Changed(self, isLogF, fStart, fStop, nSteps):
        if round(self._fStart - fStart, 8) != 0 or round(self._fStop - fStop, 8) != 0:
            return True
        if self.nSteps != nSteps:
            return True
        if self.isLogF != isLogF:
            return True
        return False

    def installBandCal(self):
        self.bandFmhz = self.Fmhz
        self.bandRef = self.OSLBandRef
        self.bandA = self.OSLBandA
        self.bandB = self.OSLBandB
        self.bandC = self.OSLBandC

    def interpolateCal(self, fMhz):
        nSteps = len(fMhz)
        self.bandRef = [(None, None)] * nSteps
        self.bandA = zeros(nSteps, dtype=complex)
        self.bandB = zeros(nSteps, dtype=complex)
        self.bandC = zeros(nSteps, dtype=complex)

        db = zeros(self._nSteps)
        deg = zeros(self._nSteps)
        for i in range (0, self._nSteps):
            (db[i], deg[i]) = self.OSLBandRef[i]

        i = 0
        for freq in fMhz:
            self.bandRef[i] = (interp(freq, self.Fmhz, db),
                               interp(freq, self.Fmhz, deg))
            i += 1

        dst = zeros(nSteps)
        src = self.OSLBandA.real
        i = 0
        for freq in fMhz:
            dst[i] = interp(freq, self.Fmhz, src)
            i += 1
        self.bandA.real = dcopy.copy(dst)
        src = self.OSLBandA.imag
        i = 0
        for freq in fMhz:
            dst[i] = interp(freq, self.Fmhz, src)
            i += 1
        self.bandA.imag = dcopy.copy(dst)

        src = self.OSLBandB.real
        i = 0
        for freq in fMhz:
            dst[i] = interp(freq, self.Fmhz, src)
            i += 1
        self.bandB.real = dcopy.copy(dst)
        src = self.OSLBandB.imag
        i = 0
        for freq in fMhz:
            dst[i] = interp(freq, self.Fmhz, src)
            i += 1
        self.bandB.imag = dcopy.copy(dst)

        src = self.OSLBandC.real
        i = 0
        for freq in fMhz:
            dst[i] = interp(freq, self.Fmhz, src)
            i += 1
        self.bandC.real = dcopy.copy(dst)
        src = self.OSLBandC.imag
        i = 0
        for freq in fMhz:
            dst[i] = interp(freq, self.Fmhz, src)
            i += 1
        self.bandC.imag = dcopy.copy(dst)

    def WriteS1P(self, fileName, p, contPhase=False):
        f = open(fileName, "w") # EON Jan 29, 2014
        f.write("!MSA, msapy %s\n" % version)
        f.write("!Date: %s\n" % time.ctime())
        f.write("!%s Sweep Path %d S11Jig=%s; S11BridgeR0=%d; S21Jig=%s; S21JigR0=%s\n" % \
                (("Linear", "Log")[p.isLogF], p.indexRBWSel+1, self.S11JigType, self.S11BridgeR0, "", ""))
        f.write("!  MHz         A_real          A_imag          B_real          B_imag          C_Real          C_Imag         RefDB     RefDeg\n")
        for freq, bandA, bandB, bandC, bandRef in zip(self.Fmhz, self.OSLBandA, self.OSLBandB, self.OSLBandC, self.OSLBandRef):
            f.write("%11.6f %15.8e %15.8e %15.8e %15.8e %15.8e %15.8e %10.5f %7.2f\n" % \
                    (freq, bandA.real, bandA.imag, bandB.real, bandB.imag, bandC.real, bandC.imag, bandRef[0], bandRef[1]))
        f.close()

    #--------------------------------------------------------------------------
    # Read OSL Calbration from file.

    @classmethod
    def FromS1PFile(cls, fileName):
        a = []
        b = []
        c = []
        Fmhz = []
        bandRef = []
        when = "**UNKNOWN DATE**"
        pathNo = 1
        isLogF = False
        S11Jig = "Bridge"
        S11BridgeR0 = 50
        f = open(fileName, "r")

        i = 0
        for line in f.readlines():
            line = line.strip()
            if len(line) > 1:
                if line[0] != "!":
                    val = re.split(" +",line)
                    if len(val) == 9:
                        Fmhz.append(float(val[0]))
                        a.append(complex(float(val[1]), float(val[2])))
                        b.append(complex(float(val[3]), float(val[4])))
                        c.append(complex(float(val[5]), float(val[6])))
                        bandRef.append((float(val[7]), float(val[8])))
                        i += 1
                    else:
                        pass
                else:
                    m = re.match("!Date: (.+)", line)
                    if m != None:
                        when = m.group(1)
                    else:
                        m = re.match("!(.+?) *Sweep *Path *(.+?) *S11Jig=(.*?);* *S11BridgeR0=(.*?);* *S21Jig=(.*?);* *S21JigR0=(.*?)", line)
                        if m != None:
                            isLogF = m.group(1) == "Log"
                            pathNo = int(m.group(2))
                            S11Jig = m.group(3)
                            S11BridgeR0 = m.group(4)
        f.close()

        n = len(Fmhz)
        if n == 0:
            raise ValueError("S1P file: no data found")

##        print ("Read %d steps." % (n-1), "Start=", Fmhz[0], "Stop=", Fmhz[-1]) # EON Jan 29, 2014
        this = cls(when, pathNo, isLogF, Fmhz[0], Fmhz[-1], n - 1, array(Fmhz))
        this.OSLBandA = array(a)
        this.OSLBandB = array(b) # EON Jan 29, 2014
        this.OSLBandC = array(c) # EON Jan 29, 2014
        this.OSLBandRef = bandRef
        this.S11JigType = S11Jig
        this.S11BridgeR0 = S11BridgeR0
        return this

# sub ConvertRawDataToReflection currStep

# For the current step in reflection mode, calculate S11, referenced to S11GraphR0

    def ConvertRawDataToReflection(self, i, Sdb, Sdeg):

# Calculate reflection in db, angle format and puts results in
# ReflectArray, which already contains the raw data.  Also calculates
# the various items in ReflectArray() from the final reflection value.
# We need to adjust the data for calibration
#
#       Reference calibration
#
# The simplest reflection calibration is to use the Open or Short as a
# reference. In that case, we still calculate OSL coefficients as though
# we did full OSL, using Ideal results for the missing data.
#
#     Full OSL
#
# More extensive calibration would include the Open, Short and Load,
# from which we calculated the a, b, c OSL coefficients during
# calibration. If we have full OSL coefficients, we apply them here.  We
# identify the type of jig used with S11JigType$, which the user sets
# during calibration.  S11JigType$ is always set to "Reflect" when doing
# full OSL, since we don't even know the nature of the actual jig.  In
# addition, S21JigR0 is set to S11BridgeR0.
#
# Note that S21 or S11 are now referenced to the S21JigR0 or
# S11BridgeR0, not the graph R0. We do the conversion here. But we also
# save S11 as an intermediate value before applying the R0 coversion or
# plane extension (but after applying cal) to make recalculations
# easier. It is saved with constIntermedS11DB and constIntermedS11Ang.
#
# First get the raw reflection data. This is the measured data, adjusted
# by subtracting the reference.  planeadj has not been applied; it is
# applied after applying calibration S21JigShuntDelay has not yet been
# applied. It will be applied here via the OSL coefficients.

#
#     trueFreq=ReflectArray(currStep,0)*1000000
#     db=ReflectArray(currStep,constGraphS11DB) : ang=ReflectArray(currStep,constGraphS11Ang)
#     if calInProgress then   'If calibrating we don't adjust anything here, or calculate anything other than S11
#         ReflectArray(currStep, constIntermedS11DB)=db  'ver115-2d
#         ReflectArray(currStep, constIntermedS11Ang)=ang  'ver115-2d
#         exit sub
#     end if
#
#     rho=uTenPower(db/20)    'mag made linear

# db, rho, and ang (degrees) now have the raw reflection data If
# necessary, we apply full OSL to the reflection data, whether it was
# derived from a reflection bridge or a transmission jig.  If doing OSL
# cal, then we don't want to apply whatever coefficients we happen to
# have now.  If doSpecialGraph<>0 we don't want to mess with the
# internally generated data

#     if doSpecialGraph=0 and applyCalLevel<>0 then   'ver115-5f
#         rads=ang*uRadsPerDegree()   'angle in radians
#         mR=rho*cos(rads) : mI=rho*sin(rads)     'measured S11, real and imaginary
#         aR=OSLa(currStep,0) : aI=OSLa(currStep,1)   'coefficient a, real and imaginary
#         bR=OSLb(currStep,0) : bI=OSLb(currStep,1)   'coefficient b, real and imaginary
#         cR=OSLc(currStep,0) : cI=OSLc(currStep,1)   'coefficient c, real and imaginary

        if True:
            M = cmath.rect(10 ** (Sdb / 20), Sdeg * RadsPerDegree)
            a = self.bandA[i]
            b = self.bandB[i]
            c = self.bandC[i]

#
#         'calculate adjusted db, ang via OSL. Note OSL must be referenced to S11BridgeR0
#         calcMethod=1    'For debugging, we have two different methods
#         if calcMethod=1 then
#                 'The first method uses  the following formula, and corresponds to CalcOSLCoeff
#                 '       S = (M - b) / (a - c*M)
#                 'where S is the actual reflection coefficient and M is the measured reflection coefficient.
#                 'S and M are in rectangular form in this equation.
#             RealCM=cR*mR-cI*mI : ImagCM=cR*mI+cI*mR     'c*M, real and imaginary
#             call cxDivide mR-bR, mI-bI, aR-RealCM,aI-ImagCM,refR, refI   'Divide M-b by a-c*M
#         else
#                 'The second method uses  the following formula, and corresponds to CalcOSLCoeff1
#                 '       S = (a - cM)/(bM - 1)
#                 'where S is the actual reflection coefficient and M is the measured reflection coefficient.
#                 'S and M are in rectangular form in this equation.
#
#             RealCM=cR*mR-cI*mI : ImagCM=cR*mI+cI*mR     'c*M, real and imaginary
#             RealBM=bR*mR-bI*mI : ImagBM=bR*mI+bI*mR     'b*M, real and imaginary
#             numR=aR-RealCM : numI=aI-ImagCM             'numerator, real and imaginary
#             denR=RealBM-1 :denI=ImagBM                  'denominator, real and imaginary
#             call cxDivide numR, numI, denR, denI, refR, refI     'Divide numerator by denominator; result is reflection coeff.
#         end if

            if True:
                # The first method uses the following formula, and corresponds to
                # CalcOSLCoeff
                #       S = (M - b) / (a - c * M)
                # where S is the actual reflection coefficient and M is the measured
                # reflection coefficient.  S and M are in rectangular form in this
                # equation.

                S = (M - b) / (a - c * M)
            else:
                # The second method uses the following formula, and corresponds to
                # CalcOSLCoeff1
                #        S = (a - cM)/(bM - 1)
                # where S is the actual reflection coefficient and M is the measured
                # reflection coefficient.  S and M are in rectangular form in this
                # equation.

                S = (a - c * M) / (b * M - 1)

#         'ver116-4k separated the following common calculations from the above if...else block
#         magSquared=refR^2+refI^2        'mag of S, squared
#         db=10*uSafeLog10(magSquared)    'S mag in db; multiply by 10 not 20 because mag is squared
#         if db>0 then db=0   'Shouldn't happen
#         ang=uATan2(refR, refI)      'angle of S in degrees
#             'db, ang (degrees) now have S11 data produced by applying OSL calibration.

        (db, deg) = polarDbDeg(S)
        if db > 0:
            db = 0

#     end if
#
#     'Save the angle prior to applying plane extension or Z0 transform, to make it easier to recalculate with a new values
#     ReflectArray(currStep, constIntermedS11DB)=db  'ver115-2d
#     ReflectArray(currStep, constIntermedS11Ang)=ang  'ver115-2d
#         'Note we do apply plane extension even when doSpecialGraph<>0
#     if planeadj<>0 or S11BridgeR0<>S11GraphR0 then call ApplyExtensionAndTransformR0 ReflectArray(currStep,0), db, ang 'ver115-2d
#
#         'Note we do not put the reflection data in datatable, which retains the original raw data
#     ReflectArray(currStep,constGraphS11DB)=db   'Save final S11 in db, angle format (in Graph R0, after plane ext)
#     while ang>180 : ang=ang-360 : wend
#     while ang<=-180 : ang=ang+360 : wend
#     ReflectArray(currStep,constGraphS11Ang)=ang
#     'We now compute the various items in ReflectArray() from S11, but if we are doing calibration we don't need this
#     'other data, and it probably doesn't make sense anyway.
#     if calInProgress=0 then call CalcReflectDerivedData currStep  'Calc other ReflectArray() data from S11.

        return db, deg

# end sub

# sub ProcessOSLCal     'Calc coefficients and reference data from raw OSL scan data

    def ProcessOSLCal(self):

#
# Calc coefficients and reference data from raw OSL scan data
#
# OSLdoneO, OSLdoneS and OSLdoneL indicate which of Open, Short, and
# Load were performed.  The relevant calibration data is in
# OSLcalOpen(), OSLcalShort() and OSLcalLoad() Calibration data will be
# the raw S11 for reflection bridge, and raw S21 for the transmission
# jigs.  In the latter case we must convert to S11 before calculating
# OSL coefficients.
#
# The measured cal data is in OSLcalOpen(), etc., as dB/angle. It is
# reflection data for the reflection bridge, For S11JigType$="Reflect",
# the data in OSLcalOpen(), etc., will be reflection per the bridge w/o
# OSL adjustment, and without being adjusted for planeadj (which we
# force to 0 in cal).  For S11JigType$="Trans", the data in
# OSLcalOpen(), etc., is "S21" of the fixture (unadjusted for any
# reference) which we are treating as the tentative estimate of
# reflection, even though it is far from true reflection.
#
# When raw data is collected in future scans, it will be adjusted by a
# reference installed into the line cal array. The reference will be
# the calibration data from the Open, except for the series jig it is
# the calibration data from the Short. In the case of a Reflection
# Bridge if we don't have the relevant Open data, we compute it from
# the Short. We assume Ideal values for the non-reference data in order
# to calc coefficients.
#
# We put the OSL coefficients into OSLBandA(), OSLBandB() and OSLBandC()
#

# 'DEBUG
# '    for i=0 to globalSteps
# '        OSLcalOpen(i,0)=0 : OSLcalOpen(i,1)=0
# '        OSLcalShort(i,0)=42.638 : OSLcalShort(i,1)=-93.4375
# '        OSLcalLoad(i,0)=39.166 : OSLcalLoad(i,1)=-92.76
# '    next i
#     calSum=OSLdoneO+OSLdoneS+OSLdoneL   'number of cals done. Will be 1 or 3
#     if calSum=0 then notice "No calibration performed" : OSLError=1 : exit sub
#     if calSum=2 then notice "Incomplete calibration performed" : OSLError=1 : exit sub   'Our OSL procedure actually never allows this to happen
#     if calSum=1 and OSLdoneL then notice "Incomplete calibration performed" : OSLError=1  : exit sub   'Our OSL procedure actually never allows this to happen
#
        calSum = 0
        self.OSLError = False
        if self.OSLdoneO:
            calSum += 1
        if self.OSLdoneS:
            calSum += 1
        if self.OSLdoneL:
            calSum += 1
        if calSum == 0:
            message("No Reference scanned.\nCalibration not performed.") # EON Jan 29, 2014
            self.OSLError = True
            return
        if calSum == 2:
            message("Incomplete calibration performed") # EON Jan 29, 2014
            self.OSLError = True
            return
        if calSum == 1 and self.OSLdoneL:
            message("Incomplete calibration performed") # EON Jan 29, 2014
            self.OSLError = True
            return

#     call CalcOSLStandards   'ver116-4k

        # Calc cal standard data for computing coefficients. For reference cal,
        # we don't need all of them, but there is no harm in calculating them.

        self.CalcOSLStandards()

        # If we have just one standard it will be reference cal with Open
        # (bridge or shunt) or Short(bridge or series), but may not be ideal
        # standard. We make up data for the missing standards so we can do
        # regular OSL.

        if self.oslDbg:
            f = open("OSLCal1.txt","w")

        if calSum == 1:

#         if OSLdoneO then OSLBandRefType$="Open" else OSLBandRefType$="Short"
#         for i=0 to globalSteps 'modver116-4n
#             if OSLdoneO then
# Note the measured values are the raw measurements of the data, which
# are the fixture transmission values but are not adjusted to any
# reference.
#                 S11R=OSLstdOpen(i,0) : S11I=OSLstdOpen(i,1)  'Actual standard S11, real/imag
#                 measDB=OSLcalOpen(i,0) : measDeg=OSLcalOpen(i,1)    'measured standard
#             else 'short
#                 S11R=OSLstdShort(i,0) : S11I=OSLstdShort(i,1) 'Actual standard S11, real/imag
#                 measDB=OSLcalShort(i,0) : measDeg=OSLcalShort(i,1)    'measured standard
#             end if
#             S11Mag=sqr(S11R^2+S11I^2) : S11dB=20*uSafeLog10(S11Mag) : S11Deg=uATan2(S11R, S11I) 'The calibration standard S11 spec in dB/angle format

            # Either the Open or Short was used as the reference. Even though the
            # cal standard may not be ideal, we use this as the (line cal)
            # reference, because it is easy to repeat when doing Update Cal. We also
            # need to create the two missing standards.  They will be created as
            # ideal, so we must also be sure that the description of the standard is
            # ideal, so we may override CalcOSLStandards that was just performed. We
            # need to find how the used standard would have performed if ideal, in
            # order to create the missing standards.

            if self.OSLdoneO:
                self.OSLBandRefType = "Open"
            else:
                self.OSLBandRefType = "Short"

            for i in range (0, self._nSteps):
                freq = self.Fmhz[i] * 1e6
                if self.OSLdoneO:
                    # Note the measured values are the raw measurements of the data, which
                    # are the fixture transmission values but are not adjusted to any
                    # reference.
                    S11 = self.OSLstdOpen[i]
                    (measDB, measDeg) = self.OSLcalOpen[i]
                else:
                    S11 = self.OSLstdShort[i]
                    (measDB, measDeg) = self.OSLcalShort[i]

                (S11dB, S11Deg) = polarDbDeg(S11)
                if self.oslDbg:
                    f.write("%2d, measDB %10.3e, measDeg %10.3e," % (i, measDB, measDeg))
                    f.write(" S11dB %10.3e, S11Deg %9.2e\n" % (S11dB, S11Deg))

#
#             if S11JigType$="Reflect" then
# Using bridge with reference cal. Reference may be Open or Short
#                 if S11dB<-40 then notice "Reference calibration standard is too close to "; S11BridgeR0; " ohms." : OSLError=1 : exit sub
#                 if OSLdoneO then
#                     OSLcalOpen(i,0)=0 : OSLcalOpen(i,1)=0  'Open adjusted by itself as reference
#                     OSLstdShort(i,0)=-1 : OSLstdShort(i,1)=0   'Force spec of Short to be ideal  (real/imag)
#                     OSLcalShort(i,0)=0-S11dB : OSLcalShort(i,1)=uNormalizeDegrees(-180-S11Deg)  'Pretend we measured the ideal Short and subtracted Open as reference (dB/ang form)
#                 else    'short is the reference
#                     OSLcalShort(i,0)=0 : OSLcalShort(i,1)=0  'Adjust short with itself as reference, resulting in 0 (dB/ang form)
#                     OSLstdOpen(i,0)=1 : OSLstdOpen(i,1)=0   'Force spec of Open to be ideal  (real/imag)
#                     OSLcalOpen(i,0)=0-S11dB : OSLcalOpen(i,1)=uNormalizeDegrees(0-S11Deg) 'Pretend we measured the ideal Open and subtracted Short as reference (dB/ang form)
#                 end if
#                 OSLstdLoad(i,0)=0 : OSLstdLoad(i,1)=0  'Force spec of load to be ideal (real/imag)
#                 OSLcalLoad(i,0)=-99-S11dB : OSLcalLoad(i,1)=0  'Pretend we measured the ideal load (dB/ang form); don't worry about angle
#             else

                if self.S11JigType == "Reflect":
                    # Using bridge with reference cal. Reference may be Open or Short
                    if S11dB < -40:
                        message("Reference calibration standard is too close to " + self.S11BridgeR0 + " ohms.") # EON Jan 29, 2014
                        self.OSLError = True
                        return

                    if self.OSLdoneO:
                        # Open adjusted by itself as reference
                        self.OSLcalOpen[i] = (0, 0)
                        # Force spec of Short to be ideal (real/imag)
                        self.OSLstdShort[i] = complex(-1, 0)
                        # Pretend we measured the ideal Short and subtracted Open as reference (dB/ang form)
                        self.OSLcalShort[i] = (-S11dB, uNormalizeDegrees(-180-S11Deg))
                    else:    # short is the reference
                        # Adjust short with itself as reference, resulting in 0 (dB/ang form)
                        self.OSLcalShort[i] = (0, 0)
                        # Force spec of Open to be ideal (real/imag)
                        self.OSLstdOpen[i] = complex(1, 0)
                        # Pretend we measured the ideal Open and subtracted Short as reference (dB/ang form)
                        self.OSLcalOpen[i] = (-S11dB, uNormalizeDegrees(-S11Deg))

                    # Force spec of load to be ideal (real/imag)
                    self.OSLstdLoad[i] = complex(0, 0)
                    # Pretend we measured the ideal load (dB/ang form); don't worry about angle
                    self.OSLcalLoad[i] = (-99 - S11dB, 0)
                else:

#                 if S21JigAttach$="Shunt" then   'calc S21 that this refco would produce
#                     phaseDelay=ReflectArray(i,0)*0.36*S21JigShuntDelay   'one way delay in degrees
#                     call uS11DBToImpedance S21JigR0, S11dB, S11Deg, impR, impX       'calc impedance
#                     call uPhaseShiftImpedance 50, phaseDelay, impR, impX    'Calculate effective impedance of Open with 50-ohm delay
#                     call uImpedanceToRefco S21JigR0, impR, impX, S11Mag, S11Deg   'calc actual Open S11 re S21JigR0 taking into account the delay
#                     call uRefcoToShuntS21DB S11Mag, S11Deg, S21dB, S21Deg   'calc S21 from the refco of the effective impedance
#                     if S11dB>-0.25 and (S11Deg<-165 or S11Deg>165) then _
#                         notice "Reference calibration standard is too close to a Short." : OSLError=1 : exit sub
#
#                     impR=0 : impX=0 'impedance of ideal Short
#                     call uPhaseShiftImpedance 50, phaseDelay, impR, impX    'Calculate effective impedance of ideal Short
#                     call uImpedanceToRefco S21JigR0, impR, impX, idealShortS11Mag, idealShortS11Deg   'calc ideal Short response taking into account the delay
#                     call uRefcoToShuntS21DB idealShortS11Mag, idealShortS11Deg, idealShortS21dB, idealShortS21Deg   'calc S21 from the refco of the effective impedance
# Adjust by the measured Open reading
#                     idealShortS21dB=idealShortS21dB - S21dB : idealShortS21Deg=uNormalizeDegrees(idealShortS21Deg - S21Deg)
#
#                     impR=S21JigR0 : impX=0  'impedance of ideal Load
#                     call uPhaseShiftImpedance 50, phaseDelay, impR, impX    'Calculate effective impedance of ideal Load
#                     call uImpedanceToRefco S21JigR0, impR, impX, idealLoadS11Mag, idealLoadS11Deg   'calc ideal Load response taking into account the delay
#                     call uRefcoToShuntS21DB idealLoadS11Mag, idealLoadS11Deg, idealLoadS21dB, idealLoadS21Deg   'calc S21 from the refco of the effective impedance
# Adjust by the same amount that the measured Open was high
#                     idealLoadS21dB=idealLoadS21dB - S21dB : idealLoadS21Deg=uNormalizeDegrees(idealLoadS21Deg  - S21Deg)
#
#                     OSLcalOpen(i,0)=0 : OSLcalOpen(i,1)=0  'Adjust open with itself as reference, resulting in 0 (dB/ang form)
#                     OSLstdShort(i,0)=-1 : OSLstdShort(i,1)=0   'Force spec of short to be ideal (real/imag)
#                     OSLcalShort(i,0)=idealShortS21dB : OSLcalShort(i,1)=idealShortS21Deg  'Pretend we measured the ideal short
#                     OSLstdLoad(i,0)=0 : OSLstdLoad(i,1)=0   'Force spec of load to be ideal (real/imag)
#                     OSLcalLoad(i,0)=idealLoadS21dB : OSLcalLoad(i,1)=idealLoadS21Deg  'Pretend we measured the ideal load

                    (S11Mag, S11Rad) = cmath.polar(S11)
                    S11Deg = S11Rad * DegreesPerRad
                    if self.S21JigAttach == "Shunt":   # calc S21 that this refco would produce

                        # For shunt fixture with no delay and a perfect Open, the ideal Load
                        # response would be 3.52 dB below the Open response and the ideal Short
                        # response would be zero. A non-zero delay or imperfect Open require us
                        # to calculate how the response of the actual Open, the ideal Load and
                        # the ideal Short would be transformed by the delay. We will use the
                        # measured Open as the reference for future measurements (i.e. it will
                        # be subtracted from the raw data the same as line cal). Therefore,
                        # whatever S21 we calculate for the actual Open, ideal Short or ideal
                        # Load, would produce reference-adjusted readings equal to that S21
                        # minus that opens calculated S21. That is, use of the measured open
                        # as a reference makes its net reading zero, and the ideal Load and
                        # Short need to be similarly adjusted The delay is assumed to be in a
                        # line of 50-ohms, not S21JigR0.

                        # one way delay in degrees
                        phaseDelay = freq * 0.36 * self.S21JigShuntDelay

                        # calc impedance
                        imp = self.uS11DBToImpedance(self.S21JigR0, S11dB, S11Deg)

                        # Calculate effective impedance of Open with 50-ohm delay
                        imp = self.uPhaseShiftImpedance(50, phaseDelay, imp)

                        # calc actual Open S11 re S21JigR0 taking into account the delay
                        (S11Mag, S11Deg) = self.uImpedanceToRefco(self.S21JigR0, imp)

                        # calc S21 from the refco of the effective impedance
                        (S21dB, S21Deg) = self.uRefcoToShuntS21DB(S11Mag, S11Deg)

                        if S11dB > -0.25 and S11Deg < -165 or S11Deg > 165:
                            message("Reference calibration standard is too close to a Short.") # EON Jan 29, 2014
                            self.OSLError = True
                            return

                        if self.oslDbg:
                            f.write("%2d S21 %s\n" % (i, pol((S21dB, S21Deg))))

                        # impedance of ideal Short
                        imp = complex(0, 0)

                        # Calculate effective impedance of ideal Short
                        imp = self.uPhaseShiftImpedance(50, phaseDelay, imp)

                        # calc ideal Short response taking into account the delay
                        (idealShortS11Mag, idealShortS11Deg) = self.uImpedanceToRefco(self.S21JigR0, imp)

                        # calc S21 from the refco of the effective impedance
                        (idealShortS21dB, idealShortS21Deg) = self.uRefcoToShuntS21DB(idealShortS11Mag, idealShortS11Deg)

                        if self.oslDbg:
                            f.write("%2d idealShortS21 %s\n" % (i, pol((idealShortS21dB, idealShortS21Deg))))

                        # Adjust by the measured Open reading
                        idealShortS21dB = idealShortS21dB - S21dB
                        idealShortS21Deg = uNormalizeDegrees(idealShortS21Deg - S21Deg)

                        # impedance of ideal Load
                        imp = complex(self.S21JigR0, 0)

                        # Calculate effective impedance of ideal Load
                        imp = self.uPhaseShiftImpedance(50, phaseDelay, imp)

                        # calc ideal Load response taking into account the delay
                        (idealLoadS11Mag, idealLoadS11Deg) = self.uImpedanceToRefco(self.S21JigR0, imp)

                        #calc S21 from the refco of the effective impedance
                        (idealLoadS21dB, idealLoadS21Deg) = self.uRefcoToShuntS21DB(idealLoadS11Mag, idealLoadS11Deg)

                        if self.oslDbg:
                            f.write("%2d idealLoadS21 %s\n" % (i, pol((idealLoadS21dB, idealLoadS21Deg))))

                        # Adjust by the same amount that the measured Open was high
                        idealLoadS21dB = idealLoadS21dB - S21dB
                        idealLoadS21Deg = uNormalizeDegrees(idealLoadS21Deg - S21Deg)

                        self.OSLcalOpen[i] = (0, 0)          # Adjust open with itself as reference, resulting in 0 (dB/ang form)
                        self.OSLstdShort[i] = complex(-1,0)  # Force spec of short to be ideal (real/imag)
                        self.OSLcalShort[i] = (idealShortS21dB, idealShortS21Deg)  # Pretend we measured the ideal short
                        self.OSLstdLoad[i] = complex(0, 0)   # Force spec of load to be ideal (real/imag)
                        self.OSLcalLoad[i] = (idealLoadS21dB, idealLoadS21Deg)     # Pretend we measured the ideal load

#                 else    'series fixture
# Series is similar to shunt, except cal is with Short, and we don't deal with delays so everything is simpler.
#                     call uRefcoToSeriesS21DB S11Mag, S11Deg, S21dB, S21Deg      'S21 that the actual short would produce
#                     if S11dB>-0.25 and S11Deg<5 and S11Deg>-5 then _
#                         notice "Reference calibration standard is too close to an Open." : OSLError=1 : exit sub
#                     OSLcalShort(i,0)=0 : OSLcalShort(i,1)=0  'Adjust short with itself as reference, resulting in 0 (dB/ang form)
#                     OSLstdOpen(i,0)=1 : OSLstdOpen(i,1)=0   'Force spec of Open to be ideal  (real/imag)
#                     OSLcalOpen(i,0)=-99-S21dB : OSLcalOpen(i,1)=uNormalizeDegrees(0-S21Deg)   'Pretend we measured the ideal Open (dB/ang form)
#                     OSLstdLoad(i,0)=0 : OSLstdLoad(i,1)=0  'Force spec of load to be ideal (real/imag)
# Load would be 3.52 dB below ideal short; actual short would produce
# S21dB@S21Deg but we set measured short to zero, so we also have to
# subtract S21dB@S21Deg from ideal load.
#                     OSLcalLoad(i,0)=-3.52-S21dB : OSLcalLoad(i,1)=uNormalizeDegrees(0-S21Deg)  'Pretend we measured the ideal load (dB/ang form)
#                 end if
#             end if
#             OSLBandRef(i,0)=ReflectArray(i,0)    'freq--actual tuning freq, not equiv 1G freq
#             OSLBandRef(i,1)=measDB :OSLBandRef(i,2)=measDeg 'save reference   'Save the measured reference
#         next i

                    else:    # series fixture
                        # Series is similar to shunt, except cal is with Short, and we don't
                        # deal with delays so everything is simpler.

                        # S21 that the actual short would produce
                        (S21dB, S21Deg) = self.uRefcoToSeriesS21DB(S11Mag, S11Deg)
                        if S11dB > -0.25 and S11Deg < 5 and S11Deg > -5:
                            message("Reference calibration standard is too close to an Open.") # EON Jan 29, 2014
                            self.OSLError = True
                            return

                        # Adjust short with itself as reference, resulting in 0 (dB/ang form)
                        self.OSLcalShort[i] = (0, 0)
                        # Force spec of Open to be ideal  (real/imag)
                        self.OSLstdOpen[i] = complex(1, 0)
                        # Pretend we measured the ideal Open (dB/ang form)
                        self.OSLcalOpen[i] = (-99 - S21dB, uNormalizeDegrees(-S21Deg))
                        # Force spec of load to be ideal (real/imag)
                        self.OSLstdLoad[i] = complex(0, 0)

                        # Load would be 3.52 dB below ideal short; actual short would produce
                        # S21dB@S21Deg but we set measured short to zero, so we also have to
                        # subtract S21dB@S21Deg from ideal load.

                        # Pretend we measured the ideal load (dB/ang form)
                        self.OSLcalLoad[i] = (-3.52 - S21dB, uNormalizeDegrees(-S21Deg))

                if self.oslDbg:
                    f.write("%2d, calOpen (%10.3e, %10.3e)," % (i, self.OSLcalOpen[i][0], self.OSLcalOpen[i][1]))
                    f.write(" calShort (%10.3e, %10.3e)" % (self.OSLcalShort[i][0], self.OSLcalShort[i][1]))
                    f.write(" calLoad (%10.3e, %10.3e)\n" % (self.OSLcalLoad[i][0], self.OSLcalLoad[i][1]))

                    f.write("%2d, stdOpen (%10.3e, %10.3e)," % (i, self.OSLstdOpen[i].real, self.OSLstdOpen[i].imag))
                    f.write(" stdShort (%10.3e, %10.3e)" % (self.OSLstdShort[i].real, self.OSLstdShort[i].imag))
                    f.write(" stdLoad (%10.3e, %10.3e)\n" % (self.OSLstdLoad[i].real, self.OSLstdLoad[i].imag))

                    f.write("%2d, freq %7.0f, measDB %10.3e, measDeg %10.3e\n\n" % (i, freq, measDB, measDeg))
                self.OSLBandRef[i] = (measDB, measDeg)


#     else    'All three standards used   'ver116-4n
# We need to determine what to use for the reference. It will be Open,
# Short or Load, whichever has the largest value.  The goal is to avoid
# the Open with a series fixture or a Short with a shunt fixture.
#         open1=OSLcalOpen(0,0) : load1=OSLcalLoad(0,0) : short1=OSLcalShort(0,0)
#         if open1>=load1 then    'choose biggest
#             if open1>=short1 then OSLBandRefType$="Open" else OSLBandRefType$="Short"
#         else
#             if load1>short1 then OSLBandRefType$="Load" else OSLBandRefType$="Short"
#         end if
#
#         for i=0 to globalSteps  'copy reference and adjust measurements per reference
#             OSLBandRef(i,0)=ReflectArray(i,0)    'freq--actual tuning freq, not equiv 1G freq
#             select case OSLBandRefType$
#                 case "Open" : refdB=OSLcalOpen(i,0) : refDeg=OSLcalOpen(i,1)
#                 case "Short" : refdB=OSLcalShort(i,0) : refDeg=OSLcalShort(i,1)
#                 case else : refdB=OSLcalLoad(i,0) : refDeg=OSLcalLoad(i,1)
#             end select
#             OSLBandRef(i,1)=refdB :OSLBandRef(i,2)=refDeg 'save reference
#             OSLcalOpen(i,0)=OSLcalOpen(i,0)-refdB : OSLcalOpen(i,1)=uNormalizeDegrees(OSLcalOpen(i,1)-refDeg)   'Adjust measurements per reference
#             OSLcalLoad(i,0)=OSLcalLoad(i,0)-refdB : OSLcalLoad(i,1)=uNormalizeDegrees(OSLcalLoad(i,1)-refDeg)
#             OSLcalShort(i,0)=OSLcalShort(i,0)-refdB : OSLcalShort(i,1)=uNormalizeDegrees(OSLcalShort(i,1)-refDeg)

        else:    # All three standards used
            # We need to determine what to use for the reference. It will be Open,
            # Short or Load, whichever has the largest value.  The goal is to avoid
            # the Open with a series fixture or a Short with a shunt fixture.
            open1 = self.OSLcalOpen[0][0]
            load1 = self.OSLcalLoad[0][0]
            short1 = self.OSLcalShort[0][0]
            if self.oslDbg:
                f.write("open %10.3e load %10.3e short %10.3e\n" % (open1, load1, short1))
            if open1 >= load1:
                if open1 >= short1:
                    self.OSLBandRefType = "Open"
                else:
                    self.OSLBandRefType = "Short"
            else:
                if load1 > short1:
                    self.OSLBandRefType = "Load"
                else:
                    self.OSLBandRefType = "Short"

            if self.oslDbg:
                f.write("%s\n" % (self.OSLBandRefType))

            for i in range (0, self._nSteps):
                if self.OSLBandRefType == "Open":
                    (refdB, refDeg) = self.OSLcalOpen[i]
                elif self.OSLBandRefType == "Short":
                    (refdB, refDeg) = self.OSLcalShort[i]
                else:
                    (refdB, refDeg) = self.OSLcalLoad[i]

                if self.oslDbg:
                    f.write("%2d, ref  %s\n" % (i, pol((refdB, refDeg))))

                self.OSLBandRef[i] = (refdB, refDeg)

                # Adjust measurements per reference
                (db, deg) = self.OSLcalOpen[i]
                self.OSLcalOpen[i] = (db - refdB, uNormalizeDegrees(deg - refDeg))
                (db, deg) = self.OSLcalLoad[i]
                self.OSLcalLoad[i] = (db - refdB, uNormalizeDegrees(deg - refDeg))
                (db, deg) = self.OSLcalShort[i]
                self.OSLcalShort[i] = (db - refdB, uNormalizeDegrees(deg - refDeg))

#         next i
#     end if
#
# ver116-4k deleted creation of missing standard when we have two. Current procedure never allows us to end up with two.
#     OSLError=0  'ver116-4k
#

        self.OSLError = False

# We want to convert the OSLcalxxx() data into S11 in rectangular form
# (real, imaginary), and calc OSL coefficients.  We leave the reference
# data in db, ang (degrees) format

#     kDegToRad=uRadsPerDegree()
#     for i=0 to globalSteps
#         rho=10^(OSLcalOpen(i,0)/20) : rad=OSLcalOpen(i,1)*kDegToRad 'to polar, radians
#         OSLcalOpen(i,0)=cos(rad)*rho : OSLcalOpen(i,1)=sin(rad)*rho 'polar to rectangular
#         rho=10^(OSLcalLoad(i,0)/20) : rad=OSLcalLoad(i,1)*kDegToRad
#         OSLcalLoad(i,0)=cos(rad)*rho : OSLcalLoad(i,1)=sin(rad)*rho
#         rho=10^(OSLcalShort(i,0)/20) : rad=OSLcalShort(i,1)*kDegToRad
#         OSLcalShort(i,0)=cos(rad)*rho : OSLcalShort(i,1)=sin(rad)*rho
#     next i

        # We want to convert the OSLcalxxx() data into S11 in rectangular form
        # (real, imaginary), and calc OSL coefficients.  We leave the reference
        # data in db, ang (degrees) format

        for i in range (0, self._nSteps):
            (db, deg) = self.OSLcalOpen[i]
            if self.oslDbg:
                f.write("%2d, calOpen  %s," % (i, pol((db, deg))))
            self.OSLcalOpen[i] = cmath.rect(10 ** (db / 20), deg * RadsPerDegree)
            if self.oslDbg:
                f.write(" %s\n" % cpx(self.OSLcalOpen[i]))

            (db, deg) = self.OSLcalLoad[i]
            if self.oslDbg:
                f.write("%2d, calLoad  %s," % (i, pol((db, deg))))
            self.OSLcalLoad[i] = cmath.rect(10 ** (db / 20), deg * RadsPerDegree)
            if self.oslDbg:
                f.write(" %s\n" % cpx(self.OSLcalLoad[i]))

            (db, deg) = self.OSLcalShort[i]
            if self.oslDbg:
                f.write("%2d, calShort %s," % (i, pol((db, deg))))
            self.OSLcalShort[i] = cmath.rect(10 ** (db / 20), deg * RadsPerDegree)
            if self.oslDbg:
                f.write(" %s\n\n" % cpx(self.OSLcalShort[i]))

        if self.oslDbg:
            f.close()

        # Calculate A, B, C coefficients; set OSLError to 1 if math error
        self.CalcOSLCoeff()

# end sub
#

# sub CalcOSLCoeff

    def CalcOSLCoeff(self):

#
# Calc coeff a, b, c for base or band OSL cal
#
# We calculate OSL coefficients for the most general case, where no
# advance assumptions are made about the cal standards.  OSLcalOpen(),
# OSLcalShort() and OSLcalLoad() have the raw calibration data (real,
# imag form) OSLstdOpen and OSLstdOpen() have the S11 data for the Open
# and Short standards (real, imag form) MO,ML, MS are the measured
# responses with the open, load and short attached SO, SL, SS are the
# actual reflection coeff. of the open, short and load standards
#
# The error model equation is as follows, where S is the actual S11 and M is
#
# the measured S11:
#   S = (M - b) / (a - c * M)
#
# Using S and M for the Open, Short and Load, we can calculate the
# coefficients a, b and c.  The double letter variables Mx and Sx are
# the measured and actual values, the second letter (O, S or L)
# indicating open, short or load.
#
# The double letter variables Mx and Sx are the measured and actual
# values, with the second letter (O, S or L) indicating open, short or
# load.
#
#    K1 = ML - MS
#    K2 = MS - MO
#    K3 = MO - ML
#    K4 = SL * SS * K1
#    K5 = SO * SS * K2
#    K6 = SL * SO * K3
#    K7 = SO * K1
#    K8 = SL * K2
#    K9 = SS * K3
#
#    D = K4 + K5 + K6
#
#    a = (MO * K7 + ML * K8 + MS * K9) / D
#    b = (MO * K4 + ML * K5 + MS * K6) / D
#    c = (K7 + K8 + K9) / D
#
#     for calStep=0 to globalSteps
#         MOr=OSLcalOpen(calStep,0) : MOi=OSLcalOpen(calStep,1)     'Measured open, real and imag
#         MLr=OSLcalLoad(calStep,0) : MLi=OSLcalLoad(calStep,1)     'Measured load, real and imag
#         MSr=OSLcalShort(calStep,0) : MSi=OSLcalShort(calStep,1)     'Measured short, real and imag
#         SOr=OSLstdOpen(calStep,0) : SOi=OSLstdOpen(calStep,1)     'Open standard, real and imag
#         SLr=OSLstdLoad(calStep,0) : SLi=OSLstdLoad(calStep,1)     'Load standard, real and imag
#         SSr=OSLstdShort(calStep,0) : SSi=OSLstdShort(calStep,1)     'Short standard, real and imag

        if self.oslDbg:
            f = open("OSLCoef1.txt", "w")
        for i in range (0, self._nSteps):
            MO = self.OSLcalOpen[i]     # Measured open, real and imag
            ML = self.OSLcalLoad[i]     # Measured load, real and imag
            MS = self.OSLcalShort[i]    # Measured short, real and imag

            SO = self.OSLstdOpen[i]     # Open standard, real and imag
            SL = self.OSLstdLoad[i]     # Load standard, real and imag
            SS = self.OSLstdShort[i]    # Short standard, real and imag
            if self.oslDbg:
                f.write("%3d mo (%10.3e, %10.3e) ml (%10.3e, %10.3e) ms (%10.3e, %10.3e)\n" % (i, MO.real, MO.imag, ML.real, ML.imag, MS.real, MS.imag))
                f.write("%3d so (%10.3e, %10.3e) sl (%10.3e, %10.3e) ss (%10.3e, %10.3e)\n" % (i, SO.real, SO.imag, SL.real, SL.imag, SS.real, SS.imag))

#         K1r=MLr-MSr : K1i=MLi-MSi   'K1=ML-MS, real and imag
#         K2r=MSr-MOr : K2i=MSi-MOi   'K2=MS-MO, real and imag
#         K3r=MOr-MLr : K3i=MOi-MLi   'K3=MO-ML, real and imag
#
#         Wr=SLr*SSr-SLi*SSi : Wi=SLr*SSi+SLi*SSr   'W=SL*SS
#         K4r=Wr*K1r-Wi*K1i : K4i=Wr*K1i+Wi*K1r     'K4=SL*SS*K1
#
#         Wr=SOr*SSr-SOi*SSi : Wi=SOr*SSi+SOi*SSr   'W=SO*SS
#         K5r=Wr*K2r-Wi*K2i : K5i=Wr*K2i+Wi*K2r     'K5=SO*SS*K2
#
#         Wr=SLr*SOr-SLi*SOi : Wi=SLr*SOi+SLi*SOr   'W=SL*SO
#         K6r=Wr*K3r-Wi*K3i : K6i=Wr*K3i+Wi*K3r     'K6=SL*SO*K3
#
#         K7r=SOr*K1r-SOi*K1i : K7i=SOr*K1i+SOi*K1r     'K7=SO*K1
#
#         K8r=SLr*K2r-SLi*K2i : K8i=SLr*K2i+SLi*K2r     'K8=SL*K2
#
#         K9r=SSr*K3r-SSi*K3i : K9i=SSr*K3i+SSi*K3r     'K9=SS*K3
#
#         Dr=K4r+K5r+K6r : Di=K4i+K5i+K6i    'D = K4 + K5 + K6

            K1 = ML - MS
            K2 = MS - MO
            K3 = MO - ML
            K4 = SL * SS * K1
            K5 = SO * SS * K2
            K6 = SL * SO * K3

            K7 = SO * K1
            K8 = SL * K2
            K9 = SS * K3

            if self.oslDbg:
                f.write("%3d k1 (%10.3e, %10.3e) k2 (%10.3e, %10.3e) k3 (%10.3e, %10.3e)\n" % (i, K1.real, K1.imag, K2.real, K2.imag, K3.real, K3.imag))
                f.write("%3d k4 (%10.3e, %10.3e) k5 (%10.3e, %10.3e) k6 (%10.3e, %10.3e)\n" % (i, K4.real, K1.imag, K5.real, K5.imag, K6.real, K6.imag))
                f.write("%3d k7 (%10.3e, %10.3e) k8 (%10.3e, %10.3e) k9 (%10.3e, %10.3e)\n" % (i, K7.real, K1.imag, K8.real, K8.imag, K9.real, K9.imag))

            D = K4 + K5 + K6

#         if Dr=0 and Di=0 then notice "Divide by zero in calculating OSL coefficients." : OSLError=1 : exit sub  'ver115-4j
#         call cxInvert Dr, Di, invDr, invDi   'invD= 1/D
# Now calculate coefficient a
#         Wr=MOr*K7r-MOi*K7i : Wi=MOr*K7i+MOi*K7r   'W=MO*K7
#         Xr=MLr*K8r-MLi*K8i : Xi=MLr*K8i+MLi*K8r   'X=ML*K8
#         Yr=MSr*K9r-MSi*K9i : Yi=MSr*K9i+MSi*K9r   'Y=MS*K9
#         Zr=Wr+Xr+Yr : Zi=Wi+Xi+Yi                  'Z=MO*K7 + ML*K8 + MS*K9
#         ar=Zr*invDr-Zi*invDi : ai=Zr*invDi+Zi*invDr   'a=(MO*K7 + ML*K8 + MS*K9)/D
#
# The procedure for calculating b is identical to that for a,
# just changing the K values.
#         Wr=MOr*K4r-MOi*K4i : Wi=MOr*K4i+MOi*K4r   'W=MO*K4
#         Xr=MLr*K5r-MLi*K5i : Xi=MLr*K5i+MLi*K5r   'X=ML*K5
#         Yr=MSr*K6r-MSi*K6i : Yi=MSr*K6i+MSi*K6r   'Y=MS*K6
#         Zr=Wr+Xr+Yr : Zi=Wi+Xi+Yi                  'Z=MO*K4 + ML*K5 + MS*K6
#         br=Zr*invDr-Zi*invDi : bi=Zr*invDi+Zi*invDr   'b=(MO*K4 + ML*K5 + MS*K6)/D
#
# Calculate coefficient c.
#         Wr=K7r+K8r+K9r : Wi=K7i+K8i+K9i     'W = K7 + K8 + K9
#         cr=Wr*invDr-Wi*invDi : ci=Wr*invDi+Wi*invDr   'c = (K7 + K8 + K9)/D
#
# Put coefficients into OSLBandx()
#         OSLBandA[i]=ar : OSLBandA(calStep,1)=ai
#         OSLBandB[i]=br : OSLBandB(calStep,1)=bi
#         OSLBandC[i]=cr : OSLBandC(calStep,1)=ci
#     next calStep

            try:
                invD = 1 / D
            except ZeroDivisionError:
                message("Divide by zero in calculating OSL coefficients.") # EON Jan 29, 2014
                self.OSLError = True
                return

            # Now calculate coefficient a
            a = (MO * K7 + ML * K8 + MS * K9) * invD

            # The procedure for calculating b is identical to that for a,
            # just changing the K values.
            b = (MO * K4 + ML * K5 + MS * K6) * invD

            # Calculate coefficient c.
            c = (K7 + K8 + K9) * invD

            # Put coefficients into OSLBandx()
            self.OSLBandA[i] = a
            self.OSLBandB[i] = b
            self.OSLBandC[i] = c
            if self.oslDbg:
                f.write("%3d a (%10.3e, %10.3e), b (%10.3e, %10.3e), c (%10.3e, %10.3e)\n\n" % (i, a.real, a.imag, b.real, b.imag, c.real, c.imag))

        if self.oslDbg:
            f.close()
# end sub
#

# sub CalcOSLCoeff1

    def CalcOSLCoeff1(self):

# Here we use the measured reflection coefficients for the open, load
# and short to determine OSL coefficients a, b and c. These in turn can
# be used to calculate actual reflection coefficients from measured
# reflection coefficients by the following formulas:
#
#        M = (S + a) / (b * S + c)
#        S = (a - c * M) / (b * M - 1)
#
# where S is the actual reflection coefficient and M is the measured
# reflection coefficient.  For subscripting variables in code and in
# the comments, the suffixes O, L and S mean Open, Load and Short,
# respectively. For example, SL is the actual reflection coefficient of
# the load; MS is the measured reflection loss of the short.
#
# The measured return losses for the open, load and short are
# determined at each frequency step before invoking this method, and
# placed into the arrays OSXOpenR, OSXOpenI, OSXLoadR, OSXLoadI,
# OSXShortR and OSXShortI. Variable names use the suffixes R and I for
# the real and imaginary parts, respectively.  We could first do a line
# calibration with the Open and then measure just the load and short,
# assigning a perfect "1" to the Open.  But to keep this calculation
# generic, if that is done the entries for the measured
#
# Open should just be assigned a value of 1 before invoking CalcOSL.
# We allow for the actual return losses of the open and short to be
# something other than ideal, by using arrays to hold their values at
# each frequency step.
#

#
# Calc coeff a, b, c for base or band OSL cal
#
# OSLcalOpen(), OSLcalShort() and OSLcalLoad() have the raw calibration
# data (real, imag form) OSLstdOpen and OSLstdOpen() have the S11 data
# for the Open and Short standards (real, imag form)
#
# MO,ML, MS are the measured responses with the open, load and short
# attached SO, SL, SS are the actual reflection coeff. of the open,
# short and load standards
#
# (SL is assumed=0)
# All must be in real, imaginary form
# The adjustment is made by the following formula:
#
#       S = (a - c * M) / (b * M - 1)
#
# This model is different from that used in CalcOSLCoeff where S is
# the actual reflection coefficient and M is the measured reflection
# coefficient.
#
# The coefficients a, b and c are calculated according to the following
# formulas:
#
# K1 = ML - MO; approx. -1
# K2 = MS - ML; appro.x -1
# K3 = MO - MS; approx. 2
#
# D = MS * SS * K1 + MO * SO * K2; approx -2
#
# c = SO * SS * K3 / D
# a = ML * c
# b = [SO * K2 + SS * K1] / D
#
#     for calStep=0 to globalSteps
#         MOr=OSLcalOpen(calStep,0) : MOi=OSLcalOpen(calStep,1)     'Measured open, real and imag
#         MLr=OSLcalLoad(calStep,0) : MLi=OSLcalLoad(calStep,1)     'Measured load, real and imag
#         MSr=OSLcalShort(calStep,0) : MSi=OSLcalShort(calStep,1)     'Measured short, real and imag
#         SOr=OSLstdOpen(calStep,0) : SOi=OSLstdOpen(calStep,1)     'Open standard, real and imag
#         SSr=OSLstdShort(calStep,0) : SSi=OSLstdShort(calStep,1)     'Short standard, real and imag

        for i in range (0, self._nSteps):
            MO = self.OSLcalOpen[i]    # Measured open, real and imag
            ML = self.OSLcalLoad[i]    # Measured load, real and imag
            MS = self.OSLcalShort[i]   # Measured short, real and imag
            SO = self.OSLstdOpen[i]    # Open standard, real and imag
            SS = self.OSLstdShort[i]   # Short standard, real and imag

#
# Compute Ks
#         K1r=MLr-MOr : K1i=MLi-MOi   'K1, real and imag
#         K2r=MSr-MLr : K2i=MSi-MLi   'K2, real and imag
#         K3r=MOr-MSr : K3i=MOi-MSi   'K3, real and imag

            # Compute Ks
            K1 = ML - MO
            K2 = MS - ML
            K3 = MO - MS

#
# Compute 1/D
#         Wr=MSr*SSr-MSi*SSi : Wi=MSr*SSi+MSi*SSr     'MS*SS
#         Xr=Wr*K1r-Wi*K1i : Xi=Wr*K1i+Wi*K1r     'MS*SS*K1
#         Yr=MOr*SOr-MOi*SOi : Yi=MOr*SOi+MOi*SOr     'MO*SO
#         Zr=Yr*K2r-Yi*K2i : Zi=Yr*K2i+Yi*K2r     'MO*SO*K2
#         Dr=Xr+Zr : Di=Xi+Zi     'D=MS*SS*K1 + MO*SO*K2
#         if Dr=0 and Di=0 then notice "Divide by zero in calculating OSL coefficients." : OSLError=1 : exit sub  'ver115-4j
#         call cxInvert Dr, Di, DinvR, DinvI       'Invert of D is in Dinv

            # Compute 1/D
            D = (MS * SS * K1) + (MO * SO * K2)
            try:
                invD = 1 / D
            except ZeroDivisionError:
                message("Divide by zero in calculating OSL coefficients.") # EON Jan 29, 2014
                self.OSLError = True
                return

# Compute c
#         Wr=SOr*SSr-SOi*SSi : Wi=SOr*SSi+SOi*SSr     'SO*SS
#         Xr=Wr*K3r-Wi*K3i : Xi=Wr*K3i+Wi*K3r     'X=SO*SS*K3
#         cr=DinvR*Xr-DinvI*Xi : ci=DinvR*Xi+DinvI*Xr     'c=X/D
# Compute a
#         ar=MLr*cr-MLi*ci : ai=MLr*ci+MLi*cr     'a=ML*c
# Compute b
#         Wr=SOr*K2r-SOi*K2i : Wi=SOr*K2i+SOi*SSr     'SO*K2
#         Xr=SSr*K1r-SSi*K1i : Xi=SSr*K1i+SSi*K1r     'SS*K1
#         Yr=Wr+Xr : Yi=Wi+Xi                    'Y=SO*K2 + SS*K1
#         br=DinvR*Yr-DinvI*Yi : bi=DinvR*Yi+DinvI*Yr     'b=Y/D

            c = (SO * SS * K3) * invD
            a = ML * c
            b = (SO * K2 + SS * K1) * invD

# Put coefficients into OSLBandx()
#         OSLBandA(calStep,0)=ar : OSLBandA(calStep,1)=ai
#         OSLBandB(calStep,0)=br : OSLBandB(calStep,1)=bi
#         OSLBandC(calStep,0)=cr : OSLBandC(calStep,1)=ci

            # Put coefficients into OSLBandx()
            self.OSLBandA[i] = a
            self.OSLBandB[i] = b
            self.OSLBandC[i] = c

#     next calStep
# end sub

# sub CalcOSLStandards

    def CalcOSLStandards(self):

#
# Calculate ref. coeff. of OSL standards
#
# The Open, Short and Load are each characterized as either a series or
# parallel RLC circuit to ground at the end of a coax delay line. This
# follows the normal format of an RLC spec used by uRLCComboResponse,
# though it is usually fairly simple.
#
# The Open is generally characterized as a time delay plus a fringe
# capacitance. The Short is generally characterized as a time delay plus
# a parallel resistance/inductance shunted to ground. The Load is
# generally characterized as a delay and resistance, and either a
# parallel capacitance or a series inductance.
#
# For each frequency in datatable, calculate the Open and Short
# response. Put the open response into OSLstdOpen() and Short response
# into OSLstdShort(), both in real, imag form.  The response is
# calculated relative to the jig or bridge R0, not the graph R0.
#
#     if S11JigType$="Trans" then R0=S21JigR0 else R0=S11BridgeR0
#     for i=0 to globalSteps :uWorkArray(i+1,0)=ReflectArray(i,0) : next i 'load frequencies into uWorkArray
#     uWorkNumPoints=globalSteps+1    'number of points is one more than number of steps
#     isErr=uRLCComboResponse(OSLOpenSpec$, R0, "S11") 'Calculate open standard response at all frequencies
#     if isErr then notice "Error in OSL standards specifications" : OSLError=1 : exit sub
#     radsPerDeg=uRadsPerDegree() 'For conversion from degrees to rads
#     for i=0 to globalSteps
#         rho=uTenPower(uWorkArray(i+1,1)/20) : theta=uWorkArray(i+1, 2)*radsPerDeg
#         OSLstdOpen(i, 0)=rho*cos(theta) : OSLstdOpen(i,1)=rho*sin(theta)    'real, imag format
#     next i

        if self.oslDbg:
            f = open("ComboResponse1.txt","w")
            f.close()
            f = open("ComboImpedance1.txt","w")
            f.close()

        # Calculate open standard response at all frequencies
        if self.S11JigType == "Trans":
            R0 = self.S21JigR0
        else:
            R0 = self.S11BridgeR0

        spec = self.OslOpenSpec
        isErr = self.uRLCComboResponse(spec, R0, "S11")
        if isErr:
            message("Error in OSL standards specifications.") # EON Jan 29, 2014
            self.OSLError = True
            return

        if self.oslDbg:
            f = open("OSLstdOpen1.txt","w")

        for i in range (0, self._nSteps):
            (rho, theta) = self.comboResp[i]
            rho = (10 ** (rho / 20))
            theta = theta * RadsPerDegree
            self.OSLstdOpen[i] = cmath.rect(rho, theta)
            if self.oslDbg:
                f.write("%2d, freq %7.0f, rho %10.3e, theta %9.2e, stdOpen r %10.3e, i %9.2e\n" %
                        (i, self.Fmhz[i], rho, theta, self.OSLstdOpen[i].real, self.OSLstdOpen[i].imag))
        if self.oslDbg:
            f.close()

#     isErr=uRLCComboResponse(OSLShortSpec$, R0, "S11") 'Calculate short standard response at all frequencies
#     if isErr then notice "Error in OSL standards specifications" : OSLError=1 : exit sub
#     for i=0 to globalSteps
#         rho=uTenPower(uWorkArray(i+1,1)/20) : theta=uWorkArray(i+1, 2)*radsPerDeg
#         OSLstdShort(i, 0)=rho*cos(theta) : OSLstdShort(i,1)=rho*sin(theta)    'real, imag format
#     next i

        # Calculate short standard response at all frequencies
        spec = self.OslShortSpec
        isErr = self.uRLCComboResponse(spec, R0, "S11")
        if isErr:
            message("Error in OSL standards specifications.") # EON Jan 29, 2014
            self.OSLError = True
            return

        if self.oslDbg:
            f = open("OSLstdShort1.txt","w")
        for i in range (0, self._nSteps):
            (rho, theta) = self.comboResp[i]
            rho = (10 ** (rho / 20))
            theta = theta * RadsPerDegree
            self.OSLstdShort[i] = cmath.rect(rho, theta)
            if self.oslDbg:
                f.write("%2d, freq %7.0f, rho %10.3e, theta %9.2e, stdShort r %10.3e, i %9.2e\n" %
                        (i, self.Fmhz[i], rho, theta, self.OSLstdShort[i].real, self.OSLstdShort[i].imag))
        if self.oslDbg:
            f.close()

#     isErr=uRLCComboResponse(OSLLoadSpec$, R0, "S11") 'Calculate load standard response at all frequencies
#     if isErr then notice "Error in OSL standards specifications" : OSLError=1 : exit sub
#     for i=0 to globalSteps
#         rho=uTenPower(uWorkArray(i+1,1)/20) : theta=uWorkArray(i+1, 2)*radsPerDeg
#         OSLstdLoad(i, 0)=rho*cos(theta) : OSLstdLoad(i,1)=rho*sin(theta)    'real, imag format
#     next i

        # Calculate short standard response at all frequencies
        spec = self.OslLoadSpec
        isErr = self.uRLCComboResponse(spec, R0, "S11")
        if isErr:
            message("Error in OSL standards specifications.") # EON Jan 29, 2014
            self.OSLError = True
            return

        if self.oslDbg:
            f = open("OSLstdLoad1.txt","w")
        for i in range (0, self._nSteps):
            (rho, theta) = self.comboResp[i]
            rho = (10 ** (rho / 20))
            theta = theta * RadsPerDegree
            self.OSLstdLoad[i] = cmath.rect(rho, theta)
            if self.oslDbg:
                f.write("%2d, freq %7.0f, rho %10.3e, theta %9.2e, stdLoad r %10.3e, i %9.2e\n" %
                        (i, self.Fmhz[i], rho, theta, self.OSLstdLoad[i].real, self.OSLstdLoad[i].imag))
        if self.oslDbg:
            f.close()

# end sub

# sub uS11DBToImpedance R0, S11DB, S11Deg, byRef Res, byRef React   'Calc impedance from S11

    def uS11DBToImpedance(self, R0, S11DB, S11Deg):

#     if S11DB>0 then S11DB=0 'Error condition; could happen from noise or rounding 'ver115-1e
#     m=uTenPower(S11DB/20)    'S11 Mag
#     call uRefcoToImpedance R0, m, S11Deg, Res, React    'ver115-1e

        if S11DB > 0:
            S11DB = 0
        return self.uRefcoToImpedance(R0, 10 ** (S11DB / 20), S11Deg)

# end sub

# sub uRefcoToImpedance R0, rho, theta, byRef Res, byRef React   'Calc impedance from refco: rho, theta (deg)

    def uRefcoToImpedance(self, R0, rho, theta):

#
# Calc impedance from refco: rho, theta (deg)
#
# Z(DUT)= Ro*(1+G)/(1-G), where G is the reflection coefficient
# Special case : if a=1 and b=0 (or close), treat the impedance as huge
# resistance
#     if rho<0 then rho=0    'rho<0 is error but could happen due to rounding
#     if rho>1 then rho=1 'rho should never exceed 1 but might due to noise or rounding ver115-1e

        if rho < 0:
            rho = 0
        if rho > 1:
            rho = 1

#     p=theta*uRadsPerDegree()   'S11 Radians
#     a=rho*cos(p) : b=rho*sin(p)

        p = theta * RadsPerDegree
        a = rho * cos(p)
        b = rho * sin(p)

# a near +1 means rho is near 1 and theta is near zero. We treat these
# as large resistances
#     if 0.999999<a then Res=constMaxValue : React=0 : exit sub   'ver115-4b

        if a > 0.999999:
            return complex(constMaxValue, 0)
#
#     'ver115-1h deleted additional test for a>0.99
#         'Similarly, a near -1 means we have a very small resistance or reactance. It doesn't make much difference
#         'which way we go.
#     if -0.999999>a then Res=0 : React=0 : exit sub   'ver115-4b

        if a < -0.999999:
            return complex(0, 0)

#     Rnum=a*R0+R0 : Inum=R0*b : Rden=1-a : Iden=0-b  'ver115-1e

        num = complex(a * R0 + R0, R0 * b)
        den = complex(1 - a, -b)

# Now do the divide, copying the procedure of cxDivide; faster than
# calling cxDivide First invert the denominator
#     D=Rden^2+Iden^2
#     if D<0.0000000001 then Res=constMaxValue : React=0: exit sub    'a near 1 and b near 0 ver115-1e

        if abs(den) < 0.0000000001:
            return complex(constMaxValue, 0)

#     Rinv=Rden/D : Iinv=0-Iden/D
# Now multiply Rnum+jInum times Rinv+jIinv
#     Res=Rnum*Rinv-Inum*Iinv
#     React=Rnum*Iinv+Inum*Rinv

        Z = num / den

#     if Res<0.001 then Res=0 'avoids printing tiny values
#     if React>-0.001 and React<0.001 then React=0 'avoids printing tiny values

        if Z.real < 0.001:
            Z = complex(0, Z.imag)
        if Z.imag > -0.001 and Z.imag < 0.001:
            Z = complex(Z.real, 0)
        return Z

# end sub

# sub uImpedanceToRefco R0, R, I, byref rho, byref theta 'Calc reflection coefficient as mag/angle from impedance

    def uImpedanceToRefco(self, R0, Z):

# Refco = (Z - R0) / (Z + R0)
#     if R<0 then rho=1 : theta=180 : exit sub  'Negative resistance is error; we return refco of -1, which is right for R=0 ver115-1e

        if R0 < 0:
            return(1, 180)

#     Rnum=R-R0 : Inum=I : Rden=R+R0 : Iden=I
# Now do the divide, copying the procedure of cxDivide; faster than calling cxDivide
# First invert the denominator
#     D=Rden^2+Iden^2
#     if D=0 then Rres=constMaxValue : Ires=0: exit sub
#     Rinv=Rden/D : Iinv=0-Iden/D
# Now multiply Rnum+jInum times Rinv+jIinv
#     refR=Rnum*Rinv-Inum*Iinv
#     refI=Rnum*Iinv+Inum*Rinv

        try:
            Z = (Z - R0) / (Z + R0)
        except ZeroDivisionError:
            return(constMaxValue, 0)

# Convert to polar form
#     rho=sqr(refR^2+refI^2)
#     theta=uATan2(refR, refI)

        (rho, theta) = cmath.polar(Z)
        theta = theta * DegreesPerRad
        return rho, theta

# end sub

# sub uImpedanceToRefcoRI R0, R, I, byref GR, byref GI 'Calc reflection coefficient as real/imag from impedance

    def uImpedanceToRefcoRI(self, R0, Z):

# Refco = (Z - R0) / (Z + R0)
#     if R<0 then GR=-1 : GI=0 : exit sub  'Negative resistance is error; we return refco of -1, which is right for R=0 ver115-1e

        if Z.real < 0:
            return complex(-1, 0)

#     Rnum=R-R0 : Inum=I : Rden=R+R0 : Iden=I
# Now do the divide, copying the procedure of cxDivide; faster than calling cxDivide
# First invert the denominator
#     D=Rden^2+Iden^2
#     if D=0 then Rres=constMaxValue : Ires=0: exit sub
#     Rinv=Rden/D : Iinv=0-Iden/D
# Now multiply Rnum+jInum times Rinv+jIinv
#     GR=Rnum*Rinv-Inum*Iinv
#     GI=Rnum*Iinv+Inum*Rinv

        try:
            Z = (Z - R0) / (Z + R0)
        except ZeroDivisionError:
            Z = complex(constMaxValue, 0)
        return Z

# end sub

# sub uSeriesImpedanceToS21DB R0, R, I, byref db, byref deg 'Calc S21 as db, degrees for series impedance when source,load=R0

    def uSeriesImpedanceToS21DB(self, R0, Z, db, deg):

# S21(Series) = 2 * R0 / (2 * R0 + Z) = 1 / (1 + Z / (2 * R0)) this is in complex number format
#     if R<0 then R=0 'error, but could happen from noise/rounding ver115-1e
#     doubleR0=2*R0

        if Z.real < 0:
            Z = complex(0, Z.imag)

#     doubleR0=2*R0
#     call cxInvert 1+R/doubleR0, I/doubleR0, Rres, Ires
#     deg=uATan2(Rres, Ires)		'phase in degrees
#     db=10*uSafeLog10(Rres^2+Ires^2)	'magnitude in db; mult by 10 not 20, because magnitude is squared

        doubleR0 = 2 * R0
        Z = doubleR0 / (doubleR0 + Z)
        (db, deg) = polarDbDeg(Z)
        return(db, deg)

# end sub

#
# sub uShuntImpedanceToS21DB R0, R, I, delay, freq, byref db, byref deg 'Calc S21 as db, degrees for shunt impedance when source,load=R0

    def uShuntImpedanceToS21DB(self, R0, Z, delay, freq):

# If delay<>0, then we adjust for the connector length of delay ns
# If delay=0, we don't need to know freq here.
# delay is in ns. freq is in Hz
# S21(Shunt) = 2 * Z / (2 * Z + R0) this is in complex number format

#     if delay<>0 then    'ver115-1e
#         'The impedance R+jI is transformed by the transmission line into a different
#         'impedance. We find that impedance and then apply the formula to find S21(Shunt)
#         theta=0.000000360*delay*freq    'degrees
#         call uPhaseShiftImpedance 50, theta, R,I    'We assume a 50-ohm connector no matter what the jig R0. ver115-4a
#     end if

        if delay != 0:
            # The impedance R+jI is transformed by the transmission line into a different
            # impedance. We find that impedance and then apply the formula to find S21(Shunt)
            theta = 0.000000360 * delay * freq
            Z = self.uPhaseShiftImpedance(50, theta, Z) # We assume a 50-ohm connector no matter what the jig R0.

#     if R<0 then R=0 'error, but could happen from noise/rounding ver115-1e
#     call cxDivide 2*R, 2*I, R0+2*R, 2*I, Rres, Ires
#     deg=uATan2(Rres, Ires)   'phase in degrees
#     db=10*uSafeLog10(Rres^2+Ires^2)       'magnitude in db; mult by 10 not 20, because magnitude is squared

        if Z.real < 0:
            Z = complex(0, Z.imag)  #error, but could happen from noise/rounding
        Z = (2 * Z) / (2 * Z + R0)
        (db,deg) = polarDbDeg(Z)
        return db, deg

# end sub

# sub uRefcoToSeriesS21DB rho, theta, byref db, byref deg  'Calc S21 in series jig for impedance with specified relect coeff

    def uRefcoToSeriesS21DB(self, rho, theta):

# refco is reflection coefficient, mag angle; we calculate S21 for shunt
# fixture in db, angle format Reference impedance for S21 is whatever it
# was for S11; it doesn't enter into the calculation
#
# S21 = 2 * (1 - S11) / (2 + (1 - S11)); then convert S21 to db
#     if rho<0 then rho=0    'rho<0 is error but could happen due to rounding
#     if rho>1 then rho=1 'rho should never exceed 1 but might due to noise or rounding ver115-1e

        if rho < 0:
            rho = 0
        if rho > 1:
            rho = 1

#     p=theta*uRadsPerDegree()   'S11 Radians
#     a=rho*cos(p) : b=rho*sin(p) 'S11 rectangular

        p = theta * RadsPerDegree
        a = rho * cos(p)
        b = rho * sin(p)

#     if a>0.99999999 then db=-199 : deg=0 : exit sub   'close to Open so no output ver116-4k

        if a > 0.99999999:
            return -199, 0

#     oneMinusS11Real=1-a : oneMinusS11Imag=0-b
#     call cxDivide 2*oneMinusS11Real, 2*oneMinusS11Imag, 2+oneMinusS11Real, oneMinusS11Imag, S21Real, S21Imag  '2(1-S11)/(2+(1-S11))
#     deg=uATan2(S21Real, S21Imag)   'phase in degrees
#     db=10*uSafeLog10(S21Real^2+S21Imag^2)       'magnitude in db; mult by 10 not 20, because magnitude is squared
#     if db<-199 then db=-199

        oneMinusS11 = complex(1 - a, -b)
        S21 = 2 * oneMinusS11 / (2 + oneMinusS11)
        (db, deg) = polarDbDeg(S21)
        if db < -199:
            db = -199
        return db, deg

# end sub

# sub uRefcoToShuntS21DB rho, theta, byref db, byref deg  'Calc S21 in shunt jig for impedance with specified relect coeff ver116-4k

    def uRefcoToShuntS21DB(self, rho, theta):

# refco is reflection coefficient, mag angle; we calculate S21 for shunt
# fixture in db, angle format delayNS is the connector delay in the
# shunt fixture; freqHZ is the frequency in MHz.  Reference impedance
# for S21 is whatever it was for S11; it doesn't enter into the calculation
#
# S21 =2 * (1 + S11) / (2 + (1 + S11)); then convert S21 to db
#
# This assumes no connector delay in the shunt fixture. To deal with
# that, rho and theta should be calculated from the original impedance
# at the end of an appropriate transmission line, with uPhaseShiftImpedance.
#
#     if rho<0 then rho=0    'rho<0 is error but could happen due to rounding
#     if rho>1 then rho=1 'rho should never exceed 1 but might due to noise or rounding ver115-1e

        if rho < 0:
            rho = 0
        if rho > 1:
            rho = 1

#     p=theta*uRadsPerDegree()   'S11 Radians
#     a=rho*cos(p) : b=rho*sin(p) 'S11 rectangular

        p = theta * RadsPerDegree
        a = rho * cos(p)
        b = rho * sin(p)

#     if a<-0.999999999 then db=-199 : deg=0 : exit sub   'close to short so no output ver116-4k

        if a < -0.99999999:
            return -199, 0

#     onePlusS11Real=1+a : onePlusS11Imag=b
#     call cxDivide 2*onePlusS11Real, 2*onePlusS11Imag, 2+onePlusS11Real, onePlusS11Imag, S21Real, S21Imag  '2(1+S11)/(2+(1+S11))
#     deg=uATan2(S21Real, S21Imag)   'phase in degrees
#     db=10*uSafeLog10(S21Real^2+S21Imag^2)       'magnitude in db; mult by 10 not 20, because magnitude is squared
#     if db<-199 then db=-199

        onePlusS11 = complex(1 + a, b)
        S21 = 2 * onePlusS11 / (2 + onePlusS11)
        (db, deg) = polarDbDeg(S21)
        if db < -199:
            db = -199
        return db, deg

# end sub
#
# function uParseRLC(spec$, byref connect$, byref R, byref L, byref C, byref QL, byref QC, byRef D, byref coaxSpecs$)  'Parse spec for parallel or series RLC; return 1 if error

    def uParseRLC(self, spec):

# spec$ describes a series or parallel combo of R, L and C, possibly at
# the end of a transmission line described per CoaxParseSpecs or by the
# delay factor D. It is in this form:
#
# RLC[S, R25, L10n, C200p, QL10, QC10, D2], Coax[xxx,xxx...]
#
# First item is S for series or P for parallel, referring to the RLC
# combination Remaining items are optional; one R,L,C QL, QC, and D are
# allowed; remaining items are data for coax cable.  Coax data is
# returned as a string, without the "Coax" or brackets, in coaxSpecs$ R,
# L, C and D are in ohms, Henries, Farads and seconds. Multiplier
# characters (k, u, n, etc.) are allowed.  QL and QC are the Q values
# for the L and C D is the delay in seconds (one-way) prior to the
# terminating components. It can be used only if there are no coax specs
# and is forced to 0 if there are.  We return the specified values, and
# return a function value of 0 for no error, 1 for error

#     tagPos=instr(spec$, "RLC")  'find RLC tag
#     if tagPos=0 then
#         RLC$=""
#     else
#         openBracket=instr(spec$, "[", tagPos)   'find open bracket after RLC
#         closeBracket=instr(spec$, "]", tagPos)  'find close bracket after RLC
#         if closeBracket=0 or closeBracket=0 or openBracket>=closeBracket then uParseRLC=1 : exit function
#         RLC$=Mid$(spec$, openBracket+1, closeBracket-openBracket-1) 'Get data in brackets
#     end if

        m = re.match("RLC\\[(.+?)\\]", spec)
        if m == None:
            RLC = ""
        else:
            RLC = m.group(1)

#
#     tagPos=instr(spec$, "Coax")  'find Coax tag
#     if tagPos=0 then
#         coaxSpecs$=""
#     else
#         openBracket=instr(spec$, "[", tagPos)   'find open bracket after Coax
#         closeBracket=instr(spec$, "]", tagPos)  'find close bracket after Coax
#         if closeBracket=0 or closeBracket=0 or openBracket>closeBracket-1 then uParseRLC=1 : exit function
#         coaxSpecs$=Mid$(spec$, openBracket+1, closeBracket-openBracket-1) 'Get data in brackets
#     end if

        m = re.match("Coax\\[(.+?)\\]", spec)
        if m == None:
            coaxSpec = ""
        else:
            coaxSpec = m.group(1)

#      'ver116-4i changed the defaults for backward compatibility with old method to specify OSL standards
#     connect$="P" : R=constMaxValue : L=constMaxValue : C=0 : D=0  'default is series RLC with high impedance and no delay
#     QL=100000 : QC=100000 'ver116-4i
#     commaPos=0
#     if RLC$<>"" then
#         specLen=len(RLC$)
#         isErr=0
#         while commaPos<specLen
#             oldCommaPos=commaPos
#             commaPos=instr(RLC$,",", commaPos+1)
#             if commaPos=0 then commaPos=specLen+1     'Pretend comma follows the string
#             compon$=Trim$(Mid$(RLC$,oldCommaPos+1, commaPos-oldCommaPos-1))   'get this component spec
#             if compon$="" then exit while  'get next word; done if there is none
#             firstChar$=Left$(compon$,1)   'data tag, single character
#             if firstChar$="Q" then
#                 tag$=Left$(compon$,2)   'QL or QC is two characters
#                 data$=Mid$(compon$,3)   'From third character to end
#                 if data$<>"" then v=uValWithMult(data$)   'Value of everything after first char
#             else
#                 tag$=firstChar$
#                 data$=Mid$(compon$,2)   'From second character to end
#                 if data$<>"" then v=uValWithMult(data$)   'Value of everything after first char
#             end if
#             select tag$   'Assign value to proper variable
#                 case "S"
#                     connect$="S"
#                     R=0 : L=0 : C=constMaxValue 'Defaults in case any components are not specified
#                 case "P"
#                     connect$="P"
#                     R=constMaxValue : L=constMaxValue : C=0 'Defaults in case any components are not specified
#                 case "R"
#                     R=v : if R<0 then isErr=1
#                 case "L"
#                     L=v
#                 case "C"
#                     C=v
#                 case "QL"  'ver151-4b
#                     QL=v : if QL<=0 then isErr=1
#                 case "QC"   'ver151-4b
#                     QC=v : if QC<=0 then isErr=1
#                 case "D"   'ver16-4i
#                     if coaxSpecs$="" then D=v   'Record D only if no coax specs
#                 case else   'Invalid component spec
#                     isErr=1
#             end select
#             if connect$="" or isErr then uParseRLC=1 : exit function
#         wend
#     end if  'end RLC

        connect = "P"
        R = constMaxValue
        L = constMaxValue
        C = 0
        D = 0
        QL = 100000
        QC = 100000
        isErr = False
        args = re.split(", *",RLC)
        for val in args:
            m = re.match("([A-Z]+)(.*)",val)
            tag = m.group(1)
            v = m.group(2)
            if tag == "S":
                connect = "S"
                R = 0
                L = 0
                C = constMaxValue
            elif tag == "P":
                connect = "P"
                R = constMaxValue
                L = constMaxValue
                C = 0
            elif v != "":
                v = floatSI(v)
                if tag == "R":
                    R = v
                elif tag == "L":
                    L = v
                elif tag == "C":
                    C = v
                elif tag == QL:
                    QL = v
                elif tag == QC:
                    QC = v
                elif tag == "D":
                    if coaxSpec == "":
                        D = v
                else:
                    isErr = True
            else:
                isErr = True
        return isErr, connect, R, L, C, QL, QC, D, coaxSpec

#     uParseRLC=0
# end function

# sub uComboImpedance connect$, R, L, C, QL, QC, freq, byref Zr, byref Zi   'Calc impedance Zr+j*Zi for RLC combo

    def uComboImpedance(self, connect, R, L, C, QL, QC, freq):

# connect = P for parallel, S for series. R, L and C are connected in
# series or parallel.  For Series circuit, C>=constMaxvalue means treat
# C as a short--there is no C in the circuit For Parallel circuit,
# L>=constMaxValue means treat L as open--there is no L in the circuit
# Units are ohms, Henries, Farads, Hz. Same results are achieved with
# ohms, uh, uf and MHz.  QL is Q of inductor; QC is Q of capacitor
# (Q=reactance/resistance)
#
#     twoPiF=2*uPi()*freq
#     if QC<=0 then QC=0.000001   'avoids problems below
#     if QL<=0 then QC=0.000001

        if self.oslDbg:
            f = open("ComboImpedance1.txt","a")
            f.write("%8.0f %s %5.0f %5.0f %5.0f %5.0f %5.0f\n" % (freq, connect, R, L, C, QL, QC))

        twoPiF = 2 * pi * freq
        if QC <= 0:
            QC = 0.000001
        if QL <= 0:
            QC = 0.000001

#     if freq<>0 and abs(L)<constMaxValue then 'If freq=0, we already have Ai=0; also, ignore huge parallel L
#         ZLi=twoPiF*L :ZLr=ZLi/QL     'Inductor impedance, imag and real, with Q
#     else
#         ZLi=constMaxValue : ZLr=0
#     end if

        if freq != 0 and abs(L) < constMaxValue:
            ZLi = twoPiF * L
            ZL = complex(ZLi / QL, ZLi)
        else:
            ZL = complex(0, constMaxValue)

#     if freq<>0 and C<>0 then    'Ignore C if freq or C is zero, because huge reactance in parallel is irrelevant
#         ZCi=-1/(twoPiF*C) :ZCr=abs(ZCi)/QC     'Capacitor impedance, imag and real, with Q
#     else    'zero freq or C; note that series connection ignores these
#         ZCi=0-constMaxValue : ZCr=0
#     end if

        if freq != 0 and C != 0:
            ZCi = -1 / (twoPiF * C)
            ZC = complex(abs(ZCi) / QC, ZCi)
        else:
            ZC = complex(0, -constMaxValue)

#
#     if connect$="S" then
#         Zr=R+ZLr
#         Zi=ZLi
#         if C=0 or freq=0 then
#             Zi=0-constMaxValue
#         else
#             if abs(C)<constMaxValue then Zi=Zi+ZCi : Zr=Zr+ZCr
#         end if

        if connect == "S":
            Z = R + ZL
            if C == 0 or freq == 0:
                Z = complex(0, -constMaxValue)
            else:
                if abs(C) < constMaxValue:
                    Z = Z + ZC

#     else 'this section modver115-1a
#         if R=0 or L=0 or abs(C)>=constMaxValue then  'parallel with a zero-ohm component
#             Zr=0 : Zi=0
#         else
#             'Parallel Add admittances and then invert
#             Ar=1/R
#             if freq=0 or abs(L)>=constMaxValue then
#                 Ai=0        'Parallel inductance is huge so C will determine the reactance
#             else
#                 call cxInvert ZLr, ZLi, YLr, YLi 'convert to admittance
#                 Ar=Ar+YLr : Ai=YLi      'Add to resistor admittance
#             end if
#             if C=0 then
#                 YCr=0 : YCi =0  'causes cap to be ignored
#             else
#                 call cxInvert ZCr, ZCi, YCr, YCi 'convert to admittance
#             end if
#             Ar=Ar+YCr : Ai=Ai+YCi      'Add to resistor plus inductor admittance
#
#             call cxInvert Ar, Ai, Zr, Zi     'Invert admittance to get impedance of combined circuit
#         end if
#     end if

        else:
            # Parallel Add admittances and then invert
            if (R == 0) or (L == 0) or (abs(C) >= constMaxValue):
                Z = complex(0, 0)
            else:
                A = complex(1 / R, 0)
                if freq == 0 or abs(L) >= constMaxValue:
                    A = complex(A.real, 0) # Parallel inductance is huge so C will determine the reactance
                else:
                    YL = 1 / ZL
                    A = A.real + YL
                if C == 0:
                    YC = complex(0, 0)
                else:
                    YC = 1 / ZC
                A = A + YC
                Z = 1 / A

#     if Zi>constMaxValue then Zi=constMaxValue       'ver115-4h imposed limits
#     if Zi<0-constMaxValue then Zi=0-constMaxValue
#     if Zr>constMaxValue then Zr=constMaxValue

        if self.oslDbg:
            f.write("%10.3e %10.3e\n" % (Z.real, Z.imag))
        if Z.imag > constMaxValue:
            Z = complex(Z.real,constMaxValue)
        if Z.imag < -constMaxValue:
            Z = complex(Z.real, -constMaxValue)
        if Z.real > constMaxValue:
            Z = complex(constMaxValue, Z.imag)
        if Z.real < 0:
            Z = complex(0,Z.imag)
        if self.oslDbg:
            f.write("%10.3e %10.3e\n" % (Z.real, Z.imag))
            f.close()
        return Z

# end sub

# function uRLCComboResponse(spec$, Z0, jig$)

    def uRLCComboResponse(self, spec, Z0, jig):

#
# Calc S21 or S11 response of RLC combo; return 1 if error
# spec$ describes the RLC combo, per uParseRLC
#
# We use the frequencies in uWorkArray (MHz) and calculate S11 or S21
# (db/degrees) for the specified RLC combo We store the resulting db in
# uWorkArray(N, 1) and degrees in uWorkArray(N,2) uWorkArray has
# uWorkNumPoints valid frequency points.  RLC combo connected per
# connect is tested at ref resistance R0 for S21 or S11 If jig == "S11"
# we do S11; if "S21Shunt" we do S21 for shunt connection; otherwise we
# do S21 for series connection.  We calculate the actual S21 or S11
# response that would have been produced by the combination after a
# theoretical perfect calibration is applied. Thus, we do not include
# the effect of S21JigShuntDelay, because that effect would be removed
# by calibration.
#
#     isErr=uParseRLC(spec$, connect$, R, L, C, QL,QC, D, coaxSpecs$)
#     if isErr=0 then isErr=CoaxParseSpecs(coaxSpecs$, R0, VF, K1, K2, lenFeet) 'ver115-5d
#     if isErr or Z0<=0 or R0<=0 then uRLCComboResponse=1 : exit function 'ver115-4a

        (isErr, connect, R, L, C, QL, QC, D, coaxSpecs) = self.uParseRLC(spec)
        if not isErr:
                (isErr, R0, VF, K1, K2, lenFeet) = Coax.CoaxParseSpecs(coaxSpecs) # EON Jan 29, 2014

#     twoPi=2*uPi()
# Note R0 is the impedance of any transmission line in the RLC combo; Z0 is the reference impedance for
# calculating S11 or S21. Both are pure resistances.
#     for i=1 to uWorkNumPoints       'uWorkNumPoints contains the number of frequency points in uWorkArray
#         freq=uWorkArray(i,0)*1000000
#         'if freq<0 then freq=0-freq  'Make frequencies positive delver115-1a
#         call uComboImpedance connect$, R, L, C, QL,QC,freq, RLCZr, RLCZi  'ver115-4b
#         if coaxSpecs$="" and D=0 then   'Simple case--no coax and no delay factor
#             ZReal=RLCZr : ZImag=RLCZi
#         else 'Get impedance of coax terminated by the RLC
#             if jig$="S11" or jig$="S21Shunt" then
#                 if coaxSpecs$<>"" then  'Presence of coax overrides the delay factor
#                     call CoaxTerminatedZFromSpecs coaxSpecs$, uWorkArray(i,0), RLCZr, RLCZi, ZReal, ZImag
#                 else    'Here apply delay factor D (sec) instead of a coax delay ver116-4i
#                     call uImpedanceToRefco R0, RLCZr, RLCZi, rho, theta       'convert to refco
#                     phaseDelay=D*360*freq         'phase delay (deg)=delay(sec)*degrees/cycle*cycles/sec
#                     theta=theta-2*phaseDelay      'Delay reflection by twice phaseDelay, for round trip.
#                     call uRefcoToImpedance R0, rho, theta, ZReal, ZImag
#                 end if
#             else
# Series S21. Any terminating impedance is deemed to be in series, but if the transmission
# line specs are not blank the termination is ignored and the coax is used by itself
#                 if coaxSpecs$<>"" then call CoaxS21FromSpecs Z0, 0, coaxSpecs$, uWorkArray(i,0), db, theta 'ver115-4e
#             end if
#         end if

        if self.oslDbg:
            f = open("ComboResponse1.txt","a")
            f.write("%s, %f, %s, %s, R0 - %f, R - %f, L - %f, C - %f, %f %f\n" % 
                    (spec, Z0, jig, connect, R0, R, L, C, QL, QC))
        for i in range (0, self._nSteps):
            freq = self.Fmhz[i] * 1e6
            RLCZ = self.uComboImpedance(connect, R, L, C, QL, QC, freq)
            if coaxSpecs == "":
                Z = RLCZ
            else:
                if jig == "S11" or jig == "S21Shunt":
                    if coaxSpecs != "":
                        Z = Coax.CoaxTerminatedZFromSpecs(coaxSpecs, freq, RLCZ) # EON Jan 29, 2014
                    else:
                        (rho, theta) = self.uImpedanceToRefco(R0, RLCZ)
                        phaseDelay = D * 360 * freq    #phase delay (deg)=delay(sec)*degrees/cycle*cycles/sec
                        theta = theta - 2 * phaseDelay #Delay reflection by twice phaseDelay, for round trip.
                        Z = self.uRefcoToImpedance(R0, rho, theta)
                else:
                    if coaxSpecs != "":
                        (db, theta) = Coax.CoaxS21FromSpecs(Z0, 0, coaxSpecs, freq) # EON Jan 29, 2014

#         if jig$="S11" then
#             call uImpedanceToRefco Z0, ZReal, ZImag, rho, theta   'Impedance to reflection coefficient
#             db=20*uSafeLog10(rho)   'rho to db
#         else
#             if jig$="S21Shunt" then
#                 call uShuntImpedanceToS21DB Z0, ZReal, ZImag, 0,freq, db, theta 'ver115-4h--Removed S21JigShuntDelay
#             else
# Series S21. If no coax, we use the RLC values in series. If coax,
# we ignore "termination" and just use the S21 (db, theta) calculated above
#                 if coaxSpecs$="" then call uSeriesImpedanceToS21DB Z0, ZReal, ZImag, db, theta 'ver115-1e
#             end if
#         end if

            if jig == "S11":
                (rho, theta) = self.uImpedanceToRefco(Z0, Z)
                db = 20 * uSafeLog10(rho)
            else:
                if jig == "S21Shunt":
                    (db, theta) = self.uShuntImpedanceToS21DB(Z0, Z, 0, freq)
                else:
                    if coaxSpecs == "":
                        (db,theta) = self.uSeriesImpedanceToS21DB(Z0, Z)

#         theta=theta mod 360
#         if theta<=-180 then theta=theta+360  'Put angle in bounds
#         if theta>180 then theta=theta-360
#         uWorkArray(i, 1)=db : uWorkArray(i,2)=theta 'Store db, degrees in uWorkArray

            theta = theta % 360
            if theta <= -180:
                theta = theta + 360
            if theta > 180:
                theta = theta - 360
            if self.oslDbg:
                f.write("%2d, %7.0f, %10.3e, %10.3e, %10.3e, %10.3e\n" % (i, freq, RLCZ.real, RLCZ.imag, db, theta))
            self.comboResp[i] = (db, theta)
        if self.oslDbg:
            f.close()

#     next i
#     uRLCComboResponse=0  'no error
# end function

#sub uPhaseShiftImpedance R0, theta, byref Zr, byref Zi   'Calc impedance of trans line terminated by Zr+j*Zi; replace Zr, Zi

    def uPhaseShiftImpedance(self, R0, theta, Z):

# Theta is in degrees, and can be positive or negative.
#
# If an impedance Z is placed at the end of a transmission line of
# characteristic impedance R0, with a length that causes (one-way)
# phase delay of theta degrees, then the impedance at the input of
# the transmission line is:
#
# newZ=R0*(Z + j*R0*tan(theta))/(R0 + j*Z*tan(theta))
#
# This equation also works with negative theta, which effectively
# calculates the impedance that would produce Zr+jZi after the
# transformation caused by the transmission line with length
# abs(theta).
#
#    while theta>180 : theta=theta-360 : wend
#    while theta<-180 : theta=theta+360 : wend

        theta = uNormalizeDegrees(theta)

#    TanTheta=0
#    if abs(theta-90)<.00000001 then TanTheta=1e9    'near 90; use huge value for tangent
#    if abs(theta+90)<.00000001 then TanTheta=-1e9   'near -90 use huge negative value for tangent
#    if TanTheta=0 then TanTheta=tan(theta*uRadsPerDegree())

        TanTheta=0
        if abs(theta - 90) < .00000001:
            TanTheta = 1e9
        if abs(theta + 90) < .00000001:
            TanTheta=-1e9
        if TanTheta == 0:
            TanTheta=tan(theta * RadsPerDegree)

#    Rnum=Zr : Inum=Zi+R0*TanTheta
#    Rden=R0-Zi*TanTheta : Iden=Zr*TanTheta  'denominator.

        Znum = complex(Z.real, Z.imag + R0 * TanTheta)
        Zden = complex(R0 - Z.imag * TanTheta, Z.real * TanTheta)

#    if abs(Rden)<0.000000001 and abs(Iden)<0.000000001 then
#        Zr=1e9 : Zi=0   'This can only happen if TanTheta=-R0/Zi and Zr=0
#    else
#        call cxInvert Rden,Iden, Rinv, Iinv     'Invert denominator into Rinv+j*Iinv
#        Zr=R0*(Rnum*Rinv-Inum*Iinv)  'Multiply R0 * numerator * inverted denominator
#        Zi=R0*(Rnum*Iinv+Inum*Rinv)
#    end if

        if abs(Zden.real) < 1e-9 and abs(Zden) < 1e-9:
            Z = complex(1e9, 0)
        else:
            Z = R0 * Znum / Zden
        return Z

#
#end sub

class Coax:
    def __init__(self):
        self.coaxData = []
        pass

# '=============Start Coax Analysis Module===================================
# function CoaxOpenDataFile$(isInput) 'open file for input or output
#     'Open coax data file; return its handle
#     'If file does not exist, return "".
#     fName$=DefaultDir$;"\MSA_Info\CoaxData.txt"
#     On Error goto [noFile]
#     if isInput then open fName$ for input as #coaxFile else open fName$ for output as #coaxFile
#     CoaxOpenDataFile$="#coaxFile"
#     exit function
# [noFile]
#     CoaxOpenDataFile$=""
# end function
#

    def CreateFile(self, fileName):
        # Each line contains coax name, Z0, VF, K1, K2, comma-separated VF is
        # velocity of propagation as fraction of speed of light, typically
        # 0.5-0.7 for coax cable K1 and K2 are in db/hundred ft per the equation
        #   Total db loss=(Len(in feet)/100) * ((K1)*Sqrt(freq) +(K2)*freq)  freq is in MHz
        # These are derived from http://www.vk1od.net/calc/tl/tllc.php and the
        # program TLDetails.exe
        fil = open(fileName,"w")
        fil.write("!Transmission line data file")
        fil.write("!Type, Z0, VF, K1, K2; K factors based on 100 ft and MHz.")
        fil.write("Lossless 50 ohms,50,0.66,0,0")
        fil.write("Lossless 75 ohms,75,0.66,0,0")
        fil.write("FR4 50-ohm microstrip,50,0.55,0.30,0.076")
        fil.write("RG6A,75,0.66,0.263,0.00159")
        fil.write("RG8,52,0.66,0.182,0.00309")
        fil.write("RG11,75,0.66,0.186,0.0023")
        fil.write("RG58,51.5,0.66,0.342,0.00901")
        fil.write("RG58C,50,0.66,0.394,0.00901")
        fil.write("RG59,73,0.66,0.321,0.00184")
        fil.write("RG59B,75,0.66,0.318,0.00192")
        fil.write("RG141A,50,0.695,0.26,0.00473")
        fil.write("RG174,50,0.66,0.792,0.00484")
        fil.write("RG188A,50,0.695,0.953,0.000192")
        fil.write("RG213,50,0.66,0.182,0.00309")
        fil.write("RG402,50,0.705,0.401,0.00074")
        fil.write("RG405,50,0.705,0.67,0.00093")
        fil.write("Andrew Heliax LDF4-50A,50,0.891,0.0643,0.000187")
        fil.write("Andrew Heliax LDF5-50A,50,0.891,0.0349,0.000153")
        fil.write("Andrew Heliax LDF6-50,50,0.891,0.0239,0.00014")
        fil.write("ARRL Generic 300,300,0.801,0.102,0.000682")
        fil.write("ARRL Generic 450,450,0.911,0.0271,0.000242")
        fil.write("Wireman 551,400,0.903,0.0496,0.0012")
        fil.write("Wireman 552,370,0.918,0.051,0.001")
        fil.write("Wireman 553,390,0.899,0.0621,0.0009")
        fil.write("Wireman 554,360,0.929,0.0414,0.0017")
        fil.close()

# function CoaxCreateFile() 'Create coax data file with default entries; return 1 if successful
#     fName$=DefaultDir$;"\MSA_Info\CoaxData.txt"
#     On Error goto [noFile]
#     open fName$ for output as #coaxFile
#         'Each line contains coax name, Z0, VF, K1, K2, comma-separated
#         'VF is velocity of propagation as fraction of speed of light, typically 0.5-0.7 for coax cable
#         'K1 and K2 are in db/hundred ft per the equation
#         '  Total db loss=(Len(in feet)/100) * ((K1)*Sqrt(freq) +(K2)*freq)  freq is in MHz
#         'These are derived from http://www.vk1od.net/calc/tl/tllc.php
#         'and the program TLDetails.exe
#     print #coaxFile, "!Transmission line data file"
#     print #coaxFile, "!Type, Z0, VF, K1, K2; K factors based on 100 ft and MHz."
#     print #coaxFile, "Lossless 50 ohms,50,0.66,0,0"
#     print #coaxFile, "Lossless 75 ohms,75,0.66,0,0"
#     print #coaxFile, "FR4 50-ohm microstrip,50,0.55,0.30,0.076"
#     print #coaxFile, "RG6A,75,0.66,0.263,0.00159"
#     print #coaxFile, "RG8,52,0.66,0.182,0.00309"
#     print #coaxFile, "RG11,75,0.66,0.186,0.0023"
#     print #coaxFile, "RG58,51.5,0.66,0.342,0.00901"
#     print #coaxFile, "RG58C,50,0.66,0.394,0.00901"
#     print #coaxFile, "RG59,73,0.66,0.321,0.00184"
#     print #coaxFile, "RG59B,75,0.66,0.318,0.00192"
#     print #coaxFile, "RG141A,50,0.695,0.26,0.00473"
#     print #coaxFile, "RG174,50,0.66,0.792,0.00484"
#     print #coaxFile, "RG188A,50,0.695,0.953,0.000192"
#     print #coaxFile, "RG213,50,0.66,0.182,0.00309"
#     print #coaxFile, "RG402,50,0.705,0.401,0.00074"
#     print #coaxFile, "RG405,50,0.705,0.67,0.00093"
#     print #coaxFile, "Andrew Heliax LDF4-50A,50,0.891,0.0643,0.000187"
#     print #coaxFile, "Andrew Heliax LDF5-50A,50,0.891,0.0349,0.000153"
#     print #coaxFile, "Andrew Heliax LDF6-50,50,0.891,0.0239,0.00014"
#     print #coaxFile, "ARRL Generic 300,300,0.801,0.102,0.000682"
#     print #coaxFile, "ARRL Generic 450,450,0.911,0.0271,0.000242"
#     print #coaxFile, "Wireman 551,400,0.903,0.0496,0.0012"
#     print #coaxFile, "Wireman 552,370,0.918,0.051,0.001"
#     print #coaxFile, "Wireman 553,390,0.899,0.0621,0.0009"
#     print #coaxFile, "Wireman 554,360,0.929,0.0414,0.0017"
#
#     close #coaxFile
#     CoaxCreateFile=1
#     exit function
# [noFile]
#     CoaxCreateFile=0    'error
# end function
#
    def LoadData(self):
        fileName = "MSA_Info\CoaxData.txt"
        if not os.path.isfile(fileName):
            self.CreateFile(fileName)

        try:
            fil = open(fileName,"r")
        except IOError:
            message("Unable to open file %s." % fileName) # EON Jan 29, 2014
            return

        for line in fil:
            (name, Z0, VF, K1, K2) = re.split(" *, *", line)
            self.coaxData.append((name, float(Z0), float(VF), float(K1), float(K2)))
        fil.close()

# sub CoaxLoadDataFile
#     'Load coax data file into coaxData$. If error, clear coaxData$
#     for i=1 to maxCoaxEntries : coaxNames$(i)="" : next i     'Blank all coax names
#     fHndl$=CoaxOpenDataFile$(1) 'open for input
#     if fHndl$="" then
#         'Error-assume file doesn't exist, and create it
#         isFile=CoaxCreateFile() 'Create file with default entries
#         if isFile=0 then notice "Unable to open/create coax data file." : exit sub
#         fHndl$=CoaxOpenDataFile$(1)  'Open the file we just created for input
#         if fHndl$="" then notice "Unable to open/create coax data file." : exit sub 'hopeless, so leave
#     end if
#     numCoaxEntries=0
#     while EOF(#fHndl$)=0
#         Line Input #fHndl$, tLine$  'get one line
#         if Left$(tLine$,1)<>"!" then    'skip comment lines, which start with !  ver115-4b
#             'Line contains name, Z0, VF, K1, K2, comma-separated
#             fullLine$=tLine$
#             aName$=uExtractTextItem$(tLine$, ",")    'get coax name
#             if aName$<>"" then
#                 isErr=uExtractNumericItems(3,tLine$,",",R0, VF, K1)
#                 if isErr=0 then isErr=uExtractNumericItems(1,tLine$,",",K2, dum1, dum2)
#                 if isErr then notice "Error reading coax data file: ";fullLine$
#             end if
#             numCoaxEntries=numCoaxEntries+1
#             coaxNames$(numCoaxEntries)=aName$ : coaxData(numCoaxEntries, 1)=R0 : coaxData(numCoaxEntries, 2)=VF
#             coaxData(numCoaxEntries, 3)=K1 : coaxData(numCoaxEntries, 4)=K2
#         end if
#     wend
#     close #fHndl$
# end sub
#

    def SaveData(self, fileName):
        fil = open(fileName,"w")
        fil.write("!Transmission line data file")
        fil.write("!Type, Z0, VF, K1, K2; K factors based on 100 ft and MHz.")
        for (name, R0, VF, K1, K2) in self.coaxData:
            fil.write("%s,%f,%f,%f,%f\n" % (name, R0, VF, K1, K2))
        fil.close()

# sub CoaxSaveDataFile
#     'Save coax data file.
#     fHndl$=CoaxOpenDataFile$(0) 'open for output
#     if fHndl$="" then notice "Unable to save coax data file." : exit sub
#     print #fHndl$, "!Transmission line data file"
#     print #fHndl$, "!Type, Z0, VF, K1, K2; K factors based on 100 ft and MHz."
#     for i=1 to numCoaxEntries
#             'Print comma-separated items
#         cName$=coaxNames$(i)
#         if cName$<>" " then print #fHndl$, cName$;",";coaxData(i,1);",";coaxData(i,2);",";coaxData(i,3);",";coaxData(i,4)
#     next i
#     close #fHndl$
# end sub
#

    def GetData(self, coaxName):
        pass
        for (name, R0, VF, K1, K2) in self.coaxData:
            if coaxName == name:
                return R0, VF, K1, K2
        return None

# sub CoaxGetData coaxName$, byref R0, byref VF, byref K1, byref K2       'Return data for named coax, or VF=0 if doesn't exist
#         'VF is velocity of propagation as fraction of speed of light
#         'K1 and K2 are in db/hundred ft per the equation
#         '  Total db loss=(Len(in feet)/100) * ((K1)*Sqrt(freq) +(K2)*freq)  freq is in MHz
#     found=0
#     for i=1 to numCoaxEntries
#         if coaxName$=coaxNames$(i) then found=i : exit for
#     next i
#     if found=0 then R0=50 : VF=1 : K1=0 : K2=0 : exit sub   'Name not found. Use ideal values.
#     R0=coaxData(found,1) : VF=coaxData(found,2)
#     K1=coaxData(found,3) : K2=coaxData(found,4)
# end sub
#

    def CoaxDelayNS(self, VF, lenFeet):
        if VF == 0:
            return constMaxValue
        else:
            # Speed of light is 983.6 million feet per second
            return (1000 * lenFeet) / (VF * 983.6)

# function CoaxDelayNS(VF,lenFeet)    'Return ns of one-way delay for velocity factor and length
#     'Speed of light is 983.6 million feet per second
#     if VF=0 then CoaxDelayNS=constMaxValue else CoaxDelayNS=1000*lenFeet/(VF*983.6) 'ver116-4i
# end function
#
    def CoaxWavelengthFt(self, fMHz, VF):
        if fMHz <= 0:
            fMHz = 0.000001
        if fMHz == 0:
            return constMaxValue
        else:
            # Speed of light is 983.6 million feet per second
            return (983.6 * VF) / fMHz

# function CoaxWavelengthFt(fMHz,VF)    'Return wavelength for f in MHz and specified veloc. factor
#     'Speed of light is 983.6 million feet per second
#     if fMHz<=0 then fMHz=0.000001   'To avoid numerical problems
#     if fMHz=0 then CoaxWavelength=constMaxValue else CoaxWavelength=(983.6*VF)/fMHz
# end function

    def CoaxLossDB(self, fMHz, K1, K2, lenFeet):
        return (lenFeet / 100) * (K1 * sqrt(fMHz) + K2 * fMHz)

#
# function CoaxLossDB(fMHz, K1, K2, lenFeet)    'Return loss in DB for specified coax
#     CoaxLossDB=(lenFeet/100) * (K1*Sqr(fMHz)+K2*fMHz)
# end function
#

    def CoaxLossA0(self, fMHz, K1, K2):
        return K1 * sqrt(fMHz) + K2 * fMHz

# function CoaxLossA0(fMHz, K1, K2)    'Return loss factor in dB per hundred feet
#     CoaxLossA0=K1*Sqr(fMHz)+K2*fMHz
# end function
#

    def CoaxLossAlpha(self, fMHz, K1, K2):
        return 0.001151 * (K1 * sqrt(fMHz) + K2 * fMHz)

# function CoaxLossAlpha(fMHz, K1, K2)    'Return loss factor in nepers/ft
#     CoaxLossAlpha=0.001151 *(K1*Sqr(fMHz)+K2*fMHz)
# end function
#
    def CoaxBeta(self, fMHz, VF):
        if VF <= 0:
            return constMaxValue
        return 2 * pi * fMHz / (VF * 983.6)

# function CoaxBeta(fMHz, VF)    'Return beta, which is the number of radians/ft
#     if VF<=0 then CoaxBeta=constMaxValue : exit function 'ver115-4b
#     CoaxBeta=2*uPi()*fMHz/(VF*983.6)
# end function
#

    def CoaxPropagationGamma(self, fMHz, VF, K1, K2):
        if fMHz <= 0:
            fMHz = 0.000001
        Greal = 0.001151 *(K1 * sqrt(fMHz) + K2 * fMHz)
        if VF <= 0:
            Gimag = constMaxValue
        else:
            Gimag = (2 * pi * fMHz) / (VF * 983.6)
        return complex(Greal, Gimag)

# sub CoaxGetPropagationGamma fMHz, VF, K1, K2, byref Greal, byref Gimag  'Return gamma=alpha +j*beta
#     if fMHz<=0 then fMHz=0.000001   'To avoid numerical problems
#     Greal=0.001151 *(K1*Sqr(fMHz)+K2*fMHz)
#     if VF<=0 then Gimag=constMaxValue : exit sub 'ver115-4b
#     Gimag=2*uPi()*fMHz/(VF*983.6)
# end sub
#

    def CoaxDelayDegrees(self, fMHz, VF, lenFeet):
        if fMHz <= 0:
            fMHz = 0.000001
        if VF <= 0:
            return constMaxValue
        delayMicroSec = lenFeet / (VF * 983.6)
        return delayMicroSec * fMHz * 360

# function CoaxDelayDegrees(fMHz,VF, lenFeet)    'Return delay in degrees
#     'Speed of light is 983.6 million feet per second
#     if fMHz<=0 then fMHz=0.000001   'To avoid numerical problems
#     if VF<=0 then CoaxDelayDegrees=constMaxValue : exit function
#     delayMicroSec=lenFeet/(VF*983.6)
#     CoaxDelayDegrees=delayMicroSec*fMHz*360
# end function
#

    def CoaxComplexZ0(self, fMHz, R, G, L, C):
        if fMHz <= 0:
            fMHz = 0.000001
        if C < 0.001:
            C = 0.001
        twoPiF = 2 * pi * fMHz
        Z = complex(R, twoPiF * L) / complex(G, twoPiF * C * 1e-6)
        return sqrt(Z)

# sub CoaxComplexZ0   fMHz, R, G, L, C, byref Z0Real, byref Z0Imag    'Calculate coax impedance from basic parameters
#     'R=resistance in ohms/ft  G=conductance in ohms/ft
#     'L=inductance in uH per foot
#     'C=capacitance in pf per foot
#     'Normally, we don't know these parameters directly, and this routine is used in iteration
#     'by CoaxComplexZ0Iterate
#     if fMHz<=0 then fMHz=0.000001   'To avoid numerical problems
#     if C<0.001 then C=0.001  'ver115-4b
#     twoPiF=2*uPi()*fMHz
#     call cxDivide R, twoPiF*L, G, twoPiF*C*1e-6, ZReal, ZImag    '(R+j*2*pi*F*L) / (G+j*2*pi*F*C*1e-6)
#     call cxSqrt ZReal, ZImag, Z0Real, Z0Imag     'Take square root for final result
# end sub
#

    def CoaxPropagationParams(self, Z0, fMHz, ac, ad, beta):
        if fMHz <= 0:
            fMHz = 0.000001
        twoPiF = 2 * pi * fMHz
        gamma = complex(ac + ad, beta)
        R = 2 * ac * Z0.real
        G = (2 * ad * Z0.real) /(Z0.real * Z0.real + Z0.imag * Z0.imag)
        L = (gamma.real * Z0.imag + gamma.imag * Z0.real) / twoPiF    #L=Im(gamma*Z0)/twoPiF
        num = G / Z0
        C = 1e6 * num.imag / twoPiF   #C=1e6*Im(gamma/Z0)/twoPiF
        return R, G, L, C

# sub CoaxPropagationParams Z0Real, Z0Imag, fMHz, ac, ad, beta, byref R, byref G, byref L, byref C    'Calc R,G,L,C
#     'Z0=complex characteristic impedance
#     'ac=conductor loss coefficient=0.001151*A0c.  A0c=K1*sqr(fMHz)--see CoaxGetData
#     'ad=dielectric loss coefficient=0.001151*A0c.  A0d=K1*fMHz--see CoaxGetData
#     'beta=phase coefficient, radians/ft
#     'R=resistance in ohms/ft  G=conductance in ohms/ft
#     'L=inductance in uH per foot
#     'C=capacitance in pf per foot
#     'Normally, we don't know these parameters directly, and this routine is used in iteration
#     'by CoaxComplexZ0Iterate
#     if fMHz<=0 then fMHz=0.000001   'To avoid numerical problems
#     twoPiF=2*uPi()*fMHz
#     gammaReal=ac+ad 'total loss coefficient
#     gammaImag=beta
#     R=2*ac*Z0Real
#     G=2*ad*Z0Real/(Z0Real^2+Z0Imag^2)
#     L=(gammaReal*Z0Imag+gammaImag*Z0Real)/twoPiF    'L=Im(gamma*Z0)/twoPiF
#     call cxDivide gammaReal, gammaImag,Z0Real, Z0Imag, numR, numI    'gamma/Z0
#     C=1e6*numI/twoPiF   'C=1e6*Im(gamma/Z0)/twoPiF
# end sub
#

    def CoaxComplexZ0Iterate(self, fMHz, VF, K1, K2, Z0):
        if fMHz <= 0:
            fMHz = 0.000001
        if K1 == 0 and K2 == 0:
            return Z0
        twoPiF= 2 * pi * fMHz
        ac = 0.0011513 * K1 * sqrt(fMHz)
        ad = 0.0011513 * K2 * fMHz
        beta = twoPiF / (VF * 983.6)  #speed of light is 983.6 million feet/sec
        Z0.imag = 0
        if Z0.real <= 0:
            Z0.real = 1
        # First iteration
        (R, G, L, C) = self.CoaxPropagationParams(Z0, fMHz, ac, ad, beta)
        Z0 = self.CoaxComplexZ0(fMHz, R, G, L, C, Z0)

        # Second iteration
        (R, G, L, C) = self.CoaxPropagationParams(Z0, fMHz, ac, ad, beta)
        Z0 = self.CoaxComplexZ0(fMHz, R, G, L, C, Z0)

        # Third iteration--needed only for low freq, or high loss at mid frequency
        # The loss thresholds below are just a bit under RG-174

        if (fMHz < 1) or (fMHz < 10 and (K1 > 0.6 or K2 > 0.03)):
            (R, G, L, C) = self.CoaxPropagationParams(Z0, fMHz, ac, ad, beta)
            Z0 = self.CoaxComplexZ0(fMHz, R, G, L, C, Z0)

        return Z0

# sub CoaxComplexZ0Iterate fMHz, VF, K1, K2, byref Z0Real, byref Z0Imag
#     'The complex Z0 is calculated by iteration, starting with Z0Real as the nominal
#     'impedance, which must be set on entry.
#     'The second iteration causes little change, and after that there is virtually none.
#     if fMHz<=0 then fMHz=0.000001   'To avoid numerical problems
#     if K1=0 and K2=0 then exit sub  'No loss, so no need to do fancy calculations
#     twoPiF=2*uPi()*fMHz
#     ac=0.0011513*K1*sqr(fMHz) : ad=0.0011513*K2*fMHz    'components of loss coefficients, nepers/ft
#     beta=twoPiF/(VF*983.6)  'speed of light is 983.6 million feet/sec
#     Z0Imag=0
#     if Z0Real<=0 then Z0Real=1  'To avoid divide by zero
#         'First iteration
#     call CoaxPropagationParams Z0Real, Z0Imag, fMHz, ac, ad, beta, R, G, L, C     'Calcs R,G,L,C
#     call CoaxComplexZ0 fMHz, R, G, L, C, Z0Real, Z0Imag     'calcs Z0
#
#         'Second iteration
#     call CoaxPropagationParams Z0Real, Z0Imag, fMHz, ac, ad, beta, R, G, L, C     'Calcs R,G,L,C
#     call CoaxComplexZ0 fMHz, R, G, L, C, Z0Real, Z0Imag     'calcs Z0
#
#         'Third iteration--needed only for low freq, or high loss at mid frequency
#         'The loss thresholds below are just a bit under RG-174
#     needThird=(fMHz<1) or ((K1>0.6 or K2>0.03) and fMHz<10) 'ver115-4b
#     if needThird then
#         call CoaxPropagationParams Z0Real, Z0Imag, fMHz, ac, ad, beta, R, G, L, C     'Calcs R,G,L,C
#         call CoaxComplexZ0 fMHz, R, G, L, C, Z0Real, Z0Imag     'calcs Z0
#     end if
# end sub
#

    def CoaxOpenZ(self, Z0, lenFeet, G):
        if lenFeet == 0:
            return complex(constMaxValue, constMaxValue)
        return Z0 / cmath.tanh(G * lenFeet)

# sub CoaxOpenZ Z0Real, Z0Imag, lenFeet, Greal,Gimag, byref ZReal, byref ZImag  'Calc Z of open coax stub
#     'We calculate ZReal+jZimag=Zopen=Z0/tanh(gamma*lenFeet)
#     'Z0Real+jZ0Imag is the coax characteristic impedance
#     'Greal+jGimag is gamma, the propagation factor obtained from CoaxGetPropagationGamma
#     if lenFeet=0 then ZReal=constMaxValue : ZImag=constMaxValue : exit sub  'zero length open has inf imped
#     tR=Greal*lenFeet : tI=Gimag*lenFeet
#     call cxTanh tR, tI, tanhR, tanhI
#     call cxDivide Z0Real, Z0Imag, tanhR, tanhI, ZReal,ZImag  'Zopen=Z0/tanh(gamma*lenFeet)
# end sub
#

    def CoaxShortZ(self, Z0, lenFeet, G):
        if lenFeet == 0:
            return complex(0, 0)
        return Z0 * cmath.tanh(G * lenFeet)
        pass

# sub CoaxShortZ Z0Real, Z0Imag, lenFeet, Greal,Gimag, byref ZReal, byref ZImag  'Calc Z of short coax stub
#     'We calculate ZReal+jZimag=Zshort=Z0*tanh(gamma*lenFeet)
#     'Z0Real+jZ0Imag is the coax characteristic impedance
#     'Greal+jGimag is gamma, the propagation factor obtained from CoaxGetPropagationGamma
#     if lenFeet=0 then ZReal=0 : ZImag=0 : exit sub  'zero length short has 0 imped
#     tR=Greal*lenFeet : tI=Gimag*lenFeet
#     call cxTanh tR, tI, tanhR, tanhI
#     call cxMultiply Z0Real, Z0Imag, tanhR, tanhI, ZReal,ZImag  'Zshort=Z0*tanh(gamma*lenFeet)
# end sub
#

    def CoaxTerminatedZ(self, Z0, Zt, lenFeet, G):
        if lenFeet == 0:
            return Zt
        A = lenFeet * G
        return Z0 * ((Zt * cmath.cosh(A) + Z0 * cmath.sinh(A)) /
                     (Zt * cmath.sinh(A) + Z0 * cmath.cosh(A)))

# sub CoaxTerminatedZ Z0Real, Z0Imag, ZtReal, ZtImag, lenFeet, Greal,Gimag, byref ZReal, byref ZImag  'Calc Z of terminated coax
#     'Z0Real+jZ0Imag is the coax characteristic impedance
#     'ZtReal+jZtImag is the terminating impedance
#     'Greal+jGimag is gamma, the propagation factor obtained from CoaxGetPropagationGamma
#     'We calculate ZReal+jZImag as the input impedance resulting from terminating the coax with Zt
#     'lenFeet is the coax length. Note that if we use a negative length, we end up calculating Z as
#     'the terminating impedance required to produce an input impedance of Zt.
#     'Zin=Z0* [Zt*cosh(A)+Z0*sinh(A)] / [Zt*sinh(A)+Z0*cosh(A)]; A=lenFeet*gamma
#     if lenFeet=0 then ZReal=ZtReal : ZImag=ZtImag : exit sub  'zero length has imped of Zt
#     tR=Greal*lenFeet : tI=Gimag*lenFeet
#     call cxSinh tR, tI, sR, sI
#     call cxCosh tR, tI, cR, cI
#     call cxMultiply ZtReal, ZtImag, sR, sI, stR, stI  'sinh*Zt
#     call cxMultiply ZtReal, ZtImag, cR, cI, ctR, ctI  'cosh*Zt
#     call cxMultiply Z0Real, Z0Imag, sR, sI, s0R, s0I  'sinh*Z0
#     call cxMultiply Z0Real, Z0Imag, cR, cI, c0R, c0I  'cosh*Z0
#     call cxDivide ctR+s0R, ctI+s0I, stR+c0R, stI+c0I, divR, divI
#     call cxMultiply Z0Real, Z0Imag, divR, divI, ZReal, ZImag   'Z0 times the result of the divide
# end sub
#

    def CoaxTerminatedZFromName(self, coaxName, fMHz, Zt, lenFeet):
        (R0, VF, K1, K2) = self.GetData(coaxName)
        spec = self.CoaxSpec(R0, VF, K1, K2, lenFeet)
        return Coax.CoaxTerminatedZFromSpecs(spec, fMHz, Zt) # EON Jan 29, 2014

# sub CoaxTerminatedZFromName coaxName$, fMHz, ZtReal, ZtImag, lenFeet, byref ZReal, byref ZImag 'Calculate Z0 and then terminated Z value
#     call CoaxGetData coaxName$, R0, VF, K1, K2
#     spec$=CoaxSpecs$(R0, VF, K1, K2,lenFeet)  'put data into a coax spec
#     call CoaxTerminatedZFromSpecs spec$, fMHz, ZtReal, ZtImag, ZReal, ZImag
# end sub
#

    @staticmethod # EON Jan 29, 2014
    def CoaxTerminatedZFromSpecs(coaxSpecs, fMHz, Zt): # JGH 1/31/14
        (isErr, R0, VF, K1, K2, lenFeet) = self.CoaxParseSpecs(coaxSpecs)
        if isErr:
            return complex(0, 0) # EON Jan 29, 2014
        Z0 = complex(R0, 0) # EON Jan 29, 2014
        if fMHz <= 0:
            fMHz = 0.000001
        Z0 = self.CoaxComplexZ0Iterate(fMHz, VF, K1, K2, Z0) # EON Jan 29, 2014
        G = self.CoaxGetPropagationGamma(fMHz, VF, K1, K2)
        Z0 = self.CoaxTerminatedZ(Z0, Zt, lenFeet, G)
        return Z0

# sub CoaxTerminatedZFromSpecs coaxSpecs$, fMHz, ZtReal, ZtImag, byref ZReal, byref ZImag  'Calculate Z0 and then terminated Z value
#     isErr=CoaxParseSpecs(coaxSpecs$, R0, VF, K1, K2, lenFeet)
#     if isErr then ZReal=0 : ZImag=0 : exit sub  'invalid spec
#     Z0Real=R0 : Z0Imag=0  'starting value
#     if fMHz<=0 then fMHz=0.000001   'To avoid numerical problems
#     call CoaxComplexZ0Iterate fMHz, VF, K1, K2, Z0Real, Z0Imag  'Calculate complex Z0
#     call CoaxGetPropagationGamma fMHz, VF, K1, K2, Greal, Gimag 'get propagation coefficient alpha +j*beta
#     call CoaxTerminatedZ Z0Real, Z0Imag, ZtReal, ZtImag, lenFeet, Greal,Gimag, ZReal, ZImag
# end sub
#

    @staticmethod # EON Jan 29, 2014
    def CoaxZ0FromTerminationImpedance(ZL, Z, GL): # EON Jan 29, 2014
        D = ( Z - ZL) * (cmath.cosh(GL) / cmath.sinh(GL))
        return (1 / 2) * (D + sqrt(D * D + 4 * Z * ZL))

# sub CoaxZ0FromTerminationImpedance ZLReal, ZLImag, ZReal, ZImag, GLreal, GLimag, byref Z0Real, byref Z0Imag    'Calc Z0 from Z and ZL
#     'ZL is the terminating impedance; Z is the measured input impedance of the line.
#     'GLreal and GLimage are the gamma*len components
#     'We calculate characteristic impedance Z0.
#     'There may be a second solution for very lossy lines if ZL is very small or very large,
#     'so it should be within a factor of 5 of the value of Z0, which the caller can check after getting
#     'the calculation results. In any case, all measurements will be most accurate if ZL is close to
#     'Z0, which will also make Z close to Z0.
#     'Z0=(1/2)*[D+sqrt(D^2+4*Z*ZL)], where D=(Z-ZL)coth(gamma*len)
#
#     call cxCosh GLreal, GLimag, cReal, cImag    'cosh of gamma*len
#     call cxSinh GLreal, GLimag, sReal, sImag    'sinh of gamma*len
#     call cxDivide cReal, cImag, sReal, sImag,cothR, cothI     'coth=cosh/sinh
#     difR=ZReal-ZLReal : difI=ZImag-ZLImag   'Z-ZL
#     call cxMultiply difR, difI, cothR, cothI, difCothR, difCothI '(Z-ZL)*coth
#     call cxMultiply difCothR, difCothI,difCothR, difCothI, difCothSqR, difCothSqI  '((Z-ZL)*coth)^2
#     call cxMultiply 4*ZReal, 4*ZImag, ZLReal, ZLImag, fourZZLreal,fourZZLimag    '4*Z*ZL
#     call cxSqrt difCothSqR+fourZZLreal,difCothSqI+fourZZLimag, sqrtR, sqrtI   'sqrt(((Z-ZL)*coth)^2-4*Z*ZL)
#     Z0Real=(difCothR+sqrtR)/2   'Add (Z-ZL)*coth and sqrt(((Z-ZL)*coth)^2-4*Z*ZL) and divide by 2.
#     Z0Imag=(difCothI+sqrtI)/2
# end sub
#

    def CoaxPhaseDelayAndLossFromSpecs(self, coaxSpecs, phase):
        pass

# function CoaxPhaseDelayAndLossFromSpecs(coaxSpecs$, phase, lossDB)    'Get delay in degrees and loss in dB for specified coax
#     'returns 1 if error in spec; otherwise 0
#     'Assumes proper termination for loss calculation
#     isErr=CoaxParseSpecs(coaxSpecs$, R0, VF, K1, K2, lenFeet)
#     if isErr then CoaxDelayAndLossFromSpecs=1 : exit function  'invalid spec
#     CoaxDelayAndLossFromSpecs=0
#     phase=CoaxDelayDegrees(fMHz,VF,lenFeet)
#     lossDB=CoaxLossA0*lenFeet/100  'loss per hundred feet times len in hundreds of feet
# end function
#

    def CoaxS21(self, sysZ0, coaxZ0, GL):
        a = cmath.exp(GL) + cmath.exp(-GL)
        b =cmath.exp(GL) - cmath.exp(-GL)
        return 2 / (a + (b / 2) * (sysZ0 / coaxZ0 + coaxZ0 / sysZ0))

# sub CoaxS21 sysZ0real, sysZ0imag, coaxZ0real, coaxZ0imag, GLreal, GLimag, byRef S21real, byRef S21imag
#     'sysZ0 (Z0) is system reference impedance
#     'coaxZ0 (ZC) is coax characteristic impedance
#     'GL is gamma times length (ft)
#     'Formula:
#     '   a=e^(gamma*Len) + e^(-gamma*Len)
#     '   b=e^(gamma*Len) - e^(-gamma*Len)
#     '   S21=2/{a + (b/2)*(Z0/ZC+ZC/Z0)}
#     call cxEPower GLreal, GLimag, ePlusR, ePlusI   'e^(gamma*Len)
#     call cxEPower 0-GLreal, 0-GLimag, eMinusR, eMinusI   'e^(-gamma*Len)
#     aR=ePlusR+eMinusR : aI=ePlusI+eMinusI           'a=e^(gamma*Len) + e^(-gamma*Len)
#     bR=(ePlusR-eMinusR)/2 : bI=(ePlusI-eMinusI)/2  'b=[e^(gamma*Len) - e^(-gamma*Len)]/2
#     call cxDivide, sysZ0real,sysZ0imag, coaxZ0real, coaxZ0imag, ratioR, ratioI 'ratio=Z0/ZC
#     call cxInvert ratioR, ratioI, invR, invI         'inv=ZC/Z0
#     cR=ratioR+invR : cI=ratioI+invI         'c=Z0/ZC+ZC/Z0
#     call cxMultiply cR, cI, bR, bI, dR, dI   'd=(1/2)[e^(gamma*Len) - e^(-gamma*Len)]*[Z0/ZC+ZC/Z0]
#     eR=aR+dR :eI=aI+dI          'e=e^(gamma*Len) + e^(-gamma*Len) + (1/2)[e^(gamma*Len) - e^(-gamma*Len)]*[Z0/ZC+ZC/Z0]
#     call cxInvert eR, eI, fR, fI     'f=1/e
#     S21real=2*fR : S21imag=2*fI     'S21=2/e, real, imag format
# end sub
#
    @staticmethod # EON Jan 29, 2014
    def CoaxS21FromSpecs(sysZ0, coaxSpecs, fMHz): # JGH 1/31/14
        if coaxSpecs == "":
            return 0, 0
        (isErr, R0, VF, K1, K2, lenFeet) = self.CoaxParseSpecs(coaxSpecs)
        if isErr:
            return 200, 0
        Z0 = complex(R0, 0)
        if fMHz <= 0:
            fMHz = 0.000001
        Z0 = self.CoaxComplexZ0Iterate(fMHz, VF, K1, K2, Z0)
        G = self.CoaxGetPropagationGamma(fMHz, VF, K1, K2)
        S21 = self.CoaxS21(sysZ0, Z0, G * lenFeet)
        return polarDbDeg(S21)

# sub CoaxS21FromSpecs sysZ0real, sysZ0imag, coaxSpecs$, fMHz, byref S21dB, byref S21ang  'Calc S21 of coax cable
#     'sysZ0 is the system reference impedance
#     'fMHz is frequency in MHz,
#     'coaxSpecs$ describes the coax
#     'We calculate S21 of the coax cable with source and load of sysZ0. Returned as db, angle (degrees)
#     if coaxSpecs$="" then S21dB=0 : S21ang=0 : exit sub 'No specs; treat as zero length coax
#     isErr=CoaxParseSpecs(coaxSpecs$, R0, VF, K1, K2, lenFeet)
#     if isErr then S21dB=-200 : S21ang=0 : exit sub  'invalid spec
#     Z0Real=R0 : Z0Imag=0  'starting value
#     if fMHz<=0 then fMHz=0.000001   'To avoid numerical problems
#     call CoaxComplexZ0Iterate fMHz, VF, K1, K2, Z0Real, Z0Imag  'Calculate complex Z0
#     call CoaxGetPropagationGamma fMHz, VF, K1, K2, Greal, Gimag 'get propagation coefficient alpha +j*beta
#     call CoaxS21 sysZ0real, sysZ0imag,Z0Real, Z0Imag, Greal*lenFeet,Gimag*lenFeet, S21real, S21imag
#         'Convert real, imag to db, angle
#     magSquared=S21real*S21real + S21imag*S21imag
#     S21dB=10*uSafeLog10(magSquared)   'use 10 instead of 20 because mag is already squared
#     S21ang=uATan2(S21real, S21imag) 'Angle, degrees
# end sub
#

    def CoaxSpec(self, R0, VF, K1, K2, lenFeet):
        return "Z%f,V%f,K%f,k%f,L%f" % (R0, VF, K1, K2, lenFeet)

# function CoaxSpecs$(R0, VF, K1, K2,lenFeet) 'Assemble coax parameters into a spec string
#     CoaxSpecs$="Z";R0;",V";VF;",K";K1;",K";K2;",L";lenFeet
# end function
#

    @staticmethod
    def CoaxParseSpecs(coaxSpecs):
        # default is lossless coax of zero len
        R0 = 50
        VF = 1
        K1 = 0
        K2 = 0
        lenFeet = 0
        isErr = False
        if coaxSpecs != "":
            args = re.split(" *, *", coaxSpecs)
            knum = 0
            for val in args:
                m = re.match("([A-Z]+)(.*)",val)
                if m.groups == 2:
                    tag = m.group(1)
                    v = floatSI(m.group(2))
                    if tag == "Z":
                        R0 = v
                    elif tag == "V":
                        VF = v
                    elif tag == "K":
                        if knum == 0:
                            K1 = v
                            knum = 1
                        else:
                            K2 = v
                    elif tag == "L":
                            lenFeet = v
                    else:
                        isErr = 1
                        break
                else:
                    isErr = 1
                    break
        return isErr, R0, VF, K1, K2, lenFeet

# function CoaxParseSpecs(coaxSpecs$, byref R0, byref VF, byref K1, byref K2, byref lenFeet)   'Get coax characteristics from specs
#     'Returns 0 if no error; 1 if error.
#     'coaxSpecs$ is in the form Z50, V0.5, K0.05, K0.05, L3
#     'Z is R0, V is velocity factor, first K is conductor loss factor (K1),
#     '   second K is dielectric loss factor (K2), L is length in feet.
#     CoaxParseSpecs=0    'Assume no error
#     R0=50 : VF=1 : K1=0 : K2=0 : lenFeet=0  'default is lossless coax of zero len
#     if coaxSpecs$="" then exit function
#     specLen=len(coaxSpecs$)
#     isErr=0 : commaPos=0
#     kNum=1
#     while commaPos<specLen
#         oldCommaPos=commaPos
#         commaPos=instr(coaxSpecs$,",", commaPos+1)
#         if commaPos=0 then commaPos=specLen+1     'Pretend comma follows the string
#         compon$=Trim$(Mid$(coaxSpecs$,oldCommaPos+1, commaPos-oldCommaPos-1))   'get this component spec
#         if compon$="" then exit while  'get next word; done if there is none
#         firstChar$=Left$(compon$,1)   'data tag, single character
#         data$=Mid$(compon$,2)   'From second character to end
#         if data$<>"" then v=uValWithMult(data$)   'Value of everything after first char
#         select firstChar$   'Assign value to proper variable
#             case "Z"    'Z0
#                 R0=v : if R0<=0 then isErr=1
#             case "V"    'velocity factor
#                 VF=v : if VF<=0 or VF>1 then isErr=1
#             case "K"    'K1 or K2
#                 if v<0 or v>1 then isErr=1
#                 if kNum=1 then
#                     K1=v : kNum=2
#                 else
#                     K2=v
#                 end if
#             case "L"    'coax len
#                 lenFeet=v
#             case else   'Invalid component spec
#                 isErr=1
#         end select
#         if isErr then CoaxParseSpecs=1 : exit function
#     wend
# end function
#
# '=============End Coax Analysis Module====================================
# End EON Jan 10 2014

#==============================================================================
# A Help dialog for a Function menu dialog.

class FunctionHelpDialog(wx.Dialog):
    def __init__(self, funcDlg):
        frame = funcDlg.frame
        p = frame.prefs
        pos = p.get(funcDlg.shortName+"HelpWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, funcDlg.title+" Help", pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        sizerV = wx.BoxSizer(wx.VERTICAL)
        self.SetBackgroundColour("WHITE")
        st = wx.StaticText(self, -1, funcDlg.helpText, pos=(10, 10))
        st.Wrap(600)
        sizerV.Add(st, 0, wx.ALL, 5)

        # OK button
        butSizer = wx.BoxSizer(wx.HORIZONTAL)
        butSizer.Add((0, 0), 0, wx.EXPAND)
        btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        butSizer.Add(btn, 0, wx.ALL, 5)
        sizerV.Add(butSizer, 0, wx.ALIGN_RIGHT)

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if pos == wx.DefaultPosition:
            self.Center()

#==============================================================================
# Base class for Functions menu function dialog boxes.

class FunctionDialog(MainDialog):
    def __init__(self, frame, title, shortName):
        self.frame = frame
        self.title = title
        self.shortName = shortName
        p = frame.prefs
        self.pos = p.get(shortName+"WinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, title, self.pos,
                            wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        frame.StopScanAndWait()
        self.helpDlg = None
        self.R0 = p.get("R0", 50.)

    #--------------------------------------------------------------------------
    # Common button events.

    def OnHelpBtn(self, event):
        self.helpDlg = dlg = FunctionHelpDialog(self)
        dlg.Show()

    def OnClose(self, event):
        p = self.frame.prefs
        self.frame.task = None
        if msa.IsScanning():
            msa.StopScan()
            event.Skip()
        setattr(p, self.shortName+"WinPos", self.GetPosition().Get())
        p.R0 = self.R0
        helpDlg = self.helpDlg
        if helpDlg:
            setattr(p, self.shortName+"HelpWinPos", \
                                        helpDlg.GetPosition().Get())
            helpDlg.Close()
        self.Destroy()

    #--------------------------------------------------------------------------
    # Return the name of the primary "Mag" or "dB" trace.

    def MagTraceName(self):
        specP = self.frame.specP
        magNames = [x for x in specP.traces.keys() \
                if ("dB" in x) or ("Mag" in x)]
        if len(magNames) != 1:
            raise RuntimeError("No Magnitude trace found (or multiple)")
        return magNames[0]

    #--------------------------------------------------------------------------
    # Find peak frequency Fs, -3 dB (or dbDownBy) points, and Fp if fullSweep.
    # Sets self.Fs and self.Fp, and returns PeakS21DB, Fdb3A, Fdb3B.
    # If isPos is False, it finds only the notch Fp, which may be dbDownBy
    # dB up from the notch or taken as an absolute level if isAbs is True.

    def FindPoints(self, fullSweep=False, dbDownBy=3, isPos=True, isAbs=False):
        frame = self.frame
        p = frame.prefs
        specP = frame.specP
        markers = specP.markers
        specP.markersActive = True
        specP.dbDownBy = dbDownBy
        specP.isAbs = isAbs

        # place L, R, P+, P- markers on Mag trace and find peaks
        magName = self.MagTraceName()
        markers["L"]  = L =  Marker("L",  magName, p.fStart)
        markers["R"]  = R =  Marker("R",  magName, p.fStop)
        if isPos:
            markers["P+"] = Pres = Pp = Marker("P+", magName, p.fStart)
        if fullSweep or not isPos:
            markers["P-"] = Pres = Pm = Marker("P-", magName, p.fStart)
        frame.SetMarkers_PbyLR()
        wx.Yield()

        # place L and R at -3db points around P+ or P-
        (frame.SetMarkers_LRbyPm, frame.SetMarkers_LRbyPp)[isPos]()
        wx.Yield()

        # The main resonance is a peak if we have a crystal or a series RLC
        # in a series fixture, or parallel RLC in parallel fixture.
        Fres = Pres.mhz
        # For crystal we may also need to zoom in more closely around the
        # series peak to get a good read on Fs.

        if fullSweep:
            # we need to find Fp ourselves
            PeakS21DB = Pp.dbm
            self.Fs = Fs = Pp.mhz
            self.Fp = Fp = Pm.mhz
            if Fp > p.fStop - 0.00005:
                msg = "Sweep does not include enough of parallel resonance."
                raise RuntimeError(msg)
            if Fs >= Fp:
                msg = "Sweep does not show proper series resonance followed " \
                        "by parallel resonance."
                raise RuntimeError(msg)
        else:
            PeakS21DB = Pres.dbm
            self.Fres = Fres
            if isPos:
                self.Fs = Fres
            else:
                self.Fp = Fres

        if L.mhz < p.fStart or R.mhz > p.fStop:
            msg = "Sweep does not contain necessary -3 dB points."
            raise RuntimeError(msg)

        return PeakS21DB, L.mhz, R.mhz

    #--------------------------------------------------------------------------
    # Read R0 from text box.

    def GetR0FromBox(self):
        self.R0 = floatOrEmpty(self.R0Box.GetValue())
        if self.R0 < 0:
            self.R0 = 50
            alertDialog(self, "Invalid R0. 50 ohms used.", "Note")


#==============================================================================
# The Analyze Filter dialog box.

class FilterAnalDialog(FunctionDialog):
    def __init__(self, frame):
        FunctionDialog.__init__(self, frame, "Analyze Filter", "filtAn")
        # JGH 2/10/14 Next 3 lines: vars not used
#        p = frame.prefs
#        markers = frame.specP.markers
#        self.sizerV = sizerV = wx.BoxSizer(wx.VERTICAL)
        c = wx.ALIGN_CENTER
        chb = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM

        # enabler and instructions
        sizerV = wx.BoxSizer(wx.VERTICAL)
        label = "Analyze filter spectrum for bandwidth, Q and shape factor."
        self.enableCB = chk = wx.CheckBox(self, -1, label)
        chk.SetValue(True)
        sizerV.Add(chk, 0, wx.ALL, 10)
        sizerV.Add(wx.StaticText(self, -1, \
            "Ref Marker is considered the peak. X1DB (typically 3 dB)"\
            "and X2DB (perhaps 30 dB,\nor 0 dB to ignore) are the dB"\
            "levels to evaluate."), 0, c|wx.ALL, 10)

        # ref marker and DB Down selection
        sizerG = wx.GridBagSizer(hgap=20, vgap=0)
        self.mNames = mNames = ("P+", "P-")
        sizerG.Add(wx.StaticText(self, -1, "Ref Marker"), (0, 0), flag=chb)
        self.peakMarkCB = cbox = wx.ComboBox(self, -1, "P+", \
                    (0, 0), (80, -1), mNames)
        sizerG.Add(cbox, (1, 0), flag=c)
        sizerG.Add(wx.StaticText(self, -1, "X1DB Down"), (0, 1), flag=chb)
        self.x1dbBox = tc = wx.TextCtrl(self, -1, "3", size=(60, -1))
        sizerG.Add(tc, (1, 1), flag=c)
        sizerG.Add(wx.StaticText(self, -1, "X2DB Down"), (0, 2), flag=chb)
        self.x2dbBox = tc = wx.TextCtrl(self, -1, "0", size=(60, -1))
        sizerG.Add(tc, (1, 2), flag=c)
        sizerV.Add(sizerG, 0, c|wx.ALL, 10)

        # Cancel and OK buttons
        butSizer = wx.BoxSizer(wx.HORIZONTAL)
        butSizer.Add((0, 0), 0, wx.EXPAND)
        btn = wx.Button(self, wx.ID_CANCEL)
        btn.Bind(wx.EVT_BUTTON, self.OnClose)
        butSizer.Add(btn, 0, wx.ALL, 5)
        btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        btn.Bind(wx.EVT_BUTTON, self.OnOK)
        butSizer.Add(btn, 0, wx.ALL, 5)
        sizerV.Add(butSizer, 0, wx.ALIGN_RIGHT|wx.ALIGN_BOTTOM|wx.ALL, 10)

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if self.pos == wx.DefaultPosition:
            self.Center()
        self.Show()

    #--------------------------------------------------------------------------
    # OK pressed- if enabled, analyze peak data and show in results box.

    def OnOK(self, event):
        frame = self.frame
        specP = frame.specP
        markers = specP.markers
        p = frame.prefs
        isLogF = p.isLogF

        if self.enableCB.IsChecked():
            # enabled: set up markers for analysis
            peakName = self.peakMarkCB.GetValue()
            print ("Analyzing filter -- peak is", peakName)
            # get the db values for the x1 and x2 analysis points and
            # force them positive
            x1db = abs(floatOrEmpty(self.x1dbBox.GetValue()))
            x2db = abs(floatOrEmpty(self.x2dbBox.GetValue()))

            # add P+/P- reference marker if necessary
            magName = self.MagTraceName()
            mPeak =  markers.get(peakName)
            if not mPeak:
                mPeak = markers[peakName] = Marker(peakName, magName, p.fStart)

            # find N-db-down points and set markers
            isPos = peakName == "P+"
            show = 1
            if x2db and x2db != 3:
                PeakS21DB, Fx2dbA, Fx2dbB = self.FindPoints(False, x2db, isPos)
                if show:
                    print ("X2: PeakS21DB=", PeakS21DB, "Fx2dbA=", Fx2dbA, \
                        "Fx2dbB=", Fx2dbB)
                if x1db:
                    if x1db != 3:
                        markers["3"] = Marker("3", magName, Fx2dbA)
                        markers["4"] = Marker("4", magName, Fx2dbB)
                    else:
                        markers["1"] = Marker("1", magName, Fx2dbA)
                        markers["2"] = Marker("2", magName, Fx2dbB)
            if x1db and x1db != 3:
                PeakS21DB, Fx1dbA, Fx1dbB = self.FindPoints(False, x1db, isPos)
                markers["1"] = Marker("1", magName, Fx1dbA)
                markers["2"] = Marker("2", magName, Fx1dbB)
                if show:
                    print ("X1: PeakS21DB=", PeakS21DB, "Fx1dbA=", Fx1dbA, \
                        "Fx1dbB=", Fx1dbB)
            PeakS21DB, Fdb3A, Fdb3B = self.FindPoints(False, 3, isPos)
            if show:
                print ("3dB: PeakS21DB=", PeakS21DB, "Fdb3A=", Fdb3A, \
                    "Fdb3B=", Fdb3B)
            if x1db == 3:
                Fx1dbA, Fx1dbB = Fdb3A, Fdb3B
            if x2db == 3:
                Fx2dbA, Fx2dbB = Fdb3A, Fdb3B

            # find amount of ripple
            # This is the max extent of the data values between the peak and
            # the last minor peak before reaching the target level.
            # To find that last peak, we take the derivative of the span
            # and find the last zero crossing. Then we can use argmin, argmax
            # on the remainder of the span.
            mPeak = markers[peakName]
            trM = specP.traces[magName]
            v = trM.v
            jP = trM.Index(mPeak.mhz, isLogF)
            jEnds = []
            for i in range(2):
                mE = markers["LR"[i]]
                dirE = 2*i - 1
                jE = trM.Index(mE.mhz, isLogF)
                de = diff(v[jE:jP:-dirE])
                jEnds.append(jE - dirE*interp(0, -de, arange(len(de))))
            span = v[jEnds[0]:jEnds[1]]
            ripple = span[span.argmax()] - span[span.argmin()]

            # compute and display filter info
            BWdb3 = Fdb3B - Fdb3A
            info = "BW(3dB)=%sHz\n" % si(BWdb3*MHz, 3)
            if x1db and x1db != 3:
                info += "BW(%gdB)=%sHz\n" % (x1db, si((Fx1dbB - Fx1dbA)*MHz,3))
            if x2db and x2db != 3:
                info += "BW(%gdB)=%sHz\n" % (x2db, si((Fx2dbB - Fx2dbA)*MHz,3))
            Q = mPeak.mhz / BWdb3
            info += "Q=%4g\n" % Q
            if x1db and x2db:
                shape = (Fx2dbB - Fx2dbA) / (Fx1dbB - Fx1dbA)
                info += "SF(%gdB)/%gdB)=%4g\n" % (x1db, x2db, shape)
            info += "IL=%4g\nRipple=%4g" % (-PeakS21DB, ripple)
            specP.results = info

        else:
            # analysis disabled: remove results box
            specP.results = None

        specP.FullRefresh()
        self.OnClose(event)


#==============================================================================
# The Component Meter dialog box.

# pointNum values: index to frequency that component is being tested at
_100kHz, _210kHz, _450kHz, _950kHz, _2MHz, _4p2MHz, _8p9MHz, _18p9MHz, \
    _40MHz = range(9)

class ComponentDialog(FunctionDialog):
    def __init__(self, frame):
        FunctionDialog.__init__(self, frame, "Component Meter", "comp")
        #p = frame.prefs    #JGH 2/10/14
        self.sizerV = sizerV = wx.BoxSizer(wx.VERTICAL)
        c = wx.ALIGN_CENTER
        self.helpText = \
        "Component Meter is a simple way to measure the value of components "\
        "which are known to be relatively pure resistors, capacitors or "\
        "inductors. It determines the component value from the attenuation "\
        "caused by the component in the test fixture. You select the fixture "\
        "and component type, run a single calibration, then insert and "\
        "measure components.\n\n"\
        "When you click Measure, the MSA will determine the component value "\
        "at one of several possible frequencies and display the frequency of "\
        "the measurement. The possible frequencies are those that the MSA "\
        "automatically included in the calibration. You may "\
        "increase/decrease the frequency of the measurement with the +Freq "\
        "and -Freq buttons, after pushing Stop.\n\n"\
        "The test fixture is typically an attenuator, then the component, "\
        "then another attenuator. The component may be connected in Series "\
        "between the attenuators, or may be Shunt to ground, which accounts "\
        "for the two different fixture types. The component will see a "\
        "certain resistance R0 looking at the incoming signal and the "\
        "outgoing signal. You must specify that R0, usually 50 ohms.\n\n"\
        "The Series fixture is calibrated with a Short (the terminals "\
        "directly shorted) and can typically measure R from 5 ohms to 100K "\
        "ohms; L from 10 nH to 1 mH, and C from 1 pF to 0.2 uF.\n\n"\
        "The Shunt fixture is calibrated with an Open (no component "\
        "attached) and can typically measure R from 0.25 ohms to 1 kohm; L "\
        "from 100 nH to 100 uH, and C from 20 pF to 2 uF.\n\n"\
        "For inductors, the series resistance and Q will be displayed, but "\
        "if Q>30, both Q and series resistance may be unreliable."

        # instructions
        st = wx.StaticText(self, -1, \
        "To measure resistance, capacitance or inductance you must first "\
        "calibrate. Calibrate with series shorted and shunt open. Then "\
        "insert the component and click Measure. The video filter should be "\
        "set to NARROW. Other settings will be made automatically. You can "\
        "temporarily change the frequency with +Freq or -Freq.")
        st.Wrap(600)
        sizerV.Add(st, 0, wx.ALL, 10)

        # test fixture
        sizerH1 = wx.BoxSizer(wx.HORIZONTAL)
        sizerH1.Add((1, 1), 1, wx.EXPAND)
        sizerH1.Add(self.FixtureBox(), 0, wx.ALIGN_TOP)
        sizerH1.Add((1, 1), 1, wx.EXPAND)

        # component type
        choices = ["Resistor", "Capacitor", "Inductor", "All"]
        self.typeRB = rb = wx.RadioBox(self, -1, "Component Type",
                        choices=choices, style=wx.RA_VERTICAL)
        self.Bind(wx.EVT_RADIOBOX, self.UpdateBtns, rb)
        sizerH1.Add(rb, 0, wx.ALIGN_TOP)
        sizerH1.Add((1, 1), 1, wx.EXPAND)
        sizerV.Add(sizerH1, 0, wx.EXPAND|wx.TOP, 10)
        sizerV.Add((1, 20), 0)

        # value display (StaticBox contents filled in by Update)
        self.freq = 0.1
        sizerGV = wx.GridBagSizer(hgap=2, vgap=5)
        self.freqText = st = wx.StaticText(self, -1, "")
        sizerGV.Add(st, (0, 0), flag=c)
        sizerGV.Add((20, 1), (0, 1), flag=wx.EXPAND)
        self.decFreqBtn = btn = wx.Button(self, -1, "-Freq")
        btn.Bind(wx.EVT_BUTTON, self.OnDecFreqBtn)
        sizerGV.Add(btn, (0, 2), flag=c)
        self.incFreqBtn = btn = wx.Button(self, -1, "+Freq")
        btn.Bind(wx.EVT_BUTTON, self.OnIncFreqBtn)
        sizerGV.Add(btn, (0, 3), flag=c)
        sb = wx.StaticBox(self, -1, "")
        self.sizerBV = sizerBV = wx.StaticBoxSizer(sb, wx.HORIZONTAL)
        sizerGV.Add(sizerBV, (1, 0), (1, 4), flag=c)
        sizerV.Add(sizerGV, 0, c|wx.ALL, 15)

        self.seriesRText = st = wx.StaticText(self, -1, "")
        sizerV.Add(st, 0, c, 0)

        # main buttons
        butSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.debugCB = chk = wx.CheckBox(self, -1, "Debug")
        butSizer.Add(chk, 0, c)
        butSizer.Add((20, 0), 0, wx.EXPAND)
        self.calibBtn = btn = wx.Button(self, -1, "Calibrate")
        btn.Bind(wx.EVT_BUTTON, self.OnCalibrateBtn)
        butSizer.Add(btn, 0, wx.ALL, 5)
        self.measBtn = btn = wx.Button(self, -1, "Measure")
        btn.Enable(False)
        btn.Bind(wx.EVT_BUTTON, self.OnMeasureBtn)
        butSizer.Add(btn, 0, wx.ALL, 5)
        btn = wx.Button(self, -1, "Help")
        btn.Bind(wx.EVT_BUTTON, self.OnHelpBtn)
        butSizer.Add(btn, 0, wx.ALL, 5)
        self.okBtn = btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        btn.Bind(wx.EVT_BUTTON, self.OnClose)
        butSizer.Add(btn, 0, wx.ALL, 5)
        sizerV.Add(butSizer, 0, wx.ALIGN_RIGHT|wx.ALIGN_BOTTOM|wx.ALL, 10)

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if self.pos == wx.DefaultPosition:
            self.Center()
        self.calibrated = False
        self.inCal = False
        self.measuring = False
        self.oldCompType = -1
        self.pointNum = None
        self.pointNums = {}
        self.UpdateBtns()
        self.valueBoxes = {}
        self.Show()

    #--------------------------------------------------------------------------
    # Update the states of all buttons and format the value box.

    def UpdateBtns(self, event=None):
        self.freqText.SetLabel("Frequency= %sHz" % si(self.freq * MHz, 3))
        calibrated = self.calibrated
        inCal = self.inCal
        newCompType = self.typeRB.GetSelection()
        afterMeasure = calibrated and not self.measuring and \
                        self.pointNum != None and newCompType != 4
        self.calibBtn.Enable(not self.measuring)
        self.calibBtn.SetLabel(("Calibrate", "Abort")[inCal])
        self.measBtn.Enable(calibrated)
        self.decFreqBtn.Enable(afterMeasure)
        self.incFreqBtn.Enable(afterMeasure)
        self.okBtn.Enable(not inCal)

        if (newCompType == 3) != (self.oldCompType == 3) or \
                self.oldCompType < 0:
            if self.measuring:
                self.StopMeasuring()
                self.calibBtn.Enable(True)
            self.oldCompType = newCompType
            # delete any previous type-dependent controls
            sizerBV = self.sizerBV
            sizerBV.Clear(deleteWindows=True)
            # create new type's controls
            c = wx.ALIGN_CENTER
            ch = wx.ALIGN_CENTER_HORIZONTAL
##            bigFont = wx.Font(fontSize*2.7, wx.SWISS, wx.NORMAL, wx.BOLD)
            bigFont = wx.Font(fontSize*2.0, wx.SWISS, wx.NORMAL, wx.BOLD)
            self.valueBoxes = {}
            if newCompType == 3:
                # Display all values at once
                sizerG2 = wx.GridBagSizer(5, 5)
                for j in range(2):
                    st = wx.StaticText(self, -1, ("Series", "Shunt")[j])
                    sizerG2.Add(st, (0, j), flag=c)
                    for i in range(3):
                        tc = wx.StaticText(self, -1, "----", size=(180, -1))
                        self.valueBoxes[(i,1-j)] = tc
                        tc.SetFont(bigFont)
                        tc.SetForegroundColour("BLUE")
                        sizerG2.Add(tc, (i+1,j), flag=c)
                sizerBV.Add(sizerG2, 0, 0)
            else:
                # Display selected component's value only
                tc = wx.StaticText(self, -1, "----", size=(200, -1))
                self.valueBox = tc
                tc.SetFont(bigFont)
                tc.SetForegroundColour("BLUE")
                sizerBV.Add(tc, 0, 0)
            sizerBV.Layout()
            self.sizerV.Fit(self)

    #--------------------------------------------------------------------------
    # Frequency up-down buttons for manual selection.

    def OnIncFreqBtn(self, event):
        if self.pointNum != None and self.pointNum < _40MHz:
            self.pointNum += 1
            self.Measure()

    def OnDecFreqBtn(self, event):
        if self.pointNum != None and self.pointNum > _100kHz:
            self.pointNum -= 1
            self.Measure()

    #--------------------------------------------------------------------------
    # Run calibration.

    def OnCalibrateBtn(self, event):
        frame = self.frame
        p = self.frame.prefs
        frame.task = None
        if msa.IsScanning():
            msa.StopScan()
            self.inCal = False
        else:
            # set up and run a calibration scan
            self.inCal = True
            self.UpdateBtns()
            p.isLogF = 1
            p.sweepDir = 0
            p.fStart = 0.1
            p.fStop = 40
            p.nSteps = 8
            p.wait = 10
            msa.calibrating = True
            savePlaneExt = p.planeExt
            frame.DoExactlyOneScan()
            frame.WaitForStop()
            msa.calibrating = False
            p.planeExt = savePlaneExt
            frame.SetBandCal(dcopy.deepcopy(frame.spectrum))
            frame.SetCalLevel(2)
            self.freq = 0.1
            self.inCal = False
            self.calibrated = True
            self.measuring = False
            frame.DoExactlyOneScan()
            frame.WaitForStop()

        self.UpdateBtns()

    #--------------------------------------------------------------------------
    # Start or stop measuring.

    def OnMeasureBtn(self, event):
        frame = self.frame
        if self.measuring:
            # was measuring: stop
            self.StopMeasuring()
        else:
            # else, continue scan if needed, and grab current spectrum
            self.measBtn.SetLabel("Stop")
            msa.WrapStep()
            msa.haltAtEnd = False
            msa.ContinueScan()
            self.measuring = True
            # set up OnTimer repeating measmts while allowing other commands
            frame.task = self
        self.UpdateBtns()

    def StopMeasuring(self):
        frame = self.frame
        frame.task = None
        frame.StopScanAndWait()
        self.measBtn.SetLabel("Measure")
        self.measuring = False

    #--------------------------------------------------------------------------
    # Take a measurement, with automatic adjustment of pointNum.

    def AutoMeasure(self):
        self.pointNum = None
        for i in range(3):
            for j in range(2):
                self.pointNums[(i,j)] = None
        try:
            self.Measure()
        except:
            # don't allow repeated errors
            self.frame.task = None
            raise

    #--------------------------------------------------------------------------
    # Measure selected or all types.

    def Measure(self):
        iCompType = self.typeRB.GetSelection()
        if iCompType == 3:
            if len(self.valueBoxes) == 0:
                return
            # All: measure and display all 6 component/jig-type values at once
            for i in range(3):
                for j in range(2):
                    valueText, color, LText = self.MeasureOne(i, j)
                    tc = self.valueBoxes[(i,j)]
                    tc.SetLabel(valueText)
                    tc.SetForegroundColour(color)
                    ##if i == 2:
                    ##    self.seriesRText.SetLabel(LText)
            self.seriesRText.SetLabel("")
        else:
            # measure just the selected type
            isSeries = self.seriesRB.GetValue()
            valueText, color, LText = self.MeasureOne(iCompType, isSeries)
            self.valueBox.SetLabel(valueText)
            self.valueBox.SetForegroundColour(color)
            self.seriesRText.SetLabel(LText)
        self.UpdateBtns()

    #--------------------------------------------------------------------------
    # Calculate component value at point specified by pointNum, but if it is
    # None find best frequency. Get the component value (ohms, F, or H)
    # and the point number at which we measured. For L and C, we also get
    # the series resistance, which is valid if we have phase.
    # It is possible to get a negative L or C value, which means the
    # self-resonance has interfered and the measurement is not valid.

    def MeasureOne(self, iCompType, isSeries):
        self.iCompType = iCompType
        self.isSeries = isSeries
        frame = self.frame
        debugM = self.debugCB.IsChecked()
        if debugM:
            self.debugCB.SetValue(False)
        ##debugM = False
        spectrum = frame.spectrum
        Sdb = spectrum.Sdb
        if debugM:
            print ("Fmhz=", spectrum.Fmhz)
            print ("Sdb=", Sdb)

        self.compType = compType = ("R", "C", "L")[iCompType]
        compUnits = (Ohms, "F", "H")[iCompType]
        self.R0 = floatOrEmpty(self.R0Box.GetValue())
        if self.typeRB.GetSelection() == 3:
            pointNum = self.pointNums[(iCompType, isSeries)]
        else:
            pointNum = self.pointNum

        # Do an initial measurement
        if pointNum == None:
            # need to find the best one -- assume we need to iterate
            nTries = 2
            if compType == "R":
                # 950kHz: high enough where LO leakages are not an issue
                pointNum = _950kHz
                nTries = 0
            else:
                lowFreqDB = Sdb[0]
                highFreqDB = Sdb[8]
                if debugM:
                    print ("lowFreqDB=", lowFreqDB, "highFreqDB=", highFreqDB, \
                        "isSeries=", isSeries, "compType=", compType)
                if compType == "C":
                    # Low impedance at 100 kHz indicates a large capacitor.
                    # High impedance at 40 MHz indicates a small capacitor.
                    # Large cap may be past its self-resonance at low freq, but
                    # will still have low impedance. Small cap will not be
                    # significantly affected by self-resonance at 40 MHz.
                    # We have to assume here small lead lengths on capacitors.
                    pointNum = _450kHz
                    if isSeries:
                        # We can tell whether we have extreme values by
                        # looking at 100 kHz and 40 MHz
                        # thresholds approx. 0.1 uF and 20 pF
                        isLowZ = lowFreqDB > -0.1
                        isHighZ = (not isLowZ) and highFreqDB < -7
                    else:
                        # thresholds approx. 0.1 uF and 100 pF
                        isLowZ = lowFreqDB < -5.5
                        isHighZ = (not isLowZ) and highFreqDB > -1.4
                    if isLowZ:
                        # Stick with lowest frequency
                        pointNum = _100kHz
                        nTries = 0
                    if isHighZ:
                        # start with highest frequency; may turn out hiZ is due
                        # to inductance
                        pointNum = _40MHz
                    if debugM:
                        print ("C: isLowZ=", isLowZ, "isHighZ=", isHighZ, \
                            "pointNum=", pointNum)
                else:
                    # Inductors are trickier, because losses can confuse the
                    # situation when just looking at S21 dB. So we make a guess
                    # at a starting point, but always do iteration, which
                    # separates L and R. Low impedance at 40 MHz indicates a
                    # very small inductor, though a lossy small inductor
                    # may be missed. It could also be large inductor that
                    # turned to a capacitor, but the iteration will take care
                    # of that case.
                    # A non-low impedance at 100 kHz indicates a large or
                    # lossy inductor. We will start with 100 kHz and iterate
                    # from there. For non-extreme inductors, we will start at
                    # 4.2 MHz and iterate
                    pointNum = _4p2MHz
                    if isSeries:
                        # thresholds 100 uH and 100 nH
                        isHighZ = lowFreqDB < -1.8
                        isLowZ = (not isHighZ) and highFreqDB > -0.45
                    else:
                        # thresholds 100 uH and 100 nH
                        isHighZ = lowFreqDB > -0.9
                        isLowZ = (not isHighZ) and highFreqDB < -3.4
                    if isHighZ:
                        # Start with lowest frequency
                        pointNum = _100kHz
                    if isLowZ:
                        # Start with highest frequency for small inductors
                        pointNum = _40MHz

            for i in range(nTries):
                value, serRes = self.GetComponentValue(pointNum, debugM)
                # See if we are at a reasonable frequency for this comp value
                if value < 0:
                    # The component measured negative, which may be a
                    # sign it is past self-resonance, so we need to go
                    # with a low frequency; but go high if we are
                    # already low
                    if pointNum == _100kHz:
                        pointNum = _40MHz
                    else:
                        pointNum = max(_100kHz, int(pointNum/2))
                else:
                    if compType == "C":
                        if isSeries:
                            # series wants high Z, meaning lower freq
                            table = [(0.,     _40MHz),
                                    ( 50*pF, _950kHz),
                                    (  5*nF, _100kHz)]
                        else:
                            # shunt C wants low Z, meaning higher freq
                            table = [(0.,     _40MHz),
                                    (100*pF, _8p9MHz),
                                    (  1*nF, _950kHz),
                                    ( 50*nF, _210kHz),
                                    (500*nF, _100kHz)]
                    else: # "L"
                        # Note: Inductor measurement is much less accurate
                        # without phase info, due to inductor losses. These
                        # ranges are se assuming phase is available. A prime
                        # goal is then to avoid the lowest freqs, where LO
                        # leakage has significant effect.
                        table = [(0.,     _40MHz),
                                (300*nH, _8p9MHz),
                                ( 10*uH, _950kHz),
                                (100*uH, _210kHz),
                                (  1*mH, _100kHz)]

                    # look up value in table of ranges
                    i = bisect_right(table, (value,)) - 1
                    if debugM:
                        print ("value=", value, "i=", i, "table=", table)
                    pointNum = table[i][1]
                    if debugM:
                        print ("pointNum=", pointNum)

        # get final value and series resistance
        value, serRes = self.GetComponentValue(pointNum, debugM)

        # display value, in red if out of range
        if value < 0:
            valueText = "------"
            valueColor = "RED"
        else:
            if value < (0.001, 10*fF, 500*pH)[iCompType]:
                value = 0.
            valueText = si(value, 4) + compUnits
            valueColor = "BLUE"
        R0ratio = self.R0 / 50
        if isSeries:
            lowLimit = (      -2,   1*pF,  10*nH)[iCompType]
            hiLimit  = (100*kOhm, 200*nF,   1*mH)[iCompType]
        else:
            lowLimit = (100*mOhm,  20*pF, 100*nH)[iCompType]
            hiLimit  = (  1*kOhm,   2*uF, 100*uH)[iCompType]
        if value < lowLimit*R0ratio or value > hiLimit*R0ratio:
            valueColor = "RED"

        # display frequency at which we measured
        self.freq = f = spectrum.Fmhz[pointNum]

        # display series resistance and Q for inductors
        LText = ""
        if compType == "L":
            if value < 0:
                Qtext = "300+"
            else:
                serX = 2*pi*self.freq*MHz * value
                Q = serX / serRes
                if Q > 300:
                    Qtext = "300+"
                else:
                    Qtext = "%g" % Q
            LText = "Series R=%5.2f Q=%s" % (serRes, Qtext)

        self.pointNums[(iCompType, isSeries)] = self.pointNum = pointNum
        return valueText, valueColor, LText

    #--------------------------------------------------------------------------
    # Calculate value of specified component.
    #
    # self.R0 of the test fixture; ignored for reflection mode, where
    #       ReflectArray data already accounts for it.
    # self.isSeries is 1 if fixture is Series; 0 if fixture is Shunt; ignored
    #     for reflection mode, where ReflectArray data already accounts for it.
    # self.compType is "R", "L" or "C"
    # step is the step at which we are measuring.
    # Returns value (Ohms, F or H) and, for L and C, series res in serRes.

    def GetComponentValue(self, step, debugM=False):
        compType = self.compType
        isSeries = self.isSeries
        R0 = self.R0
        serRes = 0.
        serX = 0.
        spectrum = self.frame.spectrum

        if msa.mode == msa.MODE_VNARefl:
            print ("Reflection mode: TODO")

        # trueFreq is frequency in Hz
        # db is S21 or S11 db of the component in the fixture
        # phase is S21 or S11 phase, unless we are in SATG mode
        trueFreq = spectrum.Fmhz[step] * MHz
        db = min(spectrum.Sdb[step], 0)
        phase = spectrum.Sdeg[step]
        if debugM:
            print ("GetCompValue: step=", step, "db=", db, "phase=", phase)

        if msa.mode == msa.MODE_SATG:
            # Calculate impedance from magnitude alone, assuming ideal phase
            # Magnitude of measured S21
            mag = 10**(db/20)
            if compType == "R":
                serX = 0
                if isSeries:
                    if mag > 0.9999:
                        serRes = 0.
                    else:
                        serRes = 2*R0 * (1 - mag) / mag
                    if debugM:
                        print ("R: mag=", mag, "serRes=", serRes)
                else:
                    if mag > 0.9999:
                        serRes = Inf
                    else:
                        serRes = R0 * mag / (2*(1 - mag))
            else:
                # L and C -- calculate reactance and then component value
                if isSeries:
                    if mag < 0.000001:
                        serX = 0.
                    else:
                        serX = 2*R0 * sqrt(1 - mag**2) / mag
                else:
                    if mag > 0.9999:
                        serX = Inf
                    else:
                        serX = R0 * mag / (2*sqrt(1 - mag**2))
                # capacitors have negative reactance
                if compType == "C":
                    serX = -serX
        else:
            # MODE_VNATran: calculate impedance from jig
            if isSeries:
                serRes, serX = SeriesJigImpedance(R0, db, phase)
            else:
                # We use no delay here, so we just provide a frequency of 1
                # assumes zero connector delay
                serRes, serX = ShuntJigImpedance(R0, db, phase, 0, 1, debugM)

        # serRes and serX now have the series resistance and reactance
        if debugM:
            print ("GetComponentValue: serRes=", serRes, "serX=", serX)
        if serRes < 0.001:
            serRes = 0.

        # if reactance is inductive, assume small resistor with parasitic
        # inductance and return series resistance
        if compType == "R":
            if serX > 0:
                return serRes, 0.
            # Here we want to return parallel resistance, because we are a
            # large resistor in parallel with parasitic capacitance
            parRes, parX = EquivParallelImped(serRes, serX)
            return parRes, 0.

        # Here for L or C. Convert reactance to component value
        if compType == "C":
            if serX == 0:
                value = 1.
            else:
                # capacitance in farads
                value = -1 / (2*pi*serX*trueFreq)
        else:
            # inductance in henries
            value = serX / (2*pi*trueFreq)
        if debugM:
            print ("--> GetComponentValue: serRes=", serRes, "value=", value, \
                    "f=", trueFreq)
        return min(value, 1.), serRes

#------------------------------------------------------------------------------
# Calculate a resistance and reactance pR and pX that when placed in
# parallel would produce an impedance of sR+j*sX.
# Returns (pR, pX).

def EquivParallelImped(sR, sX):
    print ("EquivParallelImped(R=", sR, ", sX=", sX, ")")
    if sR == Inf:
        magSquared = Inf
    else:
        magSquared = sR**2 + sX**2
    if sR == 0:
        if sX == 0:
            # target imped is zero; do small R and large X
            return 0, 1e12
        # target resistance is 0 but react is not; we need no parallel resistor
        pR = 1e12
    else:
        # res nonzero so parallel res is simple formula
        pR = magSquared / sR
    if sX == 0:
        return pR, 1e12
    return pR, magSquared / sX

#------------------------------------------------------------------------------
# Calculate impedance from S21.
# If a source and load of impedance Ro are attached to a series DUT, and
# S21 is measured, the impedance of the DUT is:
#   Z(DUT)= (2*Ro) * (1-S21)/S21 = (2*Ro) * (1/S21 - 1)
# The second formula is best when we start with S21 in db, because we can
# do the S21 inversion by taking the negative of the db value and adding
# 180 to the phase.
# special case: if S21Mag close to 0 treat the impedance as huge resistance
# Returns: Res, React

def SeriesJigImpedance(R0, db, deg):
    if db < -80:
        return Inf, Inf
    # outside range possible only through noise/rounding
    deg = min(max(deg, -90), 90)

    if db > -0.005:
        # For S21 mag near 1, the impedance is very small, and can be a
        # large capacitor, or a small resistor or inductor, or a mix.
        # In a real fixture S21 mag can even be slightly greater than
        # one, and the angle seems to be a better indicator of what we
        # have. For small reactive Z, tan(S21Deg) = -Z/(2*R0), so
        # Z = -2*R0*tan(S21Deg)
        if abs(deg) < 0.25:
            # Angle less than 0.25 degrees; assume resistance
            # Process resistance in normal way unless it is very small,
            # but make angle zero
            if db > -0.001:
                return 0., 0.
            deg = 0.
        else:
            return 0., -2*R0*tan(deg*pi/180)

    # To invert S21 while in db/angle form, negate db and angle
    lossMag = 10**(-db/20)
    lossAngle = -deg*pi/180
    # a+jb is inverted S21
    a = lossMag * cos(lossAngle)
    b = lossMag * sin(lossAngle)
    doubleR0 = 2*R0
    Res = doubleR0 * (a - 1)
    React = doubleR0 * b
    # avoids printing tiny values
    if Res < 0.001:
        Res = 0
    if abs(React) < 0.001:
        React = 0
    return Res, React

#------------------------------------------------------------------------------
# Calculate impedance from S21.
# If a source and load of impedance Ro are attached to a grounded DUT, and
# S21 is measured, the impedance of the DUT is:
#   Z(DUT)= (Ro/2) * S21 / (1-S21) = (Ro/2)/(1/S21 - 1) 'The second form works
# best for S21 originally in db
# special case: if S21Mag close to 1 treat the impedance as huge resistance

def ShuntJigImpedance(R0, db, deg, delay, freq, debugM=False):
    if debugM:
        print ("ShuntJigImpedance(R0=", R0, "db=", db, "deg=", deg, "delay=", \
            delay, "freq=", freq)
    # outside range possible only through noise/rounding
    deg = min(max(deg, -90), 90)
    extremeVal = False

    if db > -0.005:
        # For S21 mag near 1, the impedance is very large, and can be a
        # small capacitor, or a large resistor or inductor, or a mix.
        # In a real fixture S21 mag can even be slightly greater than
        # one, and the angle seems to be a better indicator of what we
        # have. For large reactive Z, tan(S21Deg) = R0/(2*Z), so
        # Z = R0/(2*tan(S21Deg))
        if abs(deg) < 0.25:
            # Angle less than 0.25 degrees; assume resistance
            # Process resistance in normal way unless it is very small,
            # but make angle zero
            if db > -0.001:
                return Inf, Inf
            deg = 0.
        else:
            React = R0/(2*tan(deg*pi/180))
            if debugM:
                print (" small dB, large ang: return 0", React)
            return 0., React

    if db < -100:
        Res = 0
        React = 0
        extremeVal = True
    if not extremeVal:
        # To invert S21 while in db/angle form, negate db and angle
        lossMag = 10**(-db/20)
        lossAngle = -deg*pi/180
        loss = lossMag * (cos(lossAngle) + 1j*sin(lossAngle))
        inv = 1 / (loss - 1)
        halfR0 = R0/2
        Res =   halfR0 * inv.real
        React = halfR0 * inv.imag
        if debugM:
            print (" not extreme: ", loss, inv, Res, React)

    # if delay != 0, then we adjust for the connector length of delay ns
    # the delay in radians is theta=2*pi*delay*freq/1e9, where delay is ns and
    # freq is Hz
    if delay != 0:
        # The impedance Res+j*React is the result of transformation by the
        # transmission line. We find the terminating impedance that produced
        # that transformed impedance. The impedance Z(DUT) which was
        # transformed into impedance Z is:
        #   Z(DUT) = 50* (Z - j*50*tan(theta)) / (50 - j*Z*tan(theta))
        # We use the same formula as is used to do the transformation, but
        # with negative length (theta).
        theta = -360 * delay * freq * ns
        Z = Res + 1j*React
        Zdut = 50 * (Z - 50j*tan(theta)) / (50 - 1j*Z*tan(theta))
        Res = Zdut.real
        React = Zdut.imag
        if debugM:
            print (" delay: ", theta, lossMag, lossAngle, Res, React)

    # avoids printing tiny values
    if Res < 0.001:
        Res = 0
    if abs(React) < 0.001:
        React = 0
    return Res, React


#==============================================================================
# The RLC Analysis dialog box.

class AnalyzeRLCDialog(FunctionDialog):
    def __init__(self, frame):
        FunctionDialog.__init__(self, frame, "RLC Analysis", "tranRLC")
        p = frame.prefs
        self.sizerV = sizerV = wx.BoxSizer(wx.VERTICAL)
        c = wx.ALIGN_CENTER

        self.helpText = \
        "RLC analysis will determine the R, L and C values for resistor, "\
        "inductor and capacitor combinations. The components may be in "\
        "series or in parallel, and either way they may be mounted in a "\
        "series or shunt fixture. The values of Q will also be determined."\
        "\n\nFor the shunt fixture, you may enter the time delay of the "\
        "connection between the actual fixture and the components; typically "\
        "on the order of 0.125 ns per inch.\n\n"\
        "You must enter the RLC Analysis function with a Transmission scan "\
        "already existing, showing the resonance peak (for series RLC in "\
        "series fixture, or parallel RLC in parallel fixture) or notch (for "\
        "series RLC in parallel fixture or parallel RLC in series fixture). "\
        "For resonance peaks, you should normally include the 3 dB points (3 "\
        "dB below a peak, or 3 dB above a dip). It is permissible, however, "\
        "to exclude one of those points. For resonant notches, you may "\
        "analyze the scan be using either the absolute -3 dB points (most "\
        "suitable for narrow notches) or the points 3 dB above the notch "\
        "bottom (most suitable for notches over 20 dB deep)."

        # description
        st = wx.StaticText(self, -1,"DETERMINATION OF COMBINED RLC PARAMETERS")
        sizerV.Add(st, 0, c|wx.TOP|wx.LEFT|wx.RIGHT, 10)
        st = wx.StaticText(self, -1, \
        "Determines individual components of an RLC combination from "\
        "resonance and 3 dB points. The scan must include the resonance and "\
        "at least one of the 3 dB points. High resolution improves "\
        "accuracy.")
        st.Wrap(600)
        sizerV.Add(st, 0, c|wx.TOP|wx.LEFT|wx.RIGHT, 10)

        # select series/parallel
        sizerG1 = wx.GridBagSizer(2, 2)
        self.parallelRLCRB = rb = wx.RadioButton(self, -1, \
            "The resistor, inductor and/or capacitor are in PARALLEL.", \
            style= wx.RB_GROUP)
        isSeriesRLC = p.get("isSeriesRLC", True)
        rb.SetValue(not isSeriesRLC)
        ##self.Bind(wx.EVT_RADIOBUTTON, self.UpdateFpBoxState, rb)
        sizerG1.Add(rb, (0, 0), (1, 6))
        self.SeriesRLCRB = rb = wx.RadioButton(self, -1, \
            "The resistor, inductor and/or capacitor are in SERIES.")
        rb.SetValue(isSeriesRLC)
        sizerG1.Add(rb, (1, 0), (1, 6))
        ##self.Bind(wx.EVT_RADIOBUTTON, self.UpdateFpBoxState, rb)
        sizerV.Add(sizerG1, 0, wx.ALL, 10)

        # test fixture
        isSeriesFix = p.get("isSeriesFix", True)
        st = self.FixtureBox(isSeriesFix, not isSeriesFix)
        sizerV.Add(st, 0, c|wx.ALL, 10)

        # select top/bottom 3dB points
        sizerG1 = wx.GridBagSizer(2, 2)
        self.useTopRB = rb = wx.RadioButton(self, -1, \
            "Use points at absolute -3 dB. (Best for narrow notches.)", \
            style= wx.RB_GROUP)
        isRLCUseTop = p.get("isRLCUseTop", True)
        rb.SetValue(not isRLCUseTop)
        self.Bind(wx.EVT_RADIOBUTTON, self.UpdateFpBoxState, rb)
        sizerG1.Add(rb, (0, 0), (1, 6))
        self.useBotRB = rb = wx.RadioButton(self, -1, \
            "Use points +3 dB from notch bottom. (Notch depth should exceed "\
            "20 dB.)")
        rb.SetValue(isRLCUseTop)
        sizerG1.Add(rb, (1, 0), (1, 6))
        self.Bind(wx.EVT_RADIOBUTTON, self.UpdateFpBoxState, rb)
        sizerV.Add(sizerG1, 0, wx.ALL, 10)

        # warning msg
        self.warnBox = st = wx.StaticText(self, -1, "")
        sizerV.Add(st, 0, c|wx.ALL, 10)
        st.SetFont(wx.Font(fontSize*1.3, wx.SWISS, wx.NORMAL, wx.BOLD))

        # text box for analysis results
        self.resultsBox = rb = wx.TextCtrl(self, -1, "", size=(400, -1))
        sizerV.Add(rb, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 20)

        #  bottom row buttons
        sizerH3 = wx.BoxSizer(wx.HORIZONTAL)
        sizerH3.Add((30, 0), 0, wx.EXPAND)
        self.analyzeBtn = btn = wx.Button(self, -1, "Analyze")
        btn.Bind(wx.EVT_BUTTON, self.OnAnalyze)
        btn.SetDefault()
        sizerH3.Add(btn, 0, c|wx.ALL, 5)
        sizerH3.Add((30, 0), 0, 0)
        self.helpBtn = btn = wx.Button(self, -1, "Help")
        btn.Bind(wx.EVT_BUTTON, self.OnHelpBtn)
        sizerH3.Add(btn, 0, c|wx.ALL, 5)
        self.okBtn = btn = wx.Button(self, wx.ID_OK)
        btn.Bind(wx.EVT_BUTTON, self.OnClose)
        sizerH3.Add(btn, 0, c|wx.ALIGN_RIGHT|wx.ALL, 5)
        sizerV.Add(sizerH3, 0, wx.ALIGN_RIGHT|wx.ALIGN_BOTTOM|wx.ALL, 10)

        self.UpdateFpBoxState()
        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if self.pos == wx.DefaultPosition:
            self.Center()
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Show()

    #--------------------------------------------------------------------------
    # Set the warning text based on top/bottom selection.

    def UpdateFpBoxState(self, event=None):
        self.useTop = useTop = self.useTopRB.GetValue()
        self.warnBox.SetLabel( \
        "Scan must show resonant notch and at least one point " +
        ("3 dB above notch bottom.", "at absolute -3 dB level.")[useTop])

    #--------------------------------------------------------------------------
    # Analyze the scan to extract RLC parameters.
    # We determine Q from resonant frequency and -3 dB bandwidth, and directly
    # measure Rs at resonance. From Q and Rs we can calculate L and C.

    def OnAnalyze(self, event):
        frame = self.frame
        specP = frame.specP
        markers = specP.markers
        p = frame.prefs
        isLogF = p.isLogF
        R0 = self.R0
        p.isSeriesRLC = isSeriesRLC = self.SeriesRLCRB.GetValue()
        p.isSeriesFix = isSeriesFix = self.seriesRB.GetValue()
        # a peak is formed if components in series and fixure is series
        isPos = not (isSeriesRLC ^ isSeriesFix)
        p.useTop = useTop = self.useTopRB.GetValue()

        try:
            Rser = 0
            isAbs = not isPos and useTop
            PeakS21DB, Fdb3A, Fdb3B = self.FindPoints(False, isPos=isPos, \
                                                      isAbs=isAbs)
            Fres = self.Fres

            if not isPos and not useTop:
                # analyze bottom of notch. Q determined from the 3 dB
                # bandwidth is assumed to be Qu
                S21 = 10**(-PeakS21DB/20)
                wp = 2*pi*Fres*MHz
                if isSeriesFix:
                    R = 2*R0 * (S21 - 1)
                else: # shunt fixture
                    R = (R0/2) / (S21 - 1)
                R = max(R, 0.001)
                BW = Fdb3B - Fdb3A
                # Qu at resonance. Accurate if notch is deep.
                Qu = Fres / BW
                if isSeriesRLC:
                    # series RLC in shunt fixture
                    Xres = R * Qu
                    QL = Xres / (R0/2)
                    Rser = R
                else:
                    # parallel RLC in shunt fixture
                    Xres = R / Qu
                    QL = Xres / (R0*2)
                    Rser = Xres / Qu

                L = Xres / wp
                C = 1 / (Xres * wp)

            else:
                # Analyze top of peak or notch
                if isSeriesRLC:
                    # For series RLC use crystal routine; Fp and Cp are bogus
                    R, C, L, Cp, Qu, QL = CrystalParameters(Fres, 1., \
                                    PeakS21DB, Fdb3A, Fdb3B, R0, isSeriesFix)
                else: # parallel RLC
                    R, C, L, Qu, QL, Rs = ParallelRLCFromScalarS21(Fres,
                                    PeakS21DB, Fdb3A, Fdb3B, R0, isSeriesFix)
                L *= uH
                C *= pF
            Fres *= MHz

        except RuntimeError:
            alertDialog(self, sys.exc_info()[1].message, "Analyze Error")
            return

        # compute and display filter info
        resText = ("F%s=%sHz, R=%s"+Ohms+", L=%sH, C=%sF, Qu=%s, QL=%s") % \
                ("ps"[isPos], si(Fres, 9), si(R, 4), si(L, 3), si(C, 3), \
                si(Qu, 3), si(QL, 3))
        if Rser > 0:
            resText += (", (Rser=%s)" % si(Rser, 3))
        self.resultsBox.SetValue(resText)

        BWdb3 = Fdb3B - Fdb3A
        info = re.sub(", ", "\n", resText) + "\n"
        info += ("BW(3dB)=%sHz" % si(BWdb3*MHz, 3))
        specP.results = info

        specP.FullRefresh()
        self.okBtn.SetDefault()

# Start EON Jan 22, 2014
#==============================================================================
# The Coax Parameters dialog box.

class CoaxParmDialog(FunctionDialog):
    def __init__(self, frame):
        FunctionDialog.__init__(self, frame, "Coaxial Cable Analysis", "coaxParms")
        p = frame.prefs
        if p.isLogF: # EON Jan 29, 2014
            message("Only linear sweep allowed for Coax Test.")
            return

        self.sizerV = sizerV = wx.BoxSizer(wx.VERTICAL)
        c = wx.ALIGN_CENTER
        self.helpText = \
        "1. Using a shunt fixture or bridge, perform an S11 scan of an "\
        "open coax stub, focused around the quarter-wavelength resonance "\
        "(near +/-180 degrees S11 phase).\n\n"\
        "2. Open Function-->Coax Analysis.\n\n"\
        "3. Enter either the length or velocity factor of the coax stub.\n\n"\
        "4. Click Analyze. The resonant frequency, length, velocity factor and "\
        "loss factor (A0, dB per hundred feet) are displayed, and the Analyze "\
        "Z0 button appears.\n\n"\
        "5. To measure Z0, attach a terminating resistor to the stub, click "\
        "Analyze Z0, and enter the value of the termination in the dialog that "\
        "opens.  When you click OK a scan will be performed and the results will "\
        "be displayed.  For best accuracy, the value of the terminating "\
        "resistor should be in the ballpark of what you expect Z0 to be, but "\
        "you may choose to use no termination at all, in which case you should "\
        "enter 1 mega-ohm or larger as the termination value.  (Z0 will be "\
        "displayed as a complex number, but only the real part is generally "\
        "used to identify coax cable.)"

        text = \
        "This module will analyze parameters of a coax cable. Before entering, "\
        "you must perform a scan of S11 for the cable with no termination. You "\
        "must specify either the length or velocity factor and then click "\
        "Analyze to determine whichever of those two you did not specify, as "\
        "well as the loss factor (A0) in dB per hundred feet. After that, if "\
        "you want to determine the characteristic impedance of the cable, click "\
        "Analyze Z0; you will be asked to attach a terminating resistance to "\
        "the cable, after which the MSA will determine the cable Z0."
        st = wx.StaticText(self, -1, text)
        st.Wrap(400)
        sizerV.Add(st, 0, c|wx.ALL, 10)

        sizerH0 = wx.BoxSizer(wx.HORIZONTAL)

        sizerV0 = wx.BoxSizer(wx.VERTICAL)
        self.lenRb = rb = wx.RadioButton(self, -1, "Length", style=wx.RB_GROUP)
        rb.Bind(wx.EVT_RADIOBUTTON, self.OnVelLen)
        sizerV0.Add(rb, 0, wx.ALL, 2)
        self.velFactRb = rb = wx.RadioButton(self, -1, "Velocity Factor")
        rb.Bind(wx.EVT_RADIOBUTTON, self.OnVelLen)
        sizerV0.Add(rb, 0, wx.ALL, 2)

        sizerH0.Add(sizerV0, 0, wx.ALL, 2)

        self.coaxValBox = tc = wx.TextCtrl(self, -1, "", size=(60, -1))
        self.coaxValBox.SetFocus() # EON Jan 29, 2014
        sizerH0.Add(tc, 0, wx.EXPAND|wx.ALL|wx.ALIGN_CENTER_VERTICAL, 10)

        sizerV1 = wx.BoxSizer(wx.VERTICAL)
        self.feetRb = rb = wx.RadioButton(self, -1, "feet", style=wx.RB_GROUP)
        sizerV1.Add(rb, 0, wx.ALL, 2)
        self.meterRb = rb = wx.RadioButton(self, -1, "meters")
        sizerV1.Add(rb, 0, wx.ALL, 2)

        sizerH0.Add(sizerV1, 0, wx.ALL, 2)
        sizerV.Add(sizerH0, 0, c|wx.ALL, 2)

        self.sizerH1 = sizerH1 = wx.BoxSizer(wx.HORIZONTAL) # EON Jan 29, 2014
        st = wx.StaticText(self, -1, "Results")
        sizerH1.Add(st, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 2)
        self.resultTxt = st = wx.StaticText(self, -1, "") # EON Jan 29, 2014
        sizerH1.Add(st, 0, wx.ALL, 2) # EON Jan 29, 2014
        sizerV.Add(sizerH1, 0, c|wx.ALL, 2)

        sizerH2 = wx.BoxSizer(wx.HORIZONTAL)
        st = wx.StaticText(self, -1, "Z0")
        sizerH2.Add(st, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 2)
        self.Z0Txt = st = wx.StaticText(self, -1, "") # EON Jan 29, 2014
        sizerH2.Add(st, 0, wx.ALL, 2) # EON Jan 29, 2014
        sizerV.Add(sizerH2, 0, c|wx.ALL, 2)

        sizerGb = wx.GridBagSizer(20, 10)
        self.analyzeBtn = btn = wx.Button(self, -1, "Analyze") # EON Jan 29, 2014
        btn.Bind(wx.EVT_BUTTON, self.OnAnalyze)
        sizerGb.Add(btn, (0, 0))
        self.analyzeZ0Btn = btn = wx.Button(self, -1, "AnalyzeZ0") # EON Jan 29, 2014
        btn.Show(False)
        btn.Bind(wx.EVT_BUTTON, self.OnAnalyzeZ0)
        sizerGb.Add(btn, (0, 1))
        self.doneBtn = btn = wx.Button(self, -1, "Done") # EON Jan 29, 2014
        btn.Bind(wx.EVT_BUTTON, self.OnDone)
        sizerGb.Add(btn, (0, 3))
        btn = wx.Button(self, -1, "Help")
        btn.Bind(wx.EVT_BUTTON, self.OnHelpBtn)
        sizerGb.Add(btn, (0, 4))
        sizerGb.AddGrowableCol(2)

        sizerV.Add(sizerGb, 0, wx.EXPAND|wx.ALL, 10)

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if self.pos == wx.DefaultPosition:
            self.Center()
        self.Show()

    def OnVelLen(self, event):
        if self.velFactRb.GetValue():
            self.feetRb.Show(False)
            self.meterRb.Show(False)
        else:
            self.feetRb.Show(True)
            self.meterRb.Show(True)

    def OnAnalyze(self, event):
        try: # EON Jan 29, 2014
            val = float(self.coaxValBox.GetValue())
        except:
            message("Length or Velocity Factor blank or invalid.")
            return

        isLen = self.lenRb.GetValue()
        meters = self.meterRb.GetValue() # EON Jan 29, 2014
        if isLen:
            coaxLen = val
            if meters: # EON Jan 29, 2014
                coaxLen *= 3.281
        else:
            coaxVF = val

        specP = self.frame.specP # EON Jan 29, 2014
        magName = self.MagTraceName()
        trMag = specP.traces[magName]

#        trPh = trMag.phaseTrace # EON Jan 29, 2014
#        vals = trPh.v
#        lastDeg = vals[0]
#        lastI = 0
#        for i in range (0, len(vals)):
#            deg = vals[i]
#            if abs(deg) > 90:
#                if (lastDeg < 0 and deg > 0) or (lastDeg > 0 and deg < 0):
#                    break
#            lastDeg = deg
#            lastI = i
#        Fmhz = trPh.Fmhz
#        fDiff = Fmhz[i] - Fmhz[lastI]
#        coaxFq = (-lastDeg / (deg - lastDeg)) * fDiff + Fmhz[lastI]

        react = trMag.Zs.imag
        lastX = react[0]
        lastI = 0
        for i in range (0, len(react)):
            X = react[i]
            if (lastX < 0 and X > 0) or (X < 0 and lastX > 0):
                break
            lastX = X
            lastI = i
        Fmhz = trMag.Fmhz # EON Jan 29, 2014
        fDiff = Fmhz[i] - Fmhz[lastI]
        self.coaxFq = coaxFq = (-lastX / (X - lastX)) * fDiff + Fmhz[lastI] # EON Jan 29, 2014

        markers = specP.markers
        markers["1"]  = m1 =  Marker("1", magName, coaxFq)
        m1.SetFromTrace(trMag, False)
        specP.markersActive = True
        specP.FullRefresh()
        wx.Yield()
        if isLen:
            coaxVF = coaxLen * coaxFq / 245.9
        else:
            coaxLen = 245.9 * coaxVF / coaxFq
        self.coaxLen = coaxLen # EON Jan 29, 2014

        x = Fmhz[i - 2 : i + 3] # EON Jan 29, 2014
        y = react[i - 2 : i + 3]
        A = numpy.vstack([x, numpy.ones(len(x))]).T
        m, c = numpy.linalg.lstsq(A, y)[0]
        w = 2 * pi * 1e6 * coaxFq
        D = m / (2 * pi * 1e6)
        X = react[i]
        R = trMag.Zs[i].real
        num = abs(X) + w * D
        coaxQ = num / (2 * R)
        self.coaxA0 = coaxA0 = 682.2 / (coaxLen * coaxQ)
        if meters:
            length = "%5.3f m" % (coaxLen / 3.281)
        else:
            length = "%5.3f ft" % coaxLen
        result = "%8.6f mHz %s VF = %5.3f A0 = %4.2f" % (coaxFq, length, coaxVF, coaxA0)
        self.resultTxt.SetLabel(result)
        self.analyzeZ0Btn.Show(True)
        self.sizerV.Fit(self)
        self.sizerV.Layout()

# [CoaxAnalyzeTL]
#     #CoaxAnalyze.LenOrVF, "!contents? s$"
#     coaxVal=uValWithMult(s$)
#     if coaxVal<=0 then notice "You must specify a valid length or velocity factor." : wait
#     if coaxHaveLen then
#         coaxLenFeet=coaxVal   'value from box
#         if coaxDoFeet=0 then coaxLenFeet=3.281*coaxLenFeet   'Feet to meters
#     else
#         coaxVF=coaxVal    'value from box
#     end if
#
#     'We need to find Fq, which is the quarter-wavelength frequency. This will be the first
#     'point with zero phase.
#     coaxPeakStep=StepWithValue(constSerReact,0,1,0)   'start at 0, go forward, look for 0 reactance
#         'coaxPeakStep may be a fractional step; convert to point number when adding marker
#     call mAddMarker "L", coaxPeakStep+1, str$(primaryAxisNum)  'So user can see what we are doing
#     call RefreshGraph 0
#     call gGetMinMaxPointNum coaxMinPoint, coaxMaxPoint
#     coaxMinStep=coaxMinPoint-1 : coaxMaxStep=coaxMaxPoint-1
#     if coaxPeakStep<coaxMinStep+10 or coaxPeakStep>coaxMaxStep-10 then _
#             notice "Resonance is too near the edge of the scan" : goto [CoaxAnalyzeTLDone]
#     coaxFq=gGetPointXVal(coaxPeakStep+1)    'point num is one more than step num
#     if coaxFq<=0 then notice "Can't process negative or zero frequencies." : goto [CoaxAnalyzeTLDone]
#
#     if coaxHaveLen then     'calculate len or VF, whichever we are missing
#         coaxVF=coaxLenFeet*coaxFq/245.9
#     else
#         coaxLenFeet=245.9*coaxVF/coaxFq
#     end if
#
#     'We don't want to base the analysis on the impedance at the peak, because for a quarter-wave stub that
#     'will be a very small value, not very accurately determined. --Actually, that impedance gets
#     'used in the Q calculation anyway.
#
#         'We will determine unloaded Q by looking at the slope of the reactance, because this
#         'will work well even for high Q values.
#     call uBestFitLines constSerReact, constSerR, 5,coaxMinStep, coaxMaxStep 'Assemble data and slopes; use 5 points for slopes
#
#     call DetermineLCEquiv "Series",coaxMinStep, coaxMaxStep,coaxPeakStep
#
#     coaxQ=auxGraphData(int(coaxPeakStep+0.5), 2)  'unloaded Q value
#
#     call ClearAuxData   'Clear auxiliary graph data (created by DetermineLCEquiv) by blanking graph names
#     coaxA0=682.2/(coaxLenFeet*coaxQ)
#
#     coaxF$=using("####.######",coaxFq)
#     if coaxDoFeet then coaxL$=using("####.###",coaxLenFeet)+" ft" else _
#                         coaxL$=using("####.###",coaxLenFeet/3.281)+" m"
#     if coaxDoFeet then coaxLenUnits$=" ft" else coaxLenUnits$=" m"
#     coaxVF$=using("#.###", coaxVF)
#     coaxA0$=using("###.##", coaxA0)
#     #CoaxAnalyze.results, "F=";coaxF$;" MHz;  Len=";coaxL$;";  VF=";coaxVF$;";  A0=";coaxA0$
#     #CoaxAnalyze.AnalyzeZ0, "!show"
#     wait
#

    def OnAnalyzeZ0(self, event):
        coaxRLoad = "50" # EON Jan 29, 2014
        dlg = TerminationDialog(self.frame)
        if dlg.ShowModal() == wx.ID_OK:
            coaxRLoad = dlg.RBox.GetValue()
        else:
            return

        try:
            rLoad = float(coaxRLoad)
        except:
            message("Load blank or invalid.")
            return

        if rLoad < 1e6:
            self.analyzeBtn.Enable(False)
            self.doneBtn.Enable(False)
            label = self.analyzeZ0Btn.GetLabel()
            self.analyzeZ0Btn.SetLabel("Scanning")
            self.sizerV.Layout()
            self.sizerV.Fit(self)
            wx.Yield()
            self.frame.DoExactlyOneScan()
            self.frame.WaitForStop()
            self.analyzeBtn.Enable(True)
            self.doneBtn.Enable(True)
            self.analyzeZ0Btn.SetLabel(label)

        specP = self.frame.specP
        magName = self.MagTraceName()
        trMag = specP.traces[magName]
        Fmhz = trMag.Fmhz
        Zs = trMag.Zs

        coaxZReal = interp(self.coaxFq, Fmhz, Zs.real)
        coaxZImag = interp(self.coaxFq, Fmhz, Zs.imag)
        Z = complex(coaxZReal, coaxZImag)

        coaxAlphaLen = 0.0011513 * self.coaxA0 * self.coaxLen
        coaxBetaLen = pi / 2
        G = complex(coaxAlphaLen, coaxBetaLen)

        # The termination resistance RLoad is measured as coax input
        # impedance of ZReal+jZImag Use that and the alpha and beta
        # factors to calculate Z0
        Z0 = Coax.CoaxZ0FromTerminationImpedance(complex(rLoad,0), Z, G)
        result = "Real = %3.1f Imag = %3.1f" % (Z0.real, Z0.imag)
        self.Z0Txt.SetLabel(result)
        self.sizerV.Layout()

#  [CoaxAnalyzeZ0]
#     coaxRLoad$="50"
#     Prompt "Attach termination resistor and enter its value."; coaxRLoad$
#     if coaxRLoad$="" then wait  'cancelled
#     coaxRLoad=uValWithMult(coaxRLoad$)
#     if coaxRLoad<=0 then notice "Invalid termination resistance." : wait
#     'Save S11 data for the open stub in auxGraphData(,0) and (,1) for use by GraphCoaxLossAndZ0
#     for i=0 to steps
#         coaxOpenS11DB=ReflectArray(i,constGraphS11DB)
#         coaxOpenS11Ang= ReflectArray(i,constGraphS11Ang)
#         auxGraphData(i,0)=coaxOpenS11DB
#         auxGraphData(i,1)=coaxOpenS11Ang
#     next i
#
#     if coaxRLoad<1e6 then
#             'If termination is huge, we just use the open scan we already have
#             'Otherwise, gather new data
#         #CoaxAnalyze.Analyze, "!disable" : #CoaxAnalyze.AnalyzeZ0, "!disable"
#         #CoaxAnalyze.Done, "!disable" : #CoaxAnalyze.Help, "!disable"
#         #CoaxAnalyze.Z0, "Performing Scan"
#
#             'Do one scan with exactly the same settings as the original, to get new S11 values
#         cursor hourglass
#         specialOneSweep=1   'So we return from [Restart]
#         gosub [Restart]     'Do actual scan to acquire data
#         cursor normal
#         #CoaxAnalyze.Analyze, "!enable" : #CoaxAnalyze.AnalyzeZ0, "!enable"
#         #CoaxAnalyze.Done, "!enable" : #CoaxAnalyze.Help, "!enable"
#     end if
#
#             'Get impedance at peak, in rectangular form, interpolating if necessary.
#     call CalcGraphDataType coaxPeakStep,constSerR, constSerReact, coaxZReal, coaxZImag, 0
#
#         'If we use the open to calculate Z0, the impedance at resonance may measure zero,
#         'which makes it impossible to determine Z0.
#     if coaxZReal=0 and coaxZImag=0 then #CoaxAnalyze.Z0, "Indeterminate Z0" : wait
#
#     coaxAlphaLen=0.0011513*coaxA0*coaxLenFeet
#     coaxBetaLen=uPi()/2 'At quarter wave, angle is pi/2
#         'The termination resistance RLoad is measured as coax input impedance of ZReal+jZImag
#         'Use that and the alpha and beta factors to calculate Z0
#     call CoaxZ0FromTerminationImpedance coaxRLoad, 0, coaxZReal, coaxZImag, coaxAlphaLen, coaxBetaLen, coaxZ0Real, coaxZ0Imag   'cal Z0
#     #CoaxAnalyze.Z0, "Z0 Real=";using("###.#",coaxZ0Real); ";  Z0 Imag=";using("###.#",coaxZ0Imag)
#
#     'call GraphCoaxLossAndZ0 coaxRLoad, fMHz, coaxZ0Real, coaxLenFeet, coaxVF,coaxK1, coaxK2    'ver115-4d
#     'call ChangeGraphsToAuxData constAux0, constAux1 'Graph Z0 real and imag   'ver115-4d
#     wait

    def OnDone(self, event):
        self.Destroy()

class TerminationDialog(wx.Dialog): # EON Jan 29, 2014
    def __init__(self, frame):
        wx.Dialog.__init__(self, frame, -1, "Termination Resistor",  wx.DefaultPosition,
                           wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        c = wx.ALIGN_CENTER

        sizerV = wx.BoxSizer(wx.VERTICAL)

        text = "Attach termination resistor and enter its value."
        st = wx.StaticText(self, -1, text)
        sizerV.Add(st, 0, c|wx.ALL, 10)

        self.RBox = tc = wx.TextCtrl(self, -1, "50", size=(60, -1))
        sizerV.Add(tc, 0, c|wx.ALL, 10)

        sizerH = wx.BoxSizer(wx.HORIZONTAL)

        btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        sizerH.Add(btn, 0, wx.ALL, 2)

        btn = wx.Button(self, wx.ID_CANCEL)
        sizerH.Add(btn, 0, wx.ALL, 2)

        sizerV.Add(sizerH, 0, wx.ALL, 2)
        self.SetSizer(sizerV)
        sizerV.Fit(self)
        self.Center()

# End EON Jan 22, 2014

#==============================================================================
# The Crystal Analysis dialog box.

class CrystAnalDialog(FunctionDialog):
    def __init__(self, frame):
        FunctionDialog.__init__(self, frame, "Crystal Analysis", "crystal")
        p = frame.prefs
        self.sizerV = sizerV = wx.BoxSizer(wx.VERTICAL)
        c = wx.ALIGN_CENTER

        if msa.mode >= msa.MODE_VNATran:
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
            if msa.mode != msa.MODE_VNATran:
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
            if False:
                searchR = vals[jP] > targVal
                signP = (-1, 1)[searchR]
                m1.FindValue(trPh, jP, isLogF, signP, searchR, targVal, show)
                if isnan(m1.mhz):
                   m1.FindValue(trPh, jP, isLogF, -signP, 1-searchR, targVal, show)
                if 1:   # set 0 to disable zero-phase Fs use to match Basic
                    Fs = m1.mhz
            else:
                lastX = vals[jP]
                lastI = 0
                for i in range (jP, len(vals)):
                    X = vals[i]
                    if (lastX < 0 and X > 0) or (X < 0 and lastX > 0):
                        break
                    lastX = X
                    lastI = i
                Fmhz = trPh.Fmhz
#                print ("i %3d lastX %6.2f X %6.2f" % (i, lastX, X))
#                print ("lastX %8.6f X %8.6f" % (Fmhz[lastI], Fmhz[i]))
                fDiff = Fmhz[i] - Fmhz[lastI]
                Fs = (-lastX / (X - lastX)) * fDiff + Fmhz[lastI]
                m1.mhz = Fs

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


#=============================================================================
# The Step Attenuator dialog box.

class StepAttenDialog(FunctionDialog):
    def __init__(self, frame):
        FunctionDialog.__init__(self, frame, "Step Attenuator", "stepAtten")
        p = frame.prefs
        self.sizerV = sizerV = wx.BoxSizer(wx.VERTICAL)
        c = wx.ALIGN_CENTER

        if msa.IsScanning():
            msa.StopScan()

        # instructions
        st = wx.StaticText(self, -1, \
        "With one or two digital step attenuator modules attached, a series "\
        "of sweeps may be made. set the number of steps and the step increment, "\
        "keeping the total within the range of the attenuator(s), and the "\
        "number of steps less than 10. Then click Run Steps. Any existing "\
        "Ref Lines will be replaced with the series. "\
        "An example: a pair of SKY12347 64-step "\
        "attenuators with 0.5dB per step could make a series of 7 in 10 dB "\
        "steps. Remember to account for attenuator insertion loss.")
        st.Wrap(600)
        sizerV.Add(st, 0, wx.ALL, 10)

        # steps range entry
        sizerH1 = wx.BoxSizer(wx.HORIZONTAL)
        self.nStepsLabel = st = wx.StaticText(self, -1, "# steps:")
        sizerH1.Add(st, 0, c|wx.RIGHT, 5)
        n = str(p.get("stepAttenN", 5))
        self.nStepsBox = tc = wx.TextCtrl(self, -1, n, size=(40, -1))
        tc.SetInsertionPoint(2)
        sizerH1.Add(tc, 0, c)
        sizerH1.Add((50, 0), 0, wx.EXPAND)
        sizerH1.Add(wx.StaticText(self, -1, "Start:"), 0, c|wx.RIGHT, 5)
        start = str(p.get("stepAttenStart", 0))
        self.stepsStartBox = tc = wx.TextCtrl(self, -1, start, size=(40, -1))
        tc.SetInsertionPoint(2)
        sizerH1.Add(tc, 0, c)
        sizerH1.Add(wx.StaticText(self, -1, "dB"), 0, c|wx.LEFT, 5)
        sizerH1.Add((50, 0), 0, wx.EXPAND)
        step = str(p.get("stepAttenStep", 5))
        sizerH1.Add(wx.StaticText(self, -1, "Step:"), 0, c|wx.RIGHT, 5)
        self.stepsStepBox = tc = wx.TextCtrl(self, -1, step, size=(40, -1))
        tc.SetInsertionPoint(2)
        sizerH1.Add(tc, 0, c)
        sizerH1.Add(wx.StaticText(self, -1, "dB"), 0, c|wx.LEFT, 5)
        sizerH1.Add((50, 0), 0, wx.EXPAND)
        sizerV.Add(sizerH1, 0, c|wx.ALL, 10)

        #  bottom row buttons
        sizerH3 = wx.BoxSizer(wx.HORIZONTAL)
        self.analyzeBtn = btn = wx.Button(self, -1, "Run Steps")
        btn.Bind(wx.EVT_BUTTON, self.OnRun)
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
    # Run a series of scans of a range of attenuations.

    def OnRun(self, event):
        frame = self.frame
        p = frame.prefs
        n = int(self.nStepsBox.GetValue())
        if n < 1:
            n = 1
        p.stepAttenN = n
        dbSave = p.stepAttenDB
        p.stepAttenDB = floatOrEmpty(self.stepsStartBox.GetValue())
        p.stepAttenStart = p.stepAttenDB
        p.stepAttenStep = step = floatOrEmpty(self.stepsStepBox.GetValue())

        # loop for each attenuator value
        for refNum in range(1, n+1):
            frame.DoExactlyOneScan()
            frame.WaitForStop()

            # create a new ref from current data
            spec = frame.spectrum
            vScales = frame.specP.vScales
            # get the units from both vertical scales
            bothU = [vs.dataType.units for vs in vScales]
            ##print ("bothU=", bothU
            for i in range(2):
                vScale = vScales[i]
                # create a ref for each axis, unless the axes are
                # (db, Deg), in which case we create one ref with both
                if i == 1 and (msa.mode < msa.MODE_VNATran or \
                         ("dB" in bothU and \
                         ("Deg" in bothU or "CDeg" in bothU))):
                    continue
                ref = Ref.FromSpectrum(refNum, spec, vScale)
                # assign trace width(s) and name
                ref.aWidth = 1
                if msa.mode >= msa.MODE_VNATran:
                    # ref for axis 0 may be both mag and phase traces
                    ref.bWidth = 1
                ref.name = "%04.1fdB" % p.stepAttenDB
                frame.refs[refNum] = ref
            frame.DrawTraces()
            frame.specP.FullRefresh()

            p.stepAttenDB += step

        p.stepAttenDB = dbSave

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

#------------------------------------------------------------------------------
# Calculate parallel RLC values in Series or Shunt Jig.
#
# Fp: parallel resonance in MHz
# PeakS21DB: S21 db at Fp (a negative value in db)
# Fdb3A, Fdb3B: -3db frequencies, in MHz, around Fs;
#                   (absolute -3dB frequencies if shunt jig)
# R0: impedance of the test jig
# isSeries: True if a series jig
#
# Returns Rp, C(pF), L(uH), Qu, QL, Rser

def ParallelRLCFromScalarS21(Fp, PeakS21DB, Fdb3A, Fdb3B, R0, isSeries):
    if Fp <= 0 or Fdb3A >= Fp or Fdb3B <= Fp:
        raise RuntimeError("Invalid frequency data for calculation:" \
                "Fp=%g Fdb3A=%g Fdb3B=%g" % (Fp, Fdb3A, Fdb3B))
    if R0 <= 0:
        raise RuntimeError("Invalid R0")
    S21 = 10**(-PeakS21DB/20)
    wp = 2*pi*Fp*MHz
    if isSeries:
        Rp = 2*R0 * (S21 - 1)
        Rsrcload = 2*R0
    else: # shunt fixture
        Rp = (R0/2) / (S21 - 1)
        Rsrcload = R0/2
    Rp = max(Rp, 0.001)
    Rnetload = Rsrcload * Rp / (Rsrcload + Rp)
    BW = Fdb3B - Fdb3A
    # loaded Q at Fp
    QL = Fp / BW
    # reactance of L, and -reactance of C, at resonance
    Xres = Rnetload / QL
    # unloaded Q is based on Rp, much larger than Rnetload
    Qu = Rp / Xres
    Rser = Xres / Qu
    L = Xres / wp
    C = 1 / (Xres * wp)
    if L < 1*pH:
        L = 0
    if C < 1*pF:
        C = 0
    return Rp, C/pF, L/uH, Qu, QL, Rser


#==============================================================================
# A Smith chart panel.

class SmithPanel(wx.Panel):
    def __init__(self, parent, frame):
        self.frame = frame
        self.prefs = p = frame.prefs

        wx.Panel.__init__(self, parent, -1)
        self.SetBackgroundColour(p.theme.backColor)
        ##self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        self.Bind(wx.EVT_PAINT,        self.OnPaint)
        self.Bind(wx.EVT_SIZE,         self.OnSizeChanged)

    #--------------------------------------------------------------------------
    # Force the grid and other parts to be redrawn on a resize.

    def FullRefresh(self):
        if debug:
            print ("Smith.FullRefresh")
        self.Refresh()

    def OnSizeChanged(self, event):
        self.FullRefresh()
        event.Skip()   # (will continue handling event)

    #--------------------------------------------------------------------------
    # Repaint the Smith chart.

    def OnPaint(self, event):
        LogGUIEvent("Smith.OnPaint")
        frame = self.frame
        specP = frame.specP
        p = self.prefs
        self.vColors = vColors = p.theme.vColors
        foreColor = p.theme.foreColor
        backColor = p.theme.backColor
        gridColor = p.theme.gridColor
        forePen = wx.Pen(foreColor, 1, wx.SOLID)
        backPen = wx.Pen(backColor, 1, wx.SOLID)
        gridPen = wx.Pen(gridColor, 1, wx.SOLID)
        fontSizeGC = fontSize * (1, 1.5)[isLinux]
        normalFont = wx.Font(fontSizeGC, wx.SWISS, wx.NORMAL, wx.NORMAL)
        backBrush = wx.Brush(backColor, wx.SOLID)
        clientWid, clientHt = self.GetSize()

        # ------ GRID ------

        # (GraphicsContext doesn't like AutoBufferedPaintDC, so we use:)
        if self.IsDoubleBuffered():
            dc = wx.PaintDC(self)
        else:
            dc = wx.BufferedPaintDC(self)
            dc.Clear()

        gc = wx.GraphicsContext.Create(dc)
        gc.Translate(clientWid/2, clientHt/2)
        foreFont = gc.CreateFont(normalFont, foreColor)
        gridFont = gc.CreateFont(normalFont, gridColor)

        # pure resistance line across center
        gc.SetFont(gridFont)
        text = "0"
        tw, th = gc.GetTextExtent(text)
        smRad = min(clientWid, clientHt)/2 - th - 5
        path = gc.CreatePath()
        path.MoveToPoint(-smRad, 0)
        path.AddLineToPoint(smRad, 0)
        gc.SetPen(gridPen)
        gc.StrokePath(path)
        gc.DrawText(text, -smRad-tw-2, -th/2)

        R0 = 50.
        for R in (0.2, 0.5, 1., 2., 4.):
            # resistance arcs
            s11r = (R-1) / (R+1)
            xcent = (s11r + 1) / 2
            radius = 1 - xcent
            path = gc.CreatePath()
            path.MoveToPoint(smRad, 0)
            path.AddCircle(xcent*smRad, 0, radius*smRad)
            gc.StrokePath(path)
            text = si(R*R0)
            tw, th = gc.GetTextExtent(text)
            tx = s11r*smRad+tw/2-2
            ty = -th-1
            path = gc.CreatePath()
            path.AddRectangle(tx, ty, tw, th)
            gc.SetBrush(backBrush)
            gc.FillPath(path)
            gc.DrawText(text, tx, ty)

            # reactance arcs
            s11 = (1j*R-1) / (1j*R+1)
            theta = angle(s11)
            ycent = tan(theta/2)
            theta2 = atan2(s11.imag-ycent, s11.real-1)
            ycent *= smRad
            path = gc.CreatePath()
            path.MoveToPoint(smRad, 0)
            path.AddArc((smRad, -ycent), ycent, pi/2, -theta2)
            path.MoveToPoint(s11.real*smRad, s11.imag*smRad)
            path.AddArc((smRad,  ycent), ycent, theta2, -pi/2)
            gc.StrokePath(path)
            txrad = smRad + sqrt(tw**2 + th**2)/2 + 1
            gc.DrawText(text, s11.real*txrad-tw/2, -s11.imag*txrad-th/2)
            text = si(-R*R0)
            tw, th = gc.GetTextExtent(text)
            gc.DrawText(text, s11.real*txrad-tw/2,  s11.imag*txrad-th/2)

        # unity circle
        path = gc.CreatePath()
        path.AddCircle(0, 0, smRad)
        gc.SetPen(wx.Pen(gridColor, 2, wx.SOLID))
        gc.StrokePath(path)

        # ------ TRACES ------

        f0 = specP.h0   # start freq (MHz)
        f1 = specP.h1   # stop freq (MHz)
        if p.isLogF:
            f0 = log10(f0)
            f1 = log10(f1)

        # draw each trace in a different color
        for name, tr in sorted(specP.traces.iteritems(), \
                     key=(lambda (k,v): -v.iScale)):
            if not tr.displayed or tr.units != "dB":
                continue
            fullLen = len(tr.S11)
            if specP.eraseOldTrace:
                nv = fullLen
            else:
                nv = min(specP.cursorStep+1, fullLen)
            f = (tr.Fmhz, tr.LFmhz)[p.isLogF][:nv]
            # jMin, jMax are limits of indices of Fmhz within the
            # displayed region
            trf0 = f[0]
            if len(f) > 1:
                trdf = f[1] - trf0
            else:
                trdf = 0
            if trdf == 0:
                jMin = 0
                jMax = nv-1
            else:
                jMin = max(min((int((f0 - trf0) / trdf) - 2), nv-2), 0)
                jMax = max(min((int((f1 - trf0) / trdf) + 2), nv-1), 1)
            ##print ("j=", jMin, jMax, "f0=", f0, "trf0=", trf0, "trdf=", trdf

            # S11.real,S11.imag: coords of points to plot
            S11 = nan_to_num(tr.S11[jMin:jMax+1])
            # x,y: window coords of those points
            x =  S11.real * smRad
            y = -S11.imag * smRad

            ##if specP.eraseOldTrace and trdf > 0:
            ##    # remove main line segs at the cursor to form a moving gap
            ##    eraseWidth = int(10/(trdf*dx)) + 1
            eraseWidth = 0 # EON Jan 29, 2014
            path = gc.CreatePath()
            path.MoveToPoint(x[0], y[0])
            for i in range(1, len(x)):
                if 0 and i > specP.cursorStep and \
                        i <= specP.cursorStep+eraseWidth:
                    path.MoveToPoint(x[i], y[i])
                else:
                    path.AddLineToPoint(x[i], y[i])
            color = vColors[tr.iColor]
            gc.SetPen(wx.Pen(color, tr.dotSize, wx.SOLID))
            gc.StrokePath(path)

            # draw dots, either on all points if few, or just the startpoint
            n = len(x)
            if specP._haveDrawnGrid and specP.graphWid/fullLen > 20:
                step = 1
            else:
                step = n
            dsz = specP.dotSize
            path = gc.CreatePath()
            for i in range(0, n, step):
                path.MoveToPoint(x[i], y[i])
                path.AddLineToPoint(x[i], y[i])
            gc.SetPen(wx.Pen(color, dsz, wx.SOLID))
            gc.StrokePath(path)

        # ------ MARKERS ------

        gc.SetFont(foreFont)

        for name, m in specP.markers.iteritems():
            tr = specP.traces.get(m.traceName)
            if tr:
                # marker frequency determines array index j
                nv = len(tr.Fmhz)
                f = (tr.Fmhz, tr.LFmhz)[p.isLogF][:nv]
                trf0 = f[0]
                if len(f) > 1:
                    trdf = f[1] - trf0
                else:
                    trdf = 0
                if trdf == 0:
                    j = 0
                else:
                    mf = (m.mhz, log10(max(m.mhz, 1e-6)))[p.isLogF]
                    j = max(min((mf - trf0) / trdf, nv), 0)

                # S11.real,S11.imag: coords of points to plot
                js = arange(len(tr.S11))
                x =  smRad * interp(j, js, tr.S11.real)
                y = -smRad * interp(j, js, tr.S11.imag)

                if m.name == "X":
                    # draw cursor, if present
                    path = gc.CreatePath()
                    path.AddRectangle(x-2.5, y-2.5, 5, 5)
                    gc.SetPen(forePen)
                    gc.StrokePath(path)
                else:
                    # draw triangle at marker position
                    q = 6
                    isPos = m.name != "P-"
                    ydir = 2*isPos - 1
                    yq =  ydir * q
                    path = gc.CreatePath()
                    path.MoveToPoint(x, y)
                    path.AddLineToPoint(x-q, y-yq)
                    path.AddLineToPoint(x+q, y-yq)
                    path.AddLineToPoint(x, y)
                    gc.SetPen(forePen)
                    gc.StrokePath(path)
                    (tw, th) = gc.GetTextExtent(m.name)
                    tx = x-tw/2
                    ty = y-yq - (ydir+1)*(th+2)/2 + 1
                    path = gc.CreatePath()
                    path.AddRectangle(tx, ty, tw, th)
                    gc.SetBrush(backBrush)
                    gc.FillPath(path)
                    gc.DrawText(m.name, tx, ty)


#==============================================================================
# A Smith chart window for Reflectance mode.

class SmithDialog(wx.Dialog):
    def __init__(self, frame):
        self.frame = frame
        specP = frame.specP
        self.prefs = p = frame.prefs
        framePos = frame.GetPosition()
        frameSize = frame.GetSize()
        self.pos = p.get("smithWinPos", (framePos.x + frameSize.x - 400,
                                framePos.y))
        self.size = p.get("smithWinSize", (400, 500))
        wx.Dialog.__init__(self, frame, -1, "Smith Chart", self.pos,
                        self.size, wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER)
        self.SetBackgroundColour(p.theme.backColor)
        sizer = wx.GridBagSizer(5, 5)
        c = wx.ALIGN_CENTER
        chb = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM

        sizer.AddGrowableCol(0)
        sizer.AddGrowableRow(1)
        sizerV1 = wx.BoxSizer(wx.VERTICAL)
        st = wx.StaticText(self, -1, specP.title)
        ##st.SetBackgroundColour("YELLOW")
        sizerV1.Add(st, 0, c)
        self.chart = chart = SmithPanel(self, frame)
        sizer.Add(chart, (1, 0), flag=c|wx.EXPAND)
        sizer.Add(sizerV1, (0, 0), flag=c|wx.EXPAND|wx.ALL, border=10)
        self.msgText = st = wx.StaticText(self, -1, "")
        ##st.SetBackgroundColour("GREEN")
        sizer.Add(st, (2, 0), flag=c|wx.EXPAND|wx.ALL, border=10)

        self.SetSizer(sizer)
        self.Show()

    def Close(self, event=None):
        self.prefs.smithWinPos = self.GetPosition().Get()
        self.prefs.smithWinSize = self.GetSize().Get()
        self.Destroy()

#==============================================================================
# The Special Tests dialog box # JGH Substantial mod on 1/25/14

class DDSTests(wx.Dialog):   # EON 12/22/13

    def __init__(self, frame):
        self.frame = frame
        self.prefs = p = frame.prefs
        self.mode = None
        framePos = frame.GetPosition()
        pos = p.get("DDStestsWinPos", (framePos.x + 100, framePos.y + 100))
        wx.Dialog.__init__(self, frame, -1, "DDS Tests", pos,
                           wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        tsz = (100, -1)

        c = wx.ALIGN_CENTER
        sizerV = wx.BoxSizer(wx.VERTICAL)
        st = wx.StaticText(self, -1, \
        "The 'Set DDS1' box (#special.dds1out) is populated with the value of " \
        "the variable DDS1array(thisstep,46). The 'with DDS Clock at' box " \
        "(#special.masclkf) is populated with the value of the variable, masterclock. " \
        "The 'Set DDS3' box (#special.dds3out) is populated with the value of " \
        "the variable, DDS3array(thisstep,46).\n" \
        "The DDS clock is 'masterclock' and will always be the 64.xyzabc MHz that " \
        "was inserted in the Hardware Configuration Manager Window.\n" \
        "The DDS1 and DDS3 frequencies will depend on where the sweep was halted " \
        "before entering the DDS Tests Window. \n" \
        "All 3 boxes can be manually changed by highlighting and typing in a new value. " \
        "Clicking the Set DDS1 button will update the DDS1 box AND the masterclock. " \
        "Clicking the Set DDS3 button will update the DDS3 box AND the masterclock.\n" \
        "NOTE: The 'with DDS Clock at' box currently displays only 5 digits to " \
        "the right of the decimal. It really needs to be at least 6 for 1 Hz resolution. ")

        st.Wrap(600)
        sizerV.Add(st, 0, c|wx.ALL, 10)

        sizerGB = wx.GridBagSizer(5,5)

        # MSA Mode selection
        btn = wx.Button(self, 0, "Set DDS1")
        btn.Bind(wx.EVT_BUTTON, self.setDDS1)
        sizerGB.Add(btn,(0,0), flag=c)
        tc = wx.TextCtrl(self, 0, str(LO1.appxdds), size=tsz)
        self.dds1FreqBox = tc
        sizerGB.Add(tc,(0,1), flag=c)

        text = wx.StaticText(self, 0, " with DDS Clock at: ")
        sizerGB.Add(text,(1,0), flag=c)
        tc = wx.TextCtrl(self, 0, str(msa.masterclock), size=tsz)
        self.masterclockBox = tc;
        sizerGB.Add(tc,(1,1), flag=c)

        btn = wx.Button(self, 0, "Set DDS3")
        btn.Bind(wx.EVT_BUTTON, self.setDDS3)
        sizerGB.Add(btn,(2,0), flag=c)
        tc = wx.TextCtrl(self, 0, str(LO3.appxdds), size=tsz)
        self.dds3FreqBox = tc
        sizerGB.Add(tc,(2,1), flag=c)

        self.dds3TrackChk = chk = wx.CheckBox(self, -1, "DDS 3 Track")
        chk.SetValue(p.get("dds3Track",False))
        chk.Bind(wx.EVT_CHECKBOX, self.DDS3Track)
        sizerGB.Add(chk,(3,0), flag=c)

        self.dds1SweepChk = chk = wx.CheckBox(self, -1, "DDS 1 Sweep")
        chk.SetValue(p.get("dds1Sweep",False))
        chk.Bind(wx.EVT_CHECKBOX, self.DDS1Sweep)
        sizerGB.Add(chk,(3,1), flag=c)

        # VNA Mode selection

        if msa.mode == msa.MODE_SATG or msa.mode == msa.MODE_SA:
            pass
        else:
            btn = wx.Button(self, 0, "Change PDM")
            btn.Bind(wx.EVT_BUTTON, self.ChangePDM)
            sizerGB.Add(btn,(5,0), flag=c)

        sizerV.Add(sizerGB, 0, c|wx.ALL, 10)
        self.SetSizer(sizerV)
        sizerV.Fit(self)

        self.Bind(wx.EVT_CLOSE, self.Close)

    def DDS3Track(self, event=None):
        self.prefs.dds3Track = self.dds3TrackChk.GetValue()

    def DDS1Sweep(self, event=None):
        self.prefs.dds1Sweep = self.dds1SweepChk.GetValue()

    def ChangePDM(self, event):  #TODO
        pass

    # JGH deleted 2/1/14 (No help needed)
##    def DDSTestsHelp(self, event):


    def Close(self, event=None):
        p = self.prefs
        p.DDStestsWinPos = self.GetPosition().Get()
##        btn = wx.Button(self, -1, "CLOSE", (5, 435), (140,-1))
##        btn.Bind(wx.EVT_BUTTON, self.CloseSpecial)
##        sizerGB.Add(btn,(6,1), flag=c)
        self.Destroy()

#--------------------------------------------------------------------------
    # Set DDS to entered frequency

    def setDDS1(self, event):
        freq = float(self.dds1FreqBox.GetValue())
        print (">>>13796<<< freq: ", freq)
        self.setDDS(freq, cb.P1_DDS1DataBit, cb.P2_fqud1)

    def setDDS3(self, event):
        freq = float(self.dds3FreqBox.GetValue())
        self.setDDS(freq, cb.P1_DDS3DataBit, cb.P2_fqud3)

    def setDDS(self, freq, P1_DDSDataBit, P2_fqud):
##        ddsclock = float(self.masterclockBox.GetValue()) # JGH 2/2/14 3 lines
        print (">>>13805<<< msa.masterclock: ", msa.masterclock)
        base = int(round(divSafe(freq * (1<<32), msa.masterclock)))
        print (">>>13807<<< base: ", base)
        DDSbits = base << P1_DDSDataBit
        print (">>>13809<<< DDSbits: ", DDSbits)
        byteList = []
        P1_DDSData = 1 << P1_DDSDataBit
        print (">>>13812<<< P1_DDSData: ", P1_DDSData)
        for i in range(40):
            a = (DDSbits & P1_DDSData)
            byteList.append(a)
            DDSbits >>= 1;
        cb.SendDevBytes(byteList, cb.P1_Clk)
        cb.SetP(1, 0)
        cb.SetP(2, P2_fqud)
        cb.SetP(2, 0)
        cb.Flush()
        cb.setIdle()

#==============================================================================
# The Control Board Tests modeless dialog window.

class CtlBrdTests(wx.Dialog):
    def __init__(self, frame):
        self.frame = frame
        self.mode = None
        self.modeCtrls = []
        self.prefs = p = frame.prefs
        framePos = frame.GetPosition() # JGH (framePos not used)
        pos = p.get("ctlBrdWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, "Control Board Tests", pos,
                           wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        c = wx.ALIGN_CENTER
        lcv = wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL
        ctlPins = (("17 Sel(L1)", 1), ("16 Init(L2)", 2),
                   ("14 Auto(L3)", 4), ("1 Strobe(L4)", 8))
        dataPins = (("2 D0", 0x01), ("3 D1", 0x02),
                    ("4 D2", 0x04), ("5 D3", 0x08),
                    ("6 D4", 0x10), ("7 D5", 0x20),
                    ("8 D6", 0x40), ("9 D7", 0x80))
        inputPins = (("11 Wait", 0x10), ("10 Ack", 0x08), ("12 PE", 0x04),
                     ("13 Select", 0x02), ("15 Error", 0x01))

        sizerH = wx.BoxSizer(wx.HORIZONTAL)

        sizerGB = wx.GridBagSizer(5,5)
        self.ctlByte = 0
        i = 0;
        for (label, mask) in ctlPins:
            btn = TestBtn(self, mask, False)
            sizerGB.Add(btn, (i, 0), flag=c)
            text = wx.StaticText(self, 0, "Pin " + label)
            sizerGB.Add(text, (i, 1), flag=lcv)
            i += 1

        self.dataByte = 0
        for (label, mask) in dataPins:
            btn = TestBtn(self, mask, True)
            sizerGB.Add(btn, (i, 0), flag=c)
            text = wx.StaticText(self, 0, "Pin " + label)
            sizerGB.Add(text, (i, 1), flag=lcv)
            i += 1
        sizerH.Add(sizerGB, 0, c|wx.ALL, 10)

        sizerGB = wx.GridBagSizer(5,5)
        btn = wx.Button(self, 0, "Capture Status")
        btn.Bind(wx.EVT_BUTTON, self.readStatus)
        sizerGB.Add(btn, (0,0), flag=c, span=(1,2))
        i = 1;
        self.inputData = []
        ts = wx.BORDER_SIMPLE|wx.ST_NO_AUTORESIZE|wx.ALIGN_CENTRE
        for (label, mask) in inputPins:
            text = wx.StaticText(self, 0, " ", size=(20,20), style=ts)
            self.inputData.append(text)
            sizerGB.Add(text, (i, 0), flag=c)
            text = wx.StaticText(self, 0, "Pin " + label)
            sizerGB.Add(text, (i, 1), flag=lcv)
            i += 1
        sizerH.Add(sizerGB, 0, wx.ALIGN_TOP|wx.ALL, 10)
        self.inputData.reverse()

        self.SetSizer(sizerH)
        sizerH.Fit(self)
        self.Bind(wx.EVT_CLOSE, self.Close)

    def Close(self, event=None):
        p = self.prefs
        p.ctlBrdWinPos = self.GetPosition().Get()
        self.Destroy()

    def readStatus(self,event):
        inp = 0x14
        for text in self.inputData:
            val = ("0","1")[inp & 1]
            text.SetLabel(val)
            inp >>= 1

class TestBtn(wx.Button):
    def __init__(self, parent, mask, data):
        self.mask = mask
        self.data = data
        self.parent = parent
        wx.Button.__init__(self,parent, 0, "0", size=(30,20))
        self.Bind(wx.EVT_BUTTON, self.toggleBit)

    def toggleBit(self, event):
        val = self.GetLabel()
        if val == "0":
            self.SetLabel("1")
            self.updateBit(True)
        else:
            self.SetLabel("0")
            self.updateBit(False)

    def updateBit(self,state):
        if self.data:
            if state:
                self.parent.dataByte |= self.mask
            else:
                self.parent.dataByte &= ~self.mask
            cb.OutPort(self.parent.dataByte)
        else:
            if state:
                self.parent.ctlByte |= self.mask
            else:
                self.parent.ctlByte &= ~self.mask
            cb.OutControl(self.parent.ctlByte ^ cb.contclear)
        cb.Flush()


#==============================================================================
# The main MSA frame showing the spectrum.

class MSASpectrumFrame(wx.Frame):
    if debug:
        print (">>>>13940<<< Entering MSASpectrumFrame")
    def __init__(self, parent, title):
        global msa, fontSize

        # read preferences file, if any
        self.refreshing = False
        self.appName = title
        self.rootName = title.lower()
        self.prefs = None
        self.LoadPrefs()
        self.consoleStderr = None

        # get preference values, using defaults if new
        p = self.prefs
        fStart = p.get("fStart", 0.)
        fStop = p.get("fStop", 1000.)
        nSteps = p.get("nSteps", 400)
        self.markMHz = 0.

        wx.Frame.__init__(self, parent, -1, title,
                            size=p.get("frameSize", (800, 900)))
        self.Bind(wx.EVT_SIZE, self.OnSizeChanged)
        self.Bind(wx.EVT_CLOSE, self.OnExit)
        self.SetDoubleBuffered(True)

        # calibrate font point size for this system
        font = wx.Font(fontSize, wx.SWISS, wx.NORMAL, wx.NORMAL)
        font.SetPixelSize((200, 200))
        pointSize200px = font.GetPointSize()
        fontSize = fontSize * pointSize200px / 170
        if 0:
            # test it
            font10 = wx.Font(fontSize, wx.SWISS, wx.NORMAL, wx.NORMAL)
            ps10 = font10.GetPointSize()
            font27 = wx.Font(fontSize*2.7, wx.SWISS, wx.NORMAL, wx.NORMAL)
            ps27 = font27.GetPointSize()
            print ("10-point pointsize=", ps10, "27-point pointsize=", ps27)

        # set up menu bar
        self.menubar = wx.MenuBar()
        self.fileMenu = self.CreateMenu("&File", (
            ("Save Image...\tSHIFT-CTRL-S", "SaveImage", -1),
            ("Load Prefs",              "LoadPrefs", -1),
            ("Save Prefs",              "SavePrefs", -1),
            ("Load Data...",            "LoadData", -1),
            ("Save Data...",            "SaveData", -1),
            ("Load/Save Test Setup...\tCTRL-S", "LoadSaveTestSetup", -1),
            ("-",                       None, -1),
            ("Close\tCTRL-W",           "OnClose", wx.ID_CLOSE),
            ("Quit\tCTRL-Q",            "OnExit", wx.ID_EXIT),
        ))
        self.setupMenu = self.CreateMenu("&Setup", (
            ("Hardware Config Manager...", "ManageHWConfig", -1),
            ("Initial Cal Manager...",  "ManageInitCal", -1),
            ("PDM Calibration...",      "PDMCal", -1),
            ("DDS Tests. . .",          "ddsTests", -1),
            ("Cavity Filter Test ...",  "CavFiltTest", -1), # JGH 1/25/14
            ("Control Board Tests...",  "CtlBrdTests",-1),
            ("-",                       None, -1),
            ("Synthetic DUT...\tCTRL-D", "SynDUT", -1)
        ))
        self.optionsMenu = self.CreateMenu("&Sweep", [
            ("Sweep Parameters\tCTRL-F", "SetSweep", -1),
            ("Show Variables\tCTRL-I",  "ShowVars", -1),
            ("-",                       None, -1),
            ("Markers Indpendent",      "SetMarkers_Indep", -2),
            ("Markers P+,P- bounded by L,R", "SetMarkers_PbyLR", -2),
            ("Markers L,R bounded by P+", "SetMarkers_LRbyPp", -2),
            ("Markers L,R bounded by P-", "SetMarkers_LRbyPm", -2),
            ("-",                       None, -1)] +
            [("Set Reference Line %d...\tCTRL-%d" % (i, i), "SetRef", 600+i)
                for i in range(1, 10)]
        )
        self.dataMenu = self.CreateMenu("&Data", (
            ("Save Graph Data",         "SaveGraphData", -1),
            ("Save Input Data",         "SaveInputData", -1),
            ("Save Intstalled Line Cal", "SaveInstalledLineCal", -1),
            ("-",                       None, -1),
            ("Dump Events",             "DumpEvents", -1),
            ("Save Debug Events",       "WriteEvents", -1),
        ))
        self.functionsMenu = self.CreateMenu("&Functions", (
            ("One Scan\tCTRL-E",        "DoExactlyOneScan", -1),
            ("One Step\tCTRL-T",        "DoOneStep", -1),
            ("Continue/Halt\tCTRL-R",   "OnContinueOrHalt", -1),
            ("-",                       None, -1),
            ("Filter Analysis...\tSHIFT-CTRL-F",  "AnalyzeFilter", -1),
            ("Component Meter...\tSHIFT-CTRL-C",  "ComponentMeter", -1),
            ("RLC Analysis...\tSHIFT-CTRL-R",     "AnalyzeRLC", -1),
            ("Coax Parameters...\tSHIFT-CTRL-X",  "CoaxParms", -1), # EON Jan 22, 2014
            ("Crystal Analysis...\tSHIFT-CTRL-K", "AnalyzeCrystal", -1),
            ("Step Attenuator Series...\tSHIFT-CTRL-S", "StepAttenuator", -1),
        ))
        self.operatingCalMenu = self.CreateMenu("&Operating Cal", (
            ("Perform Cal...\tCTRL-B",   "PerformCal", -1),
            ("Perform Update...\tCTRL-U","PerformCalUpd", -1), # EON Jan 10 2014
            ("-",                       None, -1),
            ("Reference To Band",       "SetCalRef_Band", -2),
            ("Reference To Baseline",   "SetCalRef_Base", -2),
            ("No Reference",            "SetCalRef_None", -2),
        ))
        self.modeMenu = self.CreateMenu("&Mode", (
            ("Spectrum Analyzer",       "SetMode_SA", -2),
            ("Spectrum Analyzer with TG", "SetMode_SATG", -2),
            ("VNA Transmission",        "SetMode_VNATran", -2),
            ("VNA Reflection",          "SetMode_VNARefl", -2),
        ))
        self.helpMenu = self.CreateMenu("&Help", (
            ("About",                   "OnAbout", wx.ID_ABOUT),
        ))
        self.SetMenuBar(self.menubar)
        self.closeMenuItem = self.fileMenu.FindItemById(wx.ID_CLOSE)

        self.logSplitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE)
        self.mainP = mainP = wx.Panel(self.logSplitter, style=wx.BORDER_SUNKEN)

        # define controls and panels in main spectrum panel
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.specP = specP = GraphPanel(mainP, self)
        sizer.Add(self.specP, 1, wx.EXPAND)
        botSizer = wx.BoxSizer(wx.HORIZONTAL)

        mark1Sizer = wx.BoxSizer(wx.VERTICAL)
        mark1Sizer.Add(wx.StaticText(mainP, -1, "Marker"), 0, wx.CENTER)
        self.markerNames = samples = ["None"] + \
                [str(i) for i in range(1, 7)] + ["L", "R", "P+", "P-"]
        cbox = wx.ComboBox(mainP, -1, "None", (0, 0), (80, -1), samples)
        self.markerCB = cbox
        mainP.Bind(wx.EVT_COMBOBOX, self.OnSelectMark, cbox)
        mark1Sizer.Add(cbox, 0, wx.ALL, 2)
        botSizer.Add(mark1Sizer, 0, wx.ALIGN_BOTTOM)

        mark2Sizer = wx.BoxSizer(wx.VERTICAL)
        btn = wx.Button(mainP, -1, "Delete", size=(90, -1))
        mainP.Bind(wx.EVT_BUTTON, self.OnDeleteMark, btn)
        mark2Sizer.Add(btn, 0, wx.ALL, 2)
        btn = wx.Button(mainP, -1, "Clear Marks", size=(90, -1))
        mainP.Bind(wx.EVT_BUTTON, self.ClearMarks, btn)
        mark2Sizer.Add(btn, 0, wx.ALL, 2)
        botSizer.Add(mark2Sizer, 0, wx.ALIGN_BOTTOM)

        mark3Sizer = wx.BoxSizer(wx.VERTICAL)
        mark3TSizer = wx.BoxSizer(wx.HORIZONTAL)
        btn = wx.Button(mainP, -1, "-", size=(25, -1))
        mainP.Bind(wx.EVT_BUTTON, self.OnDecMarkMHz, btn)
        mark3TSizer.Add(btn, 0, wx.ALL, 2)
        mark3TSizer.AddSpacer((0, 0), 1, wx.EXPAND)
        mark3TSizer.Add(wx.StaticText(mainP, -1, "MHz"), 0,
                    wx.ALIGN_CENTER_HORIZONTAL|wx.EXPAND|wx.ALL, 2)
        mark3TSizer.AddSpacer((0, 0), 1, wx.EXPAND)
        mark3Sizer.Add(mark3TSizer, 0, wx.EXPAND)
        self.mhzT = wx.TextCtrl(mainP, -1, str(self.markMHz), size=(100, -1))
        mark3Sizer.Add(self.mhzT, 0, wx.ALL, 2)
        btn = wx.Button(mainP, -1, "+", size=(25, -1))
        mainP.Bind(wx.EVT_BUTTON, self.OnIncMarkMHz, btn)
        mark3TSizer.Add(btn, 0, wx.ALL, 2)
        botSizer.Add(mark3Sizer, 0, wx.ALIGN_BOTTOM)
        btn = wx.Button(mainP, -1, "Enter", size=(50, -1))
        mainP.Bind(wx.EVT_BUTTON, self.OnEnterMark, btn)
        botSizer.Add(btn, 0, wx.ALIGN_BOTTOM|wx.ALL, 2)

        mark4Sizer = wx.BoxSizer(wx.VERTICAL)
        btn = wx.Button(mainP, -1, "Expand LR", size=(100, -1))
        mainP.Bind(wx.EVT_BUTTON, self.ExpandLR, btn)
        mark4Sizer.Add(btn, 0, wx.ALL, 2)
        btn = wx.Button(mainP, -1, "Mark->Cent", size=(100, -1))
        mainP.Bind(wx.EVT_BUTTON, self.OnMarkCent, btn)
        mark4Sizer.Add(btn, 0, wx.ALL, 2)
        botSizer.Add(mark4Sizer, 0, wx.ALIGN_BOTTOM)

        botSizer.AddSpacer((0, 0), 1, wx.EXPAND)
        stepSizer = wx.BoxSizer(wx.VERTICAL)
        btn = wx.Button(mainP, -1, "One Step", size=(90, -1))
        mainP.Bind(wx.EVT_BUTTON, self.DoOneStep, btn)
        stepSizer.Add(btn, 0, wx.ALL, 2)
        self.oneScanBtn = wx.Button(mainP, -1, "One Scan", size=(90, -1))
        mainP.Bind(wx.EVT_BUTTON, self.OnOneScanOrHaltAtEnd, self.oneScanBtn)
        stepSizer.Add(self.oneScanBtn, 0, wx.ALL, 2)
        ##self.oneScanBtn.SetToolTip(wx.ToolTip("Start one spectrum scan"))
        botSizer.Add(stepSizer, 0, wx.ALIGN_BOTTOM)

        goSizer = wx.BoxSizer(wx.VERTICAL)
        self.contBtn = wx.Button(mainP, -1, "Continue", size=(90, -1))
        mainP.Bind(wx.EVT_BUTTON, self.OnContinueOrHalt, self.contBtn)
        goSizer.Add(self.contBtn, 0, wx.ALL, 2)
        self.restartBtn = wx.Button(mainP, -1, "Restart", size=(90, -1))
        mainP.Bind(wx.EVT_BUTTON, self.OnRestartOrHalt, self.restartBtn)
        goSizer.Add(self.restartBtn, 0, wx.ALL, 2)
        botSizer.Add(goSizer, 0, wx.ALIGN_BOTTOM)

        sizer.Add(botSizer, 0, wx.EXPAND)
        mainP.SetSizer(sizer)

        # create a log text panel below and set it to log all output
        # (can't use LogTextCtrl-- it's broken)
        self.logPanel = logP = wx.TextCtrl(self.logSplitter,
                                    style=wx.TE_MULTILINE|wx.TE_READONLY)
        self.logSplitter.SplitHorizontally(mainP, logP, p.get("logSplit", 650))
        self.logSplitter.name = "log"
        self.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGED, self.OnSashChanged)

        logP.SetFont(wx.Font(fontSize, wx.MODERN, wx.NORMAL, wx.NORMAL))
        # redirect all output to a log file (disable this to see early errors)
        if 1:
            self.consoleStderr = sys.stderr
            logName = os.path.join(appdir, self.rootName)
            sys.stdout = Logger(logName, logP, self)
            sys.stderr = Logger(logName, logP, self)
        print (title, version, "log -- started", time.ctime())
        print ("Python", sys.version)
        print ("wx", wx.version(), "numpy", numpy.version.version)

        # initialize back end
        msa = MSA(self) # JGH MSA object is created here 1/25/14

        p.get("rbw", 150)
        p.get("wait", 10)
        p.get("sigGenFreq", 10.)
        p.get("tgOffset", 0.)
        p.get("planeExt", 3*[0.])
        if type(p.planeExt) != type([]) or len(p.planeExt) != 3:
            p.planeExt = 3*[0.]
        print ("planeExt=", p.planeExt)
        p.get("normRev", 0)
        p.get("isLogF", 0)
        p.get("continuous", False)
        p.get("sweepDir", 0)
        p.get("markerMode", Marker.MODE_INDEP)
        p.get("atten5", False)
        p.get("stepAttenDB", 0)
        p.get("switchPulse", 0) # JGH added Oct23
        if debug:
            print (">>>14172<<< MSASpectrumFrame: Back End initialized")

        # initialize spectrum graph
        va0 = p.get("va0", -120.)
        va1 = p.get("va1", 0.)
        vb0 = p.get("vb0", -180.)
        vb1 = p.get("vb1", 180.)
        specP.vScales = vScales = []
        vai = p.get("vaTypeIndex", 1)
        vbi = p.get("vbTypeIndex", 2)
        vScales.append(VScale(vai, msa.mode, va1, va0, "dB"))
        vScales.append(VScale(vbi, msa.mode, vb1, vb0, "Deg"))
        self.refs = {}
        self.lastDoneDrawTime = 0
        self.btnScanMode = False    # True when buttons in scanning mode
        self.task = None
        self.smithDlg = None

        self.spectrum = None
        self.sweepDlg = None
        self.filterAnDlg = None
        self.compDlg = None
        self.tranRLCDlg = None
        self.coaxDlg = None # EON Jan 29, 2014
        self.crystalDlg = None
        self.stepDlg = None
        self.varDlg = None
        self.ReadCalPath()
        self.ReadCalFreq()
        self.Show(True)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer)
        self.Bind(EVT_UPDATE_GRAPH, self.OnTimer)

        # Initialize cavity filter test status # JGH 1/26/14
        self.cftest = 0

        # restore markers from preferences
        for attr, value in p.__dict__.items():
            if len(attr) > 9 and attr[:8] == "markers_":
                mm, mName, mAttr = string.split(attr, "_")
                mName = re.sub("p", "+", re.sub("m", "-", mName))
                m = specP.markers.get(mName)
                if not m:
                    specP.markers[mName] = m = Marker(mName, "", 0)
                setattr(m, mAttr, value)
                delattr(p, attr)

        # put a checkmark by the current mode in the Mode menu
        for i, item in enumerate(self.modeMenu.GetMenuItems()):
            item.Check(i == msa.mode)

        self.RefreshAllParms()

        # build an operating calibration file path, creating the dirs if needed
        cdir = os.path.join(appdir, "MSA_Info", "OperatingCal")
        self.baseCalFileDir = cdir
        if not os.path.exists(cdir):
            os.makedirs(cdir)
        # Start EON Jan 28, 2014
        self.bandCalFileName = os.path.join(cdir, "BandLineCal.s1p")
        self.baseCalFileName = os.path.join(cdir, "BaseLineCal.s1p")
        # read any operating calibration files
#        msa.bandCal = self.LoadCal(self.bandCalFileName)
#        msa.baseCal = self.LoadCal(self.baseCalFileName)
        msa.bandCal = None
        msa.baseCal = None
        # Start EON Jan 28, 2014

        # make one scan to generate a graph
        if debug:
            print ("")
            print (">>>14243<<< MSASpectrumFrame: Ready to perform StartScan")
            print ("")
        self.StartScan(True)
        # EON Following 3 lines added by Eric Nystrom
        if (p.get("dds3Track",False) or p.get("dds1Sweep",False)):
            dlg = DDSTests(self)
            dlg.Show()
        # Start EON Jan 22, 2014
        self.funcModeList = [0] * 4
        self.funcModeList[MSA.MODE_SA] = ["filter","step"]
        self.funcModeList[MSA.MODE_SATG] = ["filter","step"]
        self.funcModeList[MSA.MODE_VNATran] = ["filter","component","rlc","crystal","group","step"]
        self.funcModeList[MSA.MODE_VNARefl] = ["component","rlc","coax","group","s21","step"]

        self.InitMode(msa.mode)
        # End EON Jan 22, 2014

    #--------------------------------------------------------------------------
    # Create a menu of given items calling given routines.
    # An id == -2 sets item to be in a radio group.

    def CreateMenu(self, name, itemList):
        menu = wx.Menu()
        for itemName, handlerName, idno in itemList:
            if itemName == "-":
                menu.AppendSeparator()
            else:
                if idno == -1:
                    idno = wx.NewId()
                if idno == -2:
                    idno = wx.NewId()
                    item = menu.Append(idno, itemName, itemName, wx.ITEM_RADIO)
                else:
                    item = menu.Append(idno, itemName)
                if hasattr(self, handlerName):
                    self.Connect(idno, -1, wx.wxEVT_COMMAND_MENU_SELECTED, \
                                getattr(self, handlerName))
                else:
                    item.Enable(False)
        self.menubar.Append(menu, name)
        return menu

    #--------------------------------------------------------------------------
    # Change button names while scanning.

    def SetBtnsToScan(self, scanning):
        if scanning:
            self.contBtn.SetLabel("Halt")
            self.restartBtn.SetLabel("Halt")
            self.oneScanBtn.SetLabel("Halt at End")
        else:
            self.contBtn.SetLabel("Continue")
            self.restartBtn.SetLabel("Restart")
            self.oneScanBtn.SetLabel("One Scan")
        self.btnScanMode = scanning

    #--------------------------------------------------------------------------
    # Start capturing a spectrum.

    def StartScan(self, haltAtEnd):
        if debug:
            print (">>>14305<<< Starting first scan")
        self.StopScanAndWait()
        ResetEvents()
        LogGUIEvent("StartScan")
        self.spectrum = None
        self.needRestart = False
        if msa.syndut: # JGH 2/8/14 syndutHook5
            if debug:
                print ("GETTING SYNTHETIC DATA")
            msa.syndut.GenSynthInput()
        p = self.prefs
        fStart = p.fStart
        fStop = p.fStop
        title = time.ctime()

        print ("----", title, "fStart=", mhzStr(fStart), "fStop=", \
             mhzStr(fStop), "----")
        wx.Yield()
        needsRefresh = False

        # redraw the grid if needed
        specP = self.specP
        specP.eraseOldTrace = False
        specP.markersActive = False
        if specP.h0 != fStart or specP.h1 != fStop or specP.title != title:
            LogGUIEvent("StartScan new graph range")
            specP._haveDrawnGrid = False
            specP.h0 = fStart
            specP.h1 = fStop
            specP.title = title
            needsRefresh = True

        # set up calibration table to use
        self.spectrum = None
        if not msa.calibrating:
            needsRefresh = self.CalCheck() # EON Jan 29, 2014

        if needsRefresh:
            self.RefreshAllParms()

        # tell MSA hardware backend to start a scan
        msa.Scan(self, p, haltAtEnd)

        LogGUIEvent("StartScan starting timer")
        # start display-update timer, given interval in ms
        self.timer.Start(msPerUpdate)
    #--------------------------------------------------------------------------

    #--------------------------------------------------------------------------
    # Check requested calibration level and set based on calibration present

    def CalCheck(self): # EON Jan 29, 2014
        p = self.prefs
        cal = (None, msa.baseCal, msa.bandCal)[p.calLevel]
        if cal:
            calF = cal.Fmhz
            # Start EON Jan 10 2014
            #calIsLogF = (calF[0] + calF[2])/2 != calF[1]
            calIsLogF = cal.isLogF
            # End EON Jan 10 2014
            ##print ("cal: %.20g %.20g %.20g %.20g" % \
            ##        (calF[0], fStart, calF[-1], fStop))
            ##print ("cal:", calF[0] == fStart, calF[-1] == fStop, \
            ##    cal.nSteps, p.nSteps, calIsLogF, p.isLogF)
            fStart = p.fStart
            fStop = p.fStop
            needsRefresh = False
            if round(calF[0] - fStart, 8) == 0 and \
                    round(calF[-1] - fStop, 8) == 0 and \
                    cal.nSteps == p.nSteps and calIsLogF == p.isLogF:
                # have a matching base or band calibration
                msa.calNeedsInterp = False
                # Start EON Jan 10 2014
                if cal.oslCal:
                    cal.installBandCal()
                # End EON Jan 10 2014
            elif p.calLevel > 0 and msa.baseCal and \
                        fStart >= msa.baseCal.Fmhz[0] and \
                        fStop <= msa.baseCal.Fmhz[-1]:
                # no match, but can use base
                msa.calNeedsInterp = True
                # Start EON Jan 10 2014
                if cal.oslCal:
                    msa.NewScan(p)
                    cal.interpolateCal(msa._freqs)
                # End EON Jan 10 2014
                ##print ("Cal needs interpolation")
                if p.calLevel == 2:
                    self.SetCalLevel(1)
                    needsRefresh = True
            else:
                # no usable calibration at all
                ##print ("No usable calibration")
                if p.calLevel > 0:
                    self.SetCalLevel(0)
                    needsRefresh = True
            return needsRefresh

    #--------------------------------------------------------------------------
    # Stop any scanning and wait for all results to be updated.

    def StopScanAndWait(self):
        self.specP.markersActive = True
        if msa.IsScanning():
            msa.StopScan()
            self.WaitForStop()
        else:
            self.RefreshAllParms()

    #--------------------------------------------------------------------------
    # Wait for end of scan and all results to be updated.

    def WaitForStop(self):
        while msa.IsScanning() or not msa.scanResults.empty():
            wx.Yield()
            time.sleep(0.1)
        self.RefreshAllParms()

    #--------------------------------------------------------------------------
    # "One Step" button pressed.

    def DoOneStep(self, event=None):
        LogGUIEvent("DoOneStep")
        self.StopScanAndWait()
        if not self.needRestart:
            msa.WrapStep()
            msa.CaptureOneStep()
            msa.NextStep()

    #--------------------------------------------------------------------------
    # "One Scan"/"Halt at End" button pressed.

    def OnOneScanOrHaltAtEnd(self, event):
        LogGUIEvent("OnOneScanOrHaltAtEnd: scanning=%d" % msa.IsScanning())
        if msa.IsScanning():
            msa.haltAtEnd = True
        else:
            self.StartScan(True)

    #--------------------------------------------------------------------------
    # Ctrl-E: do exactly one scan.

    def DoExactlyOneScan(self, event=None):
        LogGUIEvent("DoExactlyOneScan: scanning=%d" % msa.IsScanning())
        self.StopScanAndWait()
        self.StartScan(True)

    #--------------------------------------------------------------------------
    # Continue/Halt button pressed.

    def OnContinueOrHalt(self, event):
        LogGUIEvent("OnContinueOrHalt")
        if msa.IsScanning():
            self.StopScanAndWait()
        elif not msa.HaveSpectrum() or self.needRestart:
            self.StartScan(False)
        else:
            msa.WrapStep()
            msa.haltAtEnd = False
            msa.ContinueScan()

    #--------------------------------------------------------------------------
    # Restart/Halt button pressed.

    def OnRestartOrHalt(self, event):
        LogGUIEvent("OnRestartOrHalt: scanning=%d step=%d" % \
            (msa.IsScanning(), msa.GetStep()))
        if msa.IsScanning(): # or self.needRestart:
            self.StopScanAndWait()
        else:
            self.StartScan(False)

    #--------------------------------------------------------------------------
    # Timer tick: update display.

    def OnTimer(self, event):
        specP = self.specP
        assert wx.Thread_IsMain()
        ##LogGUIEvent("OnTimer")

        # draw any new scan data from the back end thread
        if not msa.scanResults.empty():
            spec = self.spectrum
            LogGUIEvent("OnTimer: have updates")
            if spec == None:
                spec = msa.NewSpectrumFromRequest(specP.title)
                self.spectrum = spec

            # add scanned steps to our spectrum, noting if they include
            # the last step
            includesLastStep = False
            while not msa.scanResults.empty():
                includesLastStep |= spec.SetStep(msa.scanResults.get())

            # move the cursor to the last captured step
            specP.cursorStep = spec.step
            # activate markers when at or passing last step
            specP.markersActive = includesLastStep
            if includesLastStep:
                specP.eraseOldTrace = True
                if msa.syndut:    # JGH 2/8/14 syndutHook6
                    msa.syndut.RegenSynthInput()
                if self.smithDlg and slowDisplay:
                    self.smithDlg.Refresh()
            self.DrawTraces()
            LogGUIEvent("OnTimer: all traces drawn, cursorStep=%d" % spec.step)
            if self.varDlg:
                self.varDlg.Refresh()

        # put Scan/Halt/Continue buttons in right mode
        if msa.IsScanning() != self.btnScanMode:
            self.SetBtnsToScan(msa.IsScanning())

        # write out any error messages from the backend
        while not msa.errors.empty():
            sys.stderr.write(msa.errors.get())

        # Component Meter continuous measurements, if active
        if self.task != None:
            self.task.AutoMeasure()

        ##LogGUIEvent("OnTimer: done")

    #--------------------------------------------------------------------------
    # Return the index for color i, adding it to the theme.vColor list if not
    # already there.

    def IndexForColor(self, i):
        p = self.prefs
        vColors = p.theme.vColors
        iNextColor = p.theme.iNextColor
        nColors = len(vColors)
        while len(vColors) <= i:
            vColors.append(vColors[iNextColor % nColors])
            iNextColor += 1
        p.theme.iNextColor = iNextColor
        return i

    #--------------------------------------------------------------------------
    # Copy the current and reference spectrums into the spectrum panel traces
    # and draw them.

    def DrawTraces(self):
        if debug:
            print ("DrawTraces")
        specP = self.specP
        specP.traces = {}
        p = self.prefs
        spec = self.spectrum
        if not spec:
            return
        LogGUIEvent("DrawTraces: %d steps" % len(spec.Sdb))

        # compute derived data used by various data types
        spec.f = f = spec.Fmhz
        nSteps = len(f) - 1 # JGH (unosed var nSteps)
        mode = p.mode
        includePhase = mode >= MSA.MODE_VNATran

        spec.isSeriesFix = p.get("isSeriesFix", False)
        spec.isShuntFix = p.get("isShuntFix", False)

        # set left (0) and right (1) vertical scale variables
        # and create potential traces for each (trva, trvb)
        types = traceTypesLists[mode]
        maxIndex = len(types)-1
        vScales = specP.vScales
        vs0 = vScales[0]
        p.vaTypeIndex = vaTypeIndex = min(vs0.typeIndex, maxIndex)
        p.va1 = vs0.top
        p.va0 = vs0.bot
        vaType = types[vaTypeIndex]
        if spec.vaType != vaType:
            trva = vaType(spec, 0)
            trva.maxHold = vs0.maxHold
            trva.max = False
            if incremental:
                spec.vaType = vaType
                spec.trva = trva
        else:
            trva = spec.trva
        trva.iColor = self.IndexForColor(0)
        vs1 = vScales[1]
        p.vbTypeIndex = vbTypeIndex = min(vs1.typeIndex, maxIndex)
        p.vb1 = vs1.top
        p.vb0 = vs1.bot
        vbType = types[vbTypeIndex]
        if spec.vbType != vbType:
            trvb = vbType(spec, 1)
            trvb.maxHold = vs1.maxHold
            trvb.max = False
            if incremental:
                spec.vbType = vbType
                spec.trvb = trvb
        else:
            trvb = spec.trvb
        trvb.iColor = self.IndexForColor(1)

        # determine Mag and Phase traces, if any
        trM = trP = None
        if vaTypeIndex > 0:
            specP.traces[vaType.name] = trva
            if "dB" in trva.units:
                trM = trva
            if "Deg" in trva.units:
                trP = trva

        if vbTypeIndex > 0:
            specP.traces[vbType.name] = trvb
            if "dB" in trvb.units:
                trM = trvb
            if "Deg" in trvb.units:
                trP = trvb

        # if we have both Mag and Phase traces, point them to each other
        if trM and trP:
            trM.phaseTrace = trP
            trP.magTrace = trM

        # draw any compatible reference traces
        for ri in self.refs.keys():
            ref = self.refs[ri]
            rsp = ref.spectrum
            if rsp.nSteps == spec.nSteps and rsp.Fmhz[0] == spec.Fmhz[0] \
                                         and rsp.Fmhz[-1] == spec.Fmhz[-1]:
                mathMode = ref.mathMode
                if trM and ri == 1 and ref.mathMode > 0:
                    # Ref 1 math applied to Mag, Phase
                    mData = trM.v
                    mRef = rsp.Sdb
                    if mathMode == 1:
                        mMath = mData + mRef
                    elif mathMode == 2:
                        mMath = mData - mRef
                    else:
                        mMath = mRef - mData
                    trM.v = dcopy.copy(mMath)
                    if includePhase and trP:
                        pData = trP.v
                        pRef = rsp.Sdeg
                        if mathMode == 1:
                            pMath = pData + pRef
                        elif mathMode == 2:
                            pMath = pData - pRef
                        else:
                            pMath = pRef - pData
                        trP.v = dcopy.copy(modDegree(pMath))
                else:
                    # Ref trace is displayed
                    refTypeM = ref.vScale.dataType
                    # vScales[] index 0 or 1 based on units (for now)
                    i = trvb.units and trvb.units == refTypeM.units
                    if not i:
                        i = 0
                    name = ref.name
                    refHasPhase = includePhase and refTypeM.units == "dB"
                    if refHasPhase:
                        # create ref's phase trace, with unique names for both
                        # (use continuous phase if that's being displayed)
                        continPhase = trP.units == "CDeg"
                        refTypeP = types[ref.vScale.typeIndex+1+continPhase]
                        refTrP = refTypeP(rsp, 1-i)
                        name = "%s_dB" % name
                        phName = "%s_%s" % (ref.name, trP.name.split("_")[1])
                    # create and assign name to ref's mag trace
                    specP.traces[name] = refTrM = refTypeM(rsp, i)
                    refTrM.name = name
                    refTrM.isMain = False
                    refTrM.iColor = self.IndexForColor(2 + 2*ri)
                    if refHasPhase:
                        # assign name to ref's phase trace
                        specP.traces[phName] = refTrP
                        refTrP.name = phName
                        refTrP.isMain = False
                        refTrP.iColor = self.IndexForColor(refTrM.iColor + 1)

        # enable drawing of spectrum (if not already)
        specP.Enable()

        # also show Smith chart if in reflection mode
        if msa.mode == MSA.MODE_VNARefl:
            if not self.smithDlg:
                self.smithDlg = SmithDialog(self)
            elif not slowDisplay:
                self.smithDlg.Refresh()
        else:
            if self.smithDlg:
                self.smithDlg.Close()
                self.smithDlg = None

    #--------------------------------------------------------------------------
    # Open the Configuration Manager dialog box.

    def ManageHWConfig(self, event=None): # JGH This method heavily modified 1/20/14

        self.StopScanAndWait()
        p = self.prefs
        dlg = ConfigDialog(self)
        if dlg.ShowModal() == wx.ID_OK:

            # JGH modified 2/2/14
            p.PLL1type = dlg.cmPLL1.GetValue()
            p.PLL2type = dlg.cmPLL2.GetValue()
            p.PLL3type = dlg.cmPLL3.GetValue()
            p.PLL1phasepol = int(dlg.cmPOL1.GetValue()[1])  # JGH_001
            p.PLL2phasepol = int(dlg.cmPOL2.GetValue()[1])  # JGH_001
            p.PLL3phasepol = int(dlg.cmPOL3.GetValue()[1])  # JGH_001
##            p.PLL1mode = int(dlg.cmMOD1.GetValue()[0]) # JGH 2/7/14 Fractional mode not used
##            p.PLL3mode = int(dlg.cmMOD3.GetValue()[0]) # JGH 2/7/14 Fractional mode not used
            p.PLL1phasefreq = float(dlg.tcPhF1.GetValue())
            p.PLL2phasefreq = float(dlg.tcPhF2.GetValue())
            p.PLL3phasefreq = float(dlg.tcPhF3.GetValue())

            # JGH added 1/15/14
            gr = dlg.gridRBW
            RBWFilters = []
            for row in range(4):
                RBWfreq = float(gr.GetCellValue(row, 0))
                RBWbw = float(gr.GetCellValue(row,1))
                RBWFilters.append((RBWfreq, RBWbw))
            p.RBWFilters = RBWFilters
            # JGH NOTE: need to account here for existing RBW filters only
            msa.RBWFilters = p.RBWFilters

            gv = dlg.gridVF
            VideoFilters = []
            for row in range(4):
                Label = gv.GetRowLabelValue(row)
                magCap = float(gv.GetCellValue(row,0))
                phaCap = float(gv.GetCellValue(row,1))
                VideoFilters.append({Label:[magCap, phaCap]})
            p.VideoFilters = VideoFilters
            if debug:
                print ("RBWFilters: ", RBWFilters)
                print ("RBWfreq", RBWfreq, "RBWbw", RBWbw)
                print ("RowLabel", Label, "magCap", phaCap, "phaCap", phaCap)
                print ("VideoFilters: ", VideoFilters)

##          magTC = 10 * magCap
            # magTC: mag time constant in ms is based on 10k resistor and cap in uF
##          phaTC = 2.7 * phaCap
            # phaTC: phase time constant in ms is based on 2k7 resistor and cap in uF

            # JGH NOTE: need to account here for existing Video filters only
            msa.VideoFilters = p.VideoFilters

            # Topology

            # ADC type # JGH Needs to implement this
            # TrackGen # JGH Needs to implement this
            # Cont Brd
            p.CBoption = CBopt = dlg.CBoptCM.GetValue()
            if debug:
                print ("CBopt: ", CBopt)
            # JGH should use the CBoption
            if CBopt == "RPI to CB": # JGH RaspberryPi does this
                cb = MSA_RPI()
            elif CBopt == "BBB to CB": # JGH BeagleBone does this
                cb =MSA_BBB()
            elif CBopt == "LPT to CB": # JGH Only Windows does this
                if (isWin == False):
                    text = "You must be running WINDOWS to use this option"
                    dlg.MessageBoxMessage = text
                    diag = wx.MessageDialog(None, text , "Topology: Control Brd", \
                                           wx.ID_OK)
                    retCode = diag.ShowModal()
                    if (retCode == wx.ID_OK):
                        diag.Destroy()
                        return
                # JGH 2/10/14
                if (isWin == True):
                    #elif isWin and winUsesParallelPort:

                    winUsesParallelPort = True
                    # Windows DLL for accessing parallel port
                    from ctypes import windll
                    try:
                        windll.LoadLibrary(os.path.join(resdir, "inpout32.dll"))
                    except WindowsError:
                        # Start up an application just to show error dialog
                        app = wx.App(redirect=False)
                        app.MainLoop()
                        dlg = ScrolledMessageDialog(None,
                                        "\n  inpout32.dll not found", "Error")
                        dlg.ShowModal()
                        sys.exit(-1)
                    cb = MSA_CB_PC()
            elif CBopt == "USB to CB": # JGH Windows, Linux and OSX do this
                cb = MSA_CB_USB()
                if isLinux:
                    import usb
                else:
                    # OSX: tell ctypes that the libusb backend is located in the Frameworks directory
                    fwdir = os.path.normpath(resdir + "/../Frameworks")
                    print ("fwdir :    " + str(fwdir))
                    if os.path.exists(fwdir):
                        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = fwdir
                    import usb
            else:
                pass

            # Auto Switches
            # JGH ends 1/14/14

            self.SwRBW = p.SwRBW
            self.SwVideo = p.SwVideo
            self.SwBand = p.SwBand
            self.SwTR = p.SwTR
            self.SwFR = p.SwFR

            if debug:
                print ("SwRBW = " + str(self.SwRBW))
                print ("SwVideo = " + str(self.SwVideo))
                print ("SwBand = " + str(self.SwBand))
                print ("SwTR = " + str(self.SwTR))
                print ("SwFR = " + str(self.SwFR))

            # JGH end of additions

            p.configWinPos = dlg.GetPosition().Get()
            LO1.appxdds =  p.appxdds1 =  float(dlg.dds1CentFreqBox.GetValue())
            LO1.ddsfilbw = p.dds1filbw = float(dlg.dds1BWBox.GetValue())
            LO3.appxdds =  p.appxdds3 =  float(dlg.dds3CentFreqBox.GetValue())
            LO3.ddsfilbw = p.dds3filbw = float(dlg.dds3BWBox.GetValue())
            msa.masterclock = p.masterclock = float(dlg.mastClkBox.GetValue())
            p.invDeg = float(dlg.InvDegBox.GetValue())

    #--------------------------------------------------------------------------
    # Open the Calibration File Manager dialog box.

    def ManageInitCal(self, event):
        self.StopScanAndWait()
        p = self.prefs
        dlg = CalManDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            if dlg.dirty:
                dlg.SaveIfAllowed(self)
        self.ReadCalPath()
        self.ReadCalFreq()
        p.calManWinPos = dlg.GetPosition().Get()

    #--------------------------------------------------------------------------
    # Open the PDM Calibration dialog box.

    def PDMCal(self, event):
        self.StopScanAndWait()
        p = self.prefs
        dlg = PDMCalDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            p.invDeg = dlg.invDeg
        p.pdmCalWinPos = dlg.GetPosition().Get()

    #--------------------------------------------------------------------------
    # Open the DDS Tests dialog box # Eric Nystrom, new function created 12/15/2013

    def ddsTests(self, event): # Eric Nystrom, new function created 12/15/2013
        self.StopScanAndWait()
        #p = self.prefs        # JGH 2/10/14
        dlg = DDSTests(self)
        dlg.Show()

    #--------------------------------------------------------------------------
    # Open the Control Board Tests dialog box.

    def CtlBrdTests(self, event): # Eric Nystrom, new function created 12/15/2013
        self.StopScanAndWait()
        #p = self.prefs    # JGH 2/10/14
        dlg = CtlBrdTests(self)
        dlg.Show()

    #--------------------------------------------------------------------------
    # Open the Cavity Filter Test dialog box

    def CavFiltTest(self, event): # JGH 1/25/14, new function
        self.StopScanAndWait()
        # p = self.prefs    # JGH 2/10/14
        dlg = CavityFilterTest(self)
        dlg.Show()

#--------------------------------------------------------------------------

    # Handle buttons that manipulate markers.

    def OnIncMarkMHz(self, event):
        self.markMHz += 1.
        self.mhzT.SetValue(str(self.markMHz))

    def OnDecMarkMHz(self, event):
        self.markMHz -= 1.
        self.mhzT.SetValue(str(self.markMHz))

    def OnSelectMark(self, event):
        specP = self.specP
        markName = self.markerCB.GetValue()
        m = specP.markers.get(markName)
        if m:
            self.markMHz = m.mhz
            self.mhzT.SetValue(str(m.mhz))

    def OnEnterMark(self, event):
        self.markMHz = mhz = float(self.mhzT.GetValue())
        specP = self.specP
        markName = self.markerCB.GetValue()
        m = specP.markers.get(markName)
        if m:
            m.mhz = mhz
        else:
            traceName = specP.traces.keys()[0]
            specP.markers[markName] = Marker(markName, traceName, mhz)
        self.specP.FullRefresh()

    def OnDeleteMark(self, event):
        specP = self.specP
        markName = self.markerCB.GetValue()
        m = specP.markers.get(markName)
        if m:
            specP.markers.pop(markName)
            self.specP.FullRefresh()

    def ClearMarks(self, event=None):
        self.specP.markers = {}
        self.specP.FullRefresh()

    def ExpandLR(self, event=None):
        specP = self.specP
        p = self.prefs
        left = specP.markers.get("L")
        right = specP.markers.get("R")
        if left and right:
            p.fStart = left.mhz
            p.fStop = right.mhz
        self.RefreshAllParms()
        self.spectrum = None
        self.StartScan(True)

    def OnMarkCent(self, event):
        p = self.prefs
        fCent, fSpan = StartStopToCentSpan(p.fStart, p.fStop, p.isLogF)
        p.fStart, p.fStop = CentSpanToStartStop(self.markMHz, fSpan, p.isLogF)
        self.RefreshAllParms()
        self.spectrum = None
        self.StartScan(True)

    #--------------------------------------------------------------------------
    # Refresh parameter display in all open windows.

    def RefreshAllParms(self):
        p = self.prefs
        specP = self.specP
        if debug:
            print (">>>14192<<< RefreshAllParms", specP._isReady, self.refreshing)

        # checkmark the current marker menu item in the Options menu
        items = self.optionsMenu.GetMenuItems()
        items[p.markerMode + 2].Check()
        # checkmark the current menu item in the Operating Cal menu
        items = self.operatingCalMenu.GetMenuItems()
        items[5 - p.calLevel].Check() # EON Jan 10 2014

        if (not specP or not specP._isReady) or self.refreshing:
            return
        self.refreshing = True
        specP.FullRefresh()
        if self.sweepDlg:
            self.sweepDlg.UpdateFromPrefs()
        self.refreshing = False

    #--------------------------------------------------------------------------
    # Open the Synthetic DUT dialog box.

    def SynDUT(self, event=None): # JGH 2/8/14 syndutHook7
        global hardwarePresent, cb
        if not msa.syndut:
            cb = MSA_CB()
            hardwarePresent = False
##            import syndut    # JGH 2/8/14
            msa.syndut = SynDUTDialog(self)
        else:
            msa.syndut.Raise()

    #--------------------------------------------------------------------------
    # Open the Sweep modeless dialog box.

    def SetSweep(self, event=None):
        if not self.sweepDlg:
            self.sweepDlg = SweepDialog(self)
        else:
            self.sweepDlg.Raise()
        self.sweepDlg.Show(True)

    #--------------------------------------------------------------------------
    # Open the Variables modeless info box.

    def ShowVars(self, event=None):
        if not self.varDlg:
            self.varDlg = VarDialog(self)
        else:
            self.varDlg.Raise()
        self.varDlg.Show(True)

    #--------------------------------------------------------------------------
    # Save an image of the graph to a file.

    def SaveImage(self, event):
        p = self.prefs
        context = wx.ClientDC(self.specP)
        memory = wx.MemoryDC()
        x, y = self.specP.ClientSize
        bitmap = wx.EmptyBitmap(x, y, -1)
        memory.SelectObject(bitmap)
        memory.Blit(0, 0, x, y, context, 0, 0)
        wildcard = "PNG (*.png)|*.png|JPEG (*.jpg)|*.jpg|BMP (*.bmp)|*.bmp"
        types = (".png", ".jpg", ".bmp")
        while True:
            imageDir = p.get("imageDir", appdir)
            dlg = wx.FileDialog(self, "Save image as...", defaultDir=imageDir,
                    defaultFile="", wildcard=wildcard, style=wx.SAVE)
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
            p.imageDir = os.path.dirname(path)
            chosenType = types[dlg.GetFilterIndex()]
            path = CheckExtension(path, self, types, chosenType)
            if not path:
                continue
            if ShouldntOverwrite(path, self):
                continue
            break
        base, ext = os.path.splitext(path)
        type = wx.BITMAP_TYPE_PNG
        if ext == ".jpg":
            bmtype = wx.BITMAP_TYPE_JPEG    # JGH 2/10/14
        elif ext == ".bmp":
            bmtype = wx.BITMAP_TYPE_BMP # JGH 2/10/14
        print ("Saving image to", path)
        bitmap.SaveFile(path, bmtype)   # JGH 2/10/14

    #--------------------------------------------------------------------------
    # Load or save spectrum data to an s1p file.

    def LoadData(self, event):
        self.StopScanAndWait()
        p = self.prefs
        wildcard = "S1P (*.s1p)|*.s1p"
        dataDir = p.get("dataDir", appdir)
        dlg = wx.FileDialog(self, "Choose file...", defaultDir=dataDir,
                defaultFile="", wildcard=wildcard)
        if dlg.ShowModal() != wx.ID_OK:
            return
        path = dlg.GetPath()
        p.dataDir = os.path.dirname(path)
        print ("Reading", path)
        spec = self.spectrum = Spectrum.FromS1PFile(path)
        specP = self.specP
        specP.h0 = p.fStart = spec.Fmhz[0]  # EON Jan 10 2014
        specP.h1 = p.fStop  = spec.Fmhz[-1] # EON Jan 10 2014
        p.nSteps = spec.nSteps
        self.RefreshAllParms()
        self.DrawTraces()

    def SaveData(self, event=None, data=None, writer=None, name="Data.s1p"):
        self.StopScanAndWait()
        p = self.prefs
        if writer == None:
            writer = self.spectrum.WriteS1P
        if data == None:
            data = self.spectrum
        if data == None:
            raise ValueError("No data to save")
        name = os.path.basename(name)
        base, ext = os.path.splitext(name)
        wildcard = "%s (*%s)|*%s" % (ext[1:].upper(), ext, ext)
        while True:
            dataDir = p.get("dataDir", appdir)
            dlg = wx.FileDialog(self, "Save as...", defaultDir=dataDir,
                    defaultFile=name, wildcard=wildcard, style=wx.FD_SAVE)
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
            p.dataDir = os.path.dirname(path)
            path = CheckExtension(path, self, (ext))
            if not path:
                continue
            if ShouldntOverwrite(path, self):
                continue
            break
        if debug:
            print ("Saving data to", path)
        if data == self.spectrum:
            writer(path, self.prefs)
        else:
            writer(data, path)

    #--------------------------------------------------------------------------
    # Manually load and save preferences.

    def LoadPrefs(self, event=None):
        if debug:
            print (">>>15059<<< Entering LoadPrefs")
        if self.prefs:
            self.StopScanAndWait()
        prefsName = os.path.join(appdir, self.rootName + ".prefs")
        self.prefs = p = Prefs.FromFile(prefsName)
        isLight = p.get("graphAppear", "Light") == "Light"
        p.theme = (DarkTheme, LightTheme)[isLight]
        p.theme.UpdateFromPrefs(p)
        if debug:
            print (">>>15068<<< Finished LoadPrefs")

    def SavePrefs(self, event=None):
        p = self.prefs
        self.StopScanAndWait()
        for m in self.specP.markers.values():
            m.SavePrefs(p)
        p.theme.SavePrefs(p)
        p.save()

    #--------------------------------------------------------------------------
    # Open Test Setups Dialog box.

    def LoadSaveTestSetup(self, event=None):
        self.StopScanAndWait()
        p = self.prefs
        dlg = TestSetupsDialog(self)
        dlg.ShowModal()
        p.testSetupsWinPos = dlg.GetPosition().Get()

    #--------------------------------------------------------------------------
    # Set Markers mode.

    def SetMarkers_Indep(self, event=None):
        self.prefs.markerMode = Marker.MODE_INDEP
        self.RefreshAllParms()

    def SetMarkers_PbyLR(self, event=None):
        self.prefs.markerMode = Marker.MODE_PbyLR
        self.RefreshAllParms()

    def SetMarkers_LRbyPp(self, event=None):
        self.prefs.markerMode = Marker.MODE_LRbyPp
        self.RefreshAllParms()

    def SetMarkers_LRbyPm(self, event=None):
        self.prefs.markerMode = Marker.MODE_LRbyPm
        self.RefreshAllParms()

    #--------------------------------------------------------------------------
    # Open the Reference Line Specification dialog box.

    def SetRef(self, event):
        p = self.prefs
        refNum = event.Id - 600
        dlg = RefDialog(self, refNum)
        if dlg.ShowModal() == wx.ID_OK:
            mode = dlg.mode
            if mode == 0:
                # delete it
                if self.refs.has_key(refNum):
                    self.refs.pop(refNum)
            else:
                # create a new ref from current data
                spec = self.spectrum
                vScales = self.specP.vScales
                # get the units from both vertical scales
                bothU = [vs.dataType.units for vs in vScales]
                print ("bothU=", bothU)
                for i in range(2):
                    vScale = vScales[i]
                    # create a ref for each axis, unless the axes are
                    # (db, Deg), in which case we create one ref with both
                    if not (dlg.traceEns[i]) or \
                            (i == 1 and "dB" in bothU and \
                             ("Deg" in bothU or "CDeg" in bothU)):
                        if debug:
                            print ("SetRef not doing", refNum, i)
                        continue
                    ref = Ref.FromSpectrum(refNum, spec, vScale)
                    if mode == 2:
                        # if a fixed value, assign value
                        rsp = ref.spectrum
                        n = len(rsp.Fmhz)
                        rsp.Sdb = zeros(n) + \
                                         floatOrEmpty(dlg.valueABox.GetValue())
                        if msa.mode >= msa.MODE_VNATran:
                            rsp.Sdeg = zeros(n) + \
                                         floatOrEmpty(dlg.valueBBox.GetValue())
                    # assign trace width(s), name, and math mode
                    ref.name = dlg.nameBox.GetValue()
                    ref.aWidth = int(dlg.widthACB.GetValue())
                    if msa.mode >= msa.MODE_VNATran:
                        # ref for axis 0 may be both mag and phase traces
                        ref.bWidth = int(dlg.widthBCB.GetValue())
                    if ref.name == "":
                        ref.name = "R%d" % refNum
                    self.refs[refNum] = ref
                    if refNum == 1:
                        ref.mathMode = dlg.graphOptRB.GetSelection()

        self.DrawTraces()
        self.specP.FullRefresh()
        p.refWinPos = dlg.GetPosition().Get()

    #--------------------------------------------------------------------------
    # Open the Perform Calibration dialog box.

    def PerformCal(self, event=None):
        self.StopScanAndWait()
        p = self.prefs
        dlg = PerformCalDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            p.perfCalWinPos = dlg.GetPosition().Get()

    # Start EON Jan 10 2014
    #--------------------------------------------------------------------------
    # Open the Perform Calibration dialog box.

    def PerformCalUpd(self, event=None):
        self.StopScanAndWait()
        p = self.prefs
        dlg = PerformCalUpdDialog(self)
        if not dlg.error: # EON Jan 29, 2014
            if dlg.ShowModal() == wx.ID_OK:
                p.perfCalUpdWinPos = dlg.GetPosition().Get()

    # End EON Jan 10 2014

    #--------------------------------------------------------------------------
    # Set the calibration reference to Band, Base, or None.

    def SetCalRef_Band(self, event):
        # Start EON Jan 13 2014
        if msa.IsScanning():
            self.StopScanAndWait()
        # End EON Jan 13 2014
        if not msa.bandCal:
            self.PerformCal()
        if msa.bandCal:
            self.SetCalLevel(2)
        self.RefreshAllParms()

    def SetCalRef_Base(self, event):
        # Start EON Jan 13 2014
        if msa.IsScanning():
            self.StopScanAndWait()
        # End EON Jan 13 2014
        if not msa.baseCal:
            self.PerformCal()
        if msa.baseCal:
            self.SetCalLevel(1)
        self.RefreshAllParms()

    def SetCalRef_None(self, event):
        self.SetCalLevel(0)
        self.RefreshAllParms()

    #--------------------------------------------------------------------------
    # Set the calibration reference level, base, and band, keeping msa, prefs,
    # and data files in sync.

    def SetCalLevel(self, level):
        p = self.prefs
        msa.calLevel = p.calLevel = level
        if self.CalCheck(): # EON Jan 29, 2014
            self.RefreshAllParms()


    def SetBandCal(self, spectrum):
        msa.bandCal = spectrum
        if spectrum:
            msa.bandCal.WriteS1P(self.bandCalFileName, self.prefs,
                                 contPhase=True)
        else:
            # Start EON Jan 10 2014
            try:
                os.unlink(self.bandCalFileName)
            except:
                pass
            # End EON Jan 10 2014

    def SetBaseCal(self, spectrum):
        msa.baseCal = spectrum
        self.SaveCal(spectrum, self.baseCalFileName)

    def SetBandeCal(self, spectrum):
        msa.bandCal = spectrum
        self.SaveCal(spectrum, self.bandCalFileName)

    def SaveCal(self, spectrum, path):
        if spectrum:
            spectrum.WriteS1P(path, self.prefs, contPhase=True)
        elif os.path.exists(path):
            os.unlink(path)

    def LoadCal(self, path):
        if os.path.exists(path):
            cal = Spectrum.FromS1PFile(path) # EON Jan 29, 2014
            if cal == None:
                cal = OslCal.FromS1PFile(path)
            return cal
        else:
            return None

    def CopyBandToBase(self):
        msa.baseCal = dcopy.deepcopy(msa.bandCal)
        msa.baseCal.WriteS1P(self.baseCalFileName, self.prefs, contPhase=True)

    #--------------------------------------------------------------------------
    # Read CalPath file for mag/phase linearity adjustment.

    def ReadCalPath(self):
        if debug:
            print ("10,665 Reading path calibration")
        self.StopScanAndWait()
        p = self.prefs
        directory, fileName = CalFileName(p.indexRBWSel+1)
        try:
            f = open(os.path.join(directory, fileName), "Ur")
            msa.magTableADC, msa.magTableDBm, msa.magTablePhase = \
                    CalParseMagFile(f)
            if debug:
                print (fileName, "read OK.")
        except:
            ##traceback.print_exc()
            if debug:
                print (fileName, "not found. Using defaults.")

    #--------------------------------------------------------------------------
    # Read CalFreq file for mag frequency-dependent adjustment.

    def ReadCalFreq(self):
        if debug:
            print ("Reading frequency calibration")
        self.StopScanAndWait()
        directory, fileName = CalFileName(0)
        try:
            f = open(os.path.join(directory, fileName), "Ur")
            msa.freqTableMHz, msa.freqTableDB = CalParseFreqFile(f)
            if debug:
                print (fileName, "read OK.")
        except:
            ##traceback.print_exc()
            if debug:
                print (fileName, "not found. Using defaults.")

    #--------------------------------------------------------------------------
    # Write data to a file.

    def SaveGraphData(self, event):
        self.SaveData(writer=self.specP.WriteGraph, name="GraphData.txt")

    def SaveInputData(self, event):
        self.SaveData(writer=self.spectrum.WriteInput, name="InputData.txt")

    def SaveInstalledLineCal(self, event):
        p = self.prefs
        if p.calLevel == 1:
            self.SaveData(data=msa.bandCal, writer=self.SaveCal,
                            name=self.bandCalFileName)
        elif p.calLevel == 2:
            self.SaveData(data=msa.baseCal, writer=self.SaveCal,
                            name=self.baseCalFileName)

    #--------------------------------------------------------------------------
    # Write debugging event lists to a file.

    def WriteEvents(self, event):
        msa.WriteEvents()

    def DumpEvents(self, event):
        msa.DumpEvents()

    #--------------------------------------------------------------------------
    # Show the Functions menu dialog boxes.

    def AnalyzeFilter(self, event):
        if not self.filterAnDlg:
            self.filterAnDlg = FilterAnalDialog(self)
        else:
            self.filterAnDlg.Raise()

    def ComponentMeter(self, event):
        if not self.compDlg:
            self.compDlg = ComponentDialog(self)
        else:
            self.compDlg.Raise()

    def AnalyzeRLC(self, event):
        if not self.tranRLCDlg:
            self.tranRLCDlg = AnalyzeRLCDialog(self)
        else:
            self.tranRLCDlg.Raise()
    # Start EON Jan 22, 2014
    def CoaxParms(self,event):
        if not self.coaxDlg: # EON Jan 29, 2014
            self.coaxDlg = CoaxParmDialog(self)
        else:
            self.coaxDlg.Raise()
    # End EON Jan 22, 2014
    def AnalyzeCrystal(self, event):
        if not self.crystalDlg:
            self.crystalDlg = CrystAnalDialog(self)
        else:
            self.crystalDlg.Raise()

    def StepAttenuator(self, event):
        if not self.stepDlg:
            self.stepDlg = StepAttenDialog(self)
        else:
            self.stepDlg.Raise()

    #--------------------------------------------------------------------------
    # Set the main operating mode.

    def SetMode_SA(self, event):
        self.SetMode(msa.MODE_SA)

    def SetMode_SATG(self, event):
        self.SetMode(msa.MODE_SATG)

    def SetMode_VNATran(self, event):
        # Start EON Jan 22, 2014
##        p = self.prefs
##        p.switchTR = 0   # JGH 11/25/13
        # End EON Jan 22, 2014
        self.SetMode(msa.MODE_VNATran)

    def SetMode_VNARefl(self, event):
        # Start EON Jan 22, 2014
##        p = self.prefs
##        p.switchTR = 1   # JGH 11/25/13
        # End EON Jan 22, 2014
        self.SetMode(msa.MODE_VNARefl)

    def SetMode(self, mode):
        self.StopScanAndWait()

        self.InitMode(mode) # EON Jan 22, 2014

        if debug:
            print ("Changed MSA mode to", msa.modeNames[mode])
        self.prefs.mode = mode
        msa.SetMode(mode)
        if self.spectrum:
            # reset trace type selections to default for this mode
            vScales = self.specP.vScales
            vs0 = vScales[0]
            vs0.typeIndex = 1
            vs0.dataType = dataType = traceTypesLists[mode][vs0.typeIndex]
            vs0.top = dataType.top
            vs0.bot = dataType.bot
            if vs0.top == 0 and vs0.bot == 0:
            	vs0.AutoScale(self)
            vs1 = vScales[1]
            vs1.typeIndex = (0, 2)[mode >= MSA.MODE_VNATran]
            vs1.dataType = dataType = traceTypesLists[mode][vs1.typeIndex]
            vs1.top = dataType.top
            vs1.bot = dataType.bot
            if vs1.top == 0 and vs1.bot == 0:
            	vs1.AutoScale(self)
        self.needRestart = True
        # Flip the TR switch
        self.RefreshAllParms()
        self.DrawTraces()

    # Start EON Jan 22, 2014
    def InitMode(self,mode):
        p = self.prefs
        if mode == msa.MODE_VNATran:
            p.switchTR = 0   # JGH 11/25/13
        if mode == msa.MODE_VNARefl:
            p.switchTR = 1   # JGH 11/25/13

        if mode < msa.MODE_VNATran:
            p.calLevel = msa.calLevel = 0

        menuBar = self.MenuBar
        i = menuBar.FindMenu("Functions")
        funcMenu = menuBar.GetMenu(i)
        items = funcMenu.GetMenuItems()
        funcList = self.funcModeList[mode]
        skip = True
        for m in items:
            txt = m.GetText().lower()
            if len(txt) == 0:
                skip = False
            if skip:
                continue
            found = False
            for val in funcList:
                if val in txt:
                    found = True
                    break
            m.Enable(found)

        if mode == MSA.MODE_SA or mode == MSA.MODE_SATG:
            i = menuBar.FindMenu("Operating Cal")
            if i > 0:
                menuBar.Remove(i)
        else:
            if menuBar.FindMenu("Operating Cal") < 0:
                i = menuBar.FindMenu("Mode")
                if i > 0:
                    menuBar.Insert(i,self.operatingCalMenu,"Operating Cal")
    # End EON Jan 22, 2014

    #--------------------------------------------------------------------------
    # Handle a resize event of the main frame or log pane sash.

    def OnSizeChanged(self, event):
        self.prefs.frameSize = self.GetSize()
        event.Skip()

    def OnSashChanged(self, event):
        sashWin = event.GetEventObject()
        setattr(self.prefs, sashWin.name + "Split", sashWin.GetSashPosition())
        event.Skip()

    #--------------------------------------------------------------------------
    # About dialog.

    def OnAbout(self, event):
        info = wx.AboutDialogInfo()
        info.Name = self.appName
        info.Version = version
        info.Description = "MSAPy is a portable interface for the " \
            "Modular Spectrum Analyzer."
        info.WebSite = ("http://sourceforge.net/projects/msapy/",
                        "MSAPy SourceForge page")
        info.Developers = ["Scott Forbes", "Sam Wetterlin", \
                           "Scotty Sprowls", "Jim Hontoria, W1JGH", \
                           "Eric Nystrom, W4EON"]
        wx.AboutBox(info)

    #--------------------------------------------------------------------------
    # Quitting.

    def OnExit(self, event):
        if msa.syndut:    # JGH syndutHook8
            msa.syndut.Close()
        if self.smithDlg:
            self.smithDlg.Close()
        print ("Exiting")
        self.SavePrefs()
        print ("Exiting2")
        self.Destroy()

if showThreadProfile:
    import yappi    # JGH 2/10/14, reqyuires yappi-0.82.tar.gz
elif showProfile:
    import cProfile

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
        if self.cftest == 1 and msa.IsScanning():
            self.frame.StopScanAndWait()
        p.cftest = 1
        self.Refreshing = False
        self.enterPLL2phasefreq = p.PLL2phasefreq
        LO2.PLLphasefreq = p.PLL2phasefreq = .1 # JGH 2/5/14
        # Goto restart
        self.frame.StartScan(False) # JGH True is for HaltAtEnd

    #------------------------------------------------------------------------

    def CloseCavityFilterTest(self, event=None):
        # will come here when Cavity Filter Test Window is closed
        p = self.frame.prefs
        p.cftest = 0
        LO2.PLLphasefreq = p.PLL2phasefreq = self.enterPLL2phasefreq # JGH 2/5/14
        p.CavFiltTestWinPos = self.GetPosition().Get()
        self.Destroy()

    # JGH ends

#------------------------------------------------------------------------------

#==============================================================================
# Start up application.

class MSAApp(wx.App):
    def OnInit(self):
        name = os.path.splitext(os.path.split(sys.argv[0])[1])[0]
        appPath = os.path.split(sys.argv[0])[0].split(os.path.sep)
        for f in appPath:
            if ".app" in f:
                name = f[:-4]
                break
        MSASpectrumFrame(None, name)
        return True

    def ProcessEvent(self, event):
        if debug:
            print ("ProcessEvent")
        event.Skip()

if __name__ == "__main__":
    try:
        app = MSAApp(redirect=False)
        if showThreadProfile:
            # profile code (both threads) and write results
            yappi.start(builtins=True)
            app.MainLoop()
            yappi.stop()
            f = open("msa.profile", "w")
            yappi.print_stats(f, yappi.SORTTYPE_TSUB)
            f.close()
        elif showProfile:
            # profile code (main thread only) and write results
            cProfile.run("app.MainLoop()", "msa.profile")
            # To see the stats, do:
            #   ./showprof.py
        else:
            # normal run
            ##wx.lib.inspection.InspectionTool().Show()
            app.MainLoop()
    except:
        dlg = ScrolledMessageDialog(None, traceback.format_exc(), "Error")
        dlg.ShowModal()
        sys.exit(-1)
