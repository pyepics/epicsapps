# Parser utility functions
from pyparsing import Literal, Optional

def enclose(x,start,end):
    start = Literal(start).suppress()
    end = Literal(end).suppress()
    #start.setDebug(True)
    #end.setDebug(True)
    return start + x + end

def parentheses(x):
    return enclose(x,"(",")")

def curly_braces(x):
    return enclose(x,"{","}")

def quoted(x):
    return enclose(x,'"','"')

def optionally_quoted(x):
    return Optional(Literal('"')).suppress() + x + Optional(Literal('"')).suppress()

def comma_delimited(*xs):
    """ Return each parser item given in arguments, joined by suppressed commas """
    result = xs[0]
    for x in xs[1:]:
        result += Literal(",").suppress()
        result += x
    return result
