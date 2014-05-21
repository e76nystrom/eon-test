from msaGlobal import SetModuleVersion
import string,wx

SetModuleVersion("theme",("1.30","EON","05/20/2014"))

# Waveform display colors

# light-theme colors
red       = wx.Colour(255,   0,   0)
blue      = wx.Colour(  0,   0, 255)
green     = wx.Colour(  0, 255,   0)
aqua      = wx.Colour(  0, 255, 255)
lavender  = wx.Colour(255,   0, 255)
yellow    = wx.Colour(255, 255,   0)
peach     = wx.Colour(255, 192, 203)
dkbrown   = wx.Colour(165,  42,  42)
teal      = wx.Colour(  0, 130, 130)
brown     = wx.Colour(130,   0, 130)
stone     = wx.Colour(240, 230, 140)
orange    = wx.Colour(255, 165,   0)
ltgray    = wx.Colour(180, 180, 180)

# original MSA dark-theme colors
msaGold   = wx.Colour(255, 190,  43)
msaAqua   = aqua
msaGreen  = wx.Colour(0,   255,   0)
msaYellow = wx.Colour(244, 255,   0)
msaGray   = wx.Colour(176, 177, 154)

# Convert a dictionary into a structure. Representation is evaluatable.

class Struct:
    def __init__(self, **entries):
        self.__dict__.update(entries)

    def __repr__(self):
        return "Struct(**dict(" + string.join(["%s=%s" % \
            (nm, repr(getattr(self, nm))) \
            for nm in dir(self) if nm[0] != "_"], ", ") + "))"

#==============================================================================
# A Color theme.

class Theme:

    @classmethod
    def FromDict(cls, d):
        d = Struct(**d)
        this = cls()
        this.name       = d.name
        this.backColor  = d.backColor
        this.foreColor  = d.foreColor
        this.hColor     = d.hColor
        this.vColors    = d.vColors
        this.gridColor  = d.gridColor
        this.textWeight = d.textWeight
        this.iNextColor = 0
        return this

    def UpdateFromPrefs(self, p):
        for attrName in self.__dict__.keys():
            pAttrName = "theme_%s_%s" % (p.graphAppear, attrName)
            if hasattr(p, pAttrName):
                setattr(self, attrName, getattr(p, pAttrName))

    def SavePrefs(self, p):
        for attrName, attr in self.__dict__.items():
            if attrName[0] != "_":
                pAttrName = "theme_%s_%s" % (p.graphAppear, attrName)
                setattr(p, pAttrName, attr)

DarkTheme = Theme.FromDict(dict(
        name       = "Dark",
        backColor  = wx.BLACK,
        foreColor  = wx.WHITE,
        gridColor  = msaGray,
        hColor     = wx.WHITE,
        vColors    = [msaGold, msaAqua, msaGreen, msaYellow, teal, brown],
        textWeight = wx.BOLD))

LightTheme = Theme.FromDict(dict(
        name       = "Light",
        backColor  = wx.WHITE,
        foreColor  = wx.BLACK,
        gridColor  = ltgray,
        hColor     = wx.BLACK,
        vColors    = [red, blue, green, blue, aqua, lavender, yellow, peach,
                      dkbrown, stone, orange],
        textWeight = wx.NORMAL))
