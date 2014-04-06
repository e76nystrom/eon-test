#!/bin/bash

python setup.py py2app
rm -f MSAPy_app.zip
cd dist
zip -r ../MSAPy_app MSAPy.app
