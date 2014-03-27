from msaGlobal import GetMsa, isWin, SetModuleVersion
import cmath, inspect, re, os, time, wx
from wx.lib.dialogs import alertDialog
from math import cos, floor, sin, sqrt, tan
from numpy import angle, exp, Inf, isnan, log10, mean, mod
from numpy import nan_to_num, pi, select, seterr, std

SetModuleVersion("util",("1.03","JGH","03/11/2014"))

# Set to truncate S11 to the unity circle to ignore error due to S21
# measurement losses during calibrating
truncateS11ToUnity = False

constMaxValue = 1e12

# Utilities.

def lineno():
    return inspect.currentframe().f_back.f_lineno

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

RadsPerDegree = pi / 180
DegreesPerRad = 180 / pi

def uSafeLog10(aVal):
    if aVal <= 1e-20:           #0.00001^4
        return -20
    else:
        return log10(aVal)

def polarDbDeg(Z):
    (mag, phase) = cmath.polar(Z)
    db = 20 * uSafeLog10(mag)
    deg = phase * DegreesPerRad
    return db, deg

# Return an array of minimums/maximums between corresponding arrays a and b

def min2(a, b):
    return select([b < a], [b], default=a)

def max2(a, b):
    return select([b > a], [b], default=a)

# Divide without raising a divide-by-zero exception. Only used in register
# setup, where wrong values just give wrong frequencies.

def divSafe(a, b):
    if b != 0:
        return a / b;
    return a

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
    try:
        thou = min(max(int((log10(abs(n)) + 15) / 3), 0), 9)
    except:
        thou = 0
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
    dsExp, dsMantNo = divmod(log10(wid * divSize / float(size)), 1)
    if isnan(dsMantNo):
        print ("StdScale dsMantNo=", dsMantNo)
        return 1, 0, 0, 0
    ds = (1.0, 2.0, 5.0, 5.0)[int(3 * dsMantNo + 0.1)] * 10**dsExp
    base = floor(bot/ds + 0.95) * ds
    frac = base - bot
    nDiv = max(int(wid/ds), 0) + 1
    return ds, base, frac, nDiv

def message(message, caption="", style=wx.OK): # EON Jan 29, 2014
    msa = GetMsa()
    dlg = wx.MessageDialog(msa.frame, message, caption, style)
    dlg.ShowModal()
    dlg.Destroy()

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
