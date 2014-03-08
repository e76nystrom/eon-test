from msaGlobal import appdir, GetFontSize, GetMsa, isMac, SetModuleVersion
import string, os, time, wx
from numpy import isnan
from util import gstr, ShouldntOverwrite
from StringIO import StringIO

SetModuleVersion(__name__,("1.01","03/07/2014"))

CalVersion = "1.03" # compatible version of calibration files

#==============================================================================
# The Calibration File Manager dialog box.

class CalManDialog(wx.Dialog):
    def __init__(self, frame):
        self.frame = frame
        global msa
        msa = GetMsa()
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
        tc.SetFont(wx.Font(GetFontSize()*1.2, wx.TELETYPE, wx.NORMAL, wx.NORMAL))
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
        #lc = self.filesListCtrl
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
        global msa
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
