from pyparsing import *
from parserutils import *
import os

def find_file(filename):
    """ Evaluate a file path against include directories """
    for i in list(_ctx.include_paths) + [ os.path.dirname(_ctx.filename) ]:
        full_path = os.path.join(i, filename)
        if os.path.exists(full_path):
            return full_path
    return filename # failure gets handled later on

## Parsing grammar for template database files

eol = LineEnd().suppress()

comment = OneOrMore(Regex(r"#[^\n]*") + eol)
class Comment(object):
    def __init__(self, lines):
        self.lines = lines
    def __repr__(self):
        return "\n".join(self.lines)
    def to_database(self):
        return "%s\n" % self.__repr__()
def _process_comment(s,loc,toks):
    return [] if _ctx.strip_comments else [ Comment(toks) ]
comment.setParseAction(_process_comment)

macro_name = Word(alphas, alphanums+"_")

macro_value = Forward()
default_content = ZeroOrMore( CharsNotIn("$)\n")|macro_value) # default values can be any character but newline or ), including nested macro values
macro_value << Literal("$(").suppress() + macro_name + Optional(Literal("|").suppress() - default_content) + Literal(")").suppress()

name_string = Word(alphanums+":_+-")
name_token = optionally_quoted( ZeroOrMore(name_string|macro_value) )
def _token_join(s,loc,toks):
    return "".join(toks)
name_token.setParseAction(_token_join)
default_content.setParseAction(_token_join)

field_string = CharsNotIn("\"$")
token_content = ZeroOrMore(field_string|macro_value)
token_content.setParseAction(_token_join)
field_token = quoted( token_content  )

def _evaluate_macro(s,loc,toks):
    try:
        # recursively expand macros as field token values (ie macros can contain macros)
        macro_name = toks[0]
        if len(toks) == 2:
            macro_value = _ctx.macros.get(macro_name, toks[1])
        else:
            macro_value = _ctx.macros[macro_name]
        return token_content.parseString(macro_value)
    except KeyError:
        if not _ctx.allow_missing:
            raise ParseFatalException(s, loc, "Macro %s has no value set " % toks[0])
        return ""
macro_value.setParseAction(_evaluate_macro)

field_value = Group( Literal("field").suppress() - parentheses(comma_delimited(Word(alphas, alphanums), field_token )))
field_list = curly_braces( Group( ZeroOrMore(field_value) ))

record = Group( Literal("record").suppress() - parentheses(comma_delimited( Word(alphas), name_token )) + field_list )
class Record(object):
    def __init__(self, rtype, name, fields, filename, loc, s):
        _ctx.verbose_fn("Record %s at %s - %s" % (name, filename, lineno(loc,s)))
        self.rtype = rtype
        self.name = name
        self.fields = fields
        self.filename = filename
        self.lineno = lineno(loc,s)
        # check for duplicate fields
        names = set()
        for name,value in self.fields:
            if name in names:
                raise ParseFatalException(s,loc,"Duplicate field name %s in record %s" % (name, self.name))
            names.add(name)
        if _ctx.verify_record_fn:
            _ctx.verify_record_fn(self,s,loc)

    def __repr__(self):
        return "(record %s,%s with %d fields)" % (self.name, self.rtype, len(self.fields))
    def to_database(self):
        fields = [ '  field(%s, "%s")' % v for v in self.fields ]
        return 'record(%s, %s) {\n%s\n}\n\n' % (self.rtype, self.name,
                                                "\n".join(fields))
def _process_record(s,loc,toks):
    fields = [(name,value) for name,value in toks[0][2]]
    return [ Record(toks[0][0], toks[0][1], fields,  _ctx.filename, loc, s) ]
record.setParseAction(_process_record)

include_clause = Literal("include").suppress() + dblQuotedString
def _process_include(s,loc,toks):
    path = find_file(toks[0].strip('"'))
    line = lineno(loc,s)
    _ctx.verbose_fn("include %s at %s - %s" % (path, _ctx.filename, line))
    try:
        included = parse_database_file(path, None)
    except DatabaseParseException, err:
        raise DatabaseOuterParseException(_ctx.filename, "included", line, err)
    return [ "# %s:%d include \"%s\"" % (_ctx.filename, line, path),
             included,
             "# %s:%d end include \"%s\"" % (_ctx.filename, line+1, path) ]
include_clause.setParseAction(_process_include)

substitute_clause = Literal("substitute").suppress() - Regex(r"[^\n]*") + eol
def _process_substitute(s,loc,toks):
    content = toks[0].strip('" ')
    content = content.replace('\"', '"') # escaped double-quotes, as per msi documentation
    for name,value in ( pair.strip().split("=") for pair in content.split(",") ):
        _ctx.verbose_fn("substitute %s -> %s" % (name, value))
        _ctx.macros[name] = value
    return []
substitute_clause.setParseAction(_process_substitute)

expand_macro_value = Group( Literal("macro").suppress() - parentheses(comma_delimited( macro_name, field_token )) )
expand_macro_list = curly_braces( ZeroOrMore(expand_macro_value) )
expand_clause = Word("expand").suppress() - parentheses(dblQuotedString) + Optional(expand_macro_list)
def _process_expand(s,loc,toks):
    line = lineno(loc,s)
    macros = dict( (name,value) for name,value in toks[1:] )
    path = find_file(toks[0].strip('"'))
    _ctx.verbose_fn("expand %s at %s - %s (macros %s)" % (path, _ctx.filename, line, macros))
    try:
        inner = parse_database_file(path, macros)
    except DatabaseParseException, err:
        raise DatabaseOuterParseException(_ctx.filename, "expanded", line, err)
    return [ Comment(["\n# >>> expand \"%s\" at %s:%d\n" % (path, _ctx.filename, line)]),
             inner,
             Comment(["\n# <<<< end expand \"%s\" at %s:%d\n" % (path, _ctx.filename, line+1)]) ]
expand_clause.setParseAction(_process_expand)

database_content = ZeroOrMore((comment|record|include_clause|substitute_clause|expand_clause)) + StringEnd()


# Parser context stuff, to be stored hackily in module-global variable _ctx

class ParserContext:
    def __init__(self):
        self.macro_stack = []
        self.filename_stack = []
        self.include_paths = ["."]
        self.verbose_fn = lambda msg: None
        self.verify_record_fn = None
        self.dependency_callback = lambda filename: None
        self.allow_missing = False
        self.strip_comments = False

    @property
    def macros(self):
        return self.macro_stack[-1]
    @property
    def filename(self):
        return self.filename_stack[-1]


class DatabaseParseException(Exception):
    """ DatabaseParseExceptions come in two kinds - inner exceptions are
    just thin wrappers around the pyparsing ParseException, outer exceptions
    are wrappers around inner exceptions because of expand/include nesting results
    inside each other.
    """
    pass

class DatabaseInnerParseException(DatabaseParseException):
    def __init__(self, filename, inner):
        self.inner = inner
        self.filename = filename

    def __str__(self):
        if hasattr(self.inner, "lineno"):
            return "%s at %s (line %d, col %d)" % (self.inner.msg, self.filename,
                                                   self.inner.lineno, self.inner.col)
        else:
            return "%s at %s" % (self.inner, self.filename)

    def __repr__(self):
        return self.__str__()

class DatabaseOuterParseException(DatabaseParseException):
    def __init__(self, filename, action, lineno, inner):
        self.lineno = lineno
        self.action = action # "expanded" or "included" depending on context
        self.filename = filename
        self.inner = inner

    def __str__(self):
        return "%s\n  %s from %s (line %d)" % (self.inner, self.action,
                                               self.filename, self.lineno)
    def __repr__(self):
        return self.__str__()

def parse_database_file(path, push_macro_stack=None):
    try:
        with open(path, "r") as f:
            if _ctx is not None:
                _ctx.dependency_callback(path)
            return parse_database(f, push_macro_stack)
    except IOError, r:
        raise DatabaseInnerParseException(path, r)

_ctx = None

def parse_database(fileobj, push_macro_stack=None, initial_context=None):
    """
    Parse a database file and return a list of Comment and Record objects

    Parameters:
    fileobj - file object to parse
    push_macro_stack - if set to a dict, indicates a new local "frame" of macros should be used to parse this file. Any macros in the dict will be added to the new frame.
    """
    global _ctx # non thread-safe parser state
    top_level = _ctx is None
    if top_level:
        _ctx = initial_context if initial_context else ParserContext()
    try:
        if len(_ctx.macro_stack) == 0 and push_macro_stack is None:
            push_macro_stack = {}
        if push_macro_stack is not None:
            new_frame = dict(_ctx.macro_stack[-1]) if len(_ctx.macro_stack) else {}
            new_frame.update(push_macro_stack)
            _ctx.macro_stack.append(new_frame)
        _ctx.filename_stack.append(fileobj.name)
        try:
            nested_result = database_content.parseString(fileobj.read())
        except ParseBaseException, err:
            raise DatabaseInnerParseException(fileobj.name, err)
        # pyparsing produces a nested data structure, flatten it out:
        result = []
        def flatten(r):
            for i in r:
                if isinstance(i, ParseResults) or isinstance(i, list):
                    flatten(i)
                elif i == {}:
                    continue
                else:
                    result.append(i)
        flatten(nested_result)
        return result
    finally:
        if push_macro_stack is not None:
            _ctx.macro_stack.pop()
        _ctx.filename_stack.pop()
        if top_level:
            _ctx = None
