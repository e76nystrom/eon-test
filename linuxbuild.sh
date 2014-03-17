#!/bin/bash
pi=0
if [ $pi -ne 0 ]
then
 dst=/usr/local/lib/python2.7/dist-packages/PyInstaller-2.1-py2.7.egg/PyInstaller/loader/rthooks/
else
 dst=/usr/local/lib/python2.6/dist-packages/PyInstaller/loader/rthooks/
fi
fil=pyi_rth_usb
diff $fil.txt $dst/$fil.py >/dev/null
ret=$?
if [ $ret -ne 0 ]
then
 echo "replacing $fil"
 sudo cp $fil.txt $dst/$fil.py
fi
rm -rf build
rm -rf msapy
pyinstaller linuxmsapy.spec -F
mv dist msapy
cp cycfx2prog msapy
cp usbpar.ihx msapy
tar czf msapy.tar.gz msapy
