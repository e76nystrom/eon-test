from msaGlobal import appdir, GetMsa, SetModuleVersion
import os,wx
from util import gstr, Prefs

SetModuleVersion("testSetups",("1.30","EON","05/20/2014"))

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
            "fStop", "RBWSelindex", "isCentSpan", "isLogF", "continuous",
            "markerMode", "mode", "nSteps", "normRev", "planeExt", "rbw",
            "sigGenFreq", "spurTest", "sweepDir", "sweepRefresh", "tgOffset",
            "va0", "va1", "vb0", "vb1", "vFilterSelName", "wait")

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
            (GetMsa().shortModeNames[p.mode], ("Linear", "Log")[p.isLogF],
            p.fStart, p.fStop, p.RBWSelindex+1)
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
        msa = GetMsa()
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
        msa = GetMsa()
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
