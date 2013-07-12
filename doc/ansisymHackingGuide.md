ansisym Hacking Guide
---------------------

Hacking guide revision 1, 8-July-2013.

Dave Curtis

# Overview

How to make gensymbol work the way you want it to.
Or help me make it work the way I want it to.
Patches are welcome.

Appologies for the sketchy nature of this first release 
of the hacking guide. 
Right now, I am concentrating on simply getting some
mileage on ansisym and building my symbol library.

# Internal Organization

## Parser-Model-Renderer

Ansisym is organized around a parser-model-renderer decomposition.

- The parser analyzes the input file, constructing a model.
- The model is an abstract representation of the symbol.  The model is self-validating.
- The renderer handles all aspects of symbol layout and rendering of the .sym file.

The parser is a simple LALR analyzer built using Dave Beazley's ply module.

The model is a simple tree of Python object instances.
It is self-validating and self-serializing.
Serializing the model is mainly for debug, but it is possible to 
split the normal invocation of ansisym into two phases: 1) parse to model and serialize, 
and 2) de-serialize a model from a text file and render.

The renderer is a view onto the model.
In general, there is a parallel viewer-object instance coupled to every
model instance.
Other symbol layout styles could be implemented 
or other schematic editors supported using the same input
syntax by simply replacing the renderer module with another that implements
different rendering.

(Beware the old joke: When a programmer says: "It should work.", that can usually
be translated into everyday English as "I haven't tested that.")

## External Modules

Ansisym depends on these standard Python modules:

- os
- ply
- cairo

## Internal Modules

- ansisymErrorSink - The error message funnel and exception definition.
- ansisymParser - Parses the input file, using ply.
- ansisymModel - Constructs an abstract model of an ansi symbol.
- ansisymGSView - Renders an abstract model as a gschem .sym file.
- ansisym - The main program; mainly does option processing and servers as a driver.

# Theory of Operations

## Overall flow

ansisym is a simple one-shot compiler.
After processing arguments, it either handles a few
special cases and exits, or falls into the
normal flow which has three phases of execution:

- Compile source text into a model.
- Validate model.
- Translate validated model to an output symbol.


## Parser

The lexer and parser are both defined in the file ``ansisymParser.py``.
Both are simple and straight-forward.
They are built using Dave Beazley's ply module for Python.

One oddity is that in order to avoid making the user type quotes for
every string, the lexer accepts both "quoted strings", and well as
stand-alone text and numbers as strings.
The lexer doesn't have enough context to tell if a string of digits
should be interpreted as a number or a string, so it just converts
them all, and lets the parser convert the number back to a string
when it needs to.

The parser keeps around a couple of cheezy context variables to
keep track of package lists and attribute lists.  Meh.

Error recovery is simple-minded.
Newlines are passed into the grammar, even though in truth they 
have no syntactic significance, because every line starts with 
a keyword.
They do, however, make a handy error recovery handle, and LALR
parsers very much need an anchor for error recovery.
So the basic strategy is to let the parser barf, then consume
all tokens up to a newline, which gets the parser resynchronized
on the next keyword.
If there are any syntax errors, ansisym bails at the end-of-file
without even trying to validate the model.
At least it will scan the entire input file for silly stuff
rather than quit at the first syntax error.

Related to error recovery, in the model, the base class
ModelObject has a special property called ``lineNo`` which
can be set to a line number, but need not be.
The ``lineNo`` getter returns either the value or None. 
The idea is that the parser can sprinkle line numbers into
the model when it has them (only lexical tokens have
reliable line numbers associated with them) and these can
be used in later phases for targeting error messages.
The ansisymGSView module, in particular, sows the entire
model tree together with parent pointers, so it can chase
up the model tree to higher level nodes until it gets
a non-None lineNo. 
In some cases, that lineNo might even be close to the error.

One ply idiom that will be unfamilar to users of other
yacc/bison clones is the Pythonic notion of using exceptions
as part of normal processing.
ply defines the exception ``SyntaxError``, so the parser
can ``raise SyntaxError`` when that is handy and throw
the parser into normal error recovery.

## Model

The ansisymModel.py module defines the classes for an abstract
model of the ANSI symbol for a part, with some gEDA-isms 
thrown in.
A successful parse will result in a simple tree of 
instances derived from ModelObject.
The model is self-serializing through __repr__, and 
can be written out after the compilation phase,
and also ansisym can de-serialize the model and complete
the back-end phase from a model.
This is mainly handy for debug.

### Model Validation

The model is self-validating. 
The predicate isValid() performs validation on an instance,
producing any error messages resulting from validation, and
recursively calls isValid() on any contained instances.
The intended use is to simply call isValid() on the
root part instance and let the model validate itself.

Ansisym does not proceed to layout unless the model is valid.

## Layout and Rendering flow

The module ansisymGSView.py implements a view onto a model.
Classes derived from GViewer are views onto corresponding
classes in the model.
The GViewer classes are mostly parallel to the Model tree,
with some extra specialization in places.
Like the model, the GViewer instances form a tree.

The view tree has full ``parent`` pointers so GViewer
instances can chase up the tree to the root.
This is employed for several properties by letting all 
classes inherit from GViewer an ``ask my parent`` method,
and letting classes that actually know the answer 
override that method.

Model data is not duplicated in view instances, instead,
accessor functions extract the necessary data from model instances.

## Error Reporting Strategy

The ansisymErrorSink.py module implements a simple error
message funnel and error counter.
For severities are supported: i, w, f, p for informative,
warning, fatal, and panic.
The error funnel does the actual message printing, and keeps
error counts.
In the case of a ``panic`` level message, it raises 
the ansisymPanic exception which propagates up to the driver
function and funnels into an error termination.

# Spooky Installation Behavior

Since generating the parse table for a complex grammar can be time
consuming, ply is careful to cache generated parse tables and only
regenerate them on grammar changes.
In general, this is a good thing.
During development, it is possible fool ply such that the parsetab.py
file is not rebuilt when it should be.
Those instance are rare, and simply deleting parsetab.y will force
a rebuild.

Parser table caching, however, complicates installation strategy.
Ply does allow the parsetab.py and resulting parsetab.pyc file
to be directed to a particular directory. 
(If you don't do that, they end up getting sprinked around 
the user's workspace.) 
For production deployment, the parsetab.py and parsetab.pyc files
really belong in the Python system module file layout.
The question is how to get them there.

My solution is the following:

- setup.py causes ansisym to be executed with the ``--setup`` option during the install.
  Install runs with root priveleges, which are required to write
  the parser files into the install directory.
- Executing ansisym causes it to import the ansisymParser.py module.
- During import, the ansisymParser.py module queries it's own location using
  the ``__file__`` global, and directs ply.yacc.yacc() to place
  it's output in the same directory.
- The ``--setup`` option to ansisym disables the normal
  compile and simply imports the parsetab.y file that was generated
  above, triggering the creation of parsetab.pyc, so that it, too,
  ends up in the write-protected installation directory.

At this point, parsetab.py and parsetab.pyc now reside along side
all the other ansisym modules in the correct install location.
No ply-generated files will polute the user's workspace.
Since the files were created during execution of
setup.py the file priveleges are set correctly.

# Coding conventions

- Everything is Python 2.7 -- not for any particularly good reason.
- CamelCaseNames everywhere.
- Classes start with a capital letter.
- Variables start with a lower case letter.
- Private variables start with underscore.
- gEDA viewer classes start with GV
- string ``format()`` method, not ``%`` syntax
- no one-line ifs: ``if predicate: return None`` Split this across
  two lines properly indented.

There are still some non-camel-case names and ``%``-style formatting
expressions left over from very early revisions.
Feel free to help eradicate them and send a patch.

# Open Issues

- Block-specific directives are not supported. All directives
  are global.
- Tiles that are sub-blocks are not yet supported.
- Blocks where package variants have different numbers of pins
  are not supported. Issues:

  - non-seniscal with slotting
  - need decent syntax, 
  - complicates semantic validation checks
  - impacts layout, and ability to replace one symbol
    with another and have all the hook-ups work

- Bidirectional pins are not drawn to ANSI standard.
- Renderer needs refactoring.

  - "pin art" is currently a bunch of ad-hoc methods
    iin the pin tile.  Should create a PinArt base class
    and derive classes for each type of pin art from it.
  - gschem knowlege is deeply embedded in renderer. 
    gschem-specific logic should be factored out into
    a module that the renderer includes.  This would
    facilitate using the same source to create symbols
    for other schematic editors using the same tool.
  - attributes are gschem-centric throughout.  The
    parser and model both assume gschem as the target,
    and the "gschem way" for attributes is assumed
    througout.  Any schematic editor will by nature
    have the same concept as gschem attributes, but
    the current ansisym model for attributes is 
    most likely not generic enough to easily support
    other schematic editor back-ends.

- Attributes are global, so there is no way to 
  express a block-specific attribute.
- It would be desirable to include the package-id as
  meta-text.  Unfortunately, this requires some
  pervasive re-work in the layout and rendering
  code.

# Road Map

- Stability! It should eat anything, and give
   appriate error messages everywhere.  Never silently
   product broken symbol file. 
- Pin art should be handled in a class, not ad-hoc in 
  GVPin methods as it is now.
- Bidirectional I/O drawing should suport:

  - ANSI-correct
  - Compressed
  - Semi-compressed

- Refactor renderer to enable generating symbols for other
  schematic editors.


