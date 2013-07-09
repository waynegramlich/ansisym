ansisym
=======

ansisym creates ANSI-style schematic symbols for the gEDA suite schematic
editor, gschem.

About ansisym
-------------

ansisym enables quick and simple creation of schematic symbols for the
gschem schematic editor.  The input is a simple and terse text file that
is easy to create from a datasheet.  ansisym simplifies the creation of
bifurcated part symbols -- that is, a single part may be represented by
multiple blocks, each representing a subset of the I/O.  This is important
for creating ANSI-style schematics.

The goal is a symbol that is fully compliant with ANSI standards for
schematic symbols.  Currently, ansisym is not capable of generating the 
full range of ANSI symbols, but it does support a broad range of widely
used symbol elements.  The main feature missing is graphical sub-blocks,
which was valuable in the days of MSI logic, but much less so today.  Also,
some symbols are "not quite ANSI".  Patches are welcome.

Documentation
-------------

See the Ansisym User's Guide for tutorial and reference information.

See the Ansisym Hacker's Guide when you want to dig into the code.

Install
-------

ansisym depends on pycairo (py2cairo, to be precise, as ansiym is written
in Python 2.7) and ply.  pycairo does not use distutils, so use your
distro's normal install mechanism to pull in pycairo.  Then run:

    sudo python setup.py install 

Setup should be able to find ply automatically.

License
-------

ansisym is licensed under the GPL v3 or later.

Author
------

David B curtis

davecurtis AT sonic DOT net

