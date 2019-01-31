# coding=utf-8

import os
import textwrap
import unittest
from mock import patch, MagicMock
import sys
from conans import tools
from tests.utils.test_cases.conan_client import HookTestCase

here = os.path.dirname(__file__)


@unittest.skipIf('lief' in sys.modules, "Requirement 'lief' is already installed")
class BinaryLinterImportErrorTests(HookTestCase):
    path_to_hook = os.path.join(here, '..', '..', '..', 'hooks', 'binary-linter')

    conanfile = textwrap.dedent("""\
        from conans import ConanFile

        class AConan(ConanFile):
            pass
        """)

    def test_import_error(self):
        tools.save('conanfile.py', content=self.conanfile)
        output = self.conan(['create', '.', 'name/version@jgsogo/test'], expected_return_code=1)
        self.assertIn("No module named 'lief'", output)


class BinaryLinterMockedPackageTests(HookTestCase):
    path_to_hook = os.path.join(here, '..', '..', '..', 'hooks', 'binary-linter')

    conanfile = textwrap.dedent("""\
            from conans import ConanFile

            class AConan(ConanFile):
                pass
            """)

    def test_called(self):
        tools.save('conanfile.py', content=self.conanfile)
        my_lief = MagicMock()
        with patch.dict('sys.modules', {'lief': my_lief}):
            output = self.conan(['create', '.', 'name/version@jgsogo/test'])
        self.assertIn("post_package(): conan binary linter plug-in", output)
        self.assertIn("post_package(): WARN: don't know how to verify for os None, giving up...",
                      output)
