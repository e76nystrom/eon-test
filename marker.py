from msaGlobal import SetModuleVersion
import re, warnings
from numpy import arange, interp, isnan, log10, \
    poly1d, polyfit, RankWarning

SetModuleVersion("marker",("1.02","EON","03/11/2014"))

prt = False

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
            if isPos:
                peak = data.argmax()
            else:
                peak = data.argmin()
            mhz = f0 + peak * df
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
        vals = trace.v
        if searchR:
            inc = 1
            r = range(jP,len(trace.v))
#            vals  = trace.v[jP:]
#            Fmhz =       Fmhz[jP:]
        else:
            inc = -1
            r = range(jP,0,-1)
#            vals  = trace.v[jP::-1]
#            Fmhz =       Fmhz[jP::-1]

        # using interpolation, locate exact freq where vals crosses value
        # (multiplied by slope to insure that vals are in increasing order)
#        slope = -signP
#        if show:
#            print ("FindValue: jP=", jP, "signP=", signP, \
#                "vals=", slope*vals[:10].round(3))
#            print (self.name, "searchR=", searchR, "value=", slope*value, \
#                "Fmhz=", Fmhz[:10].round(6))

        mhz = Fmhz[jP]
        found = False
        if signP > 0:
            for i in r:
                tmp = vals[i]
                if tmp < value:
                    found = True
                    break
        else:
            for i in r:
                tmp = vals[i]
                if tmp > value:
                    found = True
                    break
        if found:
            vl = vals[i - inc]
            fl = Fmhz[i - inc]
            mhz = (Fmhz[i] - fl) * ((value - vl) / (tmp - vl)) + fl
            if prt:
                fil = open("marker.txt","a")
                fil.write("jp %5d value %6.2f search %s\n" % (jP, value, searchR))
                fil.write("i  %5d inc %2d\n" % (i, inc))
                fil.write("vi %6.2f  vl %6.2f\n" % (tmp, vl))
                fil.write("fi %10.6f fl %10.6f\n" % (Fmhz[i], fl))
                fil.write("(Fmhz[i] - fl) %10.6f (value - vl) %8.4f (tmp - vl) %8.4f fl %10.6f\n" % \
                          ((Fmhz[i] - fl), (value - vl), (tmp - vl), fl))
                ival = interp(mhz, Fmhz, vals)
                self.mhz = mhz
                tval = self.TraceValue(trace, isLogF)
                fil.write("mhz %10.6f ival %6.2f tval %6.2f\n\n" % (mhz, ival, tval))
                fil.close();

#        mhz = interp(slope*value, slope*vals, Fmhz)
        if isLogF:
            mhz = 10**mhz

        # round to Hz
        # self.mhz = round(mhz, 6)
        self.mhz = mhz
        if show:
            print ("FindValue got mhz=", self.mhz)

    #--------------------------------------------------------------------------
    # Get value of given trace at marker's frequency.

    def TraceValue(self, trace, isLogF):
        if not trace:
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
        if isnan(value):
            value = 0
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
        if isnan(self.dbm):
            self.dbm = 0
        if traceP and isnan(self.deg):
            self.deg = 0

    #--------------------------------------------------------------------------
    # Save a marker's mhz and traceName preferences to p.

    def SavePrefs(self, p):
        print ("name=", self.name)
        name = re.sub("\+", "p", re.sub("-", "m", self.name))
        for attr in ("mhz", "traceName"):
            setattr(p, "markers_"+name+"_"+attr, getattr(self, attr))

