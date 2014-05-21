from msaGlobal import GetVersion, SetModuleVersion
import string, time
from numpy import array, isnan, select, zeros
from events import LogGUIEvent
from util import MHz, siScale

SetModuleVersion("spectrum",("1.30","EON","05/20/2014"))

#==============================================================================
# Holder of the parameters and results of one scan.

class Spectrum:
    def __init__(self, when, pathNo, fStart, fStop, nSteps, Fmhz):
        self.isLogF = (Fmhz[0] + Fmhz[2])/2 != Fmhz[1]
        self.desc = "%s, Path %d, %d %s steps, %g to %g MHz." % \
            (when, pathNo, nSteps, ("linear", "log")[self.isLogF], \
            fStart, fStop)
        self.nSteps = nSteps        # number of steps in scan
        self.Fmhz = Fmhz            # array of frequencies (MHz), one per step
        n = nSteps + 1
        self.oslCal = False        # EON Jan 10 2014
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
        self.maxStep = 0
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
            if i > self.maxStep:
                self.maxStep = i
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
        f.write("!MSA, msapy %s\n" % GetVersion)
        f.write("!Date: %s\n" % time.ctime())
        f.write("!%s Sweep Path %d\n" % \
            (("Linear", "Log")[p.isLogF], p.RBWSelindex+1))
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
                        f.close()
                        return None
                        #raise ValueError( \
                        #    "S1P file format wrong: expected freq, Sdb, Sdeg")
                    Fmhz.append(float(words[0]) * fScale)
                    Sdb.append(float(words[1]))
                    Sdeg.append(float(words[2]))
        f.close()

        n = len(Fmhz)
        if n == 0:
            return None
            #raise ValueError("S1P file: no data found")

        print ("Read %d steps." % (n-1), "Start=", Fmhz[0], "Stop=", Fmhz[-1])
        this = cls(when, pathNo, Fmhz[0], Fmhz[-1], n - 1, array(Fmhz))
        this.Sdb = array(Sdb)
        this.Sdeg = array(Sdeg)
        this.Scdeg = this.Sdeg
        return this
