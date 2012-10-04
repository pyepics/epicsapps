#!/usr/bin/env python
"""
pymsi is a powerful python-based alternative to the msi macro substitution tool. Some features were inspired by the VisualDCT macro substitution tool.

See the documentation page, under epicsapps/doc/pymsi.rst, for more information.
"""
import sys
import os
import argparse

import dbparser
import dbdparser

parser = argparse.ArgumentParser(description='Expand macros in an EPICS database template file.')
parser.add_argument('-o', '--output', help='Output result to file (optional, stdout will be used otherwise.)',
                    type=argparse.FileType('w'), default=sys.stdout)
parser.add_argument('--dbd', help='Verify database output against specified DBD file.',
                    type=argparse.FileType('r'))
parser.add_argument('--dbd-cache', help="Optional cache file to read/write parsed DBD data. Can save time if you're building a lot of databases and verifying against the same DBD file")
parser.add_argument('-I', '--include', help='Specify paths to search for included/expanded files (can be repeated, or paths can be colon-delimited.)',
                    action='append')
parser.add_argument('-m', '--allow-missing', help="Do not error out if a macro is missing, just expand to an empty value (this is the default msi behaviour, but not the pymsi default.)",
                    action='store_true')
parser.add_argument('-v', '--verbose', help="Produce verbose parsing output on stderr.",
                    action='store_true')
parser.add_argument('-s', '--strip-comments', help="Strip input file comments from the output.",
                    action='store_true')
group = parser.add_mutually_exclusive_group()
group.add_argument('-MF', help="Output automatic dependency makefile to file path (same as gcc -MF flag.)")
group.add_argument('-MD', help="Output automatic dependency makefile as <inputfilename>.d (same as gcc -MD flag.)", action='store_true')

parser.add_argument('input', help="Template file to read for expansion (optional, stdin will be used otherwise.)",
                    nargs='?', type=argparse.FileType('r'), default=sys.stdin)



def print_stderr(message):
    sys.stderr.write("%s\n" % message)

def output_dependencies(args):
    """
    Output a .d makefile of dependencies if requested

    (If the parse failed with an error, the dependency file will include all dependencies up until the error.)
    """
    if args.MF:
        if args.verbose:
            sys.stderr.write("Writing dependencies to %s:\n%s", (args.MF,dependencies))
        def rel(path):
            return os.path.relpath(path)
        with open(args.MF, "w") as df:
            df.write("%s:" % rel(args.output.name))
            for dep in dependencies:
                df.write(" %s" % rel(dep))
            df.write("\n")

if __name__ == "__main__":
    args = parser.parse_args()
    if not args.include:
        args.include = ["."]
    else:
        args.include = [ y for x in args.include for y in x.split(":") ]

    if (args.MD or args.MF) and args.output == sys.stdout:
        print("Cannot use the -MD or -MF options when sending output to stdout.")
        sys.exit(1)
    if args.MD:
        args.MF = os.path.splitext(args.input.name)[0] + ".d"
    dependencies = set()
    if args.input != sys.stdin:
        dependencies.add(args.input.name)

    try:
        context = dbparser.ParserContext()
        context.dbd = None
        if args.dbd is not None:
            dbd =  dbdparser.parse_dbd(args.dbd, args.dbd_cache)
            context.verify_record_fn = lambda *args: dbdparser.verify_record(dbd, *args)
        context.include_paths = args.include
        if args.verbose:
            context.verbose_fn = print_stderr
        context.allow_missing = args.allow_missing
        context.strip_comments = args.strip_comments
        context.dependency_callback = lambda filename: dependencies.add(filename)
        results = dbparser.parse_database(args.input, initial_context=context)

        for c in results:
            args.output.write(c.to_database())
    except dbparser.DatabaseParseException as err:
        print_stderr(err)
        output_dependencies(args)
        sys.exit(2)

    output_dependencies(args)
