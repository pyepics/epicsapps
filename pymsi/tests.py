#!/usr/bin/env python
import unittest
from dbparser import parse_database_file, Record, DatabaseParseException
from pyparsing import ParseSyntaxException, ParseFatalException

def _extract_records(result):
    return [ r for r in result if isinstance(r,Record) ]

class ParserTests(unittest.TestCase):

    def _assert_simple_db_properties(self, result):
        last = _extract_records(result)[-1]
        self.assertEqual(last.name, "linec:ladder:positions")
        self.assertEqual(last.rtype, "waveform")
        self.assertEqual(last.lineno, 45)
        self.assertTrue(last.filename.endswith("testdata/simple.db"), "Record filename %s should end with testdata/simple.db"%last.filename)

    def test_simple_parse(self):
        result = parse_database_file("testdata/simple.db")
        self.assertGreater(len(result), 0)
        self._assert_simple_db_properties(result)

    def test_simple_include(self):
        result = parse_database_file("testdata/simple_include.sdb")
        self.assertGreater(len(result), 0)
        self._assert_simple_db_properties(result)

    def test_simple_substitute(self):
        records = _extract_records(parse_database_file("testdata/simple_substitute.sdb"))
        self.assertEqual(len(records), 4)
        self.assertEqual(records[0].name, "name_a")
        self.assertEqual(records[3].name, "subst_name")
        self.assertTrue(("FLNK", "subst_flnk") in records[3].fields)
        self.assertTrue(("DRVH", "subst_drvh") in records[3].fields)

    def test_simple_expand(self):
        records = _extract_records(parse_database_file("testdata/simple_expand.sdb"))
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec.name, "expand_name")
        self.assertTrue(("FLNK", "expand_flnk PP") in rec.fields)
        self.assertTrue(("DRVH", "expand_drvh") in rec.fields)
        self.assertEquals(3, rec.lineno)
        self.assertTrue(rec.filename.endswith("simple.sdb"), "Record filename %s should end with simple.sdb" % rec.filename)

    def test_field_error(self):
        with self.assertRaises(DatabaseParseException) as ctx:
            parse_database_file("testdata/has_field_error.db")
        self.assertIsInstance(ctx.exception.inner, ParseSyntaxException)
        self.assertEquals(5, ctx.exception.inner.lineno)

    def test_record_error(self):
        with self.assertRaises(DatabaseParseException) as ctx:
            parse_database_file("testdata/has_record_error.db")
        self.assertIsInstance(ctx.exception.inner, ParseSyntaxException)
        self.assertEquals(3, ctx.exception.inner.lineno)

    def test_missing_macro_error(self):
        with self.assertRaises(DatabaseParseException) as ctx:
            parse_database_file("testdata/has_missing_macro_error.db")
        self.assertIsInstance(ctx.exception.inner, ParseFatalException)
        self.assertEquals(7, ctx.exception.inner.lineno)
        self.assertTrue("idontexist" in str(ctx.exception), "Error message '%s' should mention macro 'idontexist'" % ctx.exception)

    def test_invalid_macro_error(self):
        with self.assertRaises(DatabaseParseException) as ctx:
            parse_database_file("testdata/has_invalid_macro_error.db")
        self.assertIsInstance(ctx.exception.inner, ParseSyntaxException)
        self.assertEquals(6, ctx.exception.inner.lineno)

    def test_nested_error(self):
        with self.assertRaises(DatabaseParseException) as ctx:
            parse_database_file("testdata/parent_of_record_error.sdb")
        self.assertEquals(5, ctx.exception.lineno)
        self.assertIsInstance(ctx.exception.inner, DatabaseParseException)
        self.assertIsInstance(ctx.exception.inner.inner, ParseSyntaxException)
        self.assertEquals(3, ctx.exception.inner.inner.lineno)
        self.assertTrue("parent_of_record_error.sdb" in str(ctx.exception), "Parser error '%s' should mention outer filename" % ctx.exception)
        self.assertTrue("has_record_error.db" in str(ctx.exception), "Parser error '%s' should also mention inner filename" % ctx.exception)

    def test_dup_field(self):
        with self.assertRaises(DatabaseParseException) as ctx:
            parse_database_file("testdata/duplicatefield.db")
        self.assertEquals(4, ctx.exception.inner.lineno) # line number is record not field, due to parser limitation
        self.assertTrue("duplicate field" in str(ctx.exception).lower(), "Parser error '%s' should mention a duplicate field" % ctx.exception)
        self.assertTrue("DRVL" in str(ctx.exception), "Parser error '%s' should mention field name DRVL" % ctx.exception)

    def test_scope_isolation(self):
        """ A macro set at one level should not be able to be changed by a lower-level included database """
        records = _extract_records(parse_database_file("testdata/limited_scope_parent.sdb"))
        names = [r.name for r in records]
        self.assertEquals(names, [ "parent_name", "child_name_a", "child_name_b", "parent_name" ],
                          "Records (%s) should have names set by macros as per the commends in limited_scope_parent.sdb & limited_scope_child.sdb" % (names))

    def test_nested_scope_passthrough(self):
        """ If you set a macro when expanding at the top level, then expand() a database that expands() another database, the macro should still be visible in the grandchild """
        records = _extract_records(parse_database_file("testdata/nested_scope_1.sdb"))
        self.assertEquals(1, len(records))
        self.assertEquals(records[0].name, "toplevel_name")

    def test_default_values_macros(self):
        """
        When expanding a macro value you can specify a default value to use if the macro is not defined
        """
        records = _extract_records(parse_database_file("testdata/default_expand.sdb"))
        self.assertEquals(4, len(records))
        self.assertEquals(records[0].name, "default name")
        self.assertEquals(records[1].name, "some other name")
        self.assertEquals(records[2].name, "yet another name")
        self.assertEquals(records[3].name, "not just yet another name, is it?")


if __name__ == '__main__':
    unittest.main()
