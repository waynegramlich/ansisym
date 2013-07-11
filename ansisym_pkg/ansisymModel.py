"""ansisymModel - classes to model gEDA schematic symbols with sufficient
information for creating an ANSI-compliant graphic."""

#   Copyright 2013 David B. Curtis

#   This file is part of ansisym.
#   
#   ansisym is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#   
#   ansisym is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#   
#   You should have received a copy of the GNU General Public License
#   along with ansisym.  If not, see <http://www.gnu.org/licenses/>.
#   


# Class hierarchy:
# object
#   ModelObject
#     Tile
#       PinTile
#       GlyphicTile
#     Glyph
#       TextGlyph
#       RefGlyph
#       GraphicGlyph
#     Band
#       TopBand
#       BotBand
#       IOBand
#       NeckBand
#       SepBand
#       TextBand
#     BlockBase
#       Block
#       UnusedBlock
#     Attr
#     Part
# dict
#   AttrDict
# defaultdict
#   DirectiveDict

from collections import defaultdict
import re
import ansisymErrorSink as er

# Attribute names expected in a valid part.
_requiredAttrs = ['refdes','device']
_warnAttrs = ['copyright','author','uselicense','distlicense','description']

unnamedPackage = "unnamed_package" # The anonymous package name.



#
# Special dictionary for directives
#
class DirectiveDict(defaultdict):
    directiveDefaults = {
        # Alphabetical order
        'bidirstyle':(int,1),
        'fontname':(str,'Arial'),
        'minwidth':(int,0),
        'pinfontsize':(int,8),
        'samewidth':(bool,False),
        'showspacers':(bool,False),
        'textfontsize':(int,10),
    }
    def __missing__(self, key):
        "If directive hasn't been set, return the default value."
        return self.directiveDefaults[key][1] # propagate keyerror if not found.
    def isValid(self, directiveName):
        "Returns true if directiveName is valid."
        return directiveName in self.directiveDefaults
    def __setitem__(self, key, value):
        typer = self.directiveDefaults[key][0]
        val = typer(value)
        super(DirectiveDict,self).__setitem__(key, val)

#
# Base class for most models
#
class ModelObject(object):
    "Base class for ansisym model classes."
    def __repr__(self):
        s = self.__class__.__name__ + '('
        s += ','.join([repr(x) for x in self.reprvals()])
        s += ')'
        return s
    def reprvals(self):
        # Override in derived classes.
        return []
    @property
    def isValid(self):
        "Validates instance and returns True if valid."
        # Override in derived classes.
        raise NotImplementedError
    # Line numbers for error message references.
    @property
    def lineNo(self):
        try:
            return self._lineNo
        except:
            return None
    @lineNo.setter
    def lineNo(self, v):
        self._lineNo = v
#
# Tile classes.
#
class Tile(ModelObject):
    @property
    def numSlots(self):
        "Returns number of slots, or 0 if non-slotted.  -1 indicates slotting error."
        return 0
    @property
    def pkgSet(self):
        "Returns set of packages named in this tile."
        return set()
    def pinsUsed(self, pkg = None):
        return set()

class PinTile(Tile):
    _validPinTypes = frozenset(['^', '~', '!tri','!trin','%','!pas','!tp',
                                '!oc','!oe','!in','!out','!pwr','!st'])
    _mutexPinTypes = frozenset(['!tri','!pas','!tp','!oc','!oe','!pwr'])
    _conflictPinTypes = {
        '!st':frozenset(['!out','!pwr']),
        '^':frozenset(['!out','!pwr']),
        '%':frozenset(['!in', '!out','!pwr']),
    }
    _powerAlias = frozenset(['vcc','gnd','vss','vdd']) # List of pin names interpreted as a power pin.
    def __init__(self, aName, aPinFlagSet, aPackagePinListDict, aPinType=None):
        self.name = aName
        if not aPinFlagSet <= self._validPinTypes:
            raise ValueError
        self.pinFlags = aPinFlagSet
        self.pinListDict = aPackagePinListDict
        self._pinType = aPinType
    def reprvals(self):
        l = [self.name, self.pinFlags, self.pinListDict]
        if self._pinType != None:
            l.append(self_pintype)
        return l
    @classmethod
    def isValidPinType(cls, pinFlag):
        return pinFlag in cls._validPinTypes
    @property
    def anonymous(self):
        return self.name == ''
    @property
    def numSlots(self):
        "Returns number of slots, or -1 if inconsistent."
        l = [len(pl) for pl in self.pinListDict.values()]
        n = max(l)
        return n if n == min(l) else -1
    @property
    def pkgSet(self):
        return set(self.pinListDict.keys())
    @property
    def pinType(self):
        if self._pinType == None:
            # Set/guess a pin type from pin flags or pin name and cache it.
            if '^' in self.pinFlags:
                # clock
                self._pinType = 'clk'
            elif '!tri' in self.pinFlags or '!trin' in self.pinFlags:
                # Tri-state
                self._pinType = 'tri'
            elif '%' in self.pinFlags:
                # bi-directional
                self._pinType = 'io'
            elif '!pas' in self.pinFlags:
                # Passive
                self._pinType = 'pas'
            elif '!tp' in self.pinFlags:
                # totem pole
                self._pinType = 'tp'
            elif '!oc' in self.pinFlags:
                # open collector
                self._pinType = 'oc'
            elif '!oe' in self.pinFlags:
                # open emitter
                self._pinType = 'oe'
            elif '!in' in self.pinFlags:
                # in
                self._pinType = 'in'
            elif '!out' in self.pinFlags:
                # out
                self._pinType = 'out'
            elif '!pwr' in self.pinFlags or self.isPowerAlias:
                # Power pin
                self._pinType = 'pwr'
            # Just leave it at None if can't guess.
            # Caller must use left/right context to assign
            # 'in' or 'out'.
        return self._pinType
    @pinType.setter
    def pinType(self):
        pass
    def pinsUsed(self, pkg = None):
        p = pkg if pkg != None else unnamedPackage
        return set(self.pinListDict[p])
    @property
    def isValid(self):
        ns = self.numSlots
        valid = True
        if ns == 1:
            pass
        elif ns > 1:
            for l in self.pinListDict.values():
                if 0 in l:
                    er.ror.msg('f',
                        'Shadow pins not allowed in slots. Line: ' + str(self.lineNo))
                    valid = False
        else:
            valid = False
            er.ror.msg('f','Package slot counts differ. Line: ' + str(self.lineNo))
        if len(self.pinFlags.intersection(self._mutexPinTypes)) > 1:
            valid = False
            m = 'Mutually-exclusive pin flag conflict. Line: ' + str(self.lineNo)
            er.ror.msg('f', m)
        for pf in self._conflictPinTypes:
            if not self.pinFlags.isdisjoint(self._conflictPinTypes[pf]):
                valid = False
                m = 'Pin flag conflict. Line: ' + str(self.lineNo)
                er.ror.msg('f', m)
        return valid
    @property
    def isPowerAlias(self):
        s = self.name.lower() + '  '
        return s[0:3] in self._powerAlias
    def isShadowPin(self, pkg):
        # Is shadow pin if pinlist contains exactly one pin, pin number 0
        return self.pinListDict[pkg][0] == 0

class SpacerTile(Tile):
    "Forces space in layout."
    def __init__(self, width, height = 0):
        assert width > 0
        assert height >= 0
        self.w = width
        self.h = height
    def reprvals(self):
        l = [self.w]
        if self.h > 0:
            l.append(self.h)
        return l
    @property
    def isValid(self):
        return True

######################
# Graphic and Glyphs #
######################
class Glyph(ModelObject):
    "A graphical element."
    pass
    
class TextGlyph(Glyph):
    "Normal text -- draw with normal font."
    def __init__(self, someText = ''):
        self._text = someText
    def reprvals(self):
        return [self._text]
    @property
    def text(self):
        return self._text
    @text.setter
    def text(self, aStr):
        self._text = aStr
    @property
    def isValid(self):
        return len(self.text) > 0

class RefGlyph(Glyph):
    "A text glyph whose value is the value of a named attribute."
    def __init__(self, anAttr, aBlockName):
        assert not anAttr.refBy(aBlockName) # An attr can't be refered to multiple times in a block.
        self._attr = anAttr
        self._attr.addRef(aBlockName)
    def reprvals(self):
        return [self._attr]
    @property
    def text(self):
        return self._attr.value
    @text.setter
    def text(self, aStr):
        raise ValueError ("Can't set text here.")
    @property
    def isValid(self):
        return len(self.text) > 0
    @property
    def attrName(self):
        return self._attr.name
    
class GraphicGlyph(Glyph):
    _implements = frozenset(['tristate','driver','ge','testbox'])
    def __init__(self, glyphname):
        self.glyph = glyphname.strip('&')
    def reprvals(self):
        return [ self.glyph ]
    @classmethod
    def implements(cls,kw):
        return kw.strip('&') in cls._implements
    @property
    def isValid(self):
        return True

class GlyphicTile(Tile):
    "A tile containing a list of glyphs."
    # Set of attributes that are not @@ referenceable.
    _unreferenceable = frozenset(['device'])
    def __init__(self, aGlyphlist = []):
        self.glyphs = aGlyphlist
    @classmethod
    def fromSTR(cls, aStr, attrDict, blockName):
        "Interprets any escape sequences in aStr, constructing required Glyph list."
        patt = '(&[^&]*&|@[^@]+@)' # Splits on &foo& or @bar@, capturing splitter.
        chunks = re.split(patt, aStr)
        # chunks list now contains two kinds of artifacts:
        # 1. There might be empty text strings.
        # 2. There might be '&&' strings, which should be un-escaped and
        #    merged back into surrounding strings.
        chunks = ['&' if s == '&&' else s for s in chunks if s != '']
        # The above takes care of empty strings and un-escaping '&&',
        # now merge '&' strings back into surrounding text, if possible.
        l = []
        s = ''
        for chunk in chunks:
            if chunk[0] == '@' or (chunk[0] == '&' and len(chunk) > 1):
                if s != '':
                    l.append(s)
                    s = ''
                l.append(chunk)
            else:
                s += chunk
        if s != '':
            l.append(s)
        chunks = l
        # Build list of Glyphs in l
        l = []
        for chunk in chunks:
            if len(chunk) > 1 and chunk[0] == '&':
                # Create a graphic glyph.
                if GraphicGlyph.implements(chunk):
                    l.append(GraphicGlyph(chunk))
                else:
                    m = 'Invalid glyph escape: ' + chunk
                    er.ror.msg('f',m)
            elif chunk[0] == '@':
                # Create a RefGlyph
                attrName = chunk.strip('@')
                # disallow 'device' (maybe others?) as a refglyph
                divertToText = attrName in cls._unreferenceable
                try:
                    attr = attrDict[attrName]
                except:
                    m = ''.join(['Attribute "',attrName,
                        '" not defined.'])
                    er.ror.msg('f',m)
                    return
                if attr.refBy(blockName):
                    m = ''.join(['Attribute "',attrName,
                        '" already referenced by block: ', blockName])
                    er.ror.msg('f',m)
                else:
                    if divertToText:
                        er.ror.msg('w',''.join(["'",attrName,
                            "' attributes can not be @referenced@, ",
                            'value substituted as plain text.']))
                        l.append(TextGlyph(attr.value))
                    else:
                        l.append(RefGlyph(attr, blockName))
            else:
                # Ordinary TextGlyph
                l.append(TextGlyph(chunk))
        return cls(l)
    def reprvals(self):
        return [self.glyphs]
    @property
    def isValid(self):
        valid = True
        for g in self.glyphs:
            valid &= g.isValid
        return valid
    
# FIXME: Add Tile of Bands
# The full range of ANSI symbols would require a new Tile() class
# that contains a list of Band() classes.  This would be a direct
# recursive model of the ANSI concept of sub-blocks within a block.
# In the days of MSI logic this made a lot of sense.  These days,
# it doesn't seem so useful.

#################
# Band classes. #
#################
class Band(ModelObject):
    def __init__(self, leftTile = None, centerTile = None, rightTile = None):
        assert isinstance(leftTile, Tile) or leftTile == None
        assert isinstance(centerTile, Tile) or centerTile == None
        assert isinstance(rightTile, Tile) or rightTile == None
        self.ltile = leftTile
        self.ctile = centerTile
        self.rtile = rightTile
    def reprvals(self):
        return [self.ltile, self.ctile, self.rtile]
    def numSlots(self):
        l = [t.numSlots for t in [self.ltile,self.ctile,self.rtile] if t]
        if not l:
            return 0
        n = max(l)
        return n if n == min(l) else -1
    def pkgSet(self):
        "Packages named by contained tiles."
        return set()
    def pinsUsed(self,pkg):
        "Pins used in contained tiles."
        return set()
    @property
    def isValid(self):
        return min([tile.isValid if tile != None else True
            for tile in [self.ltile, self.ctile, self.rtile]])
    def pushDownLineNo(self):
        for tile in [self.ltile, self.ctile, self.rtile]:
            if tile != None:
                tile.lineNo = self.lineNo 
    
class TopBand(Band):
    def __init__(self,centerTile = None):
        "The band at the top of a block.  Required for all blocks."
        assert centerTile == None or isinstance(centerTile,Tile)
        super(TopBand,self).__init__(None, centerTile, None)
    def reprvals(self):
        return [self.ctile] if self.ctile != None else []

class BotBand(Band):
    "The band at the bottom of a block. Required for all blocks."
    def __init__(self):
        super(BotBand,self).__init__()
    def reprvals(self):
        return []

class IOBand(Band):
    def __init__(self, leftTile = None, centerTile = None, rightTile = None):
        assert leftTile == None or isinstance(leftTile,Tile)
        assert centerTile == None or isinstance(centerTile,Tile)
        assert rightTile == None or isinstance(rightTile,Tile)
        super(IOBand,self).__init__(leftTile, centerTile, rightTile)
    def pkgSet(self):
        s = set()
        if self.ltile != None:
            s |= self.ltile.pkgSet()
        if self.rtile != None:
            s |= self.rtile.pkgSet()
        return s
    def pinsUsed(self,pkg):
        s = set()
        if self.ltile != None:
            s |= self.ltile.pinsUsed(pkg)
        if self.rtile != None:
            s |= self.rtile.pinsUsed(pkg)
        return s
    
class NeckBand(Band):
    def __init__(self, centerTile = None):
        assert centerTile == None or isinstance(centerTile,Tile)
        super(NeckBand,self).__init__(None, centerTile, None)
    def reprvals(self):
        return [self.ctile]

class SepBand(Band):
    def __init__(self, wide=False):
        super(SepBand,self).__init__()
        self.wide = wide
    def reprvals(self):
        return [self.wide] if self.wide else []

class TextBand(Band):
    def __init__(self, centerTile, upKerning = 0):
        assert centerTile == None or isinstance(centerTile,Tile)
        super(TextBand,self).__init__(None, centerTile, None)
        self.upKerning = upKerning

#
# Block class.
#
class BlockBase(ModelObject):
    def numSlots(self):
        return 0
    def blockNameSet(self):
        return set()
    def pinsUsed(self,pkg):
        "Returns set of pins used by this block."
        return set()
    def pinsNotUsed(self, pkg):
        "Returns set of pins this block explicitly marks as 'unused'." 
        return set()

class UnusedBlock(BlockBase):
    def __init__(self, aPackageName, aPinList):
        assert isinstance(aPackageName, str)
        assert isinstance(aPinList, list)
        self.pkgName = aPackageName
        self.pins = aPinList
        self.bands = [] # FIXME: Really should refactor viewer so this isn't necessary.
    def reprvals(self):
        return [self.pkgName, self.pins]
    def pkgSet(self):
        return set([self.pkgName])
    @property
    def anyPkg(self):
        return self.pkgName
    def pinsNotUsed(self, pkg):
        return set(self.pins if pkg == self.pkgName else [])
    @property
    def isValid(self):
        return True

class Block(BlockBase):
    def __init__(self, packageList, bandList):
        self.pkgs = packageList # A list of (package name, block name) tuples.
        self.bands = bandList # A list of Band() instances.
    def reprvals(self):
        return [self.pkgs, self.bands]
    def numSlots(self):
        """Computes the number of slots using pin information.
        Returns -1 in case of error"""
        l = [n for n in [b.numSlots() for b in self.bands] if n > 0]
        if not l:
            return 0
        n = max(l)
        return n if n == min(l) else -1
    def pkgSet(self):
        "Returns set of all package names in pkgs."
        return set([x for (x,y) in self.pkgs])
    @property
    def anyPkg(self):
        return self.pkgs[0][0]
    def blockNameSet(self):
        "Returns set of all block names pkgs."
        return set([y for (x,y) in self.pkgs])
    @property
    def referenceBlockName(self):
        "Name used by ref attrs to refer to this block."
        return self.pkgs[0][1]
    def pinsUsed(self,pkg):
        return reduce(lambda x,y:x|y, [b.pinsUsed(pkg) for b in self.bands])
    @property
    def isValid(self):
        valid = self._validateBlockNames()
        if self.numSlots() < 0:
            er.ror.msg('f',' '.join(['Inconsistent number of slots in block',self.pkgs[0][1]]))
            valid = False
        valid &= self._validateBandorder() & self._validatePinsUsed()
        valid &= self._validateBands()
        return valid
    def _validateBandorder(self):
        "Returns True on success."
        valid = True # Hope for the best.
        tops = 0
        bottoms = 0
        necks = 0
        if not isinstance(self.bands[0], TopBand):
            m = ' '.join(['First band not a top band in block',self.pkgs[0][1]])
            er.ror.msg('f',m)
            valid = False
        if not isinstance(self.bands[-1], BotBand):
            m = ' '.join(['Last band not bottom band in block ',self.pkgs[0][1]])
            er.ror.msg('f',m)
            valid = False
        for b in self.bands:
            if isinstance(b,TopBand):
                tops +=1
            if isinstance(b,BotBand):
                bottoms +=1
            if isinstance(b,NeckBand):
                necks +=1
        if tops == 0:        
            er.ror.msg('f',' '.join(['No top band in block' + self.pkgs[0][1]]))
            valid = False
        if bottoms == 0:        
            er.ror.msg('f',' '.join(['No bottom band in block' + self.pkgs[0][1]]))
            valid = False
        if tops > 1:        
            er.ror.msg('f',' '.join(['Multiple top bands in block' + self.pkgs[0][1]]))
            valid = False
        if bottoms > 1:        
            er.ror.msg('f',' '.join(['Multiple bottom bands in block' + self.pkgs[0][1]]))
            valid = False
        if necks > 1:        
            er.ror.msg('f',' '.join(['Multiple neck bands in block' + self.pkgs[0][1]]))
            valid = False
        return valid
    def _validatePinsUsed(self):
        "Any pin number can appear at most once in a block, per package."
        valid = True
        for pkg in [p for (p,n) in self.pkgs]:
            u = set()
            for b in self.bands:
                if not u.isdisjoint(b.pinsUsed(pkg)):
                    er.ror.msg('f',''.join(['Pin(s) '] + [str(x) for x in u & b.pinsUsed(pkg)]
                                             + [' used multiple times in package "',pkg,'".']))
                    valid = False
                u |= b.pinsUsed(pkg)
                u.discard(0)
        return valid
    def _validateBands(self):
        valid = True
        for b in self.bands:
            b.pushDownLineNo()
            valid &= b.isValid
        return valid
    def _validateBlockNames(self):
        "Make sure block names don't clobber each other."
        valid = True
        s = set()
        for pkg,blk in self.pkgs:
            if blk in s:
                er.ror.msg('f',
                    ' '.join(['Block name', blk, 'appears multiple times.']))
                valid = False
        return valid

#
# Attribute classes. 
#
class Attr(ModelObject):
    def __init__(self, aName, aValue, refTo = None):
        self.name = aName
        self.value = str(aValue)
        # _refTo is a set of block names
        self._refTo = refTo if refTo != None else set()
    @property
    def value(self):
        return self._value
    @value.setter
    def value(self,v):
        # Sanity check values for some well-known attributes.
        if self.name == 'device':
            if v != v.upper():
                er.ror.msg('w',"'device' attributes should be all upper case.")
        self._value = v
    def reprvals(self):
        l = [self.name, self.value, self._refTo] 
        return l
    def refBy(self, blockName):
        return blockName in self._refTo
    def addRef(self, blockName):
        assert not blockName in self._refTo
        self._refTo.add(blockName)

class AttrDict(dict):
    '''A regular Python dictionary, but it can add an Attr() directly
    by picking up the name property from the Attr() instance.'''
    def __init__(self, attrList=[]):
        if isinstance(attrList,AttrDict): 
            self = attrList
        else:
            super(AttrDict,self).__init__()
            for a in attrList:
                self[a.name] = a
    def __repr__(self):
        s = self.__class__.__name__ + '('
        s += repr(self.values())
        s += ')'
        return s
    def add(self,v):
        self[v.name] = v

#
# Part class.
#
class Part(ModelObject):
    def __init__(self, attributes = AttrDict(), theBlocks=[], \
                 directiveDict=DirectiveDict()): 
        self.attrs = attributes
        self.blocks = theBlocks # a list
        self.directives = directiveDict
    def reprvals(self):
        return [self.attrs, self.blocks, self.directives]
    def pkgSet(self):
        s = set()
        for b in self.blocks:
            s |= b.pkgSet()
        return s
    def blockNameSet(self):
        s = set()
        for b in self.blocks:
            s |= b.blockNameSet()
        return s
    def pinsUsed(self, pkg):
        return reduce(lambda x,y:x|y, [b.pinsUsed(pkg) for b in self.blocks])
    def pinsNotUsed(self, pkg):
        return reduce(lambda x,y:x|y, [b.pinsNotUsed(pkg) for b in self.blocks])
    def _validatePinsUsedByPackage(self, pkg):
        "True if every pin from 1 to maximum pin# mentioned is accounted for."
        p = self.pinsUsed(pkg) | self.pinsNotUsed(pkg)
        valid = True
        for pin in xrange(1,max(p)):
            if pin not in p:
                er.ror.msg('f',' '.join(['Pin',str(pin),'not used by package',pkg]))
                valid = False
        return valid
    def _validatePinsUsed(self):
        "True if all packages have valid pin usage."
        valid = True
        for p in self.pkgSet():
            valid &= self._validatePinsUsedByPackage(p)
        return valid
    def _validateAttrs(self):
        "True if required attributes are present. Also issues warnings."
        valid = True
        for a in _requiredAttrs:
            if a not in self.attrs:
                er.ror.msg('f',' '.join(['Required attribute',a,'not found.']))
                valid = False
        for a in _warnAttrs:
            if a not in self.attrs:
                er.ror.msg('w',' '.join(['Standard attribute',a,'not found.']))
        return valid
    def _validateBlockNames(self):
        "All block names must be unique or the files will clobber each other."
        pass
    @property
    def isValid(self):
        valid = self._validatePinsUsed()
        valid &= self._validateAttrs()
        for b in self.blocks:
            valid &= b.isValid
        return valid

#########################
# External Entry Points #
#########################
def loadRep(f):
    "Load representation from open file 'f'."
    s = f.read()
    return eval(s)
    

########################################################################
    
if __name__ == '__main__':
    print "FIXME: add some tests."
