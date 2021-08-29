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
import os
import sys
import shutil
import unittest
import subprocess

from pybinder.core import Generator


def run(*args, **kwargs):
    """
    Run a command and print the output
    """
    output = subprocess.check_output(*args, **kwargs).decode()
    for line in output.split('\n'):
        print(line)
    return output


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
        all_includes = os.listdir('./include/')
        main_includes = ['./include/']
        output_path = './output'
        gen = Generator('Test', {'Test': available_mods}, all_includes, main_includes)
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
        for filename in ('Test.cxx', 'bind_Test_Template.hxx'):
            with open(f'output/{filename}') as f1:
                with open(f'expected/{filename}') as f2:
                    for l1, l2 in zip(f1, f2):
                        self.assertEqual(l1, l2)

    def test_compile(self):
        shutil.rmtree('build', ignore_errors=True)
        os.makedirs('build')
        output = run('cmake ../'.split(), cwd='build')
        self.assertIn('Configuring done', output)
        self.assertIn('Generating done', output)
        output = run('make', cwd='build')
        self.assertIn('Built target pyBinderTest', output)


if __name__ == '__main__':
    unittest.main()
