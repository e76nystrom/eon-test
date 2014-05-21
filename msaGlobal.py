import os, sys
import wx.lib.newevent as newevent

ModuleInfo = {}

def SetModuleVersion(name, version):
    global ModuleInfo
    ModuleInfo[name] = version

def GetModuleInfo():
    global ModuleInfo
    return(ModuleInfo)

SetModuleVersion("msaGlobal",("1.30","EON","05/20/2014"))

logEvents = False

hardwarePresent = True

# Graph update interval, in milliseconds. The tradoff is between smooth
# "cursor" movement and drawing overhead.
msPerUpdate = 100

incremental = True

isWin   = (sys.platform == "win32")
isLinux=(sys.platform == "linux2")
isMac=(sys.platform=="darwin" or not (isWin or isLinux))

# set to disable auto-double-buffering and use of anti-aliased GraphicsContext
slowDisplay = isWin

# appdir is the directory containing this program
appdir = os.path.abspath(os.path.dirname(sys.argv[0]))
resdir = appdir

# Create a new Event class and EVT binder function
(UpdateGraphEvent, EVT_UPDATE_GRAPH) = newevent.NewEvent()

if isWin:
    resdir = os.environ.get("_MEIPASS2")
    if not resdir:
        resdir = appdir
elif os.path.split(appdir)[1] == "Resources":
    appdir = os.path.normpath(appdir + "/../../..")

def SetVersion(val):
    global version
    version = val

def GetVersion():
    global version
    return(version)

def SetHardwarePresent(val):
    global hardwarePresent, msa
    hardwarePresent = val
    msa.hardwarePresent = val

def GetHardwarePresent():
    global hardwarePresent
    return(hardwarePresent)

def SetFontSize(val):
    global fontSize
    fontSize = val

def GetFontSize():
    global fontSize
    return(fontSize)

def SetMsa(val):
    global msa
    msa = val

def GetMsa():
    global msa
    return(msa)

def SetLO1(val):
    global LO1
    LO1 = val

def GetLO1():
    global LO1
    return(LO1)

def SetLO2(val):
    global LO2
    LO2 = val

def GetLO2():
    global LO2
    return(LO2)

def SetLO3(val):
    global LO3
    LO3 = val

def GetLO3():
    global LO3
    return(LO3)

def SetCb(val):
    global cb
    cb = val

def GetCb():
    global cb
    return(cb)
