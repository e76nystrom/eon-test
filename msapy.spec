# -*- mode: python -*-

# pyinstaller-2.0 build spec to create MSAPy.exe

a = Analysis(["msaRun.py",
              "cal.py",
              "calMan.py",
              "cavityFilter.py",
              "coax.py",
              "componentMeter.py",
              "configDialog.py",
              "crystal.py",
              "ctlBrdTests.py",
              "ddstest.py",
              "events.py",
              "filter.py",
              "functionDialog.py",
              "graphPanel.py",
              "marker.py",
              "memLeak.py",
              "msa.py",
              "msa_cb.py",
              "msa_cb_pc.py",
              "msa_cb_usb.py",
              "msaGlobal.py",
              "msapy.py",
              "pdmCal.py",
              "ref.py",
              "rlc.py",
              "smithPanel.py",
              "spectrum.py",
              "stepAtten.py",
              "sweepDialog.py",
              "synDUT.py",
              "testSetups.py",
              "theme.py",
              "trace.py",
              "util.py",
              "vScale.py"],
             pathex=[])

pyz = PYZ(a.pure)

binaries = a.binaries + [
            ("inpout32.dll", "inpout32.dll", "BINARY"),
            ]

data = a.datas + [
            ("usbpar.ihx", "usbpar.ihx", "DATA"),
            ]

exe = EXE( pyz,
          ##a.scripts + [("v", "", "OPTION")],
          a.scripts,
          binaries,
          a.zipfiles,
          data,
          name="MSAPy.exe",
          debug=False,    # True to see error messages when launching .exe
          strip=False,
          icon="MSAPy_icon128.ico",
          upx=True,
          console=False )
