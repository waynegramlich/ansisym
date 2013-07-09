"These classes are a gschem view onto a model of a gEDA schematic symbol."

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

# Class hierarchy. '->' indicates the model class that is viewed.
#
# GViewer
#   GVPart -> mdl.Part
#   GVAttr -> mdl.Attr
#   GVGlyph
#     GVTextGlyphBase
#       GVTextGlyph -> mdl.TextGlyph
#       GVRefGlyph -> mdl.RefGlyph
#     GVGraphicGlyphTri -> mdl.GraphicGlyph
#     GVGraphicGlyphDrv -> mdl.GraphicGlyph
#     GVGraphicGlyphGE -> mdl.GraphicGlyph
#     GVGraphicGlyphTestbox -> mdl.GraphicGlyph (For layout testing. Not documented.) 
#   GVTile
#     GVNoTile -> None
#     GVPin -> mdl.Pin
#     GVGlyphicTile -> mdl.GlyphicTile
#     GVSpacerTile -> mdl.SpacerTile
#   GVBand
#     GVIOBand -> mdl.IOBand
#     GVNeckBand -> mdl.NeckBand
#     GVSepBand -> mdl.SepBand
#     GVTopBand -> mdl.TopBand
#     GVBotBand -> mdl.BotBand
#     GVTextBand -> mdl.TextBand
#   GVBlock -> mdl.Block
#   GVUnusedBlock -> mdl.UnusedBlock
#   GVPart -> mdl.Part
#
# Other classes:
# Pt -- An extended namedtuple for points in the drawing plane.
# Stroke -- A line definition.
# FontInfo -- Font measurement information for layout caluclations.
# Layout -- Layout information.
#
# Note:
# 1. GViewer classes can not be re-contructred from repr() output,
#    since the parent object is not included in repr() output.

from collections import namedtuple
import cairo as cr

import ansisymModel as mdl

##################
# Configuration #
#################
_gridspacing = 100
_pinlength = 300
_letterHeight = 130 # FIXME: Replace usages with FontInfo references.
_minwordspace = 100
_letterspace = 10
_glyphMargin = 15
_neckindent = 200
_linewidth_for_art = 10
_linewidth_for_box = 20
_fileversion = 'v 20100214 1'
_refdesOffset = 25
#_invertLength = 100
#_invertHeight = 50
_invertLength = 150
_invertHeight = 75


###################
# gEDA constants. #
###################
gEDAcolor = {'background':0, 'pin':1, 'net_endpoint':2, \
             'graphic':3, 'net':4, 'attribute':5, \
             'logic_bubble':6, 'dots_grid':7, 'detached_attribte':8, \
             'text':9, 'bus':10, 'select':11, 'bounding_box':12, \
             'zoom_box':13, 'stroke':14, 'lock':15, 'output_background':16, \
             'freestyle1':17,'freestyle2':18,'freestyle3':19,'freestyle4':20, \
             'junction':21, 'mesh_grid_major':22, 'mesh_grid_minor':23}
gEDAtextalign = { 'ul':2, 'um':5, 'ur':8, \
                  'ml':1, 'mm':4, 'mr':7, \
                  'll':0, 'lm':3, 'lr':6}
gEDAAttrShow = {'name_val':0, 'name':2, 'val':1}

def gridUp(n):
    "Round n up to next grid size."
    n = int(n)
    return (n/_gridspacing) * _gridspacing \
           + (_gridspacing * 1 if n % _gridspacing else 0)


#######################
# Drawing primitives. #
#######################

# Named tuple used as base for drawing points.
PointBase = namedtuple('PointBase', ['x', 'y'])

class Pt(PointBase):
    "Drawing point."
    def __repr__(self):
        s = self.__class__.__name__ + '('
        s += ','.join([repr(x) for x in [self.x, self.y]])
        s += ')'
        return s
    def __add__(self, other):
        return Pt(self.x + other.x, self.y + other.y)
    def scale(self, factor):
        return Pt(int(self.x * factor),int(self.y * factor))
    @property
    def isValid(self):
        return self.x != None and self.y != None

class Layout(object):
    "Layout position and size information."
    def __init__(self, x=None, y=None, width=None, height=None):
        self.x = x
        self.y = y
        self.w = width
        self.h = height
    def __repr__(self):
        s = self.__class__.__name__ + '('
        s += ','.join([repr(x) for x in [self.x, self.y, self.w, self.h]])
        s += ')'
        return s
    @property
    def origin(self):
        return Pt(self.x, self.y)
    @property
    def top(self):
        "Global y coordinate of top."
        return self.y + self.h
    @property
    def right(self):
        "Global x cooridate of RHS."
        return self.x + self.w
    @property
    def middleX(self):
        return self.x + self.w/2
    @property
    def middleY(self):
        return self.y + self.h/2

class Stroke(object):
    "A straight line of specified width and dash style."
    def __init__(self, p1, p2, width = _linewidth_for_art, dashed=None):
        assert p1.isValid
        assert p2.isValid
        self.p1 = p1
        self.p2 = p2
        self.w = width
        self.dashControl = dashed # None, or tuple (dstyle, dashlen, dashspace)
    def __repr__(self):
        s = self.__class__.__name__ + '('
        s += ','.join([repr(x) for x in [self.p1, self.p2, self.w]])
        s += ')'
        return s
    def displaced(self, aPoint):
        return Stroke(self.p1 + aPoint, self.p2 + aPoint)
    def scale(self, factor):
        return Stroke(self.p1.scale(factor), self.p2.scale(factor))
    def render(self, offset):
        "Returns a string to print to a .sym file."
        q1 = self.p1 + offset
        q2 = self.p2 + offset
        dstyle, dlen, dspc = \
            (0,-1,-1) if self.dashControl == None else self.dashControl
        #L x1 y1 x2 y2 color width capstyle dashstyle dashlengh dashspace
        return 'L %4d %4d %4d %4d 3 %d 1 %d  %d %d' % \
                (q1.x, q1.y, q2.x, q2.y, self.w, dstyle, dlen, dspc)

class FontInfo(object):
    "Captures just enough font info to do text measurement for layout."
    _gschemScalingConstant = 10000.0/555.0 # Magic number
    def __init__(self, fontName, fontSize):
        self._name = fontName
        self._size = fontSize
        self._csf = None # Cairo Scaled Font, cached.
    @property
    def name(self):
        return self._name
    @property
    def size(self):
        return self._size
    def measure(self, aString):
        "Returns the layout length of aString in gschem distance."
        if self._csf == None:
            self._build_csf()
        width = self._csf.text_extents(aString)[2]
        return int(width)
    def height(self, aString):
        "Returns the layout height of aString in gschem distance."
        raise NotImplementedError #FIXME: Complete this method and
                    # convert references to _letterHeight over to this.
    def _build_csf(self):
        "Builds and caches a Cairo Scaled Font."
        fontFace = cr.ToyFontFace(self.name)
        identityMatrix = cr.Matrix()
        fontOptions = cr.FontOptions() # get defaults
        scaling = self.size * self._gschemScalingConstant
        scalingMatrix = cr.Matrix(xx = scaling, yy = scaling)
        self._csf = cr.ScaledFont(fontFace, scalingMatrix, 
            identityMatrix, fontOptions)

##########################
# View object base class #
##########################
class GViewer(object):
    def __init__(self, aParent):
        self.parent = aParent
    def __repr__(self):
        s = self.__class__.__name__ + '('
        s += ','.join(repr(x) for x in self.reprvals())
        s += ')'
        return s
    def reprvals(self):
        return []
    @classmethod
    def viewOf(cls, aModelObject):
        "Factory method for constructing viewers."
        # Override in classes that must specialize based on class
        # of aModelObject.
        return cls(aModelObject, self)
    @property
    def directives(self):
        return self.parent.directives
    @property
    def textFont(self):
        return self.parent.textFont
    @property
    def pinFont(self):
        return self.parent.pinFont
    @property
    def parentPart(self):
        return self.parent.parentPart
    @property 
    def parentBlockName(self):
        return self.parent.parentBlockName
    @property
    def lineNo(self):
        "Returns associated source line number if possible, or None."
        return self.parent.lineNo
    
################################
# View class for attributes #
################################
class GVAttr(GViewer):
    "View onto an attribute."
    show_name_val = {'n':2, 'v':1, 'nv':0}
    def __init__(self, anAttr, aParent):
        super(GVAttr,self).__init__(aParent)
        self.attr = anAttr
    def reprvals(self):
        return [self.attr]
    def setLayout(self, loc, alignment='ll', size = 10, \
                  color='attribute', vistuple=(False,'nv'), angle = 0):
        assert isinstance(loc, Pt)
        self.loc = loc
        self.align = gEDAtextalign[alignment]
        self.size = size
        self.col = gEDAcolor[color]
        self.vis = 1 if vistuple[0] else 0
        self.shownv = self.show_name_val[vistuple[1]]
        self.angle = angle
    def render(self):
        if self.attr.refBy(self.parent.parentBlockName):
            return [] # It gets rendered as a RefGlyph
        # T x y color size vis shownameval angle align numlines
        l = ['T %d %d %d %d %d %d %d %d 1' % \
             (self.loc.x, self.loc.y, self.col, self.size, self.vis,\
              self.shownv, self.angle, self.align)]
        l.append('%s=%s' % (self.attr.name, self.attr.value))
        return l
       

#######################################
# View classes for all glyphic items. #
#######################################
class GVGlyph(GViewer):
    viewers = dict()
    def __init__(self, aGlyph, aParent):
        super(GVGlyph,self).__init__(aParent)
        self.glyph = aGlyph
        self.lo = None # Compute a Layout() in layout() method.
        # A GVGlyph layout is the bounding box.
    @classmethod
    def viewOf(self, aGlyph, aParent):
        cn = aGlyph.__class__.__name__
        if cn == 'GraphicGlyph':
            cn += '-' + aGlyph.glyph
        return self.viewers[cn](aGlyph, aParent)
    @property
    def parentBand(self):
        "Unwinds parent nesting up to containing band."
        return self.parent.parentBand
    def layout(self, xCursor):
        raise NotImplementedError
    def strokes(self):
        'Returns list of Stroke() objects.'
        return []
    def render(self):
        return []
    @property
    def width(self):
        raise NotImplementedError # Abstract

class GVTextGlyphBase(GVGlyph):
    def reprvals(self):
        return [self.lo, self.glyph.text]
    @property
    def width(self):
        return self.textFont.measure(self.glyph.text)
    def layout(self, xCursor):
        plo = self.parentBand.lo # less typing
        y = plo.y + (plo.h - _letterHeight)/2
        self.lo = Layout(xCursor, y, self.width, _letterHeight)
    @property
    def singleGlyph(self):
        return self.parent.singleGlyph

class GVTextGlyph(GVTextGlyphBase):
    "View onto a simple text string."
    def render(self):
        # T x y color size vis shownameval angle align numlines
        if self.singleGlyph:
            x = self.lo.middleX
            align = gEDAtextalign['lm']
        else:
            x = self.lo.x
            align = gEDAtextalign['ll']
        l = ['T %d %d %d %d %d %d %d %d 1' % 
             (x, self.lo.y, gEDAcolor['text'],
              self.textFont.size, 1, 1, 0, align)]
        l.append(self.glyph.text)
        return l

class GVRefGlyph(GVTextGlyphBase):
    "View onto an attribute reference."
    def render(self):
        # T x y color size vis shownameval angle align numlines
        show = gEDAAttrShow['val']
        if self.singleGlyph:
            l = ['T %d %d %d %d %d %d %d %d 1' % 
                 (self.lo.middleX, self.lo.y, gEDAcolor['text'],
                  self.textFont.size, 1, show, 0, gEDAtextalign['lm'])]
        else:
            l = ['T %d %d %d %d %d %d %d %d 1' % 
                 (self.lo.x, self.lo.y, gEDAcolor['text'],
                  self.textFont.size, 1, show, 0, gEDAtextalign['ll'])]
        l.append('{0:s}={1:s}'.format(self.glyph.attrName, self.glyph.text))
        return l
 
class GVGraphicGlyph(GVGlyph):
    def reprvals(self):
        return [self.lo]
    def strokes(self):
        return [s.displaced(self.lo.origin) for s in self._strokelist]
    def layout(self, xCursor):
        plo = self.parent.lo # saves typing
        self.lo = Layout(xCursor,
                plo.y + self._base + (plo.h - self._height) / 2,
                self.width, self._height)

class GVGraphicGlyphTri(GVGraphicGlyph):
    _strokelist = [Stroke(Pt(0,190),Pt(120,190)), Stroke(Pt(120,190),Pt(60,10)),\
                  Stroke(Pt(60,10),Pt(0,190))]
    _base = 10
    _height = 180 
    @property
    def width(self):
        return 120

class GVGraphicGlyphDrv(GVGraphicGlyph):
    _strokelist = [Stroke(Pt(0,10),Pt(120,100)), Stroke(Pt(0,190),Pt(120,100)),\
                  Stroke(Pt(0,10),Pt(0,190))]
    _base = 10
    _height = 180
    @property
    def width(self):
        return 120

class GVGraphicGlyphGE(GVGraphicGlyph):
    _strokelist = [Stroke(Pt(0,90),Pt(90,60)),Stroke(Pt(0,30),Pt(90,60)),\
                  Stroke(Pt(0,10),Pt(90,10))]
    _base = 10
    _height = 110 # basic size 90 tall. 
    @property
    def width(self):
        return 90

class GVGraphicGlyphTestbox(GVGraphicGlyph):
    _strokelist = [Stroke(Pt(0,0),Pt(0,100)),Stroke(Pt(400,0),Pt(400,100)),\
                  Stroke(Pt(0,0),Pt(400,100)),Stroke(Pt(0,100),Pt(400,0))]
    _base = 0
    _height = 100 # basic size 90 tall. 
    @property
    def width(self):
        return 400

# Set up catalog of Glyph viewers.
GVGlyph.viewers['TextGlyph'] = GVTextGlyph
GVGlyph.viewers['RefGlyph'] = GVRefGlyph
GVGlyph.viewers['GraphicGlyph-tristate'] = GVGraphicGlyphTri
GVGlyph.viewers['GraphicGlyph-driver'] = GVGraphicGlyphDrv
GVGlyph.viewers['GraphicGlyph-ge'] = GVGraphicGlyphGE
GVGlyph.viewers['GraphicGlyph-testbox'] = GVGraphicGlyphTestbox

#####################
# Tile view classes #
#####################
class GVTile(GViewer):
    viewers = dict()
    _validPlacement = 'lcr'
    def __init__(self, viewedModel, parent, aPlacement):
        super(GVTile,self).__init__(parent)
        self.tile = viewedModel
        self.placement = aPlacement
        self.lo = None # Compute a Layout() in layout() method.
    @classmethod
    def viewOf(self, aTile, aParent, placement):
        cn = aTile.__class__.__name__
        view = self.viewers[cn](aTile, aParent, placement)
        return view
    @property
    def placement(self):
        return self._placement
    @placement.setter
    def placement(self, v):
        assert isinstance(v,str) and len(v) == 1
        if v not in self._validPlacement:
            raise ValueError
        self._placement = v
    @property
    def parentBand(self):
        "Returns parent band view.  Intended for use by contained/nested GVGlyphs."
        return self.parent
    def minWidth(self):
        'Returns computed minimum width.'
        return 0
    def minHeight(self):
        'Returns computed minimum height.'
        return 0
    def layout(self):
        pass
    def assignPinseq(self,pinMap, pkgName, n):
        "Assigns pinseq numbers, starting with n, returning next usable value."
        return n # Handles tiles with no I/O pins.
    def strokes(self, pkg): 
        return []
    def render(self,pkg):
        return []
    
class GVNoTile(GVTile):
    def __init__(self, ignored, parent, placement):
        super(GVNoTile,self).__init__(None, parent, placement)

class GVPin(GVTile):
    nameIndent = 25
    clockArtWidth = 75 # FIXME: All this ArtWidth stuff should get re-factored
    schmittArtWidth = 100 # into a class for inside-the-box pin art.
    tristateArtWidth = 25 + 2 * 58
    backArrowX = 25 # FIXME: Probably should have an outside-the-box pin art
    backArrowY = 25 # class as well.
    _validPlacement = 'lr'
    def __init__(self, viewedModel, parent, placement):
        super(GVPin,self).__init__(viewedModel, parent, placement)
        self.pinseq = dict()
    def reprvals(self):
        return [self.lo, self.tile]
    def minHeight(self):
        return 2*_gridspacing
    def minWidth(self):
        t = self.pinFont.measure(self.tile.name) + self.nameIndent \
                + self.artWidth
        return t
    def assignPinseq(self, pinMap, pkgName, n):
        if self.tile.isShadowPin(pkgName):
            return n
        self.pinseq[pkgName] = n
        pinMap[pkgName][n] = self.tile.pinListDict[pkgName]
        return n+1
    def layout(self):
        plo = self.parent.lo
        y = plo.middleY
        x = plo.x - _pinlength if self.placement == 'l' else plo.right
        self.lo = Layout(x, y, _pinlength, 0)
    def strokes(self, pkg):
        if self.tile.isShadowPin(pkg): 
            return []
        l = []
        # Inside the box pin art.
        # Note: Only one pin art at a time handled right now.  FIXME.
        if '^' in self.tile.pinFlags:
            l.extend(self._strokeClock())
        elif '!st' in self.tile.pinFlags:
            l.extend(self._strokeSchmitt())
        elif '!tri' in self.tile.pinFlags:
            l.extend(self._strokeTristate())
        # Outside the box pin decorations.
        if '~' in self.tile.pinFlags:
            # Invert also handles bidirectional and "backwards" I/O
            l.extend(self._strokeInvert())
        else:
            if '%' in self.tile.pinFlags:
                l.extend(self._strokeDirInOut())
            # FIXME: the in/out direction arrows are going to
            # be wonky for flipped symbols.  Create a directive
            # to enable this option, by default have it off.
            # OR.... maybe we just don't care about flipped ANSI
            # symbols.  Note that in user documentation.
            if True: # FIXME: replace with directives test??
                if self.tile.pinType == 'in' and self.placement == 'r':
                    l.extend(self._strokeDirIn())
                elif self.tile.pinType == 'out' and self.placement == 'l':
                    l.extend(self._strokeDirOut())
        return l
    def _strokeClock(self):
        l = []
        x1 = self.lo.right if self.placement == 'l' else self.lo.x
        x2 = x1 + self.clockArtWidth * (1 if self.placement == 'l' else -1)
        y1 = self.lo.y - self.clockArtWidth
        y2 = self.lo.y + self.clockArtWidth
        p1 = Pt(x1,y1)
        p2 = Pt(x2,self.lo.y)
        p3 = Pt(x1,y2)
        l.extend([Stroke(p1,p2), Stroke(p2,p3)])    
        return l
    @property
    def _pinDir(self):
        "Returns one of 'in', 'out', 'io' for art decisions."
        t = self.tile.pinType
        if self.tile.pinType == None:
            return 'in' if self.placement == 'l' else 'out'
        if t == 'io':
            return t
        return 'in' if t in frozenset(['clk','pas','pwr']) else 'out'
    def _strokeInvert(self):
        l = []
        pd = self._pinDir
        if pd == 'in':
            if self.placement == 'l':
                p1 = Pt(self.lo.right - _invertLength, self.lo.y)
                p2 = Pt(self.lo.right - _invertLength, self.lo.y + _invertHeight)
                p3 = Pt(self.lo.right, self.lo.y)
            else:
                p1 = Pt(self.lo.x + _invertLength, self.lo.y)
                p2 = Pt(self.lo.x + _invertLength, self.lo.y + _invertHeight)
                p3 = Pt(self.lo.x, self.lo.y)
            l.append(Stroke(p1,p2))
            l.append(Stroke(p2,p3))
        elif pd == 'out':
            if self.placement == 'r':
                l.append(Stroke(Pt(self.lo.x, self.lo.y + _invertHeight),
                            Pt(self.lo.x + _invertLength, self.lo.y)))
            else:
                l.append(Stroke(Pt(self.lo.right, self.lo.y + _invertHeight),
                            Pt(self.lo.x - _invertLength, self.lo.y)))
        else: # pd == 'io':
            style = self.directives['bidirstyle']
            if style == 0:
                if self.placement == 'l':
                    p1 = Pt(self.lo.right - _invertLength, self.lo.y)
                    p2 = Pt(self.lo.right - _invertLength, self.lo.y + _invertHeight)
                    p3 = Pt(self.lo.right, self.lo.y)
                    p4 = Pt(self.lo.right, self.lo.y - _invertHeight)
                else: # self.placement == 'r'
                    p1 = Pt(self.lo.x + _invertLength, self.lo.y - _invertHeight)
                    p2 = Pt(self.lo.x + _invertLength, self.lo.y)
                    p3 = Pt(self.lo.x, self.lo.y + _invertHeight)
                    p4 = Pt(self.lo.x, self.lo.y)
                l.append(Stroke(p1,p2))
                l.append(Stroke(p1,p4))
                l.append(Stroke(p2,p3))
            else:
                print 'FIXME: bidirstyle',style,'not handled in _strokeInvert.'
        return l
    def _strokeDirIn(self):
        l = []
        if self.placement == 'r':
            p1 = Pt(self.lo.middleX - backArroX, self.lo.y)
            p2 = Pt(self.lo.middleX, self.lo.y + backArrowY)
            p3 = Pt(self.lo.middleX, self.lo.y - backArrowY)            
            l.append(Stroke(p1,p2))
            l.append(Stroke(p1,p3))
        return l
    def _strokeDirOut(self):
        l = []
        if self.placement == 'l':
            p1 = Pt(self.lo.middleX, self.lo.y)
            p2 = Pt(self.lo.middleX + backArrowX, self.lo.y + backArrowY)
            p3 = Pt(self.lo.middleX + backArrowX, self.lo.y - backArrowY)            
            l.append(Stroke(p1,p2))
            l.append(Stroke(p1,p3))
        return l
    def _strokeDirInOut(self):
        style = self.directives['bidirstyle']
        if style == 0:
            return [] # bidirstyle 0 is "do nothing" for high-active I/O
        l = []
        print 'FIXME: bidirstyle',style,'not handled in _strokeDirInOut'
        return l
    def _strokeSchmitt(self):
        x0 = self.lo.x if self.placement == 'l' else self.lo.right -125 
        x1 = x0 + 25
        x2 = x0 + 50
        x3 = x0 + 75
        x4 = x0 + 100
        bot = -50
        top = 50
        o = Pt(self.lo.right, self.lo.top)
        l = [Stroke(Pt(x1,bot), Pt(x3,bot)).displaced(o),
             Stroke(Pt(x2,top), Pt(x4,top)).displaced(o),
             Stroke(Pt(x2,bot), Pt(x2,top)).displaced(o),
             Stroke(Pt(x3,bot), Pt(x3,top)).displaced(o)]
        return l
    def _strokeTristate(self):
        s = 58
        x0 = self.lo.x if self.placement == 'l' else self.lo.x -2*s
        x1 = x0 + (25 if self.placement == 'l' else -25)
        x2 = x1 + s
        x3 = x2 + s
        bot = -50
        top = 50
        #o = Pt(self.lo.right, self.lo.top)
        o = Pt(0,self.lo.top)
        l = []
        l.append(Stroke(Pt(x1,top), Pt(x3, top)).displaced(o)) #.displaced(o),
        l.append(Stroke(Pt(x1,top), Pt(x2, bot)).displaced(o)) #.displaced(o),
        l.append(Stroke(Pt(x3,top), Pt(x2, bot)).displaced(o)) #.displaced(o)]
        return l
    @property
    def artWidth(self):
        if '^' in self.tile.pinFlags:
            return self.clockArtWidth
        elif '!st' in self.tile.pinFlags:
            return self.schmittArtWidth
        elif '!tri' in self.tile.pinFlags:
            return self.tristateArtWidth
        else:
            return 0
    @property
    def artOffset(self):
        sign = 1 if self.placement == 'l' else -1
        return sign * self.artWidth
    def renderPinAttr(self, name, pinx, piny, pkg): 
        'Renders a pin attribute appropriately to the attribute name.'
        pinspx = 15 # FIXME: move this beauty tuning to the top.
        pinspy = 15
        #pinnumspx = 110
        pinnumspx = 175
        pinseqoffset = 300
        pintypeoffset = 1200
        l = []
        # T x y color size vis show_nm_val angle align nlines
        if name == 'pinlabel':
            if self.tile.anonymous:
                return []
            x = pinx + (pinspx if self.placement == 'l' else -pinspx)
            x += self.artOffset
            al = 1 if self.placement == 'l' else 7
            l.append('T %d %d 5 %d 1 1 0 %d 1' % (x, piny, self.pinFont.size, al))
            l.append('pinlabel=%s' % self.tile.name)
        elif name == 'pinnumber':
            x = pinx + (pinnumspx if self.placement == 'r' else -pinnumspx)
            y = piny + pinspy
            al = 0 if self.placement == 'r' else 6
            l.append('T %d %d 5 %d 1 1 0 %d 1' % (x, y, self.pinFont.size, al))
            l.append('pinnumber=%d' % self.tile.pinListDict[pkg][0])
        elif name == 'pinseq':
            offset = pinseqoffset * (1 if self.placement == 'r' else -1)
            align = 1 if self.placement == 'r' else 7
            l.append('T %d %d 5 %d 0 0 0 %d 1' %
                (pinx + offset, piny, self.textFont.size, align))
            l.append('pinseq=%d' % self.pinseq[pkg])
        elif name == 'pintype':
            if self.tile.pinType == None:
                # set pin type from left/right context
                pt = 'in' if self.placement == 'l' else 'out'
            else:
                pt = self.tile.pinType
            y = piny + pinspy
            x = pinx + pintypeoffset * (1 if self.placement == 'r' else -1)
            align = 1 if self.placement == 'r' else 7
            l.append('T %d %d 5 %d 0 0 0 %d 1' % (x, y, self.textFont.size, align))
            l.append('pintype=%s' % pt)
        else:
            assert False, 'Bad pin attribute name.'
        return l
    def render(self,pkg):
        if self.tile.isShadowPin(pkg): 
            return []
        l = []
        if self.placement == 'l':
            nearx = self.lo.right
            farx = self.lo.x
        else:
            nearx = self.lo.x
            farx = self.lo.right
        y = self.lo.y
        # Pin format:
        # P x1 y1 x2 y2 color pintype whichend
        l.append('P %d %d %d %d 1 0 0' % (farx, y, nearx, y))
        l.append('{')
        l.extend(self.renderPinAttr('pinlabel', nearx, y, pkg))
        l.extend(self.renderPinAttr('pinnumber', nearx, y, pkg))
        l.extend(self.renderPinAttr('pinseq', nearx, y, pkg))
        l.extend(self.renderPinAttr('pintype', nearx, y, pkg))
        l.append('}')
        return l

class GVGlyphicTile(GVTile):
    bufferspace = 50
    def __init__(self, viewedModel, parent, placement):
        super(GVGlyphicTile,self).__init__(viewedModel, parent, placement)
        self.glyphviews = [GVGlyph.viewOf(g,self) for g in self.tile.glyphs]
    def reprvals(self):
        return [self.lo, self.glyphviews]
    def minHeight(self):
        return 2*_gridspacing # FIXME: Allow for non-standard font heights.
    def minWidth(self):
        t = reduce(lambda x,y:x+y, [g.width for g in self.glyphviews])
        t += (len(self.glyphviews)-1) * _letterspace
        return t
    def layout(self):
        # 1. Compute a starting X cursor.
        # 2. Let GVGlyph's get band Layout from parentBand.
        # 3. Pass in current X cursor.
        # 4. Compute next X cursor from GVGlyph's layout width
        totalWidth = self.minWidth()
        plo = self.parentBand.lo # less typing
        if self.placement == 'l':
            xCursor = plo.x + _glyphMargin
        elif self.placement == 'r':
            xCursor = plo.right - _glyphMargin - totalWidth
        else: # self.placement == 'c':
            xCursor = plo.middleX - totalWidth/2
        self.lo = Layout(xCursor, plo.y + self.parentBand.upKerning,
                         totalWidth, plo.h)
        for g in self.glyphviews:
            g.layout(xCursor)
            xCursor = g.lo.right + _letterspace
    def strokes(self, pkg):
        l = []
        for g in self.glyphviews:
            l.extend(g.strokes())
        return l
    def render(self, pkg):
        l = []
        for g in self.glyphviews:
            l.extend(g.render())
        return l
    @property
    def singleGlyph(self):
        return len(self.glyphviews) == 1

class GVSpacerTile(GVTile):
    def minHeight(self):
        return self.tile.h
    def minWidth(self):
        return self.tile.w
    def layout(self):
        plo = self.parentBand.lo
        x = plo.middleX - self.tile.w/2
        self.lo = Layout(x, plo.y, self.tile.w, self.tile.h)
    def strokes(self, pkg):
        if self.directives['showspacers']:
            lineWidth = 5
            dashPen = (2,20,20)
            p1 = Pt(self.lo.x, self.lo.y)
            p2 = p1 + Pt(self.minWidth(),0)
            p3 = p2 + Pt(0,self.minHeight())
            p4 = p1 + Pt(0,self.minHeight())
            l = [Stroke(p1, p2, lineWidth, dashPen),
                 Stroke(p3, p4, lineWidth, dashPen)]
            if self.lo.x != self.parentBand.lo.x:
                l.extend([Stroke(p2, p3, lineWidth, dashPen),
                          Stroke(p4, p1, lineWidth, dashPen)])
            return l
        else:
            return []

# Set up the tile viewers.
GVTile.viewers['NoneType'] = GVNoTile
GVTile.viewers['PinTile'] = GVPin
GVTile.viewers['GlyphicTile'] = GVGlyphicTile
GVTile.viewers['SpacerTile'] = GVSpacerTile

#####################
# Band view classes #
#####################
class GVBand(GViewer):
    viewers = dict()
    def __init__(self, viewedModel, parent):
        self.band = viewedModel
        self.parent = parent 
        self.lo = Layout()
        self.lview = GVNoTile(None, self, 'l')
        self.cview = GVNoTile(None, self, 'c')
        self.rview = GVNoTile(None, self, 'r')
        self.index = None # Set by owning GVBlock() after creation.
    def reprvals(self):
        return [self.lo, self.lview, self.cview, self.rview]
    @classmethod
    def viewOf(self, aBand, aParent):
        cn = aBand.__class__.__name__
        view = self.viewers[cn](aBand, aParent)
        return view
    def pred(self):
        "Predecessor band view."
        return self.parent.predBandOf(self.index)
    def succ(self):
        "Successor band view."
        return self.parent.succBandOf(self.index)
    def minHeight(self):
        raise NotImplementedError
    def minWidth(self):
        raise NotImplementedError
    @property
    def upKerning(self):
        return 0
    def layout(self):
        for tv in [self.lview, self.cview, self.rview]:
            tv.layout()
    def assignPinseq(self, pinMap, pkgName, n):
        return n
    def strokes(self, pkg):
        return []
    def render(self,pkg):
        return self.renderTiles(pkg)
    def renderTiles(self, pkg):
        'Return list of strings to print to a .sym file'
        l = self.lview.render(pkg)
        l.extend(self.cview.render(pkg))
        l.extend(self.rview.render(pkg))
        return l
    @property
    def lineNo(self):
        n = self.band.lineNo
        return n if n != None else self.parent.lineNo

class GVIOBand(GVBand):
    def __init__(self, viewedModel, parent):
        super(GVIOBand,self).__init__(viewedModel, parent)
        self.lview = GVTile.viewOf(self.band.ltile, self, 'l')
        self.cview = GVTile.viewOf(self.band.ctile, self, 'c')
        self.rview = GVTile.viewOf(self.band.rtile, self, 'r')
    def minHeight(self):
        return max([x.minHeight() for x in [self.lview,self.cview,self.rview]])
    def minWidth(self):
        ctrMin = self.cview.minWidth()
        if ctrMin > 0:
            sp = 2 * max([self.lview.minWidth(),self.rview.minWidth()])
            sp += 2 * _minwordspace + ctrMin
        else:
            sp = self.lview.minWidth() + self.rview.minWidth() + _minwordspace
        return sp
    def assignPinseq(self, pinMap, pkgName, n):
        n = self.lview.assignPinseq(pinMap, pkgName, n)
        n = self.rview.assignPinseq(pinMap, pkgName, n)
        return n
    def strokes(self, pkg):
        l = self.lview.strokes(pkg)
        l.extend(self.cview.strokes(pkg))
        l.extend(self.rview.strokes(pkg))
        return l

class GVNeckBand(GVBand):
    def __init__(self, viewedModel, parent):
        super(GVNeckBand,self).__init__(viewedModel, parent)
        self.cview = GVTile.viewOf(self.band.ctile, self, 'c')
    def minHeight(self):
        return self.cview.minHeight()
    def minWidth(self):
        return self.cview.minWidth() + 2 * (_neckindent + _minwordspace)
    @property
    def lindent(self):
        "Left indent."
        return self.lo.x + _neckindent
    @property
    def rindent(self):
        "Right indent."
        return self.lo.right - _neckindent

class GVSepBand(GVBand):
    def __init__(self, viewedModel, parent):
        super(GVSepBand,self).__init__(viewedModel, parent)
    def minHeight(self):
        return 2*_gridspacing if self.band.wide else 0
    def minWidth(self):
        return 0
    def strokes(self, pkg):
        yy = self.lo.y + (self.height/2 if self.band.wide else 0)
        return [Stroke(Pt(self.lo.x, yy), Pt(self.lo.x + self.lo.w, yy))]

class GVTopBand(GVBand):
    def __init__(self, viewedModel, parent):
        super(GVTopBand,self).__init__(viewedModel, parent)
        self.cview = GVTile.viewOf(self.band.ctile, self, 'c')
        self.refdes = self.parentPart.attrs['refdes']
    def minHeight(self):
        return _gridspacing + self.cview.minHeight()
    def minWidth(self):
        return _minwordspace + self.cview.minWidth()
    def strokes(self, pkg):
        return self.cview.strokes(pkg)
    def render(self,pkg):
        av = GVAttr(self.refdes,self)
        ax = self.lo.middleX
        ay = self.lo.top + _refdesOffset
        av.setLayout(Pt(ax,ay),'lm',10,'attribute',(True,'v'))
        l = av.render()
        l.extend(self.renderTiles(pkg))
        return l

class GVBotBand(GVBand):
    def __init__(self, viewedModel, parent):
        super(GVBotBand,self).__init__(viewedModel,parent)
    def minWidth(self):
        return 0
    def minHeight(self):
        return 0 if isinstance(self.pred(),GVNeckBand) else _gridspacing

class GVTextBand(GVBand):
    def __init__(self, viewedModel, parent):
        super(GVTextBand,self).__init__(viewedModel, parent)
        self.cview = GVTile.viewOf(self.band.ctile, self, 'c')
    def minWidth(self):
        return self.cview.minWidth() + 2 * _minwordspace
    def minHeight(self):
        return max([self.cview.minHeight(),2*_gridspacing])
    @property
    def upKerning(self):
        return self.band.upKerning

# Set up the band viewers.
GVBand.viewers['IOBand'] = GVIOBand
GVBand.viewers['NeckBand'] = GVNeckBand
GVBand.viewers['SepBand'] = GVSepBand
GVBand.viewers['TopBand'] = GVTopBand
GVBand.viewers['BotBand'] = GVBotBand
GVBand.viewers['TextBand'] = GVTextBand

##############
# Block view #
##############
class GVBlock(GViewer):
    viewers = dict()
    def __init__(self, viewedModel, parent):
        self.block = viewedModel
        self.parent = parent
        self.bandViews = [GVBand.viewOf(b,self) for b in self.block.bands]
        self._setBandIndices() # Set up the bandView indices for succ() and pred()
        # Blocks inherit most attributes from parent part.
        # refdes gets special handling in the GVTopband.
        self.attrViews = [GVAttr(x,self) \
                          for x in self.parent.part.attrs.values() \
                          if x.name != 'refdes']
        # Initialize some view properties.
        self.lo = Layout(_pinlength, 0) # Set lower-left corner of block.
        self.pinMap = self._initialPinMap()
        self.numPins = dict() # dict[pkgName] of pin count of this block
    def reprvals(self):
        return [self.block, self.parent, self.bandViews]
    @classmethod
    def viewOf(self, aBlock, aParent):
        cn = aBlock.__class__.__name__
        view = self.viewers[cn](aBlock, aParent)
        return view
    def _initialPinMap(self):
        "Initialize empty pinMap"
        # Pin map is: dict[pkgName] of dict[pinSeq] of pinNumList.
        d = dict()
        for pkg in self.block.pkgSet():
            d[pkg] = dict()
        return d
        l = self.bandViews
        return l
    @property
    def blockNameSet(self):
        return self.block.blockNameSet()
    @property
    def parentBlockName(self):
        return self.block.referenceBlockName
    def packageNameOf(self, blockId):
        for pkg, blk in self.block.pkgs:
            if blockId == blk:
                return pkg
        return None
    # Every GVBand needs index to find it's successors and predecessors.
    def _setBandIndices(self):
        i = 0
        for b in self.bandViews:
            b.index = i
    def predBandOf(self, index):
        return self.bandViews[index-1] if index > 0 else None
    def succBandOf(self, index):
        return self.bandViews[index+1] \
               if index < len(self.bandViews)-1 else None
    # Layout methods.
    def setBandHeights(self):
        for b in self.bandViews:
            b.lo.h = gridUp(b.minHeight())
    def setBandWidths(self):
        for b in self.bandViews:
            b.lo.w = self.lo.w
    def setBandYCoords(self):
        cur_y = self.lo.y
        for b in reversed(self.bandViews):
            b.lo.y = cur_y
            cur_y = b.lo.top
        self.lo.h = cur_y
    def setBandXCoords(self):
        for b in self.bandViews:
            b.lo.x = self.lo.x
    def minWidth(self):
        return max([b.minWidth() for b in self.bandViews])
    def layout(self, minWidthSpec=None):
        self.setBandXCoords()
        wl = [gridUp(self.minWidth())]
        if minWidthSpec != None:
            wl.append(minWidthSpec)
        self.lo.w = max(wl)
        self.setBandWidths()
        self.layoutBandInteriors()
    def layoutBandInteriors(self):
        for b in self.bandViews:
            b.layout()
    def layoutAttrs(self):
        step = 2 * _gridspacing
        cur_y = self.lo.top + step
        x = self.lo.right
        al = [a for a in self.attrViews if not a.attr.refBy(self.parentBlockName)] 
        al.reverse()
        for av in al:
            av.setLayout(Pt(x,cur_y))
            cur_y += step
    # Pin Sequence and slotting
    def assignPinseq(self):
        for pkg in self.block.pkgSet():
            n = 1
            for b in self.bandViews:
                n = b.assignPinseq(self.pinMap, pkg, n)
            self.numPins[pkg] = n-1
    def slotPins(self, aPkg, aSlot):
        "Returns list of pins for aSlot in pinseq order."
        l = []
        for i in range(0,self.numPins[aPkg]):
            l.append(self.pinMap[aPkg][i+1][aSlot-1])
        return l
    def addSlotAttrs(self):
        "Creates numslots=# and slotdef=#:#,#,...  attributes if needed."
        # Slotting and shadow pins don't work together, so it is sufficient to
        # grab the first package name.
        aPkg = self.block.anyPkg
        n = self.block.numSlots()
        if n < 2:
            return
        a = mdl.Attr('numslots',n)
        self.attrViews.append(GVAttr(a,self))
        for slotnum in xrange(1,n+1):
            s = '{0:d}:'.format(slotnum)
            s += ','.join([str(p) for p in self.slotPins(aPkg, slotnum)])
            a = mdl.Attr('slotdef',s)
            self.attrViews.append(GVAttr(a,self))
        a = mdl.Attr('slot',1) # set the default slot
        self.attrViews.append(GVAttr(a,self))
    # Rendering
    def strokes(self, pkg):
        'Return list of all strokes in the block.'
        l = self.outlineStrokes()
        l.extend(self.bandStrokes(pkg))
        return l
    def findNeck(self):
        "Returns (None,None), (aGVNeckBand, 'middle'), or (aGVNeckBand,'bottom')."
        for b in self.bandViews:
            if isinstance(b,GVNeckBand):
                return (b,'bottom' if isinstance(b.succ(), GVBotBand) else 'middle')
        return (None, None)
    def outlineStrokes(self):
        'Return list of box outline strokes.'
        l = [] # Stroke accumulator
        lo = self.lo # Local dereference for readability.
        lwb = _linewidth_for_box # saves typing...
        # Top of box.
        l.append(Stroke(Pt(lo.x,lo.top),Pt(lo.right,lo.top),lwb))
        # The rest of the box shape depends on neck placement.
        neckBand, neckPlace = self.findNeck()
        if neckPlace == None:
            # Square box.
            l.append(Stroke(Pt(lo.x,lo.y),Pt(lo.x, lo.top),lwb)) # Left
            l.append(Stroke(Pt(lo.x,lo.y),Pt(lo.right,lo.y),lwb)) # Bottom
            l.append(Stroke(Pt(lo.right,lo.y),Pt(lo.right,lo.top),lwb)) # Right
            return l
        # Top part of block and neck indentation.
        l.append(Stroke(
                 Pt(lo.x, lo.top),
                 Pt(lo.x, neckBand.lo.top), lwb)) # Top left side
        l.append(Stroke(
                 Pt(lo.right, lo.top),
                 Pt(lo.right, neckBand.lo.top), lwb)) # Top right side
        l.append(Stroke(
                 Pt(lo.x, neckBand.lo.top),
                 Pt(neckBand.lindent, neckBand.lo.top),lwb)) # Left neck horizontal
        l.append(Stroke(
                 Pt(lo.right, neckBand.lo.top),
                 Pt(neckBand.rindent, neckBand.lo.top), lwb)) # Right neck horizontal
        l.append(Stroke(Pt(neckBand.lindent, neckBand.lo.top),
                 Pt(neckBand.lindent, neckBand.lo.y), lwb)) # Left neck vertical
        l.append(Stroke(Pt(neckBand.rindent, neckBand.lo.top),
                 Pt(neckBand.rindent, neckBand.lo.y), lwb)) # Right neck vertical
        if neckPlace == 'middle':
            l.append(Stroke(
                     Pt(lo.x, neckBand.lo.y),
                     Pt(lo.right, neckBand.lo.y), lwb)) # Neck separator stroke
            l.append(Stroke(
                     Pt(lo.x, lo.y),
                     Pt(lo.x, neckBand.lo.y), lwb)) # Box bottom left side
            l.append(Stroke(
                     Pt(lo.right, lo.y),
                     Pt(lo.right, neckBand.lo.y), lwb)) # Box bottom right side
            l.append(Stroke(
                     Pt(lo.x, lo.y), 
                     Pt(lo.right, lo.y), lwb)) # Box bottom horizontal stroke
        else: # neckPlace == 'bottom':
            l.append(Stroke(
                     Pt(neckBand.lindent, lo.y),
                     Pt(neckBand.rindent, lo.y), lwb)) # Bottom horizontal stroke
        return l
    def bandStrokes(self, pkg):
        l = []
        for b in self.bandViews:
            l.extend(b.strokes(pkg))
        return l
    def renderBands(self,pkg):
        '''Return a list of strings of non-stroke band information
        to print to a .sym file.'''
        l = []
        for b in self.bandViews:
            l.extend(b.render(pkg))
        return l
    def render(self, pkg):
        'Return a list of strings to print to a .sym file.'
        l = [_fileversion]
        l.extend([s.render(Pt(0,0)) for s in self.strokes(pkg)])
        for av in self.attrViews:
            l.extend(av.render())
        l.extend(self.renderBands(pkg))
        return l
    @property
    def lineNo(self):
        return self.block.lineNo

class GVUnusedBlock(GVBlock):
    def layout(self, minw):
        pass
    def layoutAttrs(self):
        pass

# Set up block viewers
# FIXME: These two viewers could probably stand refactoring.
GVBlock.viewers['Block'] = GVBlock
GVBlock.viewers['UnusedBlock'] = GVUnusedBlock

#############
# Part view #
#############
class GVPart(GViewer):
    def __init__(self, aPart):
        "View of a Part model."
        super(GVPart,self).__init__(None)
        self.part = aPart
        self.blockViews = [GVBlock.viewOf(b,self) for b in self.part.blocks]
        self._textFont = None # gets cached on first call
        self._pinFont = None # gets cached on first call
    def reprvals(self):
        return self.blockViews
    @property
    def directives(self):
        "Reference directives dictionary in viewed mdl.Part() instance."
        return self.part.directives
    @property
    def parentPart(self):
        return self.part
    @property
    def textFont(self):
        "Returns instance of FontInfo."
        if self._textFont == None:
            name = self.part.directives['fontname']
            size = self.part.directives['textfontsize']
            self._textFont = FontInfo(name, size)
        return self._textFont 
    @property
    def pinFont(self):
        "Returns instance of FontInfo."
        if self._pinFont == None:
            name = self.part.directives['fontname']
            size = self.part.directives['pinfontsize']
            self._pinFont = FontInfo(name, size)
        return self._pinFont
    def layoutAll(self):
        'Lays out the part.'
        # Set height of all bands and blocks.
        for b in self.blockViews:
            b.setBandHeights()
        # Set Y coordinate of all bands in each band.
        for b in self.blockViews:
            b.setBandYCoords()
        # Set widths of all bands and blocks.
        widths = [self.directives['minwidth']]
        if self.directives['samewidth']:
            widths.extend([b.minWidth() for b in self.blockViews])
        minw = max(widths)
        if minw == 0:
            minw = None
        # Perform detail layout.
        for b in self.blockViews:
            b.layout(minw)
            b.layoutAttrs()
    def assignPinseqAll(self):
        for b in self.blockViews:
            b.assignPinseq()
    def addSlotAttrsAll(self):
        for b in self.blockViews:
            b.addSlotAttrs()
    def blockViewing(self, blockId):
        for b in self.blockViews:
            if blockId in b.blockNameSet:
                return b
        return None
    def render(self, blockId):
        blk = self.blockViewing(blockId)
        pkg = blk.packageNameOf(blockId)
        return blk.render(pkg)

        
#######################
