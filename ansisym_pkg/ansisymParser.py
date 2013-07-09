"ansisym parser"

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

from os.path import dirname

import ply.lex as lex
import ply.yacc as yacc

import ansisymErrorSink as er
import ansisymModel as mdl


#################
# Configuration #
#################
_anonymousPin = '_'

###############################
# Parsing State and Constants #
###############################
_packageListContext = None # Nasty parsing context to track package names.
_attrContext = None # Nasty parsing context to make attribute dict available.
_blockContext = None # Especially nasty context for ref-attr validation.
_directive = mdl.DirectiveDict()
_boilerplate = [] # Expecting a list of [name, value] lists here.

####################
# Lexical Analyzer #
####################
states = (
    ('kwstate','inclusive'),
    ('strstate','exclusive'),
)

reserved_list = ['A', 'AB','BK','IO','T','U', 'BAD']
reserved = set(reserved_list)
kw_list = ['KW_SEP','KW_NECK','KW_CTXT','KW_CTXTU','KW_DIR']
recovery = reserved.union(set(kw_list))

tokens = [
    'NUM','STR','FLAG', 'NL',
] + reserved_list + kw_list

actualLiterals = [',','%','^','~',';',':','[',']','=','/']
extraneous =  '$(<`\'+{*.>!)}'

literals = actualLiterals + list(extraneous)
# Extraneous characters are simply passed on to the parser,
# which can then barf on them systematically.

precedence = (
    ('right','KW_DIR'),
    ('right','^','~','%','FLAG'),
    ('right','A','AB','NL'),
)

# Keep track of line number on newlines.
# NL's are passed to grammar only to simplify error recovery.
# A keyword implies a newline, but letting the grammar see
# the newline as well allows simplified resynchronization.
# Trigger 'kwstate' newline context processing here, also.
def t_kwstate_NL(t):
    r'\n'
    t.lexer.begin('kwstate')
    t.lexer.lineno += 1
    # Duplicate NL, absorb it.
    
def t_NL(t):
    r'\n'
    t.lexer.begin('kwstate')
    t.lexer.lineno += 1
    return t

# Keywords
# Start a line.  Some are 1 or 2 character keywords.
# Some are special characters.  Inclusive start state
# 'kwstate' is used to trigger newline context.
def t_kwstate_KW(t):
    r'[A-Z]+'
    t.type = t.value if t.value in reserved else 'BAD'
    t.lexer.begin('INITIAL')
    return t

# Special character "keywords" have a glorious regular expression.
def t_kwstate_KWS(t):
    r'(\-\-)|(\-)|(\])|(\|\^)|(\|)|%' # NO CARRIER
    if t.value == '-' or t.value == '--':
        t.type = 'KW_SEP'
    elif t.value == ']':
        t.type = 'KW_NECK'
    elif t.value == '%':
        t.type = 'KW_DIR'
    elif t.value == '|':
        t.type = 'KW_CTXT'
    elif t.value == '|^':
        t.type = 'KW_CTXTU'
    else:
        t.type = 'BAD' # Let the parser issue error message.
    t.lexer.begin('INITIAL')
    return t

# Strings and numbers.
#
# Strings:
# 1. May be explicitly deliminted by ".  This form is
#    accumulated in an exclusive start state.
# 2. Implicit string: starts with alpha, digit, or
#    one of: & @ _
#    It continues with the above characters, plus
#    any of: - ?
#
# Numbers:
# Note that case #2 above includes strings of pure digits.
# The lexer tests strings and converts them to numbers
# where possible.  Sometimes the parser needs to str() them
# back again.
def t_STR(t):
    
    r'[a-zA-Z0-9&@_][a-zA-Z0-9&@_?-]*'
    try:
        t.value = int(t.value)
    except:
        return t
    t.type = 'NUM'
    return t

def t_STR_start(t):
    r'"'
    t.lexer.begin('strstate')

# re == (not a ", newline, or \) or (\ followed by ")
# Basically, suck up escaped " chars and anything else up to newline.
def t_strstate_STR(t):
    r'([^"\n\\]|(\\"))+'
    return t

def t_strstate_done(t):
    r'"'
    t.lexer.begin('INITIAL')

# Other tokens
def t_FLAG(t):
    r'![a-z]+'
    return t
    
t_ignore = ' \t'
t_strstate_ignore = ''

def t_comment(t):
    r'\#.*'
    pass
    
def t_error(t):
    pass

def t_strstate_error(t):
    pass

##########
# Parser #
##########
# 'part' is the start symbol.
def p_part(p):
    "part : directives global_attrs block_list"
    global _attrContext
    p[0] = mdl.Part(_attrContext, p[3], _directive)

# Directives
def p_directives(p):
    """directives : directives directive 
        | directive
        | NL
        | %prec KW_DIR"""
    pass # Nothing to do here.

def p_directive(p):
    """directive : KW_DIR STR STR NL
        | KW_DIR STR NUM NL
        | KW_DIR STR NL"""
    # Capture directive setting in dictionary.
    global _directive
    if not _directive.isValid(p[2]):
        er.ror.msg('w',' '.join([p[2], 'is not a valid directive name - ignored.']))
    else:
        v = p[3] if len(p) > 4 else True
        _directive[p[2]] = v

def p_directive_err(p):
    "directive : KW_DIR error NL"
    pass # recover to a NL

# Attribute collection.
def p_global_attrs_attr(p):
    "global_attrs : global_attrs attr"
    global _attrContext
    _attrContext.add(p[2])

def p_global_attrs_boilerplate(p):
    "global_attrs : global_attrs AB NL"
    global _attrContext
    for nm,val in _boilerplate:
        _attrContext.add(mdl.Attr(nm,val))

def p_global_attrs_induce_attr(p):
    "global_attrs : attr"
    global _attrContext
    _attrContext = mdl.AttrDict()
    _attrContext.add(p[1])

def p_global_attrs_induce_boilerplate(p):
    "global_attrs : AB NL"
    global _attrContext
    _attrContext = mdl.AttrDict()
    for nm,val in _boilerplate:
        _attrContext.add(mdl.Attr(nm,val))

def p_global_attrs_completely_missing(p):
    "global_attrs : %prec 'A'"
    # Extra grammar rule here is an attempt at giving somewhat
    # informative error message.
    er.ror.msg('f', 'Attributes must appear before first block.')
    raise SyntaxError

def p_attr(p):
    """attr : A STR STR NL
        | A STR NUM NL"""
    p[0] = mdl.Attr(p[2], p[3])
    
def p_attr_err(p):
    "attr : A error NL"
    p[0] = mdl.Attr('error','in syntax')

# Block collection.
def p_block_list_recurse(p):
    "block_list : block_list block"
    p[0] = p[1]
    p[0].append(p[2])

def p_block_list_induce(p):
    "block_list : block"
    p[0] = [ p[1] ]

# The unused pin psuedo-block.
def p_block_u(p):
    """block : U STR ':' pinnum_list NL
        | U pinnum_list NL"""
    if len(p) > 4:
        pkg = p[2]
        pins = p[4]
    else:
        pkg = mdl.unnamedPackage
        pins = p[2]
    p[0] = mdl.UnusedBlock(pkg,pins)
    p[0].lineNo = p.lineno(1)

def p_block_u_err(p):
    "block : U error NL"
    p[0] = mdl.UnusedBlock('error',[])
    p[0].lineNo = p.lineno(1)
    
# Block processing.
def p_block_bk(p):
    "block : block_header band_list"
    p[2].append(mdl.BotBand())
    p[0] = mdl.Block(p[1][0],p[2])
    p[0].lineNo = p[1][1] 

def p_block_header(p):
    "block_header : BK bk_package_list NL"
    global _packageListContext
    _packageListContext = [x for (x,y) in p[2]]
    global _blockContext 
    _blockContext = p[2][0][1] # First file name becomes blockName key.
    # This is a good place to error check that if mdl.unnamedPackage
    # is present, that it is the only package.
    if mdl.unnamedPackage in _packageListContext \
    and len(_packageListContext) > 1:
        er.ror.msg('f','Explicit package name required. Line:' + str(p.lineno(1)))
    p[0] = (p[2], p.lineno(1)) # Kinda kludgy tuple to pass lineno up parse tree.
    
def p_block_header_err(p):
    "block_header : BK error NL"
    p[0] = [['error','error']]
    #p[0].lineNo = p.lineno(3)-1
    
def p_bk_package_list_recurse(p):
    "bk_package_list : bk_package_list '/' bk_package_spec"
    p[0] = p[1]
    p[0].append(p[3])

def p_bk_package_list_induce(p):
    "bk_package_list : bk_package_spec"
    p[0] = [ p[1] ]

def p_bk_package_spec(p):
    """bk_package_spec : STR ':' STR
        | STR"""
    if len(p) > 2:
        pkg = p[1]
        symname = p[3]
    else:
        pkg = mdl.unnamedPackage
        symname = p[1]
    p[0] = (pkg,symname)

# Band collection.
def p_band_list_recurse(p):
    "band_list : band_list band"
    p[0] = p[1]
    p[0].append(p[2])

def p_band_list_induce(p):
    "band_list : band"
    p[0] = [ p[1] ]

# Top band
def p_band_top(p):
    "band : T opt_str NL"
    gt = mdl.GlyphicTile.fromSTR(p[2], _attrContext, _blockContext) if p[2] != "" else None
    p[0] = mdl.TopBand(gt)
    p[0].lineNo = p.lineno(1)
    
# Neck band
def p_band_neck(p):
    "band : KW_NECK opt_str NL"
    gt = mdl.GlyphicTile.fromSTR(p[2],_attrContext, _blockContext) if p[2] != "" else None
    p[0] = mdl.NeckBand(gt)
    p[0].lineNo = p.lineno(1)

# Separator bands
def p_band_sep(p):
    "band : KW_SEP NL"
    p[0] = mdl.SepBand(p[1]=='--')
    p[0].lineNo = p.lineno(1)
    
# Text bands
def p_band_text(p):
    "band : KW_CTXT opt_glyph_tile NL"
    p[0] = mdl.TextBand(p[2])
    p[0].lineNo = p.lineno(1)
    
def p_band_kerntext(p):
    "band : KW_CTXTU NUM STR NL"
    gt = mdl.GlyphicTile.fromSTR(p[3], _attrContext, _blockContext)
    p[0] = mdl.TextBand(gt, p[2])
    p[0].lineNo = p.lineno(1)
    
# Spacer specification
def p_spacer_spec_w(p):
    "spacer_spec : '[' NUM ']' "
    p[0] = mdl.SpacerTile(p[2])

def p_spacer_spec_wh(p):
    "spacer_spec : '[' NUM ',' NUM ']' "
    p[0] = mdl.SpacerTile(p[2], p[4])

# Bad keyword error trap.
def p_band_bad(p):
    """band : BAD error NL"""
    p[0].lineNo = p.lineno(3)-1
    raise SyntaxError

    
# IO band construction.
def p_band_io(p):
    "band : IO opt_io_tile ';' opt_glyph_tile ';' opt_io_tile NL"
    p[0] = mdl.IOBand(p[2],p[4],p[6])
    p[0].lineNo = p.lineno(1)
    
# Syntax error recovery in a band
def p_band_err(p):
    "band : error NL"
    p[0] = mdl.TextBand(mdl.GlyphicTile.fromSTR('syntax error',
                        _attrContext, _blockContext))
    
# Glyph tiles.
def p_opt_glyph_tile(p):
    """opt_glyph_tile : STR
        | NUM
        | """
    if len(p) > 1:
        p[0] = mdl.GlyphicTile.fromSTR(str(p[1]),_attrContext,_blockContext)
    else:
        p[0] = None

def p_opt_glyph_spacer_tile(p):
    "opt_glyph_tile : spacer_spec "
    p[0] = p[1]
    
# IO tile processing.
def validPinnumLists(pnl):
    # pnl is a list of pinlists.
    # Each list should be irredundant.
    # If any list is longer than 1, it should not contain 0.
    # FIXME: combine with check against _packageListContext which is
    # still in the production function.
    return True # FIXME

def p_opt_io_tile(p):
    """opt_io_tile : pinflag_list NUM package_pinnum_list
       opt_io_tile : pinflag_list STR package_pinnum_list
        | """
    if len(p) > 1:
        if len(p[3]) != len(_packageListContext):
            plc = len(p[3])
            pkc = len(_packageListContext)
            m = str(plc) + ' pinlists found, but ' + str(pkc) + ' are required.'
            m += '  Line: ' + str(p.lineno(2))
            er.ror.msg('f',m)
            p[0] = None
        elif not validPinnumLists(p[3]):
            p[0] = None
        else:
            d = dict()
            for i in xrange(0,len(_packageListContext)):
                d[_packageListContext[i]] = p[3][i]
            pinName = str(p[2]) if p[2] != _anonymousPin else ''
            p[0] = mdl.PinTile(pinName, p[1], d)
    else:
        p[0] = None
    
# IO pin flags.
# Pin flags are represented as a set() of the lexical literals.
def p_pinflag_list_recurse(p):
    "pinflag_list : pinflag_list pinflag"
    p[0] = p[1]
    p[0].add(p[2])

def p_pinflag_list_induce(p):
    "pinflag_list : pinflag"
    p[0] = set([p[1]])

def p_pinflag_list_empty(p):
    "pinflag_list : %prec FLAG"
    p[0] = set()

def p_pinflag(p):
    """pinflag : '~'
        | '^'
        | '%'
        | FLAG"""
    if mdl.PinTile.isValidPinType(p[1]):
        p[0] = p[1]
    else:
        m = ' '.join([p[1],'is not a valid pin type. Line:',
                    str(p.lineno(1))])
        er.ror.msg('f',m)
        p[0] = '!pas' # Force a valid type to continue syntax checking.

# IO pin numbers.
# A package_pinnum_list list a list of lists.  The lists of
# pin numbers are collected into a list with one pinnum_list
# entry per package.
def p_package_pinnum_list_recurse(p):
    "package_pinnum_list : package_pinnum_list '/' pinnum_list"
    # p[0] is a list of lists.
    p[0] = p[1]
    p[0].append(p[3])

def p_package_pinnum_list_induce(p):
    "package_pinnum_list : pinnum_list"
    p[0] = [ p[1] ]

def p_pinnum_list_recurse(p):
    "pinnum_list : pinnum_list ',' NUM"
    p[0] = p[1]
    p[0].append(p[3])

def p_pinnum_list_induce(p):
    "pinnum_list : NUM"
    p[0] = [ p[1] ] 
    #p[0] = [] if p[1] == 0 else [ p[1] ] # Causes slot-matching validation errors.

def p_opt_str(p):
    """opt_str : STR
       | """
    p[0] = p[1] if len(p) > 1 else ""

##################
# Error Recovery #
##################
def p_error(p):
    if p.type == None:
        errtok = 'EOF'
        errline = 'EOF'
    elif p.type == 'NL':
        errtok = 'newline'
        errline = str(p.lineno-1) # compensate for lineno being off-by-1 on NL
    else:
        errtok = p.type
        errline = str(p.lineno)
    s = ''.join(["Syntax error at token: ",errtok,", line: ", errline])
    if errtok in extraneous:
        s += ' -- Extraneous character.'
    er.ror.msg('f',s)

###########################
# Build lexer and parser. #
###########################

# Make the lexer.
_lexer = lex.lex()
_lexer.lineno -= 1 # Back off by one to compensate for sour-dough '\n'.
# table generation is disabled -- this keeps ply from leaving ply-turds
# all over the user's workspace.  For a grammar this small, it isn't
# a big deal.


# Make the parser. 
# Production deployment:
try:
    _cacheDir = dirname(__file__) # Find out where this module lives during install.
except:
    _cacheDir = '.'
_parser = yacc.yacc(debug=0,outputdir=_cacheDir) # Cache files to install directory.

# Debug:
#_parser = yacc.yacc() # development - ply puts temps into cwd
#_parser = yacc.yacc(debug=0,write_tables=0) # disable ply caching and messages

#######################
# Module Entry Points #
#######################
def parse(inputText, boilerplate, debugFlag=0):
    "Parse inputText, returning a Part() instance. boilerplate = [[nm,val]...]"
    global _boilerplate
    _boilerplate = boilerplate
    # Wrapping the input text in newlines makes syntax error
    # recovery simpler.  Otherwise the grammar could leave out
    # NL's entirely and be cleaner.  NL's are the 'handle' for
    # error productions, generally, but having explicit NL's
    # in the grammar complicates the beginning and end-of-file
    # cases.  Soooo.... the input text is wrapped in gratuitous
    # newlines.
    return _parser.parse(inputText.join(['\n','\n']), debug=debugFlag)


#############################################################################
# Module quick-test #
#####################
if __name__ == '__main__':
    
    test = '''
# Generic '00 Quad 2-input NAND
%showspacers
%minwidth 400
A device "74x00"
A refdes U?
AB
# Positive logic symbol
BK 74x00-1
T &&
IO A 1,4,9,12;;
IO ;;~Y 3,6,8,11
IO B 2,5,10,13;;
# Negative logic symbol
BK 74x00-n1
T &ge&1
IO ~A 1,4,9,12;;
IO ;;Y 3,6,8,11
IO ~B 2,5,10,13;;
# Power supply symbol
BK 74x00-p1
T 74x00
IO Vcc 14;;GND 7
# Crazy stuff
BK CRAZY-1
T @device@
|
| foo
|^ 50 bar
] neck
IO A 1;;
IO ;[10];B 2
| [20,30]
| "ab\\"cd"
'''


    _lexer.input(test)
    
    while True:
        tok = _lexer.token()
        if not tok: break
        print tok

    _lexer.lineno = 0

    print '---parsing---'    
    #part = _parser.parse(test)
    #_parser.parse(test,debug=1)
    part = parse(test,[['distlicense','unlimited']])
    
    print '---part def---'
    print part
    
