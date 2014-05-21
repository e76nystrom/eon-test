from msaGlobal import GetCb, GetMsa, GetLO1, GetLO3, SetModuleVersion
import wx
from msa import MSA
from util import divSafe

SetModuleVersion("ddsTest",("1.30","EON","05/20/2014"))

#==============================================================================
# The Special Tests dialog box # JGH Substantial mod on 1/25/14

class DDSTests(wx.Dialog):   # EON 12/22/13

    def __init__(self, frame):
        global cb, msa
        cb = GetCb()
        msa = GetMsa()
        self.frame = frame
        self.prefs = p = frame.prefs
        self.mode = None
        framePos = frame.GetPosition()
        pos = p.get("DDStestsWinPos", (framePos.x + 100, framePos.y + 100))
        wx.Dialog.__init__(self, frame, -1, "DDS Tests", pos,
                           wx.DefaultSize, wx.DEFAULT_DIALOG_STYLE)
        tsz = (100, -1)

        c = wx.ALIGN_CENTER
        sizerV = wx.BoxSizer(wx.VERTICAL)
        st = wx.StaticText(self, -1, \
        "The 'Set DDS1' box (#special.dds1out) is populated with the value of " \
        "the variable DDS1array(thisstep,46). The 'with DDS Clock at' box " \
        "(#special.masclkf) is populated with the value of the variable, masterclock. " \
        "The 'Set DDS3' box (#special.dds3out) is populated with the value of " \
        "the variable, DDS3array(thisstep,46).\n" \
        "The DDS clock is 'masterclock' and will always be the 64.xyzabc MHz that " \
        "was inserted in the Hardware Configuration Manager Window.\n" \
        "The DDS1 and DDS3 frequencies will depend on where the sweep was halted " \
        "before entering the DDS Tests Window. \n" \
        "All 3 boxes can be manually changed by highlighting and typing in a new value. " \
        "Clicking the Set DDS1 button will update the DDS1 box AND the masterclock. " \
        "Clicking the Set DDS3 button will update the DDS3 box AND the masterclock.\n" \
        "NOTE: The 'with DDS Clock at' box currently displays only 5 digits to " \
        "the right of the decimal. It really needs to be at least 6 for 1 Hz resolution. ")

        st.Wrap(600)
        sizerV.Add(st, 0, c|wx.ALL, 10)

        sizerGB = wx.GridBagSizer(5,5)

        # MSA Mode selection
        btn = wx.Button(self, 0, "Set DDS1")
        btn.Bind(wx.EVT_BUTTON, self.setDDS1)
        sizerGB.Add(btn,(0,0), flag=c)
        tc = wx.TextCtrl(self, 0, str(GetLO1().appxdds), size=tsz)
        self.dds1FreqBox = tc
        sizerGB.Add(tc,(0,1), flag=c)

        text = wx.StaticText(self, 0, " with DDS Clock at: ")
        sizerGB.Add(text,(1,0), flag=c)
        tc = wx.TextCtrl(self, 0, str(msa.masterclock), size=tsz)
        self.masterclockBox = tc;
        sizerGB.Add(tc,(1,1), flag=c)

        btn = wx.Button(self, 0, "Set DDS3")
        btn.Bind(wx.EVT_BUTTON, self.setDDS3)
        sizerGB.Add(btn,(2,0), flag=c)
        tc = wx.TextCtrl(self, 0, str(GetLO3().appxdds), size=tsz)
        self.dds3FreqBox = tc
        sizerGB.Add(tc,(2,1), flag=c)

        self.dds3TrackChk = chk = wx.CheckBox(self, -1, "DDS 3 Track")
        chk.SetValue(p.get("dds3Track",False))
        chk.Bind(wx.EVT_CHECKBOX, self.DDS3Track)
        sizerGB.Add(chk,(3,0), flag=c)

        self.dds1SweepChk = chk = wx.CheckBox(self, -1, "DDS 1 Sweep")
        chk.SetValue(p.get("dds1Sweep",False))
        chk.Bind(wx.EVT_CHECKBOX, self.DDS1Sweep)
        sizerGB.Add(chk,(3,1), flag=c)

        # VNA Mode selection

        if msa.mode >= MSA.MODE_VNATran:
            btn = wx.Button(self, 0, "Change PDM")
            btn.Bind(wx.EVT_BUTTON, self.ChangePDM)
            sizerGB.Add(btn,(5,0), flag=c)

        sizerV.Add(sizerGB, 0, c|wx.ALL, 10)
        self.SetSizer(sizerV)
        sizerV.Fit(self)

        self.Bind(wx.EVT_CLOSE, self.Close)

    def DDS3Track(self, event=None):
        self.prefs.dds3Track = self.dds3TrackChk.GetValue()

    def DDS1Sweep(self, event=None):
        self.prefs.dds1Sweep = self.dds1SweepChk.GetValue()

    def ChangePDM(self, event):  #TODO
        pass


    def Close(self, event=None):
        p = self.prefs
        p.DDStestsWinPos = self.GetPosition().Get()
        self.Destroy()

#--------------------------------------------------------------------------
    # Set DDS to entered frequency

    def setDDS1(self, event):
        global cb
        freq = float(self.dds1FreqBox.GetValue())
        print (">>>13796<<< freq: ", freq)
        self.setDDS(freq, cb.P1_DDS1DataBit, cb.P2_fqud1)

    def setDDS3(self, event):
        global cb
        freq = float(self.dds3FreqBox.GetValue())
        self.setDDS(freq, cb.P1_DDS3DataBit, cb.P2_fqud3)

    def setDDS(self, freq, P1_DDSDataBit, P2_fqud):
        global cb, msa
##        ddsclock = float(self.masterclockBox.GetValue()) # JGH 2/2/14 3 lines
        print (">>>13805<<< msa.masterclock: ", msa.masterclock)
        base = int(round(divSafe(freq * (1<<32), msa.masterclock)))
        print (">>>13807<<< base: ", base)
        DDSbits = base << P1_DDSDataBit
        print (">>>13809<<< DDSbits: ", DDSbits)
        byteList = []
        P1_DDSData = 1 << P1_DDSDataBit
        print (">>>13812<<< P1_DDSData: ", P1_DDSData)
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
