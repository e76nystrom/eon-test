#!/usr/bin/python
# -*- coding: utf-8 -*-

from msaGlobal import SetModuleVersion

SetModuleVersion("msaRun",("1.0","3/6/2014"))

import sys, traceback
import msapy

debug = False
showProfile = 0     # set to 1 to generate msa.profile. Then run showprof.py.
showThreadProfile = 0  # set to 1 to generate msa.profile for both threads

#print(sys.argv[1:])
if "-h" in sys.argv[1:]:
    print ("")
    print ("COMMAND LINE ARGUMENTS:")

    print (" The following work with all systems:")
    print ("-h for this help")
    print ("-dbg for debug mode")
    print ("-pro for profiler")
    print ("")
if "-dbg" in sys.argv[1:]:
    print ("Debug mode is ON")
    debug = True
else:
    print ("Debug mode is OFF")
    debug = False
if "-pro" in sys.argv[1:]:
    print ("Profile mode is ON")
    showProfile = 1   # set to 1 to generate msa.profile. Then run showprof.py.
    showThreadProfile = 0  # set to 1 to generate msa.profile for both threads
else:
    print ("Profile mode is OFF")
    showProfile = 0
    showThreadProfile = 0  # set to 1 to generate msa.profile for both threads

if __name__ == "__main__":
    try:
        app = msapy.MSAApp(redirect=False)
        msapy.debug = debug
        if showThreadProfile:
            #import yappi    # JGH 2/10/14, requires yappi-0.82.tar.gz
            # profile code (both threads) and write results
            #yappi.start(builtins=True)
            app.MainLoop()
            #yappi.stop()
            f = open("msa.profile", "w")
            #yappi.print_stats(f, yappi.SORTTYPE_TSUB)
            f.close()
        elif showProfile:
            import cProfile
            # profile code (main thread only) and write results
            cProfile.run("app.MainLoop()", "msa.profile")
            # To see the stats, do:
            #   ./showprof.py
        else:
            # normal run
            ##wx.lib.inspection.InspectionTool().Show()
            app.MainLoop()
    except:
        from wx.lib.dialogs import ScrolledMessageDialog
        dlg = ScrolledMessageDialog(None, traceback.format_exc(), "Error")
        dlg.ShowModal()
        sys.exit(-1)
