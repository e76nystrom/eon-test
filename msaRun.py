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

from msaGlobal import SetModuleVersion

SetModuleVersion("msaRun",("1.01","EON","03/12/2014"))

import sys, traceback
import msapy

debug = False
showProfile = 0     # set to 1 to generate msa.profile. Then run showprof.py.
showThreadProfile = 0  # set to 1 to generate msa.profile for both threads

#print(sys.argv[1:])
if "-h" in sys.argv[1:]:
    print ("")
    print ("COMMAND LINE ARGUMENTS:")

    print (" The following works with all systems:")
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
