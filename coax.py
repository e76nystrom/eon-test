from msaGlobal import SetModuleVersion
import cmath, numpy, os, re, wx
from math import sqrt
from numpy import pi
from util import constMaxValue, floatSI, polarDbDeg, message
from functionDialog import FunctionDialog
from marker import Marker

SetModuleVersion("coax",("1.02","EON","03/11/2014"))

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
        "1. Using a calibrated bridge, perform an S11 scan of an "\
        "open coax stub, focused around the first quarter-wavelength resonance "\
        "(near +/-180 degrees S11 phase).  The highest step frequency should be "\
        "less than where a 360 degree phase shift occurs in the sweep\n\n"\
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
#        for i in range(len(vals)):
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
        for i in range(len(react)):
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

        coaxZReal = numpy.interp(self.coaxFq, Fmhz, Zs.real)
        coaxZImag = numpy.interp(self.coaxFq, Fmhz, Zs.imag)
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

    @classmethod
    def CoaxDelayNS(VF, lenFeet):
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
    @classmethod
    def CoaxWavelengthFt(fMHz, VF):
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

    @classmethod
    def CoaxLossDB(fMHz, K1, K2, lenFeet):
        return (lenFeet / 100) * (K1 * sqrt(fMHz) + K2 * fMHz)

#
# function CoaxLossDB(fMHz, K1, K2, lenFeet)    'Return loss in DB for specified coax
#     CoaxLossDB=(lenFeet/100) * (K1*Sqr(fMHz)+K2*fMHz)
# end function
#

    @classmethod
    def CoaxLossA0(fMHz, K1, K2):
        return K1 * sqrt(fMHz) + K2 * fMHz

# function CoaxLossA0(fMHz, K1, K2)    'Return loss factor in dB per hundred feet
#     CoaxLossA0=K1*Sqr(fMHz)+K2*fMHz
# end function
#

    @classmethod
    def CoaxLossAlpha(fMHz, K1, K2):
        return 0.001151 * (K1 * sqrt(fMHz) + K2 * fMHz)

# function CoaxLossAlpha(fMHz, K1, K2)    'Return loss factor in nepers/ft
#     CoaxLossAlpha=0.001151 *(K1*Sqr(fMHz)+K2*fMHz)
# end function
#
    @classmethod
    def CoaxBeta(fMHz, VF):
        if VF <= 0:
            return constMaxValue
        return 2 * pi * fMHz / (VF * 983.6)

# function CoaxBeta(fMHz, VF)    'Return beta, which is the number of radians/ft
#     if VF<=0 then CoaxBeta=constMaxValue : exit function 'ver115-4b
#     CoaxBeta=2*uPi()*fMHz/(VF*983.6)
# end function
#

    @classmethod
    def CoaxGetPropagationGamma(fMHz, VF, K1, K2):
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
    @classmethod
    def CoaxDelayDegrees(fMHz, VF, lenFeet):
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

    @classmethod
    def CoaxComplexZ0(fMHz, R, G, L, C):
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

    @classmethod
    def CoaxPropagationParams(Z0, fMHz, ac, ad, beta):
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

    @classmethod
    def CoaxComplexZ0Iterate(fMHz, VF, K1, K2, Z0):
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
        (R, G, L, C) = Coax.CoaxPropagationParams(Z0, fMHz, ac, ad, beta)
        Z0 = Coax.CoaxComplexZ0(fMHz, R, G, L, C, Z0)

        # Second iteration
        (R, G, L, C) = Coax.CoaxPropagationParams(Z0, fMHz, ac, ad, beta)
        Z0 = Coax.CoaxComplexZ0(fMHz, R, G, L, C, Z0)

        # Third iteration--needed only for low freq, or high loss at mid frequency
        # The loss thresholds below are just a bit under RG-174

        if (fMHz < 1) or (fMHz < 10 and (K1 > 0.6 or K2 > 0.03)):
            (R, G, L, C) = Coax.CoaxPropagationParams(Z0, fMHz, ac, ad, beta)
            Z0 = Coax.CoaxComplexZ0(fMHz, R, G, L, C, Z0)

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

    @classmethod
    def CoaxOpenZ(Z0, lenFeet, G):
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

    @classmethod
    def CoaxShortZ(Z0, lenFeet, G):
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

    @classmethod
    def CoaxTerminatedZ(Z0, Zt, lenFeet, G):
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

    @classmethod
    def CoaxTerminatedZFromName(coaxName, fMHz, Zt, lenFeet):
        (R0, VF, K1, K2) = Coax.GetData(coaxName)
        spec = Coax.CoaxSpec(R0, VF, K1, K2, lenFeet)
        return Coax.CoaxTerminatedZFromSpecs(spec, fMHz, Zt) # EON Jan 29, 2014

# sub CoaxTerminatedZFromName coaxName$, fMHz, ZtReal, ZtImag, lenFeet, byref ZReal, byref ZImag 'Calculate Z0 and then terminated Z value
#     call CoaxGetData coaxName$, R0, VF, K1, K2
#     spec$=CoaxSpecs$(R0, VF, K1, K2,lenFeet)  'put data into a coax spec
#     call CoaxTerminatedZFromSpecs spec$, fMHz, ZtReal, ZtImag, ZReal, ZImag
# end sub
#

    @staticmethod # EON Jan 29, 2014
    def CoaxTerminatedZFromSpecs(coaxSpecs, fMHz, Zt): # JGH 1/31/14
        (isErr, R0, VF, K1, K2, lenFeet) = Coax.CoaxParseSpecs(coaxSpecs)
        if isErr:
            return complex(0, 0) # EON Jan 29, 2014
        Z0 = complex(R0, 0) # EON Jan 29, 2014
        if fMHz <= 0:
            fMHz = 0.000001
        Z0 = Coax.CoaxComplexZ0Iterate(fMHz, VF, K1, K2, Z0) # EON Jan 29, 2014
        G = Coax.CoaxGetPropagationGamma(fMHz, VF, K1, K2)
        Z0 = Coax.CoaxTerminatedZ(Z0, Zt, lenFeet, G)
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
        return (1 / 2) * (D + cmath.sqrt(D * D + 4 * Z * ZL))

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

    @classmethod
    def CoaxPhaseDelayAndLossFromSpecs(coaxSpecs, fMHz):
        (isErr, R0, VF, K1, K2, lenFeet) = Coax.CoaxParseSpecs(coaxSpecs)
        if isErr:
            return True, 0, 0
        phase = Coax.CoaxDelayDegrees(fMHz, VF, lenFeet)
        lossDB = Coax.CoaxLossA0(fMHz, K1, K2) * lenFeet / 100
        return False, phase, lossDB

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

    @classmethod
    def CoaxS21(sysZ0, coaxZ0, GL):
        a = cmath.exp(GL) + cmath.exp(-GL)
        b = cmath.exp(GL) - cmath.exp(-GL)
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
        (isErr, R0, VF, K1, K2, lenFeet) = Coax.CoaxParseSpecs(coaxSpecs)
        if isErr:
            return 200, 0
        Z0 = complex(R0, 0)
        if fMHz <= 0:
            fMHz = 0.000001
        Z0 = Coax.CoaxComplexZ0Iterate(fMHz, VF, K1, K2, Z0)
        G = Coax.CoaxGetPropagationGamma(fMHz, VF, K1, K2)
        S21 = Coax.CoaxS21(sysZ0, Z0, G * lenFeet)
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

    @classmethod
    def CoaxSpec(R0, VF, K1, K2, lenFeet):
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
