# This file is part of pyOCCT_binder which automatically generates Python
# bindings to the OpenCASCADE geometry kernel using pybind11.
#
# Copyright (C) 2016-2018  Laughlin Research, LLC
# Copyright (C) 2019 Trevor Laughlin
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
import unittest

from pybinder.core import Generator


class TestBinder(unittest.TestCase):
    """
    Basic tests for pyOCCT_binder.
    """

    @classmethod
    def setUpClass(cls):
        """
        Set up the tests by parsing the header.
        """
        available_mods = {'Test'}
        inc = './include/'
        output_path = './output'
        gen = Generator(available_mods, inc)
        gen.process_config('config.txt')
        gen.parse('all_includes.h')
        gen.dump_diagnostics(1)
        gen.traverse()
        gen.sort_binders()
        gen.build_includes()
        gen.build_imports()
        gen.check_circular()
        gen.bind_templates(output_path)
        gen.bind(output_path)

    def test_compare_output(self):
        with open('output/Test.cxx') as f1:
            with open('expected/Test.cxx') as f2:
                self.assertEqual(len(set(f1).difference(f2)), 0)


if __name__ == '__main__':
    unittest.main()
