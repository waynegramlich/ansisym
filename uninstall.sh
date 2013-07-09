#!/bin/bash
# Assumes installation via: python setup.py install --record install.record
# This deletes the files, but not the path to the files.
/usr/bin/sudo rm $(cat install.record)

