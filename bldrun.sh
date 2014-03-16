#!/bin/bash
apt-get install upx-ucl
tar xzvf PyInstaller-2.1.tar.gz
cd PyInstaller-2.1/bootloader
./waf configure --no-lsb
./waf
pi=0
if [ $pi -ne 0 ]
then
 dst=/usr/local/lib/python2.7/dist-packages/PyInstaller-2.1-py2.7.egg/PyInstaller/loader/rthooks/
else
 dst=/usr/local/lib/python2.6/dist-packages/PyInstaller/loader/rthooks/
fi
cd $dst
sudo mkdir Linux-32bit-arm
cd linux-32bit-arm
sudo cp /home/debian/PyInstaller-2.1/bootloader/build/debug/run_d .
sudo cp /home/debian/PyInstaller-2.1/bootloader/build/debugw/runw_d .
sudo cp /home/debian/PyInstaller-2.1/bootloader/build/releasew/runw . 
sudo cp /home/debian/PyInstaller-2.1/bootloader/build/release/run .
cd
