from msaGlobal import incremental, SetModuleVersion
import copy as dcopy
from numpy import append, convolve, diff, exp, log10
from numpy import  nan_to_num, pi, seterr, sqrt, zeros
from numpy import ones, vstack
from numpy.linalg import lstsq
from util import mW, MHz, uF, uH
from util import truncateS11ToUnity
from util import min2
from util import EquivS11FromS21
from util import angle
from util import db
from msa import MSA

SetModuleVersion("trace",("1.30","EON","05/20/2014"))

def SetMsa(val):
    global msa
    msa = val

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
        if j < 0:
            j = 0
        elif j >= len(self.Fmhz):
            j = len(self.Fmhz) - 1
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

# A list of SA mode data types, in type-chooser order
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

class InsLossTrace1(S21Trace):
    desc = "Insertion Loss (dB)"
    name = "IL"
    units = "dB"
    top = 60
    bot = 0
    def __init__(self, spec, iScale):
        S21Trace.__init__(self, spec, iScale)
        self.v = -self.Sdb

    def SetStep(self, spec, i):
        self.v[i] = -self.Sdb[i]

class GroupDelayTrace(S21Trace):
    desc = "S21 Group Delay"
    name = "GD"
    units = "sec"
    top = 0
    bot = 0
    def __init__(self, spec, iScale, nPoints=0):
        S21Trace.__init__(self, spec, iScale)
        self.v = v = zeros(spec.nSteps + 1)
        if nPoints:
            self.calcGd(nPoints)
            return

        Scdeg = spec.Scdeg
        Fmhz = spec.Fmhz
        lastY = Scdeg[0]
        lastX = Fmhz[0]
        for i in range(1, spec.maxStep):
            val = Scdeg[i]
            deltaY = val - lastY
            if deltaY > 0.5:
                deltaY -= 1 
            elif deltaY < -0.5:
                deltaY += 1
            lastY = val
            val = Fmhz[i]
            deltaF = val - lastX
            lastX = val
            v[i] = -deltaY / (deltaF * 360000000.0)

    def SetStep(self, spec, i):
        S21Trace.SetStep(self, spec, i)
        Scdeg = spec.Scdeg
        Fmhz = spec.Fmhz
        if i > 0:
            deltaY = Scdeg[i] - Scdeg[i - 1]
            if deltaY > 0.5:
                deltaY -= 1 
            elif deltaY < -0.5:
                deltaY += 1
            deltaF = Fmhz[i] - Fmhz[i - 1]
            self.v[i] = -deltaY / (deltaF * 360000000.0)

    def calcGd(self, nPoints):
        spec = self.spec
        nSteps = spec.maxStep
        self.nPoints = nPoints;
        nLeft = int(nPoints / 2)
        self.Fmhz = Fmhz = spec.Fmhz
        self.Scdeg = Scdeg = spec.Scdeg
        for i in range(nSteps):
            start = max(0, i - nLeft)
            end = min(nSteps, start + nPoints)
            x = Fmhz[start : end]
            y = Scdeg[start : end]
            A = vstack([x, ones(len(x))]).T
            m, c = lstsq(A, y)[0]
            self.v[i] = -m / 360000000.0

traceTypesLists[MSA.MODE_VNATran] = (
    NoTrace,
    S21MagTrace,
    S21PhaseTrace,
    S21ConPhaseTrace,
    RawPowerTrace,
    RawPhaseTrace,
    InsLossTrace1,
    GroupDelayTrace,
)

#------------------------------------------------------------------------------
# Reflection Mode.

class S11Trace(Trace):
    top = 0
    bot = -100
    def __init__(self, spec, iScale):
        global msa
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
        S11 = 10**(spec.Sdb/20) * exp(1j*pi*spec.Sdeg/180)
        self.S21db = self.Sdb
        self.S21deg = self.Sdeg

        # Using a Series or Shunt "Reflectance" fixture:
        if spec.isSeriesFix or spec.isShuntFix:
            S11, Zs = EquivS11FromS21(S11, spec.isSeriesFix, msa.fixtureR0)
            self.S11 = S11
            self.Zs = Zs
            self.Sdb = db(abs(S11))
            self.Sdeg = 180*angle(S11)/pi
        else:
            self.S11 = S11
            save = seterr(all="ignore")
            self.Zs = Zs = msa.fixtureR0 * (1 + S11) / (1 - S11)
            seterr(**save)
            self.Zs = nan_to_num(self.Zs)

        # Zp is equivalent parallel impedance to Zs
        mag2 = Zs.real**2 + Zs.imag**2
        save = seterr(all="ignore")
        self.Zp = mag2/Zs.real + 1j*mag2/Zs.imag
        seterr(**save)
        self.Zp = nan_to_num(self.Zp)
        self.w = 2*pi*spec.f*MHz

    def SetStep(self, spec, i):
        global msa
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
        S11 = 10**(spec.Sdb[i]/20) * exp(1j*pi*spec.Sdeg[i]/180)
        self.S21db = self.Sdb[i]
        self.S21deg = self.Sdeg[i]
 
        # Using a Series or Shunt "Reflectance" fixture:
        if spec.isSeriesFix or spec.isShuntFix:
            S11, Zs = EquivS11FromS21(S11, spec.isSeriesFix, msa.fixtureR0)
            self.S11[i] = S11
            self.Zs[i] = Zs
            self.Sdb[i] = db(abs(S11))
            self.Sdeg[i] = 180*angle(S11)/pi
        else:
            self.S11[i] = S11
            try:
                self.Zs[i] = Zs = msa.fixtureR0 * (1 + S11) / (1 - S11)
            except:
                self.Zs[i] = Zs = complex(0, 0)

        # Zp is equivalent parallel impedance to Zs
        mag2 = Zs.real**2 + Zs.imag**2
        try:
            self.Zp[i] = mag2/Zs.real + 1j*mag2/Zs.imag
        except ZeroDivisionError:
            self.Zp[i] = 0
        self.w[i] = 2*pi*spec.f[i]*MHz

class RMagTrace(Trace):
    desc = "Magnitude (dBm)"
    name = "Mag"
    units = "dBm"
    top = 0
    bot = -120
    def __init__(self, spec, iScale):
        Trace.__init__(self, spec, iScale)
        self.v = dcopy.copy(spec.Mdb)

    def SetStep(self, spec, i):
        self.v[i] = spec.Mdb[i]

class RPhaseTrace(Trace):
    desc = "Phase (deg)"
    name = "Phase"
    units = "deg"
    top = 180
    bot = -180
    def __init__(self, spec, iScale):
        Trace.__init__(self, spec, iScale)
        self.v = dcopy.copy(spec.Mdeg)

    def SetStep(self, spec, i):
        self.v[i] = spec.Mdeg[i]

class CapTrace(S11Trace):
    units = "F"
    top = 1*uF
    bot = 0
    def __init__(self, spec, iScale):
        S11Trace.__init__(self, spec, iScale)

    def SetV(self, Z):
        save = seterr(all="ignore")
        self.v = -1 / (Z.imag*self.w)
        self.v = nan_to_num(self.v)
        seterr(**save)

    def Set(self, Z, i):
        save = seterr(all="ignore")
        self.v[i] = -1 / (Z[i].imag*self.w[i])
        self.v[i] = nan_to_num(self.v[i])
        seterr(**save)

    def SetStep(self, spec, i):
        S11Trace.SetStep(self, spec, i)

class InductTrace(S11Trace):
    units = "H"
    top = 1*uH
    bot = 0
    def __init__(self, spec, iScale):
        S11Trace.__init__(self, spec, iScale)

    def SetV(self, Z):
        save = seterr(all="ignore")
        self.v = Z.imag/self.w
        self.v = nan_to_num(self.v)
        seterr(**save)

    def Set(self, Z, i):
        save = seterr(all="ignore")
        self.v[i] = Z[i].imag/self.w[i]
        self.v[i] = nan_to_num(self.v[i])
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

class S21MagTrace1(S11Trace):
    desc = "S21 Magnitude (dB)"
    name = "S21_dB"
    units = "dB"
    top = 0
    bot = -100
    def __init__(self, spec, iScale):
        S11Trace.__init__(self, spec, iScale)
        self.v = self.S21db

    def SetStep(self, spec, i):
        self.v[i] = self.S21db[i]

class S21PhaseTrace1(S11Trace):
    desc = "S21 Phase Angle (Deg)"
    name = "S21_Deg"
    units = "Deg"
    top = 180
    bot = -180
    def __init__(self, spec, iScale):
        S11Trace.__init__(self, spec, iScale)
        self.v = self.S21deg

    def SetStep(self, spec, i):
        self.v[i] = self.S21deg[i]

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
    RMagTrace,
    RPhaseTrace,
    RhoTrace,
    ThetaTrace,
    ZMagTrace,
    ZPhaseTrace,
    S21MagTrace1,
    S21PhaseTrace1,
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
