from pyparsing import *
from parserutils import *
import os
import re
import dbparser
import pickle
import traceback

"""
Parsing & validation module for dbd files.
"""

name = Word(alphanums+"_") # valid name format for DBD names (also library symbol names)

## Menu definitions

choice_value = Group( Literal("choice").suppress()
                      - parentheses( comma_delimited(name, dblQuotedString )) )
choice_list = curly_braces( Group( ZeroOrMore(choice_value) ))

menu = Literal("menu").suppress() - parentheses(name) + choice_list
class Menu:
    def __init__(self, name, choices, loc, s):
        self.name = name
        self.choices = choices
        self.lineno = lineno(loc,s)
def _process_menu(s,loc,toks):
    choices = dict([(value.strip('"'),name) for name,value in toks[1]])
    return [ Menu(toks[0], choices, loc, s) ]
menu.setParseAction(_process_menu)


## recordtype definitions

field_param = Group( name - parentheses(dblQuotedString|name) )
field_param_list = Group( curly_braces( ZeroOrMore(field_param) ) )

field_value = ( Literal("field").suppress()
                - parentheses(comma_delimited(name, name))
                + field_param_list )
class Field:
    def __init__(self, name, field_type, params, loc, s):
        self.name = name
        self.field_type = field_type
        self.params = params

    def verify_field(self, record, record_type, value):
        t = self.field_type
        if t == "DBF_STRING":
            return validate_string(self.params, value)
        elif t == "DBF_CHAR":
            return validate_int(value, True, 8)
        elif t == "DBF_UCHAR":
            return validate_int(value, False, 8)
        elif t == "DBF_SHORT":
            return validate_int(value, True, 16)
        elif t == "DBF_USHORT":
            return validate_int(value, False, 16)
        elif t == "DBF_LONG":
            return validate_int(value, True, 32)
        elif t == "DBF_ULONG":
            return validate_int(value, False, 32)
        elif t in ( "DBF_FLOAT", "DBF_DOUBLE" ):
            return validate_double, # ignore precision
        elif t == "DBF_ENUM":
            return validate_enum(record, value)
        elif t == "DBF_MENU":
            return validate_menu(self.params, value)
        elif t == "DBF_DEVICE":
            return validate_device(record, record_type.device_types, value)
        elif t in ("DBF_INLINK", "DBF_OUTLINK", "DBF_FWDLINK"):
            return validate_link(value)
        elif t == "DBF_NOACCESS":
            raise DbdFieldError("Field is type NOACCESS, not settable in database")
        else:
            raise DbdFieldError("Got unexpected field type '%s' for field '%s'" % (t, self.name))

def _process_field(s,loc,toks):
    params = dict([ (name,value) for name,value in toks[2] ])
    return [ Field(toks[0], toks[1], params, loc, s) ]
field_value.setParseAction(_process_field)

field_list = Group( curly_braces( ZeroOrMore(field_value) ))

record_type = Literal("recordtype").suppress() - parentheses(name) + field_list
class RecordType:
    def __init__(self, name, fields, loc, s):
        self.name = name
        self.fields = dict([ (f.name,f) for f in fields ])
        self.device_types = {}
def _process_record_type(s,loc,toks):
    return [ RecordType(toks[0], toks[1], loc, s) ]
record_type.setParseAction(_process_record_type)

device = Literal("device").suppress() - parentheses( comma_delimited(name, name, name, dblQuotedString))
class Device:
    def __init__(self, rec_type, dev_type, dev_name, dev_label):
        self.rec_type = rec_type
        self.dev_type = dev_type
        self.dev_name = dev_name
        self.dev_label = dev_label.strip('"')
def _process_device(s,loc,toks):
    return [ Device(*toks) ]
device.setParseAction(_process_device)

# ignore driver, registrar, function & variable directives, mean nothing here
driver = Literal("driver").suppress() - parentheses(name).suppress()
registrar = Literal("registrar").suppress() - parentheses(name).suppress()
variable = Literal("variable").suppress() - parentheses(comma_delimited(name,name)).suppress()
function = Literal("function").suppress() - parentheses(name).suppress()

dbd_content = ZeroOrMore(menu|record_type|function|device|variable|function|driver|registrar) + StringEnd()

def parse_dbd(dbd_file, dbd_cache_path=None):
    try:
        result = try_read_cache(dbd_file, dbd_cache_path)
        if result:
            return result
        raw = dbd_content.parseString(dbd_file.read())
        # temporary dict to keep track of menu names
        menus = {}
        # result, a dict of record types w/ embedded menus & device types
        record_types = {}
        for item in raw:
            if isinstance(item, Menu):
                menus[item.name] = item
            elif isinstance(item, Device):
                record_types[item.rec_type].device_types[item.dev_label] = item
            elif isinstance(item, RecordType):
                record_types[item.name] = item
                for field in item.fields.values():
                    if "menu" in field.params: # instead of just menu name, also assign actual menu
                        field.params["menu_values"] = menus[field.params["menu"]]
        update_cache(dbd_file, record_types, dbd_cache_path)
        return record_types
    except ParseBaseException as err:
        raise dbparser.DatabaseInnerParseException(dbd_file.name, err)


def try_read_cache(dbd_file, dbd_cache_path):
    """
    Try to read a cached dbd file from the given path,
    return the dbd contents or None if failed or out of date.
    """
    try:
        with open(dbd_cache_path, "rb") as f:
            size,mtime = pickle.load(f)
            stat = os.fstat(dbd_file.fileno())
            if stat.st_size == size and stat.st_mtime == mtime:
                return pickle.load(f)
    except (TypeError, IOError):
        return None # path was null, or file didn't exist was or not readable
    except (EOFError, pickle.PickleError):
        pass # something went wrong while reading the file
    return None

def update_cache(dbd_file, dbd_contents, dbd_cache_path):
    if not dbd_cache_path:
        return
    with open(dbd_cache_path, "wb") as f:
        stat = os.fstat(dbd_file.fileno())
        pickle.dump((stat.st_size,stat.st_mtime), f)
        pickle.dump(dbd_contents, f)


# validation methods

class DbdFieldError(Exception):
    pass

def verify_record(dbd, record, s,loc):
    """
    Verify all fields in record 'record' against dbd 'dbd'

    This is called as part of a pyparsing parse run, so parsing context s & loc are supplied to allow Parser exceptions w/ locations
    """
    try:
        rtype = dbd[record.rtype]
    except KeyError:
        raise ParseFatalException(s,loc,"Record type '%s' not found in dbd" %
                                  self.rtype)
    for name,value in record.fields:
        try:
            rtype.fields[name].verify_field(record, rtype, value)
        except KeyError:
            raise ParseFatalException(s,loc,"Record '%s' - type '%s' does not define a field named '%s'" % (record.name, rtype.name, name))
        except DbdFieldError as err:
            raise ParseFatalException(s,loc,"Record '%s' - invalid field '%s': %s" %
                                      (record.name, name, err))
        except Exception as err:
            traceback.print_exc()
            raise ParseFatalException(s,loc,"Failed to verify field '%s' against dbd: %s" % (name, err))



def validate_string(params, value):
    size = int(params["size"])
    if len(value) > size:
        raise DbdFieldError("Value '%s' exceeds maximum length %d" % (value,size))

def validate_int(value, signed, bits):
    if value == "":
        return # empty string is OK as a standin for zero
    if not re.match("^-?[0-9]*$", value) and not re.match("^-?0x[0-9A-F]*$", value):
        raise DbdFieldError("Numeric value '%s' is not a valid number" % value)
    if value.startswith("-") and not signed:
        raise DbdFieldError("Unsigned field contains a negative number")
    try:
        intval = eval(value)
        if not isinstance(intval, int):
            raise SyntaxError
    except SyntaxError:
        raise DbdFieldError("Numeric value '%s' is not a valid number" % value)
    if not signed and intval >= pow(2,bits):
        raise DbdFieldError("Field value %d overflows %d-bit unsigned field" % (value,
                                                                                  bits))
    if signed and abs(intval) >= pow(2,bits-1):
        raise DbdFieldError("Field value %d overflows %d-bit signed field" % (value, bits))


def validate_double(params, value):
    try:
        float(value)
    except:
        raise DbdFieldError("Field value '%s' is not a valid floating-point number", value)

def validate_enum(record, value):
    if record.rtype in ( "bi", "bo" ) and not value in ["0", "1"]:
        raise DbdFieldError("Field value '%s' is invalid for a boolean enum (valid is 0,1")
    if record.rtype in ( "mbbi", "mbbo" ):
        try:
            intval = int(value)
            if intval < 0:
                raise DbdFieldError("Enum field values cannot be negative")
            number = ['ZRVL', 'ONVL', 'TWVL', 'THVL', 'FRVL', 'FVVL', 'SXVL', 'SVVL', 'EIVL', 'NIVL', 'TEVL', 'ELVL', 'TVVL', 'TTVL', 'FTVL', 'FFVL'][intval]
            matching = [ (name,value) for name,value in record.fields if name == number ]
            if len(matching) == 0:
                raise DbdFieldError("Field value '%s' is invalid, record contains no field '%s'" % (value, number))
        except IndexError:
            raise DbdFieldError("Field value '%s' is out of range for record type %s'" % (value, record.rtype))
        except ValueError:
            raise DbdFieldError("Field value '%s' is not a valid integer" % (value))


def validate_menu(params, value):
    if not "menu" in params:
        raise DbdFieldError("Menu field has no menu definition in dbd file")
    try:
        choices = params["menu_values"].choices
        intval = int(value)
        if intval < 0 or intval >= len(choices):
            raise DbdFieldError("Menu field index '%s' is out of range, menu only has %d choices" % (value, len(choices)))
    except KeyError:
        raise DbdFieldError("Menu field '%s' has no list of valid choices" % params["menu"])
    except ValueError:
        # not a valid integer, try as a string
        if not value in choices:
            raise DbdFieldError("'%s' is not a valid choice for menu %s" % (value, params["menu"]))

def validate_device(record, device_types, value):
    if not value in device_types:
        raise DbdFieldError("'%s' is not a known device type for record type %s" % (value, record.rtype))

def validate_link(value):
    if value.startswith("@"):
        return # TODO: verify @asyn masks look alright
    parts = value.strip().split(" ")
    PROCESS = ( "NPP", "PP", "CA", "CP", "CPP" )
    MAXIMIZE = ( "NMS", "MS" )
    if ( len(parts) == 2 and not parts[1] in PROCESS+MAXIMIZE ) or \
       ( len(parts) == 3 and (not parts[1] in PROCESS and parts[2] in MAXIMIZE) ):
        raise DbdFieldError("'%s' is not a valid link format" % value)
