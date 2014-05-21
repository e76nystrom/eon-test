from msaGlobal import GetCb, GetMsa, isMac, SetModuleVersion
import wx
from msa import MSA
from util import CentSpanToStartStop, divSafe, floatOrEmpty, isNumber, mhzStr,\
    StartStopToCentSpan
from numKeypad import TextCtrl

SetModuleVersion("ddsUtils",("1.30","JGH","05/20/2014"))

#==============================================================================
# The Special Tests dialog box # JGH Substantial mod on 5/18/14

class ddsUtils(wx.Dialog):   # JGH 5/10/14

    def __init__(self, frame, util):
        global cb, msa
        cb = GetCb()
        msa = GetMsa()
        self.frame = frame
        self.prefs = p = frame.prefs
        self.mode = None
        framePos = frame.GetPosition()
        pos = p.get("DDStestsWinPos", (framePos.x + 100, framePos.y + 100))

        step = max(msa._step - 1, 0)
        fLimit = str(int(msa.masterclock/2))

        if util == 1:
            sv = float(msa.StepArray[step][1])
##            sv = str(GetLO1().appxdds)
            dialogTitle = "DDS1 Signal Generator"
            promptText = "Please enter the desired frequency (0 to " + fLimit + " MHz)"
            self.infoTitle = "Using DDS1 as a Signal Generator"
            self.infoText = "\n"\
            "DDS1 can be commanded to any frequency between 0 and 32 MHz (or 1/2 of the master oscillator frequency). "\
            "For example, the spare output of DDS1 could be used as a CW Signal Generator. "\
            "The 'Command DDS1'  box is populated with the value of the variable dds1output "\
            "and this value will depend on where the sweep was halted before entering this test window.\n\n"\
            "The desired frequency may be manually changed by highlighting and typing in a new value instead of the initial value. "\
            "The power level ia about -8 dBm. The frequency output is extremely stable, with very low phase noise. "\
            "However the harmonics and alias frequencies will extend well into the GHz range. "\
            "They too are extremely stable and can be used for a variety of laboratory experiments. "\
            "When a frequency is entered in the 'Command DDS1' box you may use as many decimal places as wanted, "\
            "but the DDS output frequency will be rounded off at 14.9 millihertz. "\
            "The DDS1 output frequency will remain at the new fixed frequency until the 'Restart' button is clicked, "\
            "even if this test window is closed. "\
            "Therefore, if the sweep is resumed by using the 'Continue' or 'One Step' buttons, "\
            "the DDS1 output frequency will remain at the fixed frequency and the sweep plot may be meaningless or not even there.\n\n"\
            "To revert to normal operation, close the " + dialogTitle + " window and click 'Restart'."

        elif util  == 2:
            sv = float(msa.StepArray[step][17])
##            sv = str(GetLO3().appxdds)
            dialogTitle = "DDS3 Signal Generator"
            promptText = "Please enter the desired frequency (0 to " + fLimit + " MHz)"
            self.infoTitle = "Using DDS3 as a Signal Generator"
            self.infoText = "\n"\
            "DDS3 can be commanded to any frequency between 0 and 32 MHz (or 1/2 of the master oscillator frequency). "\
            "Using DDS3 as an independent Signal Generator does not impact the operation of the spectrum Analyzer. \n\n"\
            "The 'Command DDS3'  box is populated with the value of the variable dds3output "\
            "and this value will depend on where the sweep was halted before entering this test window.\n\n"\
            "The desired frequency may be manually changed by highlighting and typing in a new value instead of the initial value. "\
            "The power level ia about -8 dBm. The frequency output is extremely stable, with very low phase noise. "\
            "However the harmonics and alias frequencies will extend well into the GHz range. "\
            "They too are extremely stable and can be used for a variety of laboratory experiments. "\
            "When a frequency is entered in the 'Command DDS3' box you may use as many decimal places as wanted, "\
            "but the DDS output frequency qill be rounded off at 14.9 millihertz. "\
            "The DDS3 output frequency will remain at the new fixed frequency until the 'Restart' button is clicked, "\
            "even if this test window is closed. "\
            "Therefore, if the sweep is resumed by using the 'Continue' or 'One Step' buttons, "\
            "the DDS3 output frequency will remain at the fixed frequency and the sweep plot may be meaningless or not even there.\n\n"\
            "To revert to normal operation, close the " + dialogTitle + " window and click 'Restart'."

        elif util == 3:
            sv = ""
            dialogTitle = "DDS3 Tracking Generator"
            promptText = "Please enter the desired frequency (0 to " + fLimit + " MHz)"
            self.infoTitle = "Using DDS3 as a Tracking Generator"
            self.infoText = "\n"\
            "Even if you have DDS3 already installed in the MSA, "\
            "sometimes is prudent to use the DDS3 in lieu of the normal TG and that "\
            "is why this Function was included in the software. "\
            "By clicking the Start button, the DDS3 will become a tracking generator "\
            "and the DDS3 output frequency will track the command frequency of the MSA. "\
            "It is limited to 0-32 MHz (that is 1/2 the frequency of the Master Oscillator). "\
            "The normal Tracking Generator output becomes non-functional when DDS3 is tracking. "\
            "The DDS3 output is available at J3, its spare output.\n\n"\
            "Follow these steps for proper operation:\n\n"\
            "Go back to the Sweep Parameters window, enter the wanted Center Frequency, "\
            "anywhere between 0 and 32 MHz. This will be not only the MSA Command frequency "\
            "but also de DDS3 output frequency. Enter the Sweep Width, "\
            "making sure you don't go below 0, nor above 1/2 the frequency of the Master Clock. "\
            "Click OK, Restart and the Halt the sweep. Select in the main menu Setup > DDS utilities "\
            "> DDS3 Tracking Generator. Click on the Start button."

        elif util == 4:
            sv = ""
            dialogTitle = "DDS1 Sweep Generator"
            promptText = "Please enter the desired frequency (0 to " + fLimit + " MHz)"
            self.infoTitle = "Using DDS1 as a Sweep Generator"
            self.infoText = "\n"\
            "DDS1 cn be used as an independent sweep generator between 0Hz and 32 MHz "\
            "(or 1/2 of the Master Oscillator frequency). "\
            "This is useful if only the Basic MSA is constructed and there is no MSA Tracking Generator. "\
            "The spare output of DDS1 power level is about -8 dBm. "\
            "If the normal MSA Tracking Generator is installed the TG output will remain functional during this special function. "\
            "Normal operation of the Spectrum Analyzer will become altered, "\
            "although some attributes are still functional such as the Log detector and ADC.\n\n"\
            "Follow these steps for proper operation:\n\n"\
            "Open the Sweep Parameters window, enter the wanted Center Frequency, "\
            "anywhere between 0 and 32 MHz. This will become the DDS1 Command frequency. "\
            "Enter the Sweep Width making sure you don't go below 0, nor above 1/2 the frequency of the Master Clock. "\
            "Click OK, Restart and the Halt the sweep. Click here the DDS1 Sweep Gen button. "\
            "DDS1 will immediately command command o the frequency that the MSA is halted at. "\
            "The MSA will resume sweeping when [OneStep] or [Continue] is pressed. "\
            "DDS1 will sweep, coinciding with the frequencies that are displayed. "\
            "If [Restart] is clicked, the MSA will revert to its normal Spectrum Analyzer operation. "\
            "Therefore, to maintain DDS1 as the sweeping Generator, the [DDS1 Sweep Gen.] button must be reclicked, "\
            "and then use only the [Continue] or [OneStep] buttons.\n\n"\
            "When finished with this special mode, close this window and click [Restart] to go back to normal."

        elif util == 5:
            dialogTitle = "Master Oscillator Calibartion"
            promptText = "Enter Master Osc Frequency and Test Frequency"
            self.infoTitle = "Calibrating Master Oscillator"
            self.infoText = "\n"\
                            ""
        else:
            print ("ddsUtils>125< Call not allowed")
            return

        wx.Dialog.__init__(self, frame, -1, dialogTitle, pos,
                           wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)

        c = wx.ALIGN_CENTER

        sizerV = wx.BoxSizer(wx.VERTICAL)

        st = wx.StaticText(self, -1, promptText)
        sizerV.Add(st, 0, c|wx.ALL, 5)

        if util <= 2:
            label = "Start"
            tc3 = TextCtrl(self, -1, str(sv), size=(100,-1))
            self.ddsFreqBox = tc3
            sizerV.Add(tc3, 0, c|wx.ALL, 5)
        elif util <= 4:
            # Cent-Span or Start-Stop frequency entry
            freqSizer = wx.GridBagSizer(2, 2)
            self.centSpanRB = rb = wx.RadioButton(self, -1, "", style= wx.RB_GROUP)
            self.Bind(wx.EVT_RADIOBUTTON, self.AdjFreqTextBoxes, rb)
            freqSizer.Add(rb, (0, 0), (2, 1), 0, 0)
            cl = wx.ALIGN_CENTER|wx.LEFT
            cr = wx.ALIGN_CENTER|wx.RIGHT
            freqSizer.Add(wx.StaticText(self, -1, "Cent"), (0, 1), (1, 1), 0, cr, 2)
            self.centBox = tc = TextCtrl(self, -1, "", size=(80, -1))
            freqSizer.Add(tc, (0, 2), (1, 1), 0, 0)
            self.Bind(wx.EVT_TEXT, self.AdjFreqTextBoxes, tc)
            freqSizer.Add(wx.StaticText(self, -1, "MHz"), (0, 3), (1, 1), 0, cl, 2)
            freqSizer.Add(wx.StaticText(self, -1, "Span"), (1, 1), (1, 1), cr, 2)
            self.spanBox = tc = TextCtrl(self, -1, "", size=(80, -1))
            freqSizer.Add(tc, (1, 2), (1, 1), 0, 0)
            self.Bind(wx.EVT_TEXT, self.AdjFreqTextBoxes, tc)
            freqSizer.Add(wx.StaticText(self, -1, "MHz"), (1, 3), (1, 1), cl, 2)
            self.startstopRB = rb = wx.RadioButton(self, -1, "")
            self.Bind(wx.EVT_RADIOBUTTON, self.AdjFreqTextBoxes, rb)
            freqSizer.Add(rb, (0, 4), (2, 1), wx.LEFT, 5)
            freqSizer.Add(wx.StaticText(self, -1, "Start"), (0, 5), (1, 1), 0,cr, 2)
            self.startBox = tc = TextCtrl(self, -1, "", size=(80, -1))
            freqSizer.Add(tc, (0, 6), (1, 1), 0, 0)
            self.Bind(wx.EVT_TEXT, self.AdjFreqTextBoxes, tc)
            freqSizer.Add(wx.StaticText(self, -1, "MHz"), (0, 7), (1, 1), 0, cl, 2)
            freqSizer.Add(wx.StaticText(self, -1, "Stop"), (1, 5), (1, 1), 0, cr, 2)
            self.stopBox = tc = TextCtrl(self, -1, "", size=(80, -1))
            freqSizer.Add(tc, (1, 6), (1, 1), 0, 0)
            self.Bind(wx.EVT_TEXT, self.AdjFreqTextBoxes, tc)
            freqSizer.Add(wx.StaticText(self, -1, "MHz"), (1, 7), (1, 1), 0, cl, 2)
            sizerV.Add(freqSizer, 0, c|wx.ALL, 5)

            # Cent-Span or Start-Stop frequency entry
            self.skip = True
            isCentSpan = p.get("isCentSpan", True)
            self.centSpanRB.SetValue(isCentSpan)
            fCent, fSpan = StartStopToCentSpan(p.fStart, p.fStop, p.isLogF)
            self.centBox.SetValue(mhzStr(fCent))
            self.spanBox.SetValue(mhzStr(fSpan))
            self.startstopRB.SetValue(not isCentSpan)
            self.startBox.SetValue(str(p.fStart))
            self.stopBox.SetValue(str(p.fStop))
            self.skip = False
            self.AdjFreqTextBoxes()
            
            if util == 3:
                label = "DDS3 Track Gen"
                self.dds3TrackChk = chk = wx.CheckBox(self, -1, "DDS 3 Track")
                chk.SetValue(msa.dds3Track)
                chk.Bind(wx.EVT_CHECKBOX, self.DDS3Track)
            elif util == 4:
                label = "DDS1 Sweep Gen"
                self.dds1SweepChk = chk = wx.CheckBox(self, -1, "DDS 1 Sweep")
                chk.SetValue(msa.dds1Sweep)
                chk.Bind(wx.EVT_CHECKBOX, self.DDS1Sweep)
            sizerV.Add(chk, 0, c|wx.ALL, 5)
        elif util == 5:
            label = "Start"
            cr = wx.ALIGN_CENTER|wx.RIGHT
            gbSizer = wx.GridBagSizer(5, 5)
            gbSizer.Add(wx.StaticText(self, -1, "Master Osc"), (0, 0), (1, 1), 0, cr, 2)
            self.mastOscBox = tc = TextCtrl(self, -1, "", size=(80, -1))
            tc.SetValue(str(msa.masterclock))
            gbSizer.Add(tc, (0, 1), (1, 1), 0, 0)
            gbSizer.Add(wx.StaticText(self, -1, "DDS 1"), (1, 0), (1, 1), 0, cr, 2)
            self.dds1Box = tc = TextCtrl(self, -1, "", size=(80, -1))
            tc.SetValue("10.0")
            gbSizer.Add(tc, (1, 1), (1, 1), 0, 0)
            gbSizer.Add(wx.StaticText(self, -1, "DDS 3"), (2, 0), (1, 1), 0, cr, 2)
            self.dds3Box = tc = TextCtrl(self, -1, "", size=(80, -1))
            tc.SetValue("10.0")
            gbSizer.Add(tc, (2, 1), (1, 1), 0, 0)
            sizerV.Add(gbSizer, 0, c|wx.ALL, 5)

        sizerH2 = wx.BoxSizer(wx.HORIZONTAL)
        btn = wx.Button(self, 0, "Info")
        btn.Bind(wx.EVT_BUTTON, self.showInfo)
        sizerH2.Add(btn, 0, c|wx.ALL, 5)

        btn = wx.Button(self, 0, "Close")
        btn.Bind(wx.EVT_BUTTON, self.ddsClose)
        sizerH2.Add(btn, 1, c|wx.ALL, 5)

        btn = wx.Button(self, 0, label)
        btn.Bind(wx.EVT_BUTTON, self.ddsStart)
        sizerH2.Add(btn, 2, c|wx.ALL, 5)

        sizerV.Add(sizerH2, 0, wx.ALL|wx.CENTER)
        self.SetSizer(sizerV)
        self.Layout()

        self.util = util
        self.Bind(wx.EVT_CLOSE, self.ddsClose)
        self.SetSizerAndFit(sizerV)

    def AdjFreqTextBoxes(self, event=None, final=False):
        if event and self.skip:
            return
        p = self.prefs
        isLogF = p.isLogF
        isCentSpan = self.centSpanRB.GetValue()
        self.centBox.Enable(isCentSpan)
        self.spanBox.Enable(isCentSpan)
        self.startBox.Enable(not isCentSpan)
        self.stopBox.Enable(not isCentSpan)

        if isCentSpan:
            fCent = floatOrEmpty(self.centBox.GetValue())
            fSpan = floatOrEmpty(self.spanBox.GetValue())
            if final and fSpan < 0:
                fSpan = 0
                self.spanBox.ChangeValue(mhzStr(fSpan))
            fStart, fStop = CentSpanToStartStop(fCent, fSpan, isLogF)
            self.startBox.ChangeValue(mhzStr(fStart))
            self.stopBox.ChangeValue(mhzStr(fStop))
        else:
            fStart = floatOrEmpty(self.startBox.GetValue())
            fStop = floatOrEmpty(self.stopBox.GetValue())
            if final and fStop < fStart:
                fStart, fStop = fStop, fStart
                self.stopBox.ChangeValue(mhzStr(fStop))
                self.startBox.ChangeValue(mhzStr(fStart))
            fCent, fSpan = StartStopToCentSpan(fStart, fStop, isLogF)
            self.centBox.ChangeValue(mhzStr(fCent))
            self.spanBox.ChangeValue(mhzStr(fSpan))

    def ChangePDM(self, event):  #TODO
        pass

    def DDS3Track(self, event=None):
        global msa
        msa.dds3Track = self.dds3TrackChk.GetValue()

    def DDS1Sweep(self, event=None):
        global msa
        msa.dds1Sweep = self.dds1SweepChk.GetValue()

    def ddsStart(self, event=None):
        global cb
        self.frame.StopScanAndWait()
        if self.util <= 2:
            freq = self.ddsFreqBox.GetValue()
            print("ddsUtils>219< freq:", freq)
            freq = isNumber(freq)
            if freq == None: 
                self.showError("Frequency is not a valid numeric value!")
                return
            else:
                if freq < 0 or freq > float(msa.masterclock/2):
                    self.showError("Frequency is out of bounds!")
                    return
                # Set DDS to entered frequency
                if self.util == 1:
                    self.setDDS(freq, cb.P1_DDS1DataBit, cb.P2_fqud1)
                elif self.util == 2:
                    self.setDDS(freq, cb.P1_DDS3DataBit, cb.P2_fqud3)

        elif self.util <= 4:
            self.AdjFreqTextBoxes(final=True)
            fStart = floatOrEmpty(self.startBox.GetValue())
            fStop = floatOrEmpty(self.stopBox.GetValue())
            if fStart <= 0 or fStart > msa.masterclock/2:
                self.showError("Start frequency out of range.")
                return
            if fStop <= 0 or fStop > msa.masterclock/2:
                self.showError("Stop frequency out of range.")
                return
            self.prefs.fStart = fStart
            self.prefs.fStop = fStop
            self.frame.SetSweep()
        elif self.util <= 5:
            freq = isNumber(self.mastOscBox.GetValue())
            if not freq:
                self.showError("Masterclock frequency is not a valid number.")
                return
            msa.masterclock = freq
            self.prefs.masterclock = "%9.6f" % freq
            freq1 = isNumber(self.dds1Box.GetValue())
            if not freq1:
                self.showError("Frequency of DDS 1 is not a valid number.")
                return
            freq3 = isNumber(self.dds3Box.GetValue())
            if not freq3:
                self.showError("Frequency of DDS 3 is not a valid number.")
                return
            self.setDDS(freq1, cb.P1_DDS1DataBit, cb.P2_fqud1)
            self.setDDS(freq3, cb.P1_DDS3DataBit, cb.P2_fqud3)

    def showError(self, errorMsg):
        error = wx.MessageDialog(None, errorMsg, "ERROR", wx.OK|wx.ICON_ERROR|wx.STAY_ON_TOP)
        retCode = error.ShowModal()
        if (retCode == wx.ID_OK):
            error.Destroy()

    def showInfo(self, infoText):
        wx.MessageBox(self.infoText, self.infoTitle, wx.CANCEL)

    def ddsClose(self, event=None):
        p = self.prefs
        p.DDStestsWinPos = self.GetPosition().Get()
        self.Destroy()

#--------------------------------------------------------------------------

    def setDDS(self, freq, P1_DDSDataBit, P2_fqud):
        global cb, msa
##        ddsclock = float(self.masterclockBox.GetValue()) # JGH 5/10/14 3 lines
##        print ("ddsUtils>258< msa.masterclock: ", msa.masterclock)
        base = int(round(divSafe(freq * (1<<32), msa.masterclock)))
##        base = int(round(divSafe(freq * (1<<32), ddsclock)))
##        print ("ddsUtils>261< base %8x" % base)
        DDSbits = base << P1_DDSDataBit
##        print ("ddsUtils>263< DDSbits: ", DDSbits)
        byteList = []
        P1_DDSData = 1 << P1_DDSDataBit
##        print ("ddsUtils>266< P1_DDSData: ", P1_DDSData)
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
