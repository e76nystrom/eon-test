from msaGlobal import appdir, GetLO1, GetLO3, GetMsa, \
    isMac, isWin, SetModuleVersion
import os
import wx.grid
from util import gstr, mu

SetModuleVersion("configDialog",("1.02","EON","03/11/2014"))

#==============================================================================
# The MSA/VNA Configuration Manager dialog box (also modal) # JGH

class ConfigDialog(wx.Dialog): # JGH Heavily modified 1/20/14
    def __init__(self, frame):
        self.frame = frame
        self.prefs = p = frame.prefs
        msa = GetMsa()
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

        # PLL and DDS config
        sizerG1 = wx.GridBagSizer(hgap=10, vgap=2)  # Sizer for first column
        for i in range(3):
            text = wx.StaticText(self, -1, "PLL%d" % (i+1))
            text.SetFont(bigFont)
            sizerG1.Add(text, (0, i), flag=c)
        st = wx.StaticText(self, -1,  "-------------Type--------------" )
        sizerG1.Add(st, (1, 0), (1, 3), chbt, 5)
        st = wx.StaticText(self, -1, "---Is this a passive PLL Loop?---")
        sizerG1.Add(st, (3, 0), (1, 3), chbt, 5)
        st = wx.StaticText(self, -1, "------Phase frequency (MHz)------")
        sizerG1.Add(st, (5, 0), (1, 3), chbt, 5)
        st = wx.StaticText(self, -1, "DDS1----Center Freq (MHz)----DDS3")
        sizerG1.Add(st, (7, 0), (1, 3), chbt, 5)
        st = wx.StaticText(self, -1, "DDS1-----Bandwidth (MHz)------DDS3")
        sizerG1.Add(st, (9, 0), (1, 3), chbt, 5)

        csz = (95, -1) # JGH
        tsz = (95, -1) # JGH

        #JGH added . Modified 2/14/14
        pllTypeChoices = ["2325", "2326", "2350", "2353",\
                      "4112", "4113", "4118"]
        s = p.get("PLL1type", pllTypeChoices[1])   # Default value
        cmPLL1 = wx.ComboBox(self, -1, s, (0, 0), csz, choices=pllTypeChoices,
                             style=wx.CB_READONLY)
        cmPLL1.Enable(True)
        self.cmPLL1 = cmPLL1
        sizerG1.Add(cmPLL1, (2, 0), flag=c)

        s = p.get("PLL2type", pllTypeChoices[1])
        cmPLL2 = wx.ComboBox(self, -1, s, (0, 0), csz, choices=pllTypeChoices,
                             style=wx.CB_READONLY)
        cmPLL2.Enable(True)
        self.cmPLL2 = cmPLL2
        sizerG1.Add(cmPLL2, (2, 1), flag=c)

        s = p.get("PLL3type", pllTypeChoices[1])
        cmPLL3 = wx.ComboBox(self, -1, s, (0, 0), csz, choices=pllTypeChoices,
                             style=wx.CB_READONLY)
        cmPLL3.Enable(True)
        self.cmPLL3 =cmPLL3
        sizerG1.Add(cmPLL3, (2, 2), flag=c)

        pllPolInvChoices = [" 0 : No", " 1 : Yes"]
        s = p.get("PLL1phasepol", 0)
        s = pllPolInvChoices[s]
        cmPOL1 = wx.ComboBox(self, -1, s, (0, 0), csz,
                             choices=pllPolInvChoices, style=wx.CB_READONLY)
        cmPOL1.Enable(True)
        self.cmPOL1 = cmPOL1
        sizerG1.Add(cmPOL1, (4, 0), flag=c)

        s = p.get("PLL2phasepol", 1)
        s = pllPolInvChoices[s]
        cmPOL2 = wx.ComboBox(self, -1, s, (0, 0), csz,
                             choices=pllPolInvChoices, style=wx.CB_READONLY)
        cmPOL2.Enable(True)
        self.cmPOL2 = cmPOL2
        sizerG1.Add(cmPOL2, (4, 1), flag=c)

        s = p.get("PLL3phasepol", 0)
        s = pllPolInvChoices[s]
        cmPOL3 = wx.ComboBox(self, -1, s, (0, 0), csz,
                             choices=pllPolInvChoices, style=wx.CB_READONLY)
        cmPOL3.Enable(True)
        self.cmPOL3 = cmPOL3
        sizerG1.Add(cmPOL3, (4, 2), flag=c)

        s = p.get("PLL1phasefreq", 0.974)
        tcPhF1 = wx.TextCtrl(self, -1, gstr(s), size=tsz)
        tcPhF1.Enable(True)
        self.tcPhF1 = tcPhF1
        sizerG1.Add(tcPhF1, (6, 0), flag=c)

        s = p.get("PLL2phasefreq", 4.000) # JGH 2/15/14
        tcPhF2 = wx.TextCtrl(self, -1, gstr(s), size=tsz)
        tcPhF2.Enable(True)
        self.tcPhF2 = tcPhF2
        sizerG1.Add(tcPhF2, (6, 1), flag=c)

        s = p.get("PLL3phasefreq", 0.974)
        tcPhF3 = wx.TextCtrl(self, -1, gstr(s), size=tsz)
        tcPhF3.Enable(True)
        self.tcPhF3 = tcPhF3
        sizerG1.Add(tcPhF3, (6, 2), flag=c)

        # JGH 2/15/14: PLL mode no longer used

        cvl = wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_LEFT
        #cvr = wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT
        # JGH addition end

        tc = wx.TextCtrl(self, -1, gstr(GetLO1().appxdds), size=tsz) # JGH 2/2/14
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        tc.Enable(True)
        self.dds1CentFreqBox = tc
        sizerG1.Add(tc, (8, 0), flag=c)

        tc = wx.TextCtrl(self, -1, gstr(GetLO3().appxdds), size=tsz) # JGH 2/2/14
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        tc.Enable(True)
        self.dds3CentFreqBox = tc
        sizerG1.Add(tc, (8, 2), flag=c)

        tc = wx.TextCtrl(self, -1, gstr(GetLO1().ddsfilbw), size=tsz) # JGH 2/2/14
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        tc.Enable(True)
        self.dds1BWBox = tc
        sizerG1.Add(tc, (10, 0), flag=c)

        tc = wx.TextCtrl(self, -1, gstr(GetLO3().ddsfilbw), size=tsz) # JGH 2/2/14
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        tc.Enable(True)
        self.dds3BWBox = tc
        sizerG1.Add(tc, (10, 2), flag=c)


        st = wx.StaticText(self, -1, "DDS1 Parser")
        sizerG1.Add(st, (11, 0), (1, 1), chbt, 10)
        s = p.get("dds1Parser", "16bit serial")
        dds1Parser = wx.ComboBox(self, -1, s, (0, 0), csz, [s])
        dds1Parser.Enable(True)
        self.dds1Parser = dds1Parser
        sizerG1.Add(dds1Parser, (12, 0), flag=c)

        st = wx.StaticText(self, -1, "LO2 (MHz)")
        sizerG1.Add(st, (11, 1), (1, 1), chbt, 10)
        s = p.get("appxLO2", 1024)
        tc = wx.TextCtrl(self, -1, gstr(s), size=tsz) # JGH 2/2/14
        tc.Enable(True)
        self.appxLO2 = tc
        sizerG1.Add(tc, (12, 1), flag=c)

        st = wx.StaticText(self, -1, "Mast Clk (MHz)")
        sizerG1.Add(st, (11, 2), (1, 1), chbt, 10)
        s = p.get("masterclock", 64)
        mastClkBox = wx.TextCtrl(self, -1, gstr(s), size=tsz) # JGH 2/2/14
        mastClkBox.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        mastClkBox.Enable(True)
        self.mastClkBox = mastClkBox
        sizerG1.Add(mastClkBox, (12, 2), flag=c)

        st = wx.StaticText(self, -1,  "Max PDM out" )
        sizerG1.Add(st, (13, 0), (1, 1), chbt, 10)
        maxPDMout = wx.TextCtrl(self, -1, gstr(2**16-1), size=tsz) # JGH 2/2/14
        maxPDMout.Enable(True) # JGH changed to True
        self.maxPDMout = maxPDMout
        sizerG1.Add(maxPDMout, (14, 0), flag=c)

        st = wx.StaticText(self, -1,  "Sig Gen MHz" ) # JGH added 2/15/14
        sizerG1.Add(st, (13, 1), (1, 1), chbt, 10)
        sigGenBox = wx.TextCtrl(self, -1, gstr(msa._sgout), size=tsz)
        sigGenBox.Enable(True)
        self.sigGenBox = sigGenBox
        sizerG1.Add(sigGenBox, (14, 1), flag=c)

        st = wx.StaticText(self, -1,  "Inv Deg" )
        sizerG1.Add(st, (13, 2), (1, 1), chbt, 10)
        s = p.get("invDeg", 180)
        invDegBox = wx.TextCtrl(self, -1, gstr(s), size=tsz) # JGH 2/2/14
        invDegBox.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        invDegBox.Enable(True)
        self.invDegBox = invDegBox
        sizerG1.Add(invDegBox, (14, 2), flag=c)

        # Cancel and OK buttons

        self.helpBtn = btn = wx.Button(self, -1, "Help")
        btn.Bind(wx.EVT_BUTTON, self.OnHelp)
        sizerG1.Add(btn, (16,0), flag=c)
        btn = wx.Button(self, wx.ID_CANCEL)
        sizerG1.Add(btn, (16,1), flag=c)
        btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        sizerG1.Add(btn, (16,2), flag=c)

        sizerH0.Add(sizerG1, 0, wx.ALL, 10)
        sizerV2 = wx.BoxSizer(wx.VERTICAL) # DEFINE SECOND COLUMN SIZER
        sizerH2 = wx.BoxSizer(wx.HORIZONTAL)
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
        gr.EnableEditing(1)
        sizerV2A.Add(gr, 0, wx.ALIGN_CENTER) # JGH 1/28/14
##      The next two lines might be needed later
##        gr.Bind(wx.grid.EVT_GRID_SELECT_CELL, self.OnRBWCellSel)
##        gr.Bind(wx.grid.EVT_GRID_LABEL_LEFT_CLICK, self.OnRBWLabelSel)

        sizerH2.Add(sizerV2A, 0, wx.ALL|wx.EXPAND, 5)

        # Video Filters config

        self.vidFiltBoxTitle = \
            wx.StaticBox(self, -1, "Video Filters")
        sizerV2B = wx.StaticBoxSizer(self.vidFiltBoxTitle, wx.VERTICAL)

        colLabels = "(%sF)" % mu
        rowLabels = msa.vFilterNames
        self.gridVF = gv = wx.grid.Grid(self)
        gv.CreateGrid(4,1)
        for (i, uFcap) in enumerate(msa.vFilterCaps): # JGH 2/22/14
            gv.SetCellValue(i, 0, "%4.3f" % uFcap) # JGH 2/22/14
        gv.SetRowLabelSize(72)
        gv.SetDefaultColSize(64)
        gv.SetColLabelValue(0, colLabels)
        for row in range(4):
            gv.SetRowLabelValue(row, rowLabels[row])
        gv.SetDefaultCellAlignment(wx.ALIGN_RIGHT, wx.ALIGN_CENTRE)
        gv.EnableEditing(1)
        sizerV2B.Add(gv, 1, flag=cv)

        sizerH2.Add(sizerV2B, 0, wx.ALL|wx.EXPAND, 4)
        sizerV2.Add(sizerH2, 0)

        # Optional Modules
        optModsTitle = \
                wx.StaticBox(self, -1, "Optional Modules" ) #JGH 3/3/14
        sizerH3 = wx.StaticBoxSizer(optModsTitle, wx.HORIZONTAL)
        sizerV3A = wx.BoxSizer(wx.VERTICAL)
        st = wx.StaticText(self, -1, "Available Mods")
        sizerV3A.Add(st, 0, flag=c)
        availModList = wx.ListBox(self, -1, pos=wx.DefaultPosition, \
                                  size=(120,120), choices=['DUTatten', 'SyntDUT'], \
                                  style=wx.LB_ALWAYS_SB|wx.LB_SINGLE)
        sizerV3A.Add(availModList, 1, flag=c)
        sizerH3.Add(sizerV3A, 0)
        sizerV3B = wx.BoxSizer(wx.VERTICAL)
        mrBtn = wx.Button(self, -1, ">>")
        mrBtn.Bind(wx.EVT_BUTTON, self.OnMoveRight)
        sizerV3B.Add(mrBtn, 0, flag=c)
        mlBtn = wx.Button(self, -1, "<<")
        mlBtn.Bind(wx.EVT_BUTTON, self.OnMoveLeft)
        sizerV3B.Add(mlBtn, 0, flag=c)
        sizerH3.Add(sizerV3B, 1, flag=wx.ALIGN_CENTER_VERTICAL)
        sizerV3C = wx.BoxSizer(wx.VERTICAL)
        st = wx.StaticText(self, -1, "Imported Mods")
        sizerV3C.Add(st, 0, flag=c)
        importModList = wx.ListBox(self, -1, pos=wx.DefaultPosition, \
                                  size=(120,120), choices="", style=wx.LB_ALWAYS_SB|wx.LB_SINGLE)
        sizerV3C.Add(importModList, 1, flag=c)
        sizerH3.Add(sizerV3C, 2)
        sizerV2.Add(sizerH3, 0)
        
        # TOPOLOGY

        self.topologyBoxTitle = wx.StaticBox(self, -1, "Topology")
        sizerV2C = wx.StaticBoxSizer(self.topologyBoxTitle, wx.VERTICAL)

        sizerG2B = wx.GridBagSizer(hgap=4, vgap=2)
        cwsz = (120, -1)

        sizerG2B.Add(wx.StaticText(self, -1,  "ADC type" ), (0, 0), flag=cvl)
        ADCoptions = ["16bit serial", "12bit serial", "12bit ladder"]
        s = p.get("ADCtype", ADCoptions[0])
        cm = wx.ComboBox(self, -1, s, (0, 0), cwsz, style=wx.CB_READONLY)
        cm.Enable(True)
        self.ADCoptCM = cm
        sizerG2B.Add(cm, (0, 1), flag=cv)

        sizerG2B.Add(wx.StaticText(self, -1,  "Interface" ), (1, 0), flag=cvl)
        
        if isWin:
            CBoptions = ['LPT', 'USB', 'RPI', 'BBB']
            s = p.get("CBopt", CBoptions[1])
        else:
            CBoptions = ['USB', 'RPI', 'BBB'] # JGH 1/16/14
            s = p.get("CBopt", CBoptions[0])
        cm = wx.ComboBox(self, -1, s, (0, 0), cwsz, choices=CBoptions, style=wx.CB_READONLY)
        cm.Enable(True)
        sizerG2B.Add(cm, (1, 1), flag=cv)
        self.CBoptCM = cm
        sizerV2C.Add(sizerG2B, 0, wx.ALL, 5)

        sizerV2.Add(sizerV2C, 0, wx.ALL|wx.EXPAND, 4)
        sizerH0.Add(sizerV2, 0, wx.ALIGN_TOP)

        # JGH add end

        sizerV0.Add(sizerH0, 0, wx.ALL, 10)

        self.SetSizer(sizerV0)
        sizerV0.Fit(self)
        if pos == wx.DefaultPosition:
            self.Center()

    #--------------------------------------------------------------------------
    # Module directory
    def CreateModDir(self):
    
        directory = os.path.join(appdir, "MSA_Mods")
        if not os.path.exists(directory):
            os.makedirs(directory)
        return directory

    def OnMoveRight(self, event=None):
        pass

    def OnMoveLeft(self, event=None):
        pass

    def OnModOK(self, event=None):
        pass

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
