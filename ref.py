from msaGlobal import GetMsa, SetModuleVersion
import wx
import copy as dcopy
import wx.lib.colourselect as csel
from numpy import zeros
from util import floatOrEmpty
from msa import MSA
from spectrum import Spectrum

SetModuleVersion("ref",("1.02","EON","03/11/2014"))

debug = False

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
        global msa
        msa = GetMsa()
        if msa.mode >= MSA.MODE_VNATran:
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

        if msa.mode >= MSA.MODE_VNATran:
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
        btn.Bind(wx.EVT_BUTTON, self.OnOk)
#        btn.SetDefault()
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
        msa = GetMsa()
        if msa.mode >= MSA.MODE_VNATran:
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

    def OnOk(self, event):
        global msa
        frame = self.frame
        mode = self.mode
        refNum = self.refNum
        if mode == 0:
            # delete it
            if frame.refs.has_key(refNum):
                frame.refs.pop(refNum)
        else:
            # create a new ref from current data
            spec = frame.spectrum
            vScales = frame.specP.vScales
            # get the units from both vertical scales
            bothU = [vs.dataType.units for vs in vScales]
            print ("bothU=", bothU)
            for i in range(2):
                vScale = vScales[i]
                # create a ref for each axis, unless the axes are
                # (db, Deg), in which case we create one ref with both
                if not (self.traceEns[i]) or \
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
                                     floatOrEmpty(self.valueABox.GetValue())
                    if msa.mode >= MSA.MODE_VNATran:
                        rsp.Sdeg = zeros(n) + \
                                     floatOrEmpty(self.valueBBox.GetValue())
                # assign trace width(s), name, and math mode
                ref.name = self.nameBox.GetValue()
                ref.aWidth = int(self.widthACB.GetValue())
                if msa.mode >= MSA.MODE_VNATran:
                    # ref for axis 0 may be both mag and phase traces
                    ref.bWidth = int(self.widthBCB.GetValue())
                if ref.name == "":
                    ref.name = "R%d" % refNum
                frame.refs[refNum] = ref
                if refNum == 1:
                    ref.mathMode = self.graphOptRB.GetSelection()
        self.Hide()
