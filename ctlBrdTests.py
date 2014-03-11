from msaGlobal import GetCb, SetModuleVersion
import wx

SetModuleVersion("ctlBrdTests",("1.02","EON","03/11/2014"))

#==============================================================================
# The Control Board Tests modeless dialog window.

class CtlBrdTests(wx.Dialog):
    def __init__(self, frame):
        self.frame = frame
        self.mode = None
        self.modeCtrls = []
        self.prefs = p = frame.prefs
        #framePos = frame.GetPosition() # JGH (framePos not used)
        pos = p.get("ctlBrdWinPos", wx.DefaultPosition)
        wx.Dialog.__init__(self, frame, -1, "Control Board Tests", pos,
                           wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        c = wx.ALIGN_CENTER
        lcv = wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL
        ctlPins = (("17 Sel(L1)", 1), ("16 Init(L2)", 2),
                   ("14 Auto(L3)", 4), ("1 Strobe(L4)", 8))
        dataPins = (("2 D0", 0x01), ("3 D1", 0x02),
                    ("4 D2", 0x04), ("5 D3", 0x08),
                    ("6 D4", 0x10), ("7 D5", 0x20),
                    ("8 D6", 0x40), ("9 D7", 0x80))
        inputPins = (("11 Wait", 0x10), ("10 Ack", 0x08), ("12 PE", 0x04),
                     ("13 Select", 0x02), ("15 Error", 0x01))

        sizerH = wx.BoxSizer(wx.HORIZONTAL)

        sizerGB = wx.GridBagSizer(5,5)
        self.ctlByte = 0
        i = 0;
        for (label, mask) in ctlPins:
            btn = TestBtn(self, mask, False)
            sizerGB.Add(btn, (i, 0), flag=c)
            text = wx.StaticText(self, 0, "Pin " + label)
            sizerGB.Add(text, (i, 1), flag=lcv)
            i += 1

        self.dataByte = 0
        for (label, mask) in dataPins:
            btn = TestBtn(self, mask, True)
            sizerGB.Add(btn, (i, 0), flag=c)
            text = wx.StaticText(self, 0, "Pin " + label)
            sizerGB.Add(text, (i, 1), flag=lcv)
            i += 1
        sizerH.Add(sizerGB, 0, c|wx.ALL, 10)

        sizerGB = wx.GridBagSizer(5,5)
        btn = wx.Button(self, 0, "Capture Status")
        btn.Bind(wx.EVT_BUTTON, self.readStatus)
        sizerGB.Add(btn, (0,0), flag=c, span=(1,2))
        i = 1;
        self.inputData = []
        ts = wx.BORDER_SIMPLE|wx.ST_NO_AUTORESIZE|wx.ALIGN_CENTRE
        for (label, mask) in inputPins:
            text = wx.StaticText(self, 0, " ", size=(20,20), style=ts)
            self.inputData.append(text)
            sizerGB.Add(text, (i, 0), flag=c)
            text = wx.StaticText(self, 0, "Pin " + label)
            sizerGB.Add(text, (i, 1), flag=lcv)
            i += 1
        sizerH.Add(sizerGB, 0, wx.ALIGN_TOP|wx.ALL, 10)
        self.inputData.reverse()

        self.SetSizer(sizerH)
        sizerH.Fit(self)
        self.Bind(wx.EVT_CLOSE, self.Close)

    def Close(self, event=None):
        p = self.prefs
        p.ctlBrdWinPos = self.GetPosition().Get()
        self.Destroy()

    def readStatus(self,event):
        cb = GetCb()
        inp = cb.ReadStatus()
        for text in self.inputData:
            val = ("0","1")[inp & 1]
            text.SetLabel(val)
            inp >>= 1

class TestBtn(wx.Button):
    def __init__(self, parent, mask, data):
        self.mask = mask
        self.data = data
        self.parent = parent
        wx.Button.__init__(self,parent, 0, "0", size=(30,20))
        self.Bind(wx.EVT_BUTTON, self.toggleBit)

    def toggleBit(self, event):
        val = self.GetLabel()
        if val == "0":
            self.SetLabel("1")
            self.updateBit(True)
        else:
            self.SetLabel("0")
            self.updateBit(False)

    def updateBit(self,state):
        cb = GetCb()
        if self.data:
            if state:
                self.parent.dataByte |= self.mask
            else:
                self.parent.dataByte &= ~self.mask
            cb.OutPort(self.parent.dataByte)
        else:
            if state:
                self.parent.ctlByte |= self.mask
            else:
                self.parent.ctlByte &= ~self.mask
            cb.OutControl(self.parent.ctlByte ^ cb.contclear)
        cb.Flush()

