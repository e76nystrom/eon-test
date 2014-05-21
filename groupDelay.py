from msaGlobal import SetModuleVersion
import wx
from util import message
from msa import MSA
from functionDialog import FunctionDialog
from trace import GroupDelayTrace, traceTypesLists

SetModuleVersion("coax",("1.30","EON","05/20/2014"))

class GroupDelayDialog(FunctionDialog):
    def __init__(self, frame):
        FunctionDialog.__init__(self, frame, "Group Delay", "grpDly")

        self.sizerV = sizerV = wx.BoxSizer(wx.VERTICAL)
        c = wx.ALIGN_CENTER

        self.helpText = \
        "Especially when passing signals through a filter, it is sometimes "\
        "desirable for group delay to be fairly constant.  In that case, "\
        "group delay represents the delay, in seconds, of the envelope of a "\
        "signal.  When group delay is not constant, the envelope will "\
        "become distorted, though in the non-constant situation it is not "\
        "possible to attribute a simple meaning to the group delay at each "\
        "frequency. For example, when group delay varies a lot it may "\
        "actually become negative, which does not really indicate that the "\
        "envelope leaves before it arrives.\n\n"\
        "Using a larger number of points for the calculation can smooth out "\
        "erratic behavior caused by noise, but can cause errors where the "\
        "true group delay is changing rapidly. But a large number of "\
        "points may be useful when group delay is fairly constant, which "\
        "is usually the circumstance of greatest interest."

        text = \
        "This function will create a graph of group delay from the current "\
        "S21 data. Group delay is the negative of the slope of phase over "\
        "frequency. This change can be erratic from point to point, so the "\
        "average of the slope is used over a series of points."
        st = wx.StaticText(self, -1, text)
        st.Wrap(400)
        sizerV.Add(st, 0, c|wx.ALL, 10)

        sizerH0 = wx.BoxSizer(wx.HORIZONTAL)
        text = "Number of points to include in slope calculations (2-25)"
        st = wx.StaticText(self, -1, text)
        sizerH0.Add(st, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 2)
        self.pointsBox = tc = wx.TextCtrl(self, -1, "5", size=(40, -1))
        sizerH0.Add(tc, 0, wx.ALL, 2)

        sizerV.Add(sizerH0, 0, c|wx.ALL, 2)

        sizerH1 = wx.BoxSizer(wx.HORIZONTAL)
        self.analyzeBtn = btn = wx.Button(self, -1, "Analyze")
        btn.Bind(wx.EVT_BUTTON, self.OnAnalyze)
        sizerH1.Add(btn, 0, wx.ALL, 2)
        btn = wx.Button(self, -1, "Help")
        btn.Bind(wx.EVT_BUTTON, self.OnHelpBtn)
        sizerH1.Add(btn, 0, wx.ALL, 2)

        sizerV.Add(sizerH1, 0, wx.EXPAND|wx.ALL, 10)

        self.SetSizer(sizerV)
        sizerV.Fit(self)
        if self.pos == wx.DefaultPosition:
            self.Center()
        self.Show()
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.gdTrace = None
        self.oldIndex = None

    def OnAnalyze(self, event):
        frame = self.frame
        msa = frame.msa
        msa.haltAtEnd = True
        if msa.IsScanning():
            frame.WaitForStop()
        specP = frame.specP
        nPoints = int(self.pointsBox.GetValue());
        if self.gdTrace:
            self.gdTrace.calcGd(nPoints)
            specP.FullRefresh()
            return

        trace = None
        for name in specP.traces:
            if "deg" in name.lower():
                trace = specP.traces[name]
                break
        if not trace:
            message("no phase trace")
            return

        scaleIndex = 0
        for scale in specP.vScales:
            if name == scale.dataType.name:
                break;
            scaleIndex += 1

        self.vs = vs = specP.vScales[scaleIndex]
        self.oldDataType = vs.dataType
        vs.dataType = dataType = GroupDelayTrace
        typeIndex = 0
        for trcType in traceTypesLists[MSA.MODE_VNATran]:
            if trcType == dataType:
                break;
            typeIndex = typeIndex + 1;

        spec = frame.spectrum

        self.gdTrace = gdTrace = dataType(spec, scaleIndex, nPoints)

        self.oldIndex = vs.typeIndex
        vs.typeIndex = typeIndex
        vs.top = dataType.top
        vs.bot = dataType.bot
        vs.primeTraceUnits = dataType.units
        vs.AutoScale(frame, gdTrace)

        if scaleIndex == 0:
            spec.vaType = dataType
            spec.trva = gdTrace
        else:
            spec.vbType = dataType
            spec.trvb = gdTrace

        frame.DrawTraces()
        specP.FullRefresh()

    def OnClose(self, event):
        if self.oldIndex != None:
            frame = self.frame
            vs = self.vs
            vs.typeIndex = self.oldIndex
            vs.dataType = dataType = self.oldDataType
            vs.top = dataType.top
            vs.bot = dataType.bot
            vs.primeTraceUnits = dataType.units
            frame.needRestart = True
            frame.DrawTraces()
            frame.specP.FullRefresh()
        super(GroupDelayDialog, self).OnClose(event)

#[GDAnalyze] 'button has been pushed to calculate group delay
#
#    #functGD.Analyze, "!disable" : #functGD.Help, "!disable"
#    #functGD.nPoints, "!contents? nPoints$"
#    nPoints=val(nPoints$)
#    if nPoints<2 or nPoints>pCount/4 then
#        nPoints=defPoints : #functGD.nPoints, nPoints
#        notice "Invalid number of points. ";defPoints;" used."
#    end if
#    GDLastNumPoints=nPoints 'save for next time we enter this dialog
#    call ClearAuxData   'Clear auxiliary graph data by blanking graph names
#    call gGetMinMaxPointNum pMin, pMax
#    for i=0 to pMin-1 : auxGraphData(i,0)=0 : next i    'Clear unused points
#    for i=pMax+1 to globalSteps : auxGraphData(i,0)=0 : next i    'Clear unused points
#    maxGD=0 : minGD=0
#    nLeft=int(nPoints/2)    'Number of points left of analyzed point to use for slope; total is nPoints
#    for i=pMin-1 to pMax-1
#        'Here use the slopes to calculate GD
#        GDStart=i-nLeft : if GDStart<pMin-1 then GDStart=pMin-1
#        GDEnd=i+nPoints-nLeft-1 : if GDEnd>pMax+1 then GDStart=pMax+1
#        call uBestFitLine constAngle, GDStart, GDEnd, m, b     'Get slope from GDStart to GDEnd
#        currGD=0-m/360000000 'Group delay is negative of the slope--360 converts delta degrees to delta cycles; 1e6 converts MHz->Hz
#        if currGD<minGD then minGD=currGD   'save min for scaling
#        if currGD>maxGD then maxGD=currGD   'save max for scaling
#       auxGraphData(i,0)=currGD    'Put group delay into aux graph 0
#    next i
#
#        'Set graph to show the GD data from auxiliary graph 0.
#    yAxisLabel$="Grp Delay (sec)" :  yLabel$="G.D."
#    yForm$="3,2,4//UseMultiplier//DoCompact"
#    auxGraphDataFormatInfo$(0,0)="Grp Del(sec)" : auxGraphDataFormatInfo$(0,1)=yForm$
#    auxGraphDataFormatInfo$(0,2)="Grp Del": auxGraphDataFormatInfo$(0,3)="GD"
#    auxGraphDataInfo(0,0)=0 'not an angle
#    auxGraphDataInfo(0,1)=uRoundDownToPower(minGD,10) 'axis min
#    auxGraphDataInfo(0,2)=uRoundUpToPower(maxGD,10)  'axis max is power of 10
#    if gGetPrimaryAxis()=1 then call ChangeGraphsToAuxData constAux0, constAngle else call ChangeGraphsToAuxData constAngle, constAux0
#    close #functGD
#    exit sub    'We have created the graph, so quit this dialog
#end sub


