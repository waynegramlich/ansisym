#!/usr/bin/env python
from setuptools import setup
from subprocess import call

setup(name="ansisym",
      version = "0.1",
      description = "Generates ANSI-style symbols for gEDA gschem.",
      author = "David B. Curtis",
      author_email = "davecurtis@sonic.net",
      packages = ['ansisym_pkg'],
      scripts = ['ansisym'],
      long_description="""
Ansisym generates ANSI-style schematic symbols for use with the
GNU EDA suite (gEDA) schematic editor, gschem.  The input is a
simple text file.  The resulting symbol aspires to be compliant
with ANSI standards.""",
      install_requires = [
          'ply',
      ]
)

call(['ansisym', '--setup'])



