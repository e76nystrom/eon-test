#!/usr/bin/env python

"""
wxPython Calculator Demo in 50 lines of code by Chris barker, NOAA

This demo was pulled from the wxPython Wiki:

http://wiki.wxpython.org/CalculatorDemo by Miki Tebeka

It has been altered to allow it to be "driven" by an external script,
plus a little layout improvement Modified to work with the Modular
spectrum Analyzer software by Jim Hontoria, W1JGH.
"""

# Calculator GUI:

# ___________v
# [7][8][9][/]
# [4][5][6][*]
# [1][2][3][-]
# [0][.][C][+]
# [ = ]

from __future__ import division # So that 8/3 will be 2.6666 and not 2
import wx
import wx.lib.buttons as buttons
from msaGlobal import GetMsa
#from math import * # So we can evaluate "sqrt(8)"

class NumKeypad(wx.Dialog):
    def __init__(self, frame):
        wx.Dialog.__init__(self, frame, -1, "Numeric Entry",
                           wx.DefaultPosition, wx.DefaultSize,
                           wx.DEFAULT_DIALOG_STYLE)

##        self.osk = Calculator(self)

##        S = wx.BoxSizer(wx.VERTICAL)
##        S.Add(self.osk, 1, wx.GROW|wx.ALL, 5)
##        self.SetSizerAndFit(S)
##        self.CenterOnScreen()

##class Calculator(wx.Panel):
##    '''Main calculator dialog'''
##    def __init__(self, *args, **kwargs):
##        wx.Panel.__init__(self, *args, **kwargs)
        sizer = wx.BoxSizer(wx.VERTICAL) # Main vertical sizer

        self.display = wx.ComboBox(self) # Current calculation
        sizer.Add(self.display, 0, wx.EXPAND|wx.BOTTOM, 8) # Add to main sizer

        # [7][8][9][/]
        # [4][5][6][*]
        # [1][2][3][-]
        # [0][.][C][+]
        gsizer = wx.GridSizer(4, 4, 5, 5)
        for row in (("7", "8", "9", "/"),
                    ("4", "5", "6", "*"),
                    ("1", "2", "3", "-"),
                    ("0", ".", "C", "+")):
            for label in row:
##                b = wx.Button(self, label=label, size=(40,-1))
                b = buttons.GenButton(self,-1, label, size=(40,30))
                font = 12
                b.SetFont(wx.Font(font, wx.SWISS, wx.NORMAL, wx.BOLD, False))
                b.SetBezelWidth(5)
                b.SetBackgroundColour("white")
                b.SetForegroundColour("black")
                gsizer.Add(b)
                b.Bind(wx.EVT_BUTTON, self.OnButton)
        sizer.Add(gsizer, 1, wx.EXPAND)

        # [ = ]
##        b = wx.Button(self, label="=")
        b = buttons.GenButton(self,label="=")
        b.SetFont(wx.Font(font, wx.SWISS, wx.NORMAL, wx.BOLD, False))
        b.SetBezelWidth(5)
        b.SetBackgroundColour("white")
        b.SetForegroundColour("black")
        b.Bind(wx.EVT_BUTTON, self.OnButton)
        sizer.Add(b, 0, wx.EXPAND|wx.ALL, 8)
        self.equal = b
        self.OnResult = None

        # Set sizer and center
        self.SetSizerAndFit(sizer)

##        S = wx.BoxSizer(wx.VERTICAL)
##        S.Add(self.osk, 1, wx.GROW|wx.ALL, 5)
##        self.SetSizerAndFit(S)
##        self.CenterOnScreen()


    def OnButton(self, evt):
        '''Handle button click event'''
        
        # Get title of clicked button
        label = evt.GetEventObject().GetLabel()

        if label == "=": # Calculate
            result = self.Calculate()
            if self.OnResult != None:
                self.OnResult(result)
        elif label == "C": # Clear
            self.display.SetValue("")

        else: # Just add button text to current calculation
            self.display.SetValue(self.display.GetValue() + label)
            self.display.SetInsertionPointEnd()
            self.equal.SetFocus() # Set the [=] button in focus

    def Calculate(self):
        """
do the calculation itself
in a separate method, so it can be called outside of a button event handler
"""
        try:
            compute = self.display.GetValue()
            # Ignore empty calculation
            if not compute.strip():
                return

            # Calculate result
            result = eval(compute)

            # Add to history
            self.display.Insert(compute, 0)

            # Show result
            self.display.SetValue(str(result))
            return(str(result))
        except Exception, e:
            wx.LogError(str(e))
            return

    def ComputeExpression(self, expression):
        """
Compute the expression passed in.
This can be called from another class, module, etc.
"""
        print "ComputeExpression called with:", expression
        self.display.SetValue(expression)
        self.Calculate()

    def SetOnResult(self, OnResult):
        self.OnResult = OnResult

class TextCtrl(wx.TextCtrl):
    def __init__(self, *args, **kwargs):
        wx.TextCtrl.__init__(self,*args, **kwargs)
        self.Bind(wx.EVT_RIGHT_DOWN, self.OnRightClick)

    def OnRightClick(self, event):
        self.osk = osk = NumKeypad(GetMsa().frame)
        osk.display.SetValue(self.GetValue())
        osk.Bind(wx.EVT_CLOSE, self.OnClose)
        osk.SetOnResult(self.OnResult)
        osk.ShowModal()

    def OnResult(self, result):
        self.SetValue(result)

    def OnClose(self, event):
        osk = self.osk
        value = osk.display.GetValue().strip()
        if len(value) != 0:
            try:
                value = eval(value)
                self.SetValue(str(value))
            except:
                pass
        osk.Destroy()
