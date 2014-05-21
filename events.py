from msaGlobal import logEvents, SetModuleVersion
from util import msElapsed
from numpy import mod

SetModuleVersion("events",("1.30","EON","05/20/2014"))

debug = False

#------------------------------------------------------------------------------
# Debug-event gathering. These events are stored without affecting timing or
# the display, and may be dumped later via the menu Data>Debug Events.

eventNo = 0
guiEvents = []

class Event:
    def __init__(self, what):
        global eventNo
        self.what = what
        self.when = int(msElapsed())*1000 + eventNo
        if debug:
            print ("Event %5d.%3d: %s" % (self.when/1000, \
                mod(self.when, 1000), what))
        eventNo += 1

def ResetEvents():
    global eventNo, guiEvents
    eventNo = 0
    guiEvents = []

# Log one GUI event, given descriptive string. Records elapsed time.

def LogGUIEvent(what):
    global guiEvents
    if logEvents: # EON Jan 22, 2014
        guiEvents.append(Event(what))

def GuiEvents():
    return guiEvents
