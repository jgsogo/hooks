# coding=utf-8

import os
import sys
import unittest

from mock import patch, MagicMock


class BinaryLinterTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        hook_basename, _ = os.path.splitext('binary-linter.py')
        here = os.path.dirname(__file__)
        hook_path = os.path.normpath(os.path.join(here, '..', '..', '..', 'hooks'))

        old_write_bytecode = sys.dont_write_bytecode
        sys.path.insert(0, hook_path)
        try:
            sys.dont_write_bytecode = True
            my_lief = MagicMock()
            with patch.dict('sys.modules', {'lief': my_lief}):
                loaded = __import__(hook_basename)
            cls.BinaryLinter = loaded.BinaryLinter
        finally:
            sys.dont_write_bytecode = old_write_bytecode
            sys.path.pop(0)

    def setUp(self):
        conanfile = MagicMock()
        conanfile_path = "aaa"
        output = MagicMock()
        self.binary_linter = self.BinaryLinter(output, conanfile, conanfile_path)

    @unittest.expectedFailure
    def tests_aaa(self):
        self.binary_linter.verify()
        self.fail("AAAA")
