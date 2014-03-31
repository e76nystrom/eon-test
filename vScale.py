from msaGlobal import GetMsa, isMac, SetModuleVersion
import wx
import copy as dcopy
from numpy import isfinite
from trace import traceTypesLists
from util import floatSI, si, SI_ASCII, StdScale

SetModuleVersion("vScale",("1.03","EON","03/15/2014"))

#==============================================================================
# The Vertical Scale Parameters dialog window.

class VScaleDialog(wx.Dialog):
    def __init__(self, specP, vScale, pos):
        self.specP = specP
        self.vScale = vScale
        self.prefs = specP.prefs
        units = vScale.dataType.units
        wx.Dialog.__init__(self, specP, -1, "Vert %s Scale" % units,
                            pos, wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        c = wx.ALIGN_CENTER
        chb = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM
        cvr = wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT

        # limits entry
        sizerV = wx.BoxSizer(wx.VERTICAL)
        sizerGB = wx.GridBagSizer(10, 8)
        st = wx.StaticText(self, -1, "Top Ref")
        sizerGB.Add(st, (0, 1), flag=cvr)
        self.topRefTC = tc = wx.TextCtrl(self, -1,
                            si(vScale.top, flags=SI_ASCII), size=(80, -1))
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        tc.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        sizerGB.Add(tc, (0, 2), flag=c)
        st = wx.StaticText(self, -1, "Bot Ref")
        sizerGB.Add(st, (1, 1), flag=cvr)
        self.botRefTC = tc = wx.TextCtrl(self, -1,
                            si(vScale.bot, flags=SI_ASCII), size=(80, -1))
        tc.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        tc.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        sizerGB.Add(tc, (1, 2), flag=c)
        btn = wx.Button(self, -1, "Auto Scale")
        btn.Bind(wx.EVT_BUTTON, self.OnAutoScale)
        sizerGB.Add(btn, (2, 2), flag=c)

        st = wx.StaticText(self, -1, "Divisions")
        sizerGB.Add(st, (3, 1), flag=cvr)
        choices = ("Auto","6","8","10","12")
        div = vScale.div
        if div == 0:
            i = 0
        else:
            for i in range(1, len(choices)):
                if div == int(choices[i]):
                    break
        cbox = wx.ComboBox(self, -1, choices[i], (0, 0), (80, -1), choices)
        cbox.SetStringSelection(choices[i])
        self.divSelCB = cbox
        self.Bind(wx.EVT_COMBOBOX, self.OnSelectDiv, cbox)
        sizerGB.Add(cbox, (3, 2), flag=c)

        # graph data select
        st = wx.StaticText(self, -1, "Graph Data")
        sizerGB.Add(st, (0, 4), flag=chb)
        typeList = traceTypesLists[GetMsa().mode]
        choices = [ty.desc for ty in typeList]
        i = min(vScale.typeIndex, len(choices)-1)
        cbox = wx.ComboBox(self, -1, choices[i], (0, 0), (200, -1), choices)
        cbox.SetStringSelection(choices[i])
        self.typeSelCB = cbox
        self.Bind(wx.EVT_COMBOBOX, self.OnSelectType, cbox)
        sizerGB.Add(cbox, (1, 4), flag=c)
        self.MaxHoldChk = chk = wx.CheckBox(self, -1, "Max Hold")
        chk.SetValue(vScale.maxHold)
        chk.Bind(wx.EVT_CHECKBOX ,self.OnMaxHold)
        sizerGB.Add(chk, (2, 4), flag=c)
        sizerGB.AddGrowableCol(3)

        # TODO: VScale primary trace entry
        # TODO: VScale priority entry
        sizerV.Add(sizerGB, 0, wx.EXPAND|wx.ALL, 20)

        # Cancel and OK buttons
        butSizer = wx.BoxSizer(wx.HORIZONTAL)
        butSizer.Add((0, 0), 0, wx.EXPAND)
        btn = wx.Button(self, wx.ID_CANCEL)
        butSizer.Add(btn, 0, wx.ALL, 5)
        btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        butSizer.Add(btn, 0, wx.ALL, 5)
        sizerV.Add(butSizer, 0, wx.ALIGN_RIGHT)

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if pos == wx.DefaultPosition:
            self.Center()

    #--------------------------------------------------------------------------
    # Update vert scale parameters from dialog.

    def Update(self):
        specP = self.specP
        vScale = self.vScale
        vScale.top = floatSI(self.topRefTC.GetValue())
        vScale.bot = floatSI(self.botRefTC.GetValue())
        specP.frame.DrawTraces()
        specP.FullRefresh()

    #--------------------------------------------------------------------------
    # Key focus changed.

    def OnSetFocus(self, event):
        if isMac:
            tc = event.GetEventObject()
            tc.SelectAll()
        event.Skip()

    def OnKillFocus(self, event):
        self.Update()
        event.Skip()

    #--------------------------------------------------------------------------
    # Auto Scale pressed- calculate new top, bottom values.

    def OnAutoScale(self, event):
        specP = self.specP
        vScale = self.vScale
        vScale.AutoScale(self.specP.frame)
        self.topRefTC.SetValue(si(vScale.top, flags=SI_ASCII))
        self.botRefTC.SetValue(si(vScale.bot, flags=SI_ASCII))
        specP.frame.DrawTraces()
        specP.FullRefresh()

    def OnMaxHold(self, event):
        specP = self.specP
        vScale = self.vScale
        vScale.maxHold = hold = self.MaxHoldChk.GetValue()
        name = vScale.dataType.name
        trace = specP.traces[name]
        trace.maxHold = hold
        trace.max = False

    #--------------------------------------------------------------------------
    # Number of divisions is selected

    def OnSelectDiv(self, event):
        vScale = self.vScale
        val = self.divSelCB.GetValue()

        if val == "Auto":
            val = 0
        else:
            val = int(val)

        if val != vScale.div:
            vScale.div = val
        self.Update()

    #--------------------------------------------------------------------------
    # A graph data type selected- if new, remember it and run auto scale.

    def OnSelectType(self, event):
        vScale = self.vScale
        i = self.typeSelCB.GetSelection()

        if i != vScale.typeIndex:
            # have chosen a new data type: perform auto-scale
            vScale.typeIndex = i
            vScale.dataType = dataType = traceTypesLists[GetMsa().mode][i]
            vScale.top = self.top = dataType.top
            vScale.bot = self.bot = dataType.bot
            if self.top == 0 and self.bot == 0:
                self.OnAutoScale(event)
            else:
                self.topRefTC.SetValue(si(self.top, flags=SI_ASCII))
                self.botRefTC.SetValue(si(self.bot, flags=SI_ASCII))
                self.Update()
        else:
            self.Update()

#==============================================================================
# A graph vertical axis scale.
# Each trace refers to one of these, and these in turn refer to one primary
# (or only) trace for their color. The scale is placed on either side of the
# graph, with higher-priority scales on the inside.

class VScale:
    def __init__(self, typeIndex, mode, top, bot, div, primeTraceUnits):
        self.typeIndex = typeIndex
        self.top = top
        self.bot = bot
        self.div = div
        self.maxHold = False
        self.primeTraceUnits = primeTraceUnits
        typeList = traceTypesLists[mode]
        self.dataType = typeList[min(typeIndex, len(typeList)-1)]

    #--------------------------------------------------------------------------
    # Perform auto-scale on limits to fit data.

    def AutoScale(self, frame, tr=None):
        dataType = self.dataType
        if dataType.units == "Deg":
            self.top = 180
            self.bot = -180
        elif self.typeIndex > 0:
            if tr == None:
                tr = dataType(frame.spectrum, 0)
            v = tr.v
            vmin = v[v.argmin()]
            vmax = v[v.argmax()]
            if isfinite(vmin) and isfinite(vmax) and vmax > vmin:
                print ("Auto scale: values from", vmin, "to", vmax)
                # round min/max to next even power
                ds, base, frac, nDiv = StdScale(vmin, vmax, 1., 1.)
                print ("Auto scale: ds=", ds, "base=", base, "frac=", \
                       frac, "nDiv=", nDiv)
                if isfinite(base) and isfinite(ds):
                    if frac == 0:
                        bot = base
                    else:
                        bot = base - ds
                    top = bot + ds*nDiv
                    if top < vmax:
                        top += ds
                else:
                    bot = tr.bot
                    top = tr.top
            else:
                bot = tr.bot
                top = tr.top
            self.top = top
            self.bot = bot

    #--------------------------------------------------------------------------
    # Open the Vertical Scale dialog box and apply to this scale.

    def Set(self, frame, pos):
        specP = frame.specP
        dlg = VScaleDialog(specP, self, pos)
        save = dcopy.copy(self)
        if dlg.ShowModal() == wx.ID_OK:
            dlg.Update()
        else:
            self.top = save.top
            self.bot = save.bot
            self.typeIndex = save.typeIndex
            self.dataType = save.dataType
            frame.DrawTraces()
            specP.FullRefresh()

