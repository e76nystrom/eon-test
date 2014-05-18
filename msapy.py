#!/usr/bin/env python
# -*- coding: utf-8 -*-
###############################################################################
#
#                       MODULAR SPECTRUM ANALYZER 
#
# The original Python software, written by Scott Forbes, was a complete rewrite
# of the original Liberty Basic code developed by Scotty Sprowls (the designer
# of the Spectrum Analyzer) and Sam Weterlin. Over a period of nine months,
# comencing in May/June, 2013, Scott's code has been expanded and debugged by
# Jim Hontoria, W1JGH and Eric Nystrom, W1EON in close consultation with Scotty.
# Other contributors to the testing have been Will Dillon and  Earle Craig.
#
# Copyright (c) 2011, 2013 Scott Forbes
#
# This file may be distributed and/or modified under the terms of the
# GNU General Public License version 2 as published by the Free Software
# Foundation. (See COPYING.GPL for details.)
#
# This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
# WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
#
###############################################################################
from __future__ import division

##Updated with LB ver117rev0-A
##msaVersion$="117"   'ver117rev0
##msaRevision$="A"    'ver117a

version = "0.2.70_JGH Dec 23, 2013 PRELIM"
#released for editing as msapyP102 on 12/23/13
version = "0.2.71_EON Jan 10, 2014 PRELIM"
#released for editing as msapyP105 on 1/22/2014
version = "0.2.72 Jan 22, 2014 PRELIM"
version = "2.7.P3 (2/2/14)"
version = "2.7.P106 (2/3/14)"
version = "P108JGH_F (2/24/14)"
version = "P109GEORGE (2/25/14)"
version = "1.01 (4/01/14)"
version = "1.12 (4/06/14)"
# This is the source for the MSAPy application. It's composed of two parts:
#
# Hardware Back End
#   * Communicates with the spectrum analyzer hardware.
#   * Has functions to initialize hardware, set modes, and capture data.
#
# GUI Front End
#   * Communicates with the user using the wxPython GUI library.
#   * Refreshes the spectrum graph on each timer tick whenever more capture data
#     from the back end is ready, or whenever its window is resized.
#
# The code is mostly a set of object-oriented classes, arranged starting with
# the most primitive; a search from the top will usually locate an item's
# definition. A search for "#=" will find the class definitions.
###############################################################################

import sys
print ("Python:", sys.version) # Requires python v2.7
print("sys.platform: ", sys.platform)

import msaGlobal
from msaGlobal import appdir, EVT_UPDATE_GRAPH, GetHardwarePresent, \
    incremental, isMac, isWin, msPerUpdate, resdir, SetFontSize, \
    SetModuleVersion, SetVersion, slowDisplay
import os, re, string, time, threading, wx
import copy as dcopy
import numpy.version
from wx.lib.dialogs import ScrolledMessageDialog
import trace
from util import CentSpanToStartStop, CheckExtension, message, \
    mhzStr, modDegree, Prefs, ShouldntOverwrite, StartStopToCentSpan
from theme import DarkTheme, LightTheme
from events import ResetEvents, LogGUIEvent, GuiEvents
from msa import MSA
from marker import Marker
from calMan import CalFileName, CalParseFreqFile, CalParseMagFile
from vScale import VScale
from spectrum import Spectrum
import twoPort   # Added by JGH 3/29/14

SetModuleVersion("msapy",("1.10","JGH.e","03/24/2014"))
SetVersion(version)

msa = None

# debugging and profiling settings

debug = False        # set True to write debugging messages to msapy.log

# standard font pointsize-- will be changed to calibrated size for this system
fontSize = 11
SetFontSize(fontSize)

print ("PROGRAM STARTED")

#==============================================================================

#******************************************************************************
#****                          MSA GUI Front End                          *****
#******************************************************************************

#==============================================================================
# The main MSA frame showing the spectrum.

class MSASpectrumFrame(wx.Frame):
    def __init__(self, parent, title):
        global msa, fontSize

        # read preferences file, if any
        self.refreshing = False
        self.appName = title
        self.rootName = title.lower()
        self.prefs = None
        self.LoadPrefs()
        self.consoleStderr = None

        # get preference values, using defaults if new
        p = self.prefs

        self.markMHz = 0.
        self.fHdim = fHdim = 800 ; self.fVdim = fVdim = 600 # JGH 2/16/14
        #fHdim = 800 ; fVdim = 600
        title = "Modular Spectrum Analyzer"
        wx.Frame.__init__(self, parent, -1, title,
                            size=p.get("frameSize", (fHdim, fVdim)))
        self.Bind(wx.EVT_SIZE, self.OnSizeChanged)
        self.Bind(wx.EVT_CLOSE, self.OnExit)
        self.SetDoubleBuffered(True)

        # calibrate font point size for this system
        font = wx.Font(fontSize, wx.SWISS, wx.NORMAL, wx.NORMAL)
        font.SetPixelSize((200, 200))
        pointSize200px = font.GetPointSize()
        fontSize = fontSize * pointSize200px / 170
        SetFontSize(fontSize)
        if 0:
            # test it
            font10 = wx.Font(fontSize, wx.SWISS, wx.NORMAL, wx.NORMAL)
            ps10 = font10.GetPointSize()
            font27 = wx.Font(fontSize*2.7, wx.SWISS, wx.NORMAL, wx.NORMAL)
            ps27 = font27.GetPointSize()
            print ("10-point pointsize=", ps10, "27-point pointsize=", ps27)

        # set up menu bar
        self.menubar = wx.MenuBar()
        self.fileMenu = self.CreateMenu("&File", (
            ("Save Image...\tSHIFT-CTRL-S", "SaveImage", -1),
            ("Load Prefs",              "LoadPrefsFile", -1),
            ("Save Prefs",              "SavePrefsFile", -1),
            ("Load Data...",            "LoadData", -1),
            ("Save Data...",            "SaveData", -1),
            ("Load/Save Test Setup...\tCTRL-s", "LoadSaveTestSetup", -1),
            ("-",                        None, -1),
            ("Log Panel -->",            None, 2),
            ("logP Show",                "logPshow", -2),
            ("logP Hide",                "logPhide", -2),
            ("Close\tCTRL-w",            "OnClose", wx.ID_CLOSE),
            ("Quit\tCTRL-q",             "OnExit", wx.ID_EXIT),
        ))
        self.setupMenu = self.CreateMenu("&Setup", (
            ("Hardware Config Manager...", "ManageHWConfig", -1),
            ("Initial Cal Manager...",  "ManageInitCal", -1),
            ("PDM Calibration...",      "PDMCal", -1),
            ("DDS Tests. . .",          "ddsTests", -1),
            ("Cavity Filter Test ...",  "CavFiltTest", -1), # JGH 1/25/14
            ("Control Board Tests...",  "CtlBrdTests",-1),
            ("-",                       None, -1),
            ("Synthetic DUT...\tCTRL-D", "SynDUT", -1),
        ))
        self.sweepMenu = self.CreateMenu("&Sweep", [
            ("Sweep Parameters\tCTRL-F", "SetSweep", -1),
            ("Show Variables\tCTRL-I",  "ShowVars", -1),
            ("-",                        None, -1),
            ("Markers -->",              None, 4),
            ("Markers Independent",      "SetMarkers_Indep", -2),
            ("Markers P+,P- bounded by L,R", "SetMarkers_PbyLR", -2),
            ("Markers L,R bounded by P+", "SetMarkers_LRbyPp", -2),
            ("Markers L,R bounded by P-", "SetMarkers_LRbyPm", -2),
            ("Reference Lines -->",       None, 8)] +
            [("Set Reference Line %d...\tCTRL-%d" % (i, i), "SetRef", -1)
                for i in range(8)]
        )
        self.dataMenu = self.CreateMenu("&Data", (
            ("Save Graph Data",         "SaveGraphData", -1),
            ("Save Input Data",         "SaveInputData", -1),
            ("Save Installed Line Cal", "SaveInstalledLineCal", -1),
            ("-",                       None, -1),
            ("Dump Events",             "DumpEvents", -1),
            ("Save Debug Events",       "WriteEvents", -1),
        ))
        self.functionsMenu = self.CreateMenu("&Functions", (
            ("One Scan\tCTRL-E",        "DoExactlyOneScan", -1),
            ("One Step\tCTRL-T",        "DoOneStep", -1),
            ("Continue/Halt\tCTRL-R",   "OnContinueOrHalt", -1),
            ("-",                       None, -1),
            ("Filter Analysis...\tSHIFT-CTRL-F",  "AnalyzeFilter", -1),
            ("Component Meter...\tSHIFT-CTRL-C",  "ComponentMeter", -1),
            ("RLC Analysis...\tSHIFT-CTRL-R",     "AnalyzeRLC", -1),
            ("Coax Parameters...\tSHIFT-CTRL-X",  "CoaxParms", -1),
            ("Crystal Analysis...\tSHIFT-CTRL-K", "AnalyzeCrystal", -1),
            ("Group Delay...\tSHIFT-CTRL-G",  "GroupDelay", -1),
            ("Step Attenuator Series...\tSHIFT-CTRL-S", "StepAttenuator", -1),
        ))
        self.operatingCalMenu = self.CreateMenu("&Operating Cal", (
            ("Perform Cal...\tCTRL-B",   "PerformCal", -1),
            ("Perform Update...\tCTRL-U","PerformCalUpd", -1), # EON Jan 10 2014
            ("-",                       None, -1),
            ("Reference -->",           None, 3),
            ("Reference To Band",       "SetCalRef_Band", -2),
            ("Reference To Baseline",   "SetCalRef_Base", -2),
            ("No Reference",            "SetCalRef_None", -2),
        ))
        self.twoPortMenu = self.CreateMenu("&Two Port", (
            ("Show Two Port Window...\tCTRL-P", "TwoPortShow", -1),
        ))
        self.modeMenu = self.CreateMenu("&Mode", (
            ("Spectrum Analyzer",       "SetMode_SA", -2),
            ("Spectrum Analyzer with TG", "SetMode_SATG", -2),
            ("VNA Transmission",        "SetMode_VNATran", -2),
            ("VNA Reflection",          "SetMode_VNARefl", -2)
        ))
        self.helpMenu = self.CreateMenu("&Help", (
            ("About",                   "OnAbout", wx.ID_ABOUT),
        ))
        self.SetMenuBar(self.menubar)
        self.closeMenuItem = self.fileMenu.FindItemById(wx.ID_CLOSE)
        

        self.logSplitter = ls = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE)
        ls.Bind(wx.EVT_SPLITTER_DCLICK, self.OnSplitterDClick)
        self.mainP = mainP = wx.Panel(self.logSplitter, style=wx.BORDER_SUNKEN)

        # define controls and panels in main spectrum panel
        sizer = wx.BoxSizer(wx.VERTICAL)
        from graphPanel import GraphPanel
        self.specP = specP = GraphPanel(mainP, self)
        sizer.Add(self.specP, 1, wx.EXPAND)
        botSizer = wx.BoxSizer(wx.HORIZONTAL)

        mark1Sizer = wx.BoxSizer(wx.VERTICAL)
        mark1Sizer.Add(wx.StaticText(mainP, -1, "Marker"), 0, wx.CENTER)
        self.markerNames = samples = ["None"] + \
                [str(i) for i in range(1, 7)] + ["L", "R", "P+", "P-"]
        cbox = wx.ComboBox(mainP, -1, "None", (0, 0), (80, -1), samples)
        self.markerCB = cbox
        mainP.Bind(wx.EVT_COMBOBOX, self.OnSelectMark, cbox)
        mark1Sizer.Add(cbox, 0, wx.ALL, 2)
        botSizer.Add(mark1Sizer, 0, wx.ALIGN_BOTTOM)

        mark2Sizer = wx.BoxSizer(wx.VERTICAL)
        btn = wx.Button(mainP, -1, "Delete", size=(90, -1))
        mainP.Bind(wx.EVT_BUTTON, self.OnDeleteMark, btn)
        mark2Sizer.Add(btn, 0, wx.ALL, 2)
        btn = wx.Button(mainP, -1, "Clear Marks", size=(90, -1))
        mainP.Bind(wx.EVT_BUTTON, self.ClearMarks, btn)
        mark2Sizer.Add(btn, 0, wx.ALL, 2)
        botSizer.Add(mark2Sizer, 0, wx.ALIGN_BOTTOM)

        mark3Sizer = wx.BoxSizer(wx.VERTICAL)
        mark3TSizer = wx.BoxSizer(wx.HORIZONTAL)
        btn = wx.Button(mainP, -1, "-", size=(25, -1))
        mainP.Bind(wx.EVT_BUTTON, self.OnDecMarkMHz, btn)
        mark3TSizer.Add(btn, 0, wx.ALL, 2)
        mark3TSizer.AddSpacer((0, 0), 1, wx.EXPAND)
        mark3TSizer.Add(wx.StaticText(mainP, -1, "MHz"), 0,
                    wx.ALIGN_CENTER_HORIZONTAL|wx.EXPAND|wx.ALL, 2)
        mark3TSizer.AddSpacer((0, 0), 1, wx.EXPAND)
        mark3Sizer.Add(mark3TSizer, 0, wx.EXPAND)
        self.mhzT = wx.TextCtrl(mainP, -1, str(self.markMHz), size=(100, -1))
        mark3Sizer.Add(self.mhzT, 0, wx.ALL, 2)
        btn = wx.Button(mainP, -1, "+", size=(25, -1))
        mainP.Bind(wx.EVT_BUTTON, self.OnIncMarkMHz, btn)
        mark3TSizer.Add(btn, 0, wx.ALL, 2)
        botSizer.Add(mark3Sizer, 0, wx.ALIGN_BOTTOM)
        btn = wx.Button(mainP, -1, "Enter", size=(50, -1))
        mainP.Bind(wx.EVT_BUTTON, self.OnEnterMark, btn)
        botSizer.Add(btn, 0, wx.ALIGN_BOTTOM|wx.ALL, 2)

        mark4Sizer = wx.BoxSizer(wx.VERTICAL)
        btn = wx.Button(mainP, -1, "Expand LR", size=(100, -1))
        mainP.Bind(wx.EVT_BUTTON, self.ExpandLR, btn)
        mark4Sizer.Add(btn, 0, wx.ALL, 2)
        btn = wx.Button(mainP, -1, "Mark->Cent", size=(100, -1))
        mainP.Bind(wx.EVT_BUTTON, self.OnMarkCent, btn)
        mark4Sizer.Add(btn, 0, wx.ALL, 2)
        botSizer.Add(mark4Sizer, 0, wx.ALIGN_BOTTOM)

        botSizer.AddSpacer((0, 0), 1, wx.EXPAND)
        stepSizer = wx.BoxSizer(wx.VERTICAL)
        btn = wx.Button(mainP, -1, "One Step", size=(90, -1))
        mainP.Bind(wx.EVT_BUTTON, self.DoOneStep, btn)
        stepSizer.Add(btn, 0, wx.ALL, 2)
        self.oneScanBtn = wx.Button(mainP, -1, "One Scan", size=(90, -1))
        mainP.Bind(wx.EVT_BUTTON, self.OnOneScanOrHaltAtEnd, self.oneScanBtn)
        stepSizer.Add(self.oneScanBtn, 0, wx.ALL, 2)
        ##self.oneScanBtn.SetToolTip(wx.ToolTip("Start one spectrum scan"))
        botSizer.Add(stepSizer, 0, wx.ALIGN_BOTTOM)

        goSizer = wx.BoxSizer(wx.VERTICAL)
        self.contBtn = wx.Button(mainP, -1, "Continue", size=(90, -1))
        mainP.Bind(wx.EVT_BUTTON, self.OnContinueOrHalt, self.contBtn)
        goSizer.Add(self.contBtn, 0, wx.ALL, 2)
        self.restartBtn = wx.Button(mainP, -1, "Restart", size=(90, -1))
        mainP.Bind(wx.EVT_BUTTON, self.OnRestartOrHalt, self.restartBtn)
        goSizer.Add(self.restartBtn, 0, wx.ALL, 2)
        botSizer.Add(goSizer, 0, wx.ALIGN_BOTTOM)

        sizer.Add(botSizer, 0, wx.EXPAND)
        mainP.SetSizer(sizer)

        # create a log text panel below and set it to log all output
        # (can't use LogTextCtrl-- it's broken)
        logP = wx.TextCtrl(self.logSplitter, \
                           style=wx.TE_MULTILINE|wx.TE_READONLY)
        logP.SetFont(wx.Font(fontSize, wx.MODERN, wx.NORMAL, wx.NORMAL))
        self.logP = logP
        lsVdim = int(p.get("logSplit", 0.8 * self.fVdim)) # On start
        self.logSplitter.SplitHorizontally(mainP, logP, lsVdim) # JGH 2/16/14
        self.logSplitter.name = "log"
        self.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGED, self.OnSashChanged)
       
        # redirect all output to a log file (disable this to see early errors)
        if 1:
            self.consoleStderr = sys.stderr
            logName = os.path.join(appdir, self.rootName)
            sys.stdout = self.Logger(logName, logP, self)
            sys.stderr = self.Logger(logName, logP, self)
        print (title, version, "log -- started", time.ctime())
        print ("Python", sys.version)
        print ("wx", wx.version(), "numpy", numpy.version.version)

        if isMac:
            path = os.path.abspath(os.path.dirname(sys.argv[0]))
            m = re.match(".+(Resources)$", path)
            if m != None:
                path = path[0:m.start(1)] + "Frameworks"
                os.environ['DYLD_FALLBACK_LIBRARY_PATH'] = path
                print ("DYLD_FALLBACK_PATH %s" % path)

        global msa
        self.msa = msa = MSA(self) # JGH MSA object is created here 1/25/14
        msaGlobal.SetMsa(msa)
        trace.SetMsa(msa)

        # initialize back end
        p.get("rbw", 300)
        p.get("wait", 10)
        p.get("waitTCF", 10)
        p.get("waitAuto", False)
        p.get("sigGenFreq", 10.)
        p.get("tgOffset", 0.)
        p.get("planeExt", 3*[0.])
        if type(p.planeExt) != type([]) or len(p.planeExt) != 3:
            p.planeExt = 3*[0.]
        print ("planeExt=", p.planeExt)
        p.get("normRev", 0)
        p.get("isLogF", 0)
        p.get("continuous", False)
        p.get("sweepDir", 0)
        p.get("markerMode", Marker.MODE_INDEP)
        p.get("atten5", False)
        p.get("stepAttenDB", 0)
        p.get("switchPulse", 0) # JGH added Oct23
        p.get("syntData", False)
        p.get("rbwP4", False) # RBW may use P4 (new, True) or P1 (classic, False)
        p.get("winLPT", False) # True when Windows uses parallel port
        p.get("mBand", False) # True if using multiband

        # initialize spectrum graph
        p.get("fStart", -1.5)
        p.get("fStop", 1.5)
        p.get("nSteps", 400)        
        va0 = p.get("va0", -120.)
        va1 = p.get("va1", 0.)
        specP.vScales = vScales = []
        vai = p.get("vaTypeIndex", 1)
        vaDiv = p.get("vaDiv", 10)
        vScales.append(VScale(vai, msa.mode, va1, va0, vaDiv, "dB"))
        vbDiv = p.get("vbDiv", 10)
        if msa.mode < MSA.MODE_VNATran:
            vb0 = p.get("vb0", 0)
            vb1 = p.get("vb1", 0.)
            vbi = p.get("vbTypeIndex", 0)
            vScales.append(VScale(vbi, msa.mode, vb1, vb0, vbDiv, "None"))
        else:
            vb0 = p.get("vb0", -180.)
            vb1 = p.get("vb1", 180.)
            vbi = p.get("vbTypeIndex", 2)
            vScales.append(VScale(vbi, msa.mode, vb1, vb0, vbDiv, "Deg"))
        self.refs = {}
        self.lastDoneDrawTime = 0
        self.btnScanMode = False    # True when buttons in scanning mode
        self.task = None
        self.smithDlg = None

        self.spectrum = None
        self.sweepDlg = None
        self.filterAnDlg = None
        self.compDlg = None
        self.tranRLCDlg = None
        self.coaxDlg = None
        self.grpDlyDlg = None
        self.crystalDlg = None
        self.stepDlg = None
        self.varDlg = None
        self.ReadCalPath()
        self.ReadCalFreq()
        self.Show(True)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer)
        self.Bind(EVT_UPDATE_GRAPH, self.OnTimer)
        self.yLock = threading.Lock()
        self.screenWidth, self.screenHeight = wx.Display().GetGeometry()[2:4]

        # restore markers from preferences
        if False:
            for attr, value in p.__dict__.items():
                if len(attr) > 9 and attr[:8] == "markers_":
                    mm, mName, mAttr = string.split(attr, "_")
                    mName = re.sub("p", "+", re.sub("m", "-", mName))
                    m = specP.markers.get(mName)
                    if not m:
                        specP.markers[mName] = m = Marker(mName, "", 0)
                    setattr(m, mAttr, value)
                    delattr(p, attr)

        # put a checkmark by the current mode in the Mode menu
        for i, item in enumerate(self.modeMenu.GetMenuItems()):
            item.Check(i == msa.mode)

        if p.get("logP",0) == 1:
            self.logPhide(None)
        else:
            self.logPshow(None)

        self.RefreshAllParms()

        # build an operating calibration file path, creating the dirs if needed
        cdir = os.path.join(appdir, "MSA_Info", "OperatingCal")
        self.baseCalFileDir = cdir
        if not os.path.exists(cdir):
            os.makedirs(cdir)
        # Start EON Jan 28, 2014
        self.bandCalFileName = os.path.join(cdir, "BandLineCal.s1p")
        self.baseCalFileName = os.path.join(cdir, "BaseLineCal.s1p")
        # read any operating calibration files
#        msa.bandCal = self.LoadCal(self.bandCalFileName)
#        msa.baseCal = self.LoadCal(self.baseCalFileName)
        msa.bandCal = None
        msa.baseCal = None
        # Start EON Jan 28, 2014

        # MAKE ONE SCAN TO CONFIGURE GRAPH
        msa.cftest = False
        self.ScanPrecheck(True)
        if (p.get("dds3Track",False) or p.get("dds1Sweep",False)):
            self.ddsTests
        # Define functions available at the menu to each mode:
        self.funcModeList = [0] * 4
        self.funcModeList[MSA.MODE_SA] = ["filter","step"]
        self.funcModeList[MSA.MODE_SATG] = ["filter","component","step"]
        self.funcModeList[MSA.MODE_VNATran] = ["filter","component","rlc","crystal","group","step"]
        self.funcModeList[MSA.MODE_VNARefl] = ["component","rlc","coax","s21","step"]

        self.InitMode(msa.mode)

    def wxYield(self):
        self.yLock.acquire(True)
        wx.Yield()
        self.yLock.release()

    #==============================================================================
    # The message pane and log file to which stdout and stderr are redirected to.

    class Logger:
        def __init__(self, name, textCtrl, frame):
            global logFile
            logFile = file(name + ".log", "w+")
            self.textCtrl = textCtrl
            self.frame = frame
            self.lineCount = 0

        def write(self, s):
            global msa, logFile
            try:
                if "\n" in s:
                    self.lineCount += 1
                maxLogWinLines = 10000
                if wx.Thread_IsMain() and self.lineCount < maxLogWinLines:
                    logFile.write(s)
                    self.textCtrl.AppendText(s)
                elif self.lineCount < maxLogWinLines or msa.showError:
                    msa.errors.put(s)
            except:
                pass # don't recursively crash on errors

    #--------------------------------------------------------------------------
    # Create a menu of given items calling given routines.
    # An id == -2 sets item to be in a radio group.

    def CreateMenu(self, menuName, menuArray):
        if 0 or debug:
            print("msapy>496< menuName:", menuName, "menuArray:", menuArray, "Length:", len(menuArray))
        menu = wx.Menu()
        s = 0
        submenu = None
        subName = ""
        
        for (itemName, handlerName, menuId) in menuArray:
            if itemName == "-":
                menu.AppendSeparator()
            else:
                if menuId == -1:
                    menuId = wx.NewId()
                    if s == 0:
                        item = menu.Append(menuId, itemName)
                    else:
                        item = submenu.Append(menuId, itemName)
                        s -= 1
                        if s == 0:
                            menu.AppendMenu(menuId, subName, submenu)
                elif menuId == -2:
                    menuId = wx.NewId()
                    if s == 0:
                        item = menu.AppendRadioItem(menuId, itemName)
                    else:
                        item = submenu.AppendRadioItem(menuId, itemName)
                        s -= 1
                        if s == 0:
                            menu.AppendMenu(menuId, subName, submenu)
                elif menuId > 0 and menuId < 10:
                    if 0 or debug:
                        print("msapy>526< Next " + str(menuId) + " items are part of a submenu")
                    subName = itemName
                    submenu = wx.Menu()
                    s = menuId
                    continue
                else:
                    item = menu.Append(menuId, itemName)
                if hasattr(self, handlerName):
                    self.Connect(menuId, -1, wx.wxEVT_COMMAND_MENU_SELECTED, \
                                getattr(self, handlerName))
                else:
                    item.Enable(False)
        self.menubar.Append(menu, menuName)
        
        return menu
    
    #--------------------------------------------------------------------------
    # derived from Menuitem class
    def SubMenu(self, parentMenu, menuId, text, menuHelp, kind, subMenu):
        pass

    #--------------------------------------------------------------------------
    # Change button names while scanning.

    def SetBtnsToScan(self, scanning):
        if scanning:
            self.contBtn.SetLabel("Halt")
            self.restartBtn.SetLabel("Halt")
            self.oneScanBtn.SetLabel("Halt at End")
        else:
            self.contBtn.SetLabel("Continue")
            self.restartBtn.SetLabel("Restart")
            self.oneScanBtn.SetLabel("One Scan")
        self.btnScanMode = scanning

    #--------------------------------------------------------------------------
    # Start capturing a spectrum.

    def ScanPrecheck(self, haltAtEnd=False, scan=True):
        global msa
        self.StopScanAndWait()
        ResetEvents()
        LogGUIEvent("ScanPrecheck")
        self.spectrum = None
        self.needRestart = False
        if msa.syndut: # JGH 2/8/14 syndutHook5
            if 0 or debug:
                print ("msapy>573< GETTING SYNTHETIC DATA")
            msa.syndut.GenSynthInput()
        p = self.prefs

        fStart = p.fStart
        fStop = p.fStop
        title = time.ctime()

        print ("----", title, "fStart=", mhzStr(fStart), "fStop=", \
             mhzStr(fStop), "----")
        self.wxYield()
        needsRefresh = False

        # get ready to redraw the grid if needed
        specP = self.specP
        specP.eraseOldTrace = False
        specP.markersActive = False
        if specP.h0 != fStart or specP.h1 != fStop or specP.title != title:
            LogGUIEvent("ScanPrecheck new graph range")
            specP._haveDrawnGrid = False
            specP.h0 = fStart
            specP.h1 = fStop
            specP.title = title
            needsRefresh = True

        # set up calibration table to use
        self.spectrum = None
        if not msa.calibrating:
            needsRefresh = self.CalCheck() # EON Jan 29, 2014

        if needsRefresh:
            self.RefreshAllParms()

        # tell MSA hardware backend to start a scan (msa.py module)
        if scan:
            msa.ConfigForScan(self, p, haltAtEnd)

        if not GetHardwarePresent() and not msa.syndut:
            msa.scanResults.put((0, 0, 0, 0, 0, 0, 0, 0, 0))
            message("Hardware not present. If you want to run with "
                    "Synthetic Data, use Hardware Configuration Manager "
                    "to enable Synthetic Data.",
                    caption="Hardware not Present")

        LogGUIEvent("ScanPrecheck starting timer")
        # start display-update timer, given interval in ms
        self.timer.Start(msPerUpdate)
    #--------------------------------------------------------------------------

    #--------------------------------------------------------------------------
    # Check requested calibration level and set based on calibration present

    def CalCheck(self):
        global msa
        p = self.prefs
        cal = (None, msa.baseCal, msa.bandCal)[p.calLevel]
        if cal:
            if ((msa.mode == MSA.MODE_VNATran and cal.oslCal) or \
                (msa.mode == MSA.MODE_VNARefl and (not cal.oslCal))):
                    self.SetCalLevel(0)
                    return True
            calF = cal.Fmhz
            # Start EON Jan 10 2014
            #calIsLogF = (calF[0] + calF[2])/2 != calF[1]
            calIsLogF = cal.isLogF
            # End EON Jan 10 2014
            ##print ("cal: %.20g %.20g %.20g %.20g" % \
            ##        (calF[0], fStart, calF[-1], fStop))
            ##print ("cal:", calF[0] == fStart, calF[-1] == fStop, \
            ##    cal.nSteps, p.nSteps, calIsLogF, p.isLogF)
            fStart = p.fStart
            fStop = p.fStop
            needsRefresh = False
            if round(calF[0] - fStart, 8) == 0 and \
                    round(calF[-1] - fStop, 8) == 0 and \
                    cal.nSteps == p.nSteps and calIsLogF == p.isLogF:
                # have a matching base or band calibration
                msa.calNeedsInterp = False
                # Start EON Jan 10 2014
                if cal.oslCal:
                    cal.installBandCal()
                # End EON Jan 10 2014
            elif p.calLevel > 0 and msa.baseCal and \
                        fStart >= msa.baseCal.Fmhz[0] and \
                        fStop <= msa.baseCal.Fmhz[-1]:
                # no match, but can use base
                msa.calNeedsInterp = True
                # Start EON Jan 10 2014
                if cal.oslCal:
                    msa.NewScanSettings(p)
                    cal.interpolateCal(msa._freqs)
                # End EON Jan 10 2014
                ##print ("Cal needs interpolation")
                if p.calLevel == 2:
                    self.SetCalLevel(1)
                    needsRefresh = True
            else:
                # no usable calibration at all
                ##print ("No usable calibration")
                if p.calLevel > 0:
                    self.SetCalLevel(0)
                    needsRefresh = True
            return needsRefresh

    #--------------------------------------------------------------------------
    # Stop any scanning and wait for all results to be updated.

    def StopScanAndWait(self):
        global msa
        self.specP.markersActive = True
        if msa.IsScanning():
            msa.StopScan()
            self.WaitForStop()
        else:
            self.RefreshAllParms()

    #--------------------------------------------------------------------------
    # Wait for end of scan and all results to be updated.

    def WaitForStop(self):
        global msa
        while msa.IsScanning() or not msa.scanResults.empty():
            self.wxYield()
            time.sleep(0.1)
        self.RefreshAllParms()

    #--------------------------------------------------------------------------
    # "One Step" button pressed.

    def DoOneStep(self, event=None):
        global msa
        LogGUIEvent("DoOneStep")
        self.StopScanAndWait()
        if not self.needRestart:
            msa.WrapStep()
            msa.CaptureOneStep()
            msa.NextStep()

    #--------------------------------------------------------------------------
    # "One Scan"/"Halt at End" button pressed.

    def OnOneScanOrHaltAtEnd(self, event):
        global msa
        LogGUIEvent("OnOneScanOrHaltAtEnd: scanning=%d" % msa.IsScanning())
        if msa.IsScanning():
            msa.haltAtEnd = True
        else:
            self.ScanPrecheck(True)

    #--------------------------------------------------------------------------
    # Ctrl-E: do exactly one scan.

    def DoExactlyOneScan(self, event=None):
        LogGUIEvent("DoExactlyOneScan: scanning=%d" % msa.IsScanning())
        self.StopScanAndWait()
        self.ScanPrecheck(True)

    #--------------------------------------------------------------------------
    # Continue/Halt button pressed.

    def OnContinueOrHalt(self, event):
        global msa
        LogGUIEvent("OnContinueOrHalt")
        if msa.IsScanning():
            self.StopScanAndWait()
        elif not msa.HaveSpectrum() or self.needRestart:
            self.ScanPrecheck(False)
        else:
            msa.WrapStep()
            msa.haltAtEnd = False
            msa.ContinueScan()

    #--------------------------------------------------------------------------
    # Restart/Halt button pressed.

    def OnRestartOrHalt(self, event=None):
        global msa
        LogGUIEvent("OnRestartOrHalt: scanning=%d step=%d" % \
            (msa.IsScanning(), msa.GetStep()))
        if msa.IsScanning(): # or self.needRestart:
            self.StopScanAndWait()
        else:
            self.ScanPrecheck(False)

    #--------------------------------------------------------------------------
    # Timer tick: update display.

    def OnTimer(self, event):
        global msa
        specP = self.specP
        assert wx.Thread_IsMain()
        ##LogGUIEvent("OnTimer")

        # draw any new scan data from the back end thread
        if not msa.scanResults.empty():
            spec = self.spectrum
            LogGUIEvent("OnTimer: have updates")
            if spec == None:
                spec = msa.NewSpectrumFromRequest(specP.title)
                self.spectrum = spec

            # add scanned steps to our spectrum, noting if they include
            # the last step
            includesLastStep = False
            while not msa.scanResults.empty():
                includesLastStep |= spec.SetStep(msa.scanResults.get())

            # move the cursor to the last captured step
            specP.cursorStep = spec.step
            # activate markers when at or passing last step
            specP.markersActive = includesLastStep
            if includesLastStep:
                specP.eraseOldTrace = True
                if msa.syndut:    # JGH 2/8/14 syndutHook6
                    msa.syndut.RegenSynthInput()
                if self.smithDlg and slowDisplay:
                    self.smithDlg.Refresh()
            self.DrawTraces()
            LogGUIEvent("OnTimer: all traces drawn, cursorStep=%d" % spec.step)
            if self.varDlg:
                self.varDlg.Refresh()

        # put Scan/Halt/Continue buttons in right mode
        if msa.IsScanning() != self.btnScanMode:
            self.SetBtnsToScan(msa.IsScanning())

        # write out any error messages from the backend
        while not msa.errors.empty():
            sys.stderr.write(msa.errors.get())

        # Component Meter continuous measurements, if active
        if self.task != None:
            self.task.AutoMeasure()

        ##LogGUIEvent("OnTimer: done")

    #--------------------------------------------------------------------------
    # Return the index for color i, adding it to the theme.vColor list if not
    # already there.

    def IndexForColor(self, i):
        p = self.prefs
        vColors = p.theme.vColors
        iNextColor = p.theme.iNextColor
        nColors = len(vColors)
        while len(vColors) <= i:
            vColors.append(vColors[iNextColor % nColors])
            iNextColor += 1
        p.theme.iNextColor = iNextColor
        return i

    #--------------------------------------------------------------------------
    # Copy the current and reference spectrums into the spectrum panel traces
    # and draw them.

    def DrawTraces(self):
        global msa
        if 0 or debug:
            print ("DrawTraces")
        specP = self.specP
        specP.traces = {}
        p = self.prefs
        spec = self.spectrum
        if not spec:
            return
        LogGUIEvent("DrawTraces: %d steps" % len(spec.Sdb))

        # compute derived data used by various data types
        spec.f = spec.Fmhz
        #nSteps = len(f) - 1 # JGH (unused var nSteps)
        mode = p.mode
        includePhase = mode >= MSA.MODE_VNATran

        spec.isSeriesFix = p.get("isSeriesFix", False)
        spec.isShuntFix = p.get("isShuntFix", False)

        # set left (0) and right (1) vertical scale variables
        # and create potential traces for each (trva, trvb)
        types = trace.traceTypesLists[mode]
        maxIndex = len(types)-1
        vScales = specP.vScales
        vs0 = vScales[0]
        p.vaTypeIndex = vaTypeIndex = min(vs0.typeIndex, maxIndex)
        p.va1 = vs0.top
        p.va0 = vs0.bot
        p.vaDiv = vs0.div
        vaType = types[vaTypeIndex]

        if spec.vaType != vaType:
            trva = vaType(spec, 0)
            trva.maxHold = vs0.maxHold
            trva.max = False
            if incremental:
                spec.vaType = vaType
                spec.trva = trva
        else:
            trva = spec.trva

        trva.iColor = self.IndexForColor(0)
        vs1 = vScales[1]
        p.vbTypeIndex = vbTypeIndex = min(vs1.typeIndex, maxIndex)
        p.vb1 = vs1.top
        p.vb0 = vs1.bot
        p.vbDiv = vs1.div
        vbType = types[vbTypeIndex]

        if spec.vbType != vbType:
            trvb = vbType(spec, 1)
            trvb.maxHold = vs1.maxHold
            trvb.max = False
            if incremental:
                spec.vbType = vbType
                spec.trvb = trvb
        else:
            trvb = spec.trvb
        trvb.iColor = self.IndexForColor(1)

        # determine Mag and Phase traces, if any
        trM = trP = None
        if vaTypeIndex > 0:
            specP.traces[vaType.name] = trva
            if "dB" in trva.units:
                trM = trva
            if "Deg" in trva.units:
                trP = trva

        if vbTypeIndex > 0:
            specP.traces[vbType.name] = trvb
            if "dB" in trvb.units:
                trM = trvb
            if "Deg" in trvb.units:
                trP = trvb

        # if we have both Mag and Phase traces, point them to each other
        if trM and trP:
            trM.phaseTrace = trP
            trP.magTrace = trM

        # draw any compatible reference traces
        for ri in self.refs.keys():
            ref = self.refs[ri]
            rsp = ref.spectrum
            if rsp.nSteps == spec.nSteps and rsp.Fmhz[0] == spec.Fmhz[0] \
                                         and rsp.Fmhz[-1] == spec.Fmhz[-1]:
                mathMode = ref.mathMode
                if trM and ri == 1 and ref.mathMode > 0:
                    # Ref 1 math applied to Mag, Phase
                    mData = trM.v
                    mRef = rsp.Sdb
                    if mathMode == 1:
                        mMath = mData + mRef
                    elif mathMode == 2:
                        mMath = mData - mRef
                    else:
                        mMath = mRef - mData
                    trM.v = dcopy.copy(mMath)
                    if includePhase and trP:
                        pData = trP.v
                        pRef = rsp.Sdeg
                        if mathMode == 1:
                            pMath = pData + pRef
                        elif mathMode == 2:
                            pMath = pData - pRef
                        else:
                            pMath = pRef - pData
                        trP.v = dcopy.copy(modDegree(pMath))
                else:
                    # Ref trace is displayed
                    refTypeM = ref.vScale.dataType
                    # vScales[] index 0 or 1 based on units (for now)
                    i = trvb.units and trvb.units == refTypeM.units
                    if not i:
                        i = 0
                    name = ref.name
                    refHasPhase = includePhase and refTypeM.units == "dB"
                    if refHasPhase:
                        # create ref's phase trace, with unique names for both
                        # (use continuous phase if that's being displayed)
                        continPhase = trP.units == "CDeg"
                        refTypeP = types[ref.vScale.typeIndex+1+continPhase]
                        refTrP = refTypeP(rsp, 1-i)
                        name = "%s_dB" % name
                        phName = "%s_%s" % (ref.name, trP.name.split("_")[1])
                    # create and assign name to ref's mag trace
                    specP.traces[name] = refTrM = refTypeM(rsp, i)
                    refTrM.name = name
                    refTrM.isMain = False
                    refTrM.iColor = self.IndexForColor(2 + 2*ri)
                    if refHasPhase:
                        # assign name to ref's phase trace
                        specP.traces[phName] = refTrP
                        refTrP.name = phName
                        refTrP.isMain = False
                        refTrP.iColor = self.IndexForColor(refTrM.iColor + 1)

        # enable drawing of spectrum (if not already)
        specP.Enable()

        # also show Smith chart if in reflection mode
        if msa.mode == MSA.MODE_VNARefl:
            if not self.smithDlg:
                from smithPanel import SmithDialog
                self.smithDlg = SmithDialog(self)
            elif not slowDisplay:
                self.smithDlg.Refresh()
        else:
            if self.smithDlg:
                self.smithDlg.Close()
                self.smithDlg = None

    #--------------------------------------------------------------------------
    # Open the Configuration Manager dialog box.

    def ManageHWConfig(self, event=None):
        self.StopScanAndWait()
        from configDialog import ConfigDialog
        dlg = ConfigDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            dlg.GetHardwareSet()
        dlg.Close() # Do not Destroy() or variables will be lost
        self.SavePrefs()
        p = self.prefs

    #--------------------------------------------------------------------------
    # Open the Calibration File Manager dialog box.

    def ManageInitCal(self, event):
        self.StopScanAndWait()
        p = self.prefs
        from calMan import CalManDialog
        dlg = CalManDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            if dlg.dirty:
                dlg.SaveIfAllowed(self)
        self.ReadCalPath()
        self.ReadCalFreq()
        p.calManWinPos = dlg.GetPosition().Get()

    #--------------------------------------------------------------------------
    # Open the PDM Calibration dialog box.

    def PDMCal(self, event):
        self.StopScanAndWait()
        p = self.prefs
        from pdmCal import PDMCalDialog
        dlg = PDMCalDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            p.invDeg = dlg.invDeg
        p.pdmCalWinPos = dlg.GetPosition().Get()

    #--------------------------------------------------------------------------
    # Open the DDS Tests dialog box # Eric Nystrom, new function created 12/15/2013

    def ddsTests(self, event=None): # Eric Nystrom, new function created 12/15/2013
        self.StopScanAndWait()
        from ddstest import DDSTests
        dlg = DDSTests(self)
        dlg.Show()

    #--------------------------------------------------------------------------
    # Open the Control Board Tests dialog box.

    def CtlBrdTests(self, event): # Eric Nystrom, new function created 12/15/2013
        self.StopScanAndWait()
        from ctlBrdTests import CtlBrdTests
        dlg = CtlBrdTests(self)
        dlg.Show()

    #--------------------------------------------------------------------------
    # Open the Cavity Filter Test dialog box

    def CavFiltTest(self, event): # JGH 1/25/14, new function
        self.StopScanAndWait()
        # p = self.prefs    # JGH 2/10/14
        from cavityFilter import CavityFilterTest
        dlg = CavityFilterTest(self)
        dlg.Show()

#--------------------------------------------------------------------------

    # Handle buttons that manipulate markers.

    def OnIncMarkMHz(self, event):
        self.markMHz += 1.
        self.mhzT.SetValue(str(self.markMHz))

    def OnDecMarkMHz(self, event):
        self.markMHz -= 1.
        self.mhzT.SetValue(str(self.markMHz))

    def OnSelectMark(self, event):
        specP = self.specP
        markName = self.markerCB.GetValue()
        m = specP.markers.get(markName)
        if m:
            self.markMHz = m.mhz
            self.mhzT.SetValue(str(m.mhz))

    def OnEnterMark(self, event):
        self.markMHz = mhz = float(self.mhzT.GetValue())
        specP = self.specP
        markName = self.markerCB.GetValue()
        m = specP.markers.get(markName)
        if m:
            m.mhz = mhz
        else:
            traceName = specP.traces.keys()[0]
            specP.markers[markName] = Marker(markName, traceName, mhz)
        self.specP.FullRefresh()

    def OnDeleteMark(self, event):
        specP = self.specP
        markName = self.markerCB.GetValue()
        m = specP.markers.get(markName)
        if m:
            specP.markers.pop(markName)
            self.specP.FullRefresh()

    def ClearMarks(self, event=None):
        self.specP.markers = {}
        self.specP.FullRefresh()

    def ExpandLR(self, event=None, start=0, stop=0, steps=0):
        specP = self.specP
        p = self.prefs
        if start == 0:
            left = specP.markers.get("L")
            if left:
                start = left.mhz
        if stop == 0:
            right = specP.markers.get("R")
            if right:
                stop = right.mhz
        if start != 0 and stop != 0:
            p.fStart = start
            p.fStop = stop
        if steps != 0:
            p.nSteps = steps
        self.RefreshAllParms()
        self.spectrum = None
        self.ScanPrecheck(True)

    def OnMarkCent(self, event):
        p = self.prefs
        fCent, fSpan = StartStopToCentSpan(p.fStart, p.fStop, p.isLogF)
        p.fStart, p.fStop = CentSpanToStartStop(self.markMHz, fSpan, p.isLogF)
        self.RefreshAllParms()
        if p.fStart < -48:
            self.SetSweep()
            message("Start frequency out of range.")
        else:
            self.spectrum = None
            self.ScanPrecheck(True)

    #--------------------------------------------------------------------------
    # Refresh parameter display in all open windows.

    def RefreshAllParms(self):
        p = self.prefs
        specP = self.specP
        if 0 or debug:
            print ("msapy>1126< RefreshAllParms", specP._isReady, self.refreshing)

##        # checkmark the current marker menu item in the Sweep menu
##        items = self.sweepMenu.Markers.GetSubMenu()
##        items[p.markerMode + 2].Check()
##        # checkmark the current menu item in the Operating Cal menu
##        items = self.operatingCalMenu.GetMenuItems()
##        items[5 - p.calLevel].Check() # EON Jan 10 2014

        # EON modified the following two checkmark tests 2/24/14
        # checkmark the current marker menu item in the Sweep menu
        for m in self.sweepMenu.GetMenuItems():
            if "markers" in m.GetText().lower():
                subItems = m.GetSubMenu().GetMenuItems()
                subItems[p.markerMode - 1].Check()
                break
        # checkmark the current menu item in the Operating Cal menu
        for m in self.operatingCalMenu.GetMenuItems():
            if "ref" in m.GetText().lower():
                subItems = m.GetSubMenu().GetMenuItems()
                subItems[2 - p.calLevel].Check()
                break
        for m in self.fileMenu.GetMenuItems():
            if "log" in m.GetText().lower():
                subItems = m.GetSubMenu().GetMenuItems()
                subItems[p.get("logP",0)].Check()
                break
        
        if (not specP or not specP._isReady) or self.refreshing:  # JGH
            return
        self.refreshing = True
        specP.FullRefresh()
        if self.sweepDlg:
            self.sweepDlg.UpdateFromPrefs()
        self.refreshing = False

    #--------------------------------------------------------------------------
    # Open the Synthetic DUT dialog box.

    def SynDUT(self, event=None): # JGH 2/8/14 syndutHook7
        global msa
        if not msa.syndut:
            from synDUT import SynDUTDialog
            msa.syndut = SynDUTDialog(self)
        else:
            msa.syndut.Raise()
        msa.syndut.Show(True)

    #--------------------------------------------------------------------------
    # Open the Sweep modeless dialog box.

    def SetSweep(self, event=None):
        if not self.sweepDlg:
            from sweepDialog import SweepDialog
            self.sweepDlg = SweepDialog(self)
        else:
            self.sweepDlg.Raise()
        self.sweepDlg.Show(True)
        self.SavePrefs()
    #--------------------------------------------------------------------------
    # Open the Variables modeless info box.

    def ShowVars(self, event=None):
        if not self.varDlg:
            self.varDlg = self.VarDialog(self)
        else:
            self.varDlg.Raise()
        self.varDlg.Show(True)

    #==============================================================================
    # A window showing important variables.

    class VarDialog(wx.Dialog):
        def __init__(self, frame):
            global msa
            self.frame = frame
            self.prefs = p = frame.prefs
            framePos = frame.GetPosition()
            #frameSize = frame.GetSize()
            pos = p.get("varWinPos", (frame.screenWidth-200, framePos.y))
            textList = msa.GetVarsTextList()
            size = (200, 40 + (fontSize+6)*(len(textList)))
            wx.Dialog.__init__(self, frame, -1, "Variables", pos,
                               size, wx.DEFAULT_DIALOG_STYLE)
            self.Bind(wx.EVT_PAINT,     self.OnPaint)
            self.Bind(wx.EVT_MOVE,     self.OnMove)
            self.SetBackgroundColour(p.theme.backColor)
            self.Show()

        def OnPaint(self, event):
            dc = wx.PaintDC(self)
            p = self.prefs
            textList = msa.GetVarsTextList()
            coords = [(10, 5+(fontSize+6)*i) for i in range(len(textList))]
            dc.SetTextForeground(p.theme.foreColor)
            dc.SetFont(wx.Font(fontSize-1, wx.SWISS, wx.NORMAL, wx.NORMAL))
            dc.DrawTextList(textList, coords)

        def OnMove(self, event):
            self.prefs.varWinPos = self.GetPosition().Get()

        def OnClose(self, event):
            self.Destroy()
            self.frame.varDlg = None

    #--------------------------------------------------------------------------
    # Save an image of the graph to a file.

    def SaveImage(self, event):
        p = self.prefs
        context = wx.ClientDC(self.specP)
        memory = wx.MemoryDC()
        x, y = self.specP.ClientSize
        bitmap = wx.EmptyBitmap(x, y, -1)
        memory.SelectObject(bitmap)
        memory.Blit(0, 0, x, y, context, 0, 0)
        wildcard = "PNG (*.png)|*.png|JPEG (*.jpg)|*.jpg|BMP (*.bmp)|*.bmp"
        types = (".png", ".jpg", ".bmp")
        while True:
            imageDir = p.get("imageDir", appdir)
            dlg = wx.FileDialog(self, "Save image as...", defaultDir=imageDir,
                    defaultFile="", wildcard=wildcard, style=wx.SAVE)
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
            p.imageDir = os.path.dirname(path)
            chosenType = types[dlg.GetFilterIndex()]
            path = CheckExtension(path, self, types, chosenType)
            if not path:
                continue
            if ShouldntOverwrite(path, self):
                continue
            break
        base, ext = os.path.splitext(path)
        #type = wx.BITMAP_TYPE_PNG
        bmtype = wx.BITMAP_TYPE_PNG
        if ext == ".jpg":
            bmtype = wx.BITMAP_TYPE_JPEG    # JGH 2/10/14
        elif ext == ".bmp":
            bmtype = wx.BITMAP_TYPE_BMP # JGH 2/10/14
        print ("msapy>1266< Saving image to", path)
        bitmap.SaveFile(path, bmtype)   # JGH 2/10/14

    #--------------------------------------------------------------------------
    # Load or save spectrum data to an s1p file.

    def LoadData(self, event):
        self.StopScanAndWait()
        p = self.prefs
        wildcard = "S1P (*.s1p)|*.s1p"
        dataDir = p.get("dataDir", appdir)
        dlg = wx.FileDialog(self, "Choose file...", defaultDir=dataDir,
                defaultFile="", wildcard=wildcard)
        if dlg.ShowModal() != wx.ID_OK:
            return
        path = dlg.GetPath()
        p.dataDir = os.path.dirname(path)
##        print ("Reading", path)
        spec = self.spectrum = Spectrum.FromS1PFile(path)
        specP = self.specP
        specP.h0 = p.fStart = spec.Fmhz[0]  # EON Jan 10 2014
        specP.h1 = p.fStop  = spec.Fmhz[-1] # EON Jan 10 2014
        specP.eraseOldTrace = True
        p.nSteps = specP.cursorStep = spec.nSteps
        self.RefreshAllParms()
        self.DrawTraces()

    def SaveData(self, event=None, data=None, writer=None, name="Data.s1p"):
        self.StopScanAndWait()
        p = self.prefs
        if writer == None:
            writer = self.spectrum.WriteS1P
        if data == None:
            data = self.spectrum
        if data == None:
            raise ValueError("No data to save")
        name = os.path.basename(name)
        base, ext = os.path.splitext(name)
        wildcard = "%s (*%s)|*%s" % (ext[1:].upper(), ext, ext)
        while True:
            dataDir = p.get("dataDir", appdir)
            dlg = wx.FileDialog(self, "Save as...", defaultDir=dataDir,
                    defaultFile=name, wildcard=wildcard, style=wx.FD_SAVE)
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
            p.dataDir = os.path.dirname(path)
            path = CheckExtension(path, self, (ext))
            if not path:
                continue
            if ShouldntOverwrite(path, self):
                continue
            break
        if 0 or debug:
            print ("msapy>1320< Saving data to", path)
        if data == self.spectrum:
            writer(path, self.prefs)
        else:
            writer(data, path)

    #--------------------------------------------------------------------------
    # Load and save preferences using a dialog.

    def LoadPrefsFile(self, event):
        self.StopScanAndWait()
        p = self.prefs
        wildcard = "*.prefs"
        dataDir = p.get("dataDir", appdir)
        name = self.rootName + ".prefs"
        dlg = wx.FileDialog(self, "Choose file...", defaultDir=dataDir,
                defaultFile=name, wildcard=wildcard)
        if dlg.ShowModal() != wx.ID_OK:
            return
        path = dlg.GetPath()
        p.dataDir = os.path.dirname(path)
        self.prefs = p = Prefs.FromFile(path)
        isLight = p.get("graphAppear", "Light") == "Light"
        p.theme = (DarkTheme, LightTheme)[isLight]
        p.theme.UpdateFromPrefs(p)

    def SavePrefsFile(self, event):
        self.StopScanAndWait()
        p = self.prefs
        wildcard = "*.prefs"
        dataDir = p.get("dataDir", appdir)
        name = self.rootName + ".prefs"
        dlg = wx.FileDialog(self, "Save as...", defaultDir=dataDir,
            defaultFile=name, wildcard=wildcard, style=wx.FD_SAVE)
        if dlg.ShowModal() != wx.ID_OK:
            return
        path = dlg.GetPath()
        for m in self.specP.markers.values():
            m.SavePrefs(p)
        p.save(path)

    #--------------------------------------------------------------------------
    # Manually load and save preferences.

    def LoadPrefs(self, event=None):
        if self.prefs:
            self.StopScanAndWait()
        prefsName = os.path.join(appdir, self.rootName + ".prefs")
        self.prefs = p = Prefs.FromFile(prefsName)
        isLight = p.get("graphAppear", "Light") == "Light"
        p.theme = (DarkTheme, LightTheme)[isLight]
        p.theme.UpdateFromPrefs(p)

    def SavePrefs(self, event=None):
        p = self.prefs
        self.StopScanAndWait()
        for m in self.specP.markers.values():
            m.SavePrefs(p)
        p.theme.SavePrefs(p)
        p.save()

    #--------------------------------------------------------------------------
    # Open Test Setups Dialog box.

    def LoadSaveTestSetup(self, event=None):
        self.StopScanAndWait()
        p = self.prefs
        from testSetups import TestSetupsDialog
        dlg = TestSetupsDialog(self)
        dlg.ShowModal()
        p.testSetupsWinPos = dlg.GetPosition().Get()

    #--------------------------------------------------------------------------
    # Set Markers mode.

    def SetMarkers_Indep(self, event=None):
        self.prefs.markerMode = Marker.MODE_INDEP
        self.RefreshAllParms()

    def SetMarkers_PbyLR(self, event=None):
        self.prefs.markerMode = Marker.MODE_PbyLR
        self.RefreshAllParms()

    def SetMarkers_LRbyPp(self, event=None):
        self.prefs.markerMode = Marker.MODE_LRbyPp
        self.RefreshAllParms()

    def SetMarkers_LRbyPm(self, event=None):
        self.prefs.markerMode = Marker.MODE_LRbyPm
        self.RefreshAllParms()

    #--------------------------------------------------------------------------
    # Open the Reference Line Specification dialog box.

    def SetRef(self, event):
        p = self.prefs
        eventId = event.Id
        for m in self.sweepMenu.GetMenuItems():
            if "ref" in m.GetText().lower():
                subItems = m.GetSubMenu().GetMenuItems()
                refNum = 0
                for sub in subItems:
                    if eventId == sub.GetId():
                        break
                    refNum += 1
        from ref import RefDialog
        dlg = RefDialog(self, refNum)
        dlg.ShowModal()
        p.refWinPos = dlg.GetPosition().Get()

        self.DrawTraces()
        self.specP.FullRefresh()

    #--------------------------------------------------------------------------
    # Open the Perform Calibration dialog box.

    def PerformCal(self, event=None):
        self.StopScanAndWait()
        p = self.prefs
        from cal import PerformCalDialog
        dlg = PerformCalDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            p.perfCalWinPos = dlg.GetPosition().Get()
            return True
        return False

    # Start EON Jan 10 2014
    #--------------------------------------------------------------------------
    # Open the Perform Calibration dialog box.

    def PerformCalUpd(self, event=None):
        self.StopScanAndWait()
        p = self.prefs
        from cal import PerformCalUpdDialog
        dlg = PerformCalUpdDialog(self)
        if not dlg.error: # EON Jan 29, 2014
            if dlg.ShowModal() == wx.ID_OK:
                p.perfCalUpdWinPos = dlg.GetPosition().Get()

    # End EON Jan 10 2014

    #--------------------------------------------------------------------------
    # Set the calibration reference to Band, Base, or None.

    def SetCalRef_Band(self, event):
        global msa
        if msa.IsScanning():
            self.StopScanAndWait()
        if not msa.bandCal:
            self.PerformCal()
        if msa.bandCal:
            self.SetCalLevel(2)
        self.RefreshAllParms()

    def SetCalRef_Base(self, event):
        global msa
        if msa.IsScanning():
            self.StopScanAndWait()
        if not msa.baseCal:
            self.PerformCal()
        if msa.baseCal:
            self.SetCalLevel(1)
        self.RefreshAllParms()

    def SetCalRef_None(self, event):
        self.SetCalLevel(0)
        self.RefreshAllParms()

    #--------------------------------------------------------------------------
    # Set the calibration reference level, base, and band, keeping msa, prefs,
    # and data files in sync.

    def SetCalLevel(self, level):
        global msa
        p = self.prefs
        msa.calLevel = p.calLevel = level
        if self.CalCheck(): # EON Jan 29, 2014
            self.RefreshAllParms()

    def SetBandCal(self, spectrum):
        global msa
        msa.bandCal = spectrum
        if spectrum:
            msa.bandCal.WriteS1P(self.bandCalFileName, self.prefs,
                                 contPhase=True)
        else:
            try:
                os.unlink(self.bandCalFileName)
            except:
                pass

    def SetBaseCal(self, spectrum):
        global msa
        msa.baseCal = spectrum
        self.SaveCal(spectrum, self.baseCalFileName)

    def SetBandeCal(self, spectrum):
        global msa
        msa.bandCal = spectrum
        self.SaveCal(spectrum, self.bandCalFileName)

    def SaveCal(self, spectrum, path):
        if spectrum:
            spectrum.WriteS1P(path, self.prefs, contPhase=True)
        elif os.path.exists(path):
            os.unlink(path)

    def LoadCal(self, path):
        if os.path.exists(path):
            cal = Spectrum.FromS1PFile(path) # EON Jan 29, 2014
            if cal == None:
                from cal import OslCal
                cal = OslCal.FromS1PFile(path)
            return cal
        else:
            return None

    def CopyBandToBase(self):
        global msa
        if msa.bandCal != None:
            msa.baseCal = dcopy.deepcopy(msa.bandCal)
            msa.baseCal.WriteS1P(self.baseCalFileName, self.prefs, contPhase=True)

    #--------------------------------------------------------------------------
    # Read CalPath file for mag/phase linearity adjustment.

    def ReadCalPath(self):
        global msa
        if 0 or debug:
            print ("msapy>1549< Reading path calibration")
        self.StopScanAndWait()
        p = self.prefs
        directory, fileName = CalFileName(p.RBWSelindex+1)
        try:
            f = open(os.path.join(directory, fileName), "Ur")
            msa.magTableADC, msa.magTableDBm, msa.magTablePhase = \
                    CalParseMagFile(f)
            if 0 or debug:
                print (fileName, "read OK.")
        except:
            ##traceback.print_exc()
            if 0 or debug:
                print ("msapy>1562<", fileName, "not found. Using defaults.")

    #--------------------------------------------------------------------------
    # Read CalFreq file for mag frequency-dependent adjustment.

    def ReadCalFreq(self):
        global msa
        if 0 or debug:
            print ("msapy>1570< Reading frequency calibration")
        self.StopScanAndWait()
        directory, fileName = CalFileName(0)
        try:
            f = open(os.path.join(directory, fileName), "Ur")
            msa.freqTableMHz, msa.freqTableDB = CalParseFreqFile(f)
            if 0 or debug:
                print (fileName, "read OK.")
        except:
            ##traceback.print_exc()
            if 0 or debug:
                print (fileName, "not found. Using defaults.")

    #--------------------------------------------------------------------------
    # Write data to a file.

    def SaveGraphData(self, event):
        self.SaveData(writer=self.specP.WriteGraph, name="GraphData.txt")

    def SaveInputData(self, event):
        self.SaveData(writer=self.spectrum.WriteInput, name="InputData.txt")

    def SaveInstalledLineCal(self, event):
        global msa
        p = self.prefs
        if p.calLevel == 1:
            self.SaveData(data=msa.bandCal, writer=self.SaveCal,
                            name=self.bandCalFileName)
        elif p.calLevel == 2:
            self.SaveData(data=msa.baseCal, writer=self.SaveCal,
                            name=self.baseCalFileName)

    #--------------------------------------------------------------------------
    # Write debugging event lists to a file.

    def WriteEvents(self, event):
        global msa
        msa.WriteEvents(GuiEvents())

    def DumpEvents(self, event):
        global msa
        msa.DumpEvents()

    #--------------------------------------------------------------------------
    # Show the Functions menu dialog boxes.

    def AnalyzeFilter(self, event):
        if not self.filterAnDlg:
            from filter import FilterAnalDialog
            self.filterAnDlg = FilterAnalDialog(self)
        else:
            self.filterAnDlg.Raise()

    def ComponentMeter(self, event):
        if not self.compDlg:
            from componentMeter import ComponentDialog
            self.compDlg = ComponentDialog(self)
        else:
            self.compDlg.Raise()

    def AnalyzeRLC(self, event):
        if not self.tranRLCDlg:
            from rlc import AnalyzeRLCDialog
            self.tranRLCDlg = AnalyzeRLCDialog(self)
        else:
            self.tranRLCDlg.Raise()

    def CoaxParms(self,event):
        if not self.coaxDlg:
            from coax import CoaxParmDialog
            self.coaxDlg = CoaxParmDialog(self)
        else:
            self.coaxDlg.Raise()

    def AnalyzeCrystal(self, event):
        if not self.crystalDlg:
            from crystal import CrystAnalDialog
            self.crystalDlg = CrystAnalDialog(self)
        else:
            self.crystalDlg.Raise()

    def GroupDelay(self,event):
        if not self.grpDlyDlg:
            from  groupDelay import GroupDelayDialog
            self.grpDlyDlg = GroupDelayDialog(self)
        else:
            self.grpDlyDlg.Raise()

    def StepAttenuator(self, event):
        if not self.stepDlg:
            from stepAtten import StepAttenDialog
            self.stepDlg = StepAttenDialog(self)
        else:
            self.stepDlg.Raise()

    #--------------------------------------------------------------------------
    # Set the main operating mode.

    def SetMode_SA(self, event=None):
        self.SetMode(MSA.MODE_SA)
        
    def SetMode_SATG(self, event):
        self.SetMode(MSA.MODE_SATG)

    def SetMode_VNATran(self, event):
        self.SetMode(MSA.MODE_VNATran)

    def SetMode_VNARefl(self, event):
        self.SetMode(MSA.MODE_VNARefl)

    def SetMode(self, mode):
        global msa
        self.StopScanAndWait()

        self.InitMode(mode)

        if 0 or debug:
            print ("msapy>1687< Changed MSA mode to", msa.modeNames[mode])
        self.prefs.mode = mode
        msa.SetMode(mode)
        if self.specP:
            # reset trace type selections to default for this mode
            vScales = self.specP.vScales
            vs0 = vScales[0]
            vs0.typeIndex = 1
            vs0.dataType = dataType = trace.traceTypesLists[mode][vs0.typeIndex]
            vs0.top = dataType.top
            vs0.bot = dataType.bot
            if vs0.top == 0 and vs0.bot == 0:
                vs0.AutoScale(self)
            vs1 = vScales[1]
            vs1.typeIndex = (0, 2)[mode >= MSA.MODE_VNATran]
            vs1.dataType = dataType = trace.traceTypesLists[mode][vs1.typeIndex]
            vs1.top = dataType.top
            vs1.bot = dataType.bot
            if vs1.top == 0 and vs1.bot == 0:
                vs1.AutoScale(self)
        self.needRestart = True
        # Flip the TR switch
        self.RefreshAllParms()
        self.DrawTraces()

    # Start EON Jan 22, 2014
    # Initializes menu bar based on mode
    def InitMode(self,mode):
        global msa
        p = self.prefs
        if mode == MSA.MODE_SA:
            p.switchSG = 0    # switchSG not implemented in software
        elif mode == MSA.MODE_SATG:
            p.switchSG = 1    # switchSG not implemented in software
        elif mode == MSA.MODE_VNATran:
            p.switchTR = 0
        elif mode == MSA.MODE_VNARefl:
            p.switchTR = 1

        p.calLevel = msa.calLevel = 0

        menuBar = self.MenuBar
        i = menuBar.FindMenu("Functions")
        funcMenu = menuBar.GetMenu(i)
        skip = True
        for m in funcMenu.GetMenuItems():
            txt = m.GetText().lower()
            if len(txt) == 0:
                skip = False
            if skip:
                continue # Goes no next m
            found = False # Divider line found
            for val in self.funcModeList[mode]:
                if val in txt:
                    found = True
                    break
            m.Enable(found) # Enables items for the mode selected

        if mode == MSA.MODE_SA or mode == MSA.MODE_SATG:
            i = menuBar.FindMenu("Operating Cal")
            if i > 0:
                menuBar.Remove(i)
            i = menuBar.FindMenu("Two Port")
            if i > 0:
                menuBar.Remove(i)
        else:
            if menuBar.FindMenu("Operating Cal") < 0:
                i = menuBar.FindMenu("Mode")
                if i > 0:
                    menuBar.Insert(i,self.operatingCalMenu,"Operating Cal")
            if menuBar.FindMenu("Two Port") < 0:
                i = menuBar.FindMenu("Mode")
                if i > 0:
                    menuBar.Insert(i,self.twoPortMenu,"Two Port")

    #--------------------------------------------------------------------------
    # Open the Two Port  dialog box. TENTAVIVE : JGH 3/29/14

    def TwoPortShow(self, event): # Added by JGH 3/29/14
        
        self.StopScanAndWait()
        from twoPort import TransferParams
        dlg = TransferParams(self)
        dlg.Show()

    #--------------------------------------------------------------------------
    # Handle a resize event of the main frame or log pane sash.

    def OnSizeChanged(self, event):
        p = self.prefs
        (self.fHdim, self.fVdim) = p.frameSize = self.GetSize()
        event.Skip()

    def OnSashChanged(self, event):
        p =  self.prefs
        sashWin = event.GetEventObject()
        p.logSplit = sashWin.GetSashPosition()
        #print("sashWin.name: ", sashWin.name) # JGH: sashWin.name is "log"
        setattr(self.prefs, sashWin.name + "Split", sashWin.GetSashPosition())
        event.Skip()

    #--------------------------------------------------------------------------
    # Hide/ reveal message panel

    def logPshow(self, event):
        p = self.prefs
##        print("logSplit on show: ", p.logSplit)
        self.logSplitter.SetSashPosition(p.logSplit)
        self.logP.Show()
        p.logP = 0
        if event:
            self.RefreshAllParms()
            event.Skip()

    def logPhide(self, event):
        p = self.prefs
        if 0 or debug:
            print("msapy>1804< logSplit on hide: ", p.logSplit)
        self.logSplitter.SetSashPosition(self.fVdim)
        self.logP.Hide()
        p.logP = 1
        if event:
            self.RefreshAllParms()
            event.Skip()

    def OnSplitterDClick(self, event):
        event.Veto()
        self.logPhide(None)
        self.RefreshAllParms()

    #--------------------------------------------------------------------------
    # About dialog.

    def OnAbout(self, event):
        info = wx.AboutDialogInfo()
        info.Name = self.appName
        info.Version = version
        info.Description = "MSAPy is a portable interface for the " \
            "Modular Spectrum Analyzer."
        info.WebSite = ("http://sourceforge.net/projects/msapy/",
                        "MSAPy SourceForge page")
        info.Developers = ["Scott Forbes", "Sam Wetterlin", \
                           "Scotty Sprowls", "Jim Hontoria, W1JGH", \
                           "Eric Nystrom, W4EON"]
        wx.AboutBox(info)

    #--------------------------------------------------------------------------
    # Quitting.

    def OnExit(self, event):
        global msa
        if msa.syndut:    # JGH syndutHook8
            msa.syndut.Close()
        if self.smithDlg:
            self.smithDlg.Close()
        self.SavePrefs()
        print ("Exiting2")
        self.Destroy()

#==============================================================================
# Start up application.

class MSAApp(wx.App):
    def OnInit(self):
        name = os.path.splitext(os.path.split(sys.argv[0])[1])[0]
        appPath = os.path.split(sys.argv[0])[0].split(os.path.sep)
        for f in appPath:
            if ".app" in f:
                name = f[:-4]
                break
        MSASpectrumFrame(None, name)
        return True

    def ProcessEvent(self, event):
        if 0 or debug:
            print ("ProcessEvent")
        event.Skip()
