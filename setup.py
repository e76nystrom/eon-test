"""
py2app/py2exe build script for MSAPy.

Usage (Mac OS X):
    python2.5 setup.py py2app

 (Windows build uses pyinstaller instead)
"""
import ez_setup
ez_setup.use_setuptools()

import sys
from setuptools import setup

mainscript = "msaRun.py"
longName = "Modular Spectrum Analyzer"

# grab version and copyright info from source
version = "None"
copyright = "None"
for line in open(mainscript).readlines():
    if line.find("# Copyright") == 0:
        copyright = line[2:].rstrip()
    elif line.find("version = ") == 0:
        version = line[10:].rstrip().replace('"', '')

if sys.platform == "darwin":
    extra_options = dict(
        setup_requires=["py2app"],
        app=[mainscript],
        options=dict(py2app=dict(iconfile="MSAPy_app.icns",
            includes=["usb"],
            plist=dict(CFBundleGetInfoString=longName,
                CFBundleIdentifier="net.sf.msapy",
                CFBundleVersion=version,
                NSHumanReadableCopyright=copyright,
            ),
            resources=["usbpar.ihx", "cycfx2prog"],
        )),
        data_files=[("../Frameworks",
            ["/opt/local/lib/libusb-legacy/libusb-legacy-0.1.4.dylib",
             "/opt/local/lib/libusb-1.0.dylib"])]
    )
elif sys.platform != "win32":
    extra_options = dict(
        # Normally unix-like platforms will use "setup.py install"
        # and install the main script as such
         scripts=[mainscript],
    )

setup(
    name="MSAPy",
    **extra_options
)
