#!/bin/bash
dst=/etc/udev/rules.d
fil=z70_usbfx2.rules
diff $fil $dst/$fil >/dev/null 2>&1
ret=$?
#echo $ret
if [ $ret -ne 0 ]
then
 echo "replacing $fil"
 sudo cp $fil $dst
fi
dst=/etc/modprobe.d
fil=blacklist.conf
sudo grep usbtest $dst/$fil >/dev/null 2>&1
ret=$?
#echo $ret
if [ $ret -ne 0 ]
then
 echo "adding usbtest to blacklist.conf"
 echo "blacklist usbtest" >>$dst/$fil
fi