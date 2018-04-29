# This file is part of pyOCCT_binder which provides automatic generation of
# pybind11 binding code for pyOCCT.
#
# Copyright (C) 2016-2018  Laughlin Research, LLC (info@laughlinresearch.com)
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
from bind import BindOCCT

# Initialize the main class containing the core data. Must provide path to the
# libclang Python libraries.
gen = BindOCCT('C:/Users/Trevor/Tools/Development/LLVM/build/bin')

# Specify the configuration file.
gen.process_config('config.txt')

# Add paths to the header files of the relevant libraries.
gen.include_paths.append('C:/Miniconda/envs/occt/Library/include/opencascade')
gen.include_paths.append('C:/Users/Trevor/Work/Products/SMESH/install/include/smesh')
gen.include_paths.append('C:/Users/Trevor/Work/Products/NETGEN/install_/include')
gen.include_paths.append('C:/Miniconda/envs/occt/Library/include')
gen.include_paths.append('C:/Miniconda/envs/occt/Library/include/vtk-7.1')

# Specify the file containing all the relevant header files and parse it.
gen.file = 'all_includes.h'
gen.parse()
gen.dump_diagnostics()

# Save a local copy of the AST so the next time you run the script you can load
# it instead of having to parse everything again. Comment out the above step
# the save comment and uncomment the load command in that scenario.
gen.save('OCCT_720.ast')
# gen.load_ast('OCCT_720.ast')

# Traverse the AST, organizing the cursors into their modules. Provide some
# keywords that will help determine if the found cursor is relevant or not.
gen.traverse('opencascade', 'SMESH')

# The following three steps should be run to finish some organization,
# find all relevant header files for each module, and check for circular
# dependencies. These should be run if you are planning to generate and export
# any binding code, whether it's for all or only a single module.
# gen.populate_includes()
# gen.build_aliases()
# gen.check_circular()

# Generate binding code for all modules. This should be used with caution since
# it could overwrite a large number of existing files.
# gen.generate('./src')

# Generate binding code for a list of modules. Use this for "one-off" module
# generation.
# mods = ['StdMeshers']
# for mod in mods:
#     mod = gen.get_module(mod)
#     mod.generate('./src')

# Generate binding text for a single cursor.
# from bind import Binder
#
# c = gen.get_cursor('StdMeshers_FaceSide')
# b = Binder(c)
# b.generate()
# fout = open('bind.cpp', 'w')
# fout.write(b.txt)
# fout.close()
