# TODO Use list concatenation to build final string rather than +=
# This file is part of binderOCCT which provides automatic generation of
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
"""
KNOWN ISSUES:

- How to handle/determine C++ modifying Python immutable types?

- Returning raw pointer (TColStd_DataMapOfIntegerTransient::Bound)

- Support for nested types

- Binding data members (fields)

- Don't add base class if not registered

- "typedef opencascade::handle<> Alias" is treated as unique_ptr holder type (QuadBvhHandle, IntSurf_Allocator)

"""
from __future__ import print_function

import os
import re
from collections import OrderedDict, defaultdict
from ctypes import c_uint
from pprint import pprint

import cymbal
from clang.cindex import (AccessSpecifier, Config, Cursor, CursorKind, Index, TranslationUnit, Type,
                          TypeKind)

# Configuration data
_module_comments = defaultdict(list)
_excluded_modules = set()
_extra_headers = defaultdict(list)
_excluded_functions = set()
_excluded_classes = set()
_sort_priotiry = {}
_import_guards = defaultdict(set)
_call_guards = defaultdict(set)
_python_names = {}
_immutable_types = set()
_no_inout = set()
_no_delete = set()

# Keep track of canonical types to make sure they are only registered once. If a type is already
# registered, use this data to assign a module attribute rather than register a new type. For this
# dictionary, the key will be the name of the canonical type and the value will be the name of the
# first registration.
_canonical_types = OrderedDict()
_all_mods = OrderedDict()

# Set of all available header files
_available_header_files = set()

# Available templates
_available_templates = set()

fwarn = open('warnings.txt', 'w')

# C++ to Python operators
_py_operators = {
    'operator+': '__add__',
    'operator-': '__sub__',
    'operator/': '__truediv__',
    'operator*': '__mul__',

    'operator+=': '__iadd__',
    'operator-=': '__isub__',
    'operator/=': '__itruediv__',
    'operator*=': '__imul__',

    'operator=': 'assign',
    'operator==': '__eq__',
    'operator()': '__call__',
    'operator!=': '__ne__',
    'operator[]': '__getitem__',
    'operator++': 'plus_plus',
    'operator--': 'minus_minus',
    'operator<': '__lt__',
    'operator<=': '__le__',
    'operator>': '__gt__',
    'operator>=': '__ge__',
    'operator>>': 'bits_right',
    'operator<<': 'bits_left'
}


class BindOCCT(object):
    """
    Main binding generation class for OCCT.

    :param str libclang_path: Path to libclang library.

    :var clang.cindex.Index index: The Index instance.
    :var str file: The main file to parse.
    :var list[str] include_paths: Include paths.
    :var clang.index.TranslationUnit translation_unit: The translation unit.
    """
    file = 'all_includes.h'
    include_paths = []
    tu = None
    _modules = {}

    def __init__(self, libclang_path):
        Config.set_library_path(libclang_path)
        self.index = Index.create()

        # Default patches
        # Patches for extra libclang methods
        self.add_type_patch('get_template_argument_type',
                            'clang_Type_getTemplateArgumentAsType',
                            [Type, c_uint],
                            Type)

        self.add_type_patch('get_num_template_arguments',
                            'clang_Type_getNumTemplateArguments',
                            [Type],
                            c_uint)

        self.add_cursor_patch('get_specialization',
                              'clang_getSpecializedCursorTemplate',
                              [Cursor],
                              Cursor)

        self.add_cursor_patch('get_template_kind',
                              'clang_getTemplateCursorKind',
                              [Cursor],
                              c_uint)

        self.add_cursor_patch('get_num_overloaded_decl',
                              'clang_getNumOverloadedDecls',
                              [Cursor],
                              c_uint)

        self.add_cursor_patch('get_overloaded_decl',
                              'clang_getOverloadedDecl',
                              [Cursor, c_uint],
                              Cursor)

    @property
    def modules(self):
        """
        :return: List of all modules.
        :rtype: list[Module]
        """
        return self._modules.values()

    @staticmethod
    def add_cursor_patch(method_name, clang_method, args, result):
        """
        Add a cursor patch to libclang using cymbal.

        :param method_name:
        :param clang_method:
        :param args:
        :param result:

        :return: None
        """

        cymbal.monkeypatch_cursor(method_name, clang_method, args, result)

    @staticmethod
    def add_type_patch(method_name, clang_method, args, result):
        """
        Add a type patch to libclang using cymbal.

        :param method_name:
        :param clang_method:
        :param args:
        :param result:

        :return: None.
        """

        cymbal.monkeypatch_type(method_name, clang_method, args, result)

    @staticmethod
    def process_config(fn):
        """
        Process a configuration file.

        :param str fn: The filename.

        :return: None.
        """
        process_config(fn)

    def parse(self):
        """
        Parse the main file.

        :return: None
        """
        args = [
            '-x',
            'c++',
            '-std=c++14',
            '-DNo_Exception',
            '-DNDEBUG',
            '-fms-compatibility-version=19'
        ]
        for path in self.include_paths:
            args += [''.join(['-I', path])]

        print('Parsing headers...')
        BindOCCT.tu = self.index.parse(self.file, args, options=TranslationUnit.PARSE_INCOMPLETE)
        print('done.\n\n')

    def save(self, fname):
        """
        Save the TranslationUnit to a file.

        :param str fname: The filename.

        :return: None.
        """
        BindOCCT.tu.save(fname)

    def load_ast(self, fname):
        """
        Load a TranslationUnit from a saved AST file.

        :param str fname: The filename.

        :return: None.
        """
        BindOCCT.tu = TranslationUnit.from_ast_file(fname, self.index)

    def traverse(self, *location_keys):
        """
        Traverse the AST and collect the binders.

        :param collections.Sequence(str) location_keys: Key(s) to filter binders originating from source path(s) that
            contain the key. If the key is not present in the source path of the binder then it is rejected.
        """

        print('Traversing AST...')

        for c in BindOCCT.tu.cursor.get_children():
            # Skip if binder not located in OCCT include directory
            has_key = False
            try:
                loc = c.location.file.name
                for key in location_keys:
                    if key in loc:
                        has_key = True
                        break
            except AttributeError:
                continue
            if not has_key:
                continue

            # Generate binder if a supported type is encountered
            if c.kind in [CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL,
                          CursorKind.FUNCTION_DECL,
                          CursorKind.ENUM_DECL,
                          CursorKind.TYPEDEF_DECL,
                          CursorKind.CLASS_TEMPLATE]:
                binder = Binder(c)

                if not binder.is_handle and 'Handle_' not in binder.dname:
                    mod_name = get_module_name_from_binder(binder)
                    mod = self.get_module(mod_name)
                    _all_mods[mod_name] = mod
                    # Sort where binders go based on module name
                    mod.add_binder(binder.qname, binder)
                    # Add to available templates
                    if c.kind == CursorKind.CLASS_TEMPLATE:
                        _available_templates.add(c.spelling)

        print('done.\n')

    def get_module(self, name):
        """
        Get a module by spelling. If the spelling doesn't exist a new module will be
        returned.

        :return: The module.
        :rtype: Module
        """
        # Return existing
        if name in self._modules:
            return self._modules[name]

        # Create new one
        mod = Module(name)
        self._modules[name] = mod
        return mod

    def populate_includes(self):
        """
        Populate all the modules with relevant include files and import modules.
        """
        print('Populating includes...')

        # Get files
        for path in self.include_paths:
            items = set(os.listdir(path))
            _available_header_files.update(items)

        for mod in self.modules:
            for b in mod.binders:
                b.relevant_includes(mod)
        print('done.')

    def build_aliases(self):
        """
        Gather all binders and build initial aliases.

        :return:
        """
        print('Creating initial aliases...')
        # Sort modules alphabetically
        mods = []
        for mod in self.modules:
            mods.append((mod.name, mod))
        mods.sort()
        mods = [m[1] for m in mods]

        # Swap any modules based on sort priority
        for name in _sort_priotiry:
            loc = _sort_priotiry[name]
            mod = self.get_module(name)
            i = mods.index(mod)
            mods[loc], mods[i] = mods[i], mods[loc]

        # Gather all binders and sort by spelling
        binders = []
        for mod in mods:
            for binder in mod.binders:
                if not binder.is_typedef:
                    continue
                binders.append(binder)

        for b in binders:
            type_ = b.cursor.type
            if is_type_pointer(type_):
                type_ = type_.get_pointee()
            ctype_ = type_.get_canonical()
            if ctype_.spelling in _canonical_types:
                b.alias = _canonical_types[ctype_.spelling]
            else:
                _canonical_types[ctype_.spelling] = b
        print('done.\n')

        print('Checking direction of aliased types...')
        for binder in binders:
            if not binder.is_typedef:
                continue
            if binder.alias is None:
                continue

            # Check dependency between the two modules. If the imported module is dependent on
            # this one, swap the aliases.
            dmod = _all_mods[binder.alias.module_name]
            imod = _all_mods[binder.module_name]
            try:
                if is_mod_dependent(dmod, imod):
                    binder.alias.alias = binder
                    binder.alias = None
            except RuntimeError:
                print('\tFound circular imports: {}<-->{}'.format(dmod.name, imod.name))
        print('done.\n')

    def check_circular(self):
        """
        Check for circular imports.

        :return:
        """
        mods = self.modules
        for i, mod1 in enumerate(mods):
            for mod2 in mods[i + 1:-1]:
                if mod1.name in mod2.import_mods and mod2.name in mod1.import_mods:
                    print('Found circular import: {} <--> {}'.format(mod1.name, mod2.name))

    def generate_templates(self, path='./inc'):
        """
        Generate binding templates.

        :param str path: The folder where the source files will be created.

        :return: None.
        """
        raise RuntimeError("Are you sure you want to do this?!?")
        print('Binding templates...')
        for mod in self.modules:
            mod.generate_templates(path)
        print('done.')

    def generate(self, path='./src'):
        """
        Generate the binding sources for all modules.

        :param str path: The folder where the source files will be created.

        :return: None.
        """
        raise RuntimeError("Are you sure you want to do this?!?")
        print('Binding modules...')
        nmod = len(self.modules)
        i = 1
        for mod in self.modules:
            if mod.name in _excluded_modules:
                print('\tSkipping module {}'.format(mod.name))
                continue

            print('\t{} ({} of {})'.format(mod.name, i, nmod))
            mod.generate(path)
            i += 1

    def get_cursors(self, spelling, kind=None):
        """
        Get a list of cursors in the translation unit.

        :param spelling:
        :param kind:

        :return:
        """
        return get_cursors(BindOCCT.tu, spelling, kind)

    def get_cursor(self, spelling):
        """
        Get a cursor in the translation unit.

        :param spelling:

        :return:
        """
        return get_cursor(BindOCCT.tu, spelling)

    def dump_cursor(self, spelling, max_depth=0, kind=None):
        """
        Dump cursor information to the screen.

        :param spelling:
        :param max_depth:
        :param kind:

        :return:
        """
        for c in self.get_cursors(spelling, kind):
            dump_cursor(c, max_depth)

    def dump_diagnostics(self):
        """
        Show diagnostics.

        :return: None.
        """
        dump_diag_info(BindOCCT.tu)

    def export_modules(self, fn):
        """
        Export the module names to a text file.

        :param str fn: The filename.
        """
        mods = [mod.name + '\n' for mod in self.modules]
        mods.sort()
        fout = open(fn, 'w')
        fout.writelines(mods)


class Module(object):
    """
    OCCT module.

    :param str name: The module spelling.

    :var list[str] include_files: The relevant include files for this module
        that will be exported to the source files.
    :var list[str] import_mods: List of modules that will be imported by this module.
    """
    _mods = {}

    def __init__(self, name):
        self.name = name

        self._binders = OrderedDict()
        self.include_files = []
        self.import_mods = []
        self._enums = []
        self._funcs = []
        self._classes = []
        self._typedefs = []

    @property
    def binders(self):
        """
        :return: List of all binders.
        :rtype: list[Binder]
        """
        return self._binders.values()

    @property
    def enum_binders(self):
        """
        :return: List of all enum binders.
        :rtype: list[Binder]
        """
        return self._enums

    @property
    def function_binders(self):
        """
        :return: List of all function binders.
        :rtype: list[Binder]
        """
        return self._funcs

    @property
    def class_binders(self):
        """
        :return: List of all class binders.
        :rtype: list[Binder]
        """
        return self._classes

    @property
    def typedef_binders(self):
        """
        :return: List of all typedef binders.
        :rtype: list[Binder]
        """
        return self._typedefs

    def add_binder(self, name, binder):
        """
        Add a binder to the module by spelling. Will overwrite existing spelling.

        :param str name: The spelling.
        :param Binder binder: The binder.

        :return: None.
        """
        self._binders[name] = binder

    def get_binder(self, name):
        """
        Get a binder by its key name.

        :param str name: The name.

        :return: The binder.
        :rtype: Binder
        """
        return self._binders[name]

    def add_include_file(self, name, add_import=True):
        """
        Add a relevant include file to the module.

        :param str name: The name of the file.
        :param bool add_import: Resolve module name and add as relative import.

        :return: None.
        """
        if not name:
            return None

        # Don't include anything that doesn't end in .h*
        if '.h' not in name:
            return None

        if name not in _available_header_files:
            return None

        if name not in self.include_files:
            self.include_files.append(name)

            if add_import:
                mod_name = get_module_name_from_str(name)
                self.add_import_module(mod_name)

    def add_import_module(self, mod):
        """
        Add a module to import in this module.

        :param str mod: The module.

        :return: None.
        """
        if mod in _excluded_modules:
            return None

        if self.name == 'Standard' and mod != 'Standard':
            fwarn.write('Nothing should go in Standard. Tried to add {}\n'.format(mod))
            return None

        if mod == self.name:
            return None

        if mod in _import_guards[self.name]:
            return None

        if mod not in _all_mods:
            return None

        if mod not in self.import_mods:
            self.import_mods.append(mod)

    def group_binders(self):
        """
        Group binders into lists for enums, functions, classes, and typedef's.

        :return: None.
        """
        for b in self.binders:
            if b.is_enum:
                self._enums.append(b)
            elif b.is_function:
                self._funcs.append(b)
            elif b.is_class:
                self._classes.append(b)
            elif b.is_typedef:
                self._typedefs.append(b)

    def generate_templates(self, path='./inc'):
        """
        Generate binding templates.

        :param str path: The folder where the source files will be created.

        :return: None.
        """
        class_templates = []
        for b in self.binders:
            if b.is_class_template:
                class_templates.append((b.dname, b))

        if not class_templates:
            return None

        class_templates.sort()

        # Open the file
        fname = '/'.join([path, self.name + '_Templates.hpp'])
        fout = open(fname, 'w')

        # Header guard
        fout.write('#ifndef __{}_Templates_Header__\n'.format(self.name))
        fout.write('#define __{}_Templates_Header__\n\n'.format(self.name))

        # Include common
        fout.write('#include <pyOCCT_Common.hpp>\n\n')

        # Get include file of each template
        all_includes = set()
        for _, b in class_templates:
            include_files = relevant_includes_of_template(b.cursor)
            for f in include_files:
                if f in all_includes:
                    continue

                # Don't include anything that doesn't end in .h*
                if '.h' not in f:
                    continue

                if f not in _available_header_files:
                    continue

                fout.write('#include <{}>\n'.format(f))
                all_includes.add(f)

        fout.write('\n')

        # Write bindings
        for _, b in class_templates:
            generate_class_template(b)
            txt = b.txt
            if not txt:
                continue
            fout.write(txt)

        fout.write('#endif')
        fout.close()

    def generate(self, path='./src'):
        """
        Generate the source file for the module.

        :param str path: The folder where the source file will be created.

        :return: None.
        """
        # Group the binders
        self.group_binders()

        # Open the file
        fname = '/'.join([path, self.name + '.cpp'])
        fout = open(fname, 'w')

        # Write comments
        if self.name in _module_comments:
            comments = _module_comments[self.name]
            for comment in comments:
                fout.write('// {}\n'.format(comment))

        # Include common
        fout.write('#include <pyOCCT_Common.hpp>\n\n')

        # Add extra include files
        if self.name in _extra_headers:
            for header in _extra_headers[self.name]:
                fout.write('#include <{}>\n'.format(header))
            fout.write('\n')

        # Add relevant includes
        for inc in self.include_files:
            fout.write('#include <{}>\n'.format(inc))

        # Includes for binding templates
        template_includes = []
        for binder in self.typedef_binders:
            tname = binder.tname
            if not tname:
                continue
            if tname not in _available_templates:
                continue
            t = tname.split('_')[0]
            inc_file = '{}_Templates.hpp'.format(t)
            if inc_file not in template_includes:
                fout.write('#include <{}>\n'.format(inc_file))
                template_includes.append(inc_file)

        # Module initialization
        fout.write('\nPYBIND11_MODULE({}, mod) {{\n\n'.format(self.name))

        if self.name in _excluded_modules:
            # End module
            fout.write('}\n')
            fout.close()
            return None

        # Import other modules
        fout.write('\t// IMPORT\n')
        for mod_name in self.import_mods:
            if mod_name != self.name:
                fout.write('\tpy::module::import(\"OCCT.{}\");\n'.format(mod_name))
        fout.write('\n')

        # Module in case dynamic attribute is set
        fout.write('\tpy::module other_mod;\n\n')

        # Call guards to resolve circular imports
        fout.write('\t// IMPORT GUARDS\n')
        for mod_name in _import_guards[self.name]:
            fout.write('\tstruct Import{}{{\n'.format(mod_name))
            fout.write('\t\tImport{}() {{ py::module::import(\"OCCT.{}\"); }}\n'.format(mod_name,
                                                                                        mod_name))
            fout.write('\t};\n\n')
        fout.write('\n')

        # Export bindings by enums, functions, and then classes
        fout.write('\t// ENUMS\n')
        for b in self.enum_binders:
            b.generate()
            fixme, txt = b.fixme, b.txt
            if fixme and txt:
                txt = add_class_fixme_txt(txt)
            fout.write(txt)
        fout.write('\n')

        fout.write('\t// FUNCTIONS\n')
        for b in self.function_binders:
            b.generate()
            fixme, txt = b.fixme, b.txt
            if fixme and txt:
                txt = add_class_fixme_txt(txt)
            fout.write(txt)
        fout.write('\n')

        fout.write('\t// CLASSES\n')
        # Combine classes and typedefs of classes
        all_classes = self.class_binders + self.typedef_binders
        sort_class_binders(all_classes)
        for b in all_classes:
            # txt = r'cout << "Importing {}\n";{}'.format(b.qname, '\n')
            # fout.write(txt)
            b.generate()
            fixme, txt = b.fixme, b.txt
            if fixme or (not txt and b.alias is None):
                txt = add_class_fixme_txt(txt)
                txt += '\n'
            fout.write(txt)
        fout.write('\n')

        # fout.write('\t// TYPEDEFS\n')
        # for b in self.typedef_binders:
        #     txt = b.generate()
        #     fout.write(txt)
        # fout.write('\n')

        # End module
        fout.write('}\n')
        fout.close()


class Binder(object):
    """
    Base class for all binders.

    :param clang.cindex.Cursor cursor: The cursor.

    :var clang.cindex.Cursor cursor: The cursor.
    :var str txt: The binding text.
    :var bool fixme: Fixme flag.
    :var str parent: The name of the parent binder (default='mod').
    """

    def __init__(self, cursor):
        self.alias = None
        self.txt = ''
        self.fixme = False
        self.binding_parent = 'mod'
        self.parent_override = None
        self.pname_override = ''
        self.is_nested = False

        self._cursor = cursor

        # Work around for forward declarations of types
        if self.is_class or self.is_typedef or self.is_class_template:
            c = self.cursor.get_definition()
            if c:
                self._cursor = c

    @property
    def is_none(self):
        return self._cursor is None

    @property
    def cursor(self):
        """
        :return: The cursor.
        :rtype: clang.cindex.Cursor
        """
        return self._cursor

    @property
    def kind(self):
        """
        :return: The cursor kind.
        :rtype: clang.cindex.CursorKind
        """
        return self.cursor.kind

    @property
    def type(self):
        """
        :return: The type.
        :rtype: clang.cindex.Type
        """
        return self.cursor.type

    @property
    def rtype(self):
        """
        :return: The type of the result.
        :rtype: clang.cindex.Type
        """
        return self.cursor.result_type

    @property
    def underlying_typedef_type(self):
        """
        :return: The underlying type.
        :rtype: clang.cindex.Type
        """
        return self.cursor.underlying_typedef_type

    @property
    def pointee(self):
        """
        :return: The type pointed to.
        :rtype: clang.cindex.Type
        """
        if not self.is_pointer_like:
            return self.type
        return self.type.get_pointee()

    @property
    def location(self):
        """
        :return: The file name of the binder.
        :rtype: str
        """
        return self.cursor.location.file.name

    @property
    def is_definition(self):
        return self.cursor.is_definition()

    @property
    def no_decl(self):
        return self.cursor.kind == CursorKind.NO_DECL_FOUND

    @property
    def is_tu(self):
        return self.cursor.kind == CursorKind.TRANSLATION_UNIT

    @property
    def is_enum(self):
        return self.cursor.kind == CursorKind.ENUM_DECL

    @property
    def is_function(self):
        return self.cursor.kind == CursorKind.FUNCTION_DECL

    @property
    def is_class(self):
        return self.cursor.kind in [CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL]

    @property
    def is_typedef(self):
        return self.cursor.kind == CursorKind.TYPEDEF_DECL

    @property
    def is_cxx_base(self):
        return self.cursor.kind == CursorKind.CXX_BASE_SPECIFIER

    @property
    def is_constructor(self):
        return self.cursor.kind == CursorKind.CONSTRUCTOR

    @property
    def is_destructor(self):
        return self.cursor.kind == CursorKind.DESTRUCTOR

    @property
    def is_cxx_method(self):
        return self.cursor.kind == CursorKind.CXX_METHOD

    @property
    def is_param(self):
        return self.cursor.kind == CursorKind.PARM_DECL

    @property
    def is_template_ref(self):
        return self.cursor.kind == CursorKind.TEMPLATE_REF

    @property
    def is_class_template(self):
        return self.cursor.kind == CursorKind.CLASS_TEMPLATE

    @property
    def is_function_template(self):
        return self.cursor.kind == CursorKind.FUNCTION_TEMPLATE

    @property
    def is_template_type_param(self):
        return self.cursor.kind == CursorKind.TEMPLATE_TYPE_PARAMETER

    @property
    def is_using_decl(self):
        return self.cursor.kind == CursorKind.USING_DECLARATION

    @property
    def is_overloaded_decl_ref(self):
        return self.cursor.kind == CursorKind.OVERLOADED_DECL_REF

    @property
    def is_cxx_access_spec(self):
        return self.cursor.kind == CursorKind.CXX_ACCESS_SPEC_DECL

    @property
    def is_enum_constant(self):
        return self.cursor.kind == CursorKind.ENUM_CONSTANT_DECL

    @property
    def is_public(self):
        return not self.is_private and not self.is_protected

    @property
    def is_private(self):
        return self.cursor.access_specifier == AccessSpecifier.PRIVATE

    @property
    def is_protected(self):
        return self.cursor.access_specifier == AccessSpecifier.PROTECTED

    @property
    def is_pointer(self):
        return self.cursor.type.kind == TypeKind.POINTER

    @property
    def is_lvalue(self):
        return self.cursor.type.kind == TypeKind.LVALUEREFERENCE

    @property
    def is_rvalue(self):
        return self.cursor.type.kind == TypeKind.RVALUEREFERENCE

    @property
    def is_pointer_like(self):
        return self.is_pointer or self.is_lvalue or self.is_rvalue

    @property
    def is_definition(self):
        return self.cursor.is_definition()

    @property
    def is_virtual_method(self):
        return self.cursor.is_virtual_method()

    @property
    def is_pure_virtual_method(self):
        return self.cursor.is_pure_virtual_method()

    @property
    def is_const_method(self):
        return self.cursor.is_const_method()

    @property
    def is_static_method(self):
        return self.cursor.is_static_method()

    @property
    def is_move_ctor(self):
        return self.cursor.is_move_constructor()

    @property
    def is_copy_ctor(self):
        return self.cursor.is_copy_constructor()

    @property
    def is_default_ctor(self):
        return self.cursor.is_default_constructor()

    @property
    def is_anonymous(self):
        return self.cursor.is_anonymous()

    @property
    def is_operator(self):
        """
        :return: Check if function is an operator.
        :rtype: bool
        """
        if self.is_function or self.is_cxx_method:
            return self.spelling in _py_operators
        return False

    @property
    def is_standard_transient(self):
        """
        :return: Check to see if class is derived from Standard_Transient.
        :rtype: bool
        """
        if self.dname == 'Standard_Transient':
            return True

        all_bases = self.all_bases
        for base in all_bases:
            if base.spelling == 'class Standard_Transient':
                return True
        return False

    @property
    def is_smds_mesh_object(self):
        """
        :return: Check to see if class is derived from SMDS_MeshObject
        :rtype: bool
        """
        if self.dname == 'SMDS_MeshObject':
            return True

        all_bases = self.all_bases
        for base in all_bases:
            if base.spelling == 'class SMDS_MeshObject':
                return True
        return False

    @property
    def is_smeshds_hypothesis(self):
        """
        :return: Check to see if class is derived from SMESHDS_Hypothesis.
        :rtype: bool
        """
        if self.dname == 'SMESHDS_Hypothesis':
            return True

        all_bases = self.all_bases
        for base in all_bases:
            if base.spelling == 'class SMESHDS_Hypothesis':
                return True
        return False

    @property
    def is_maybe_iterable(self):
        """
        :return: Check to see if the type is maybe iterable (has begin and end methods).
        :rtype: bool
        """
        method_names = set()
        for f in self.methods:
            if not f.is_public:
                continue
            method_names.add(f.spelling)

        return 'begin' in method_names and 'end' in method_names

    @property
    def is_const_parm(self):
        """
        Hack because Type.is_const_qualified() is always returning false...

        :return: If a parmeter declaration is "const" qualified.
        :rtype: bool
        """
        if not self.is_param:
            return False
        return self.type.spelling.startswith('const')

    @property
    def is_immutable(self):
        """
        :return: Check if the canonical type is a Python immutable type.
        :rtype: bool
        """
        type_ = self.type
        if self.is_pointer_like:
            type_ = type_.get_pointee()
        return type_.spelling in _immutable_types

    @property
    def is_template_instance(self):
        """
        :return: Check if the binder has a template reference as a child.
        :rtype: bool
        """
        for c in self.cursor.get_children():
            if c.kind == CursorKind.TEMPLATE_REF:
                return True
        return False

    @property
    def is_array_like(self):
        """
        :return: Check to see if argument type is array-like.
        :rtype: bool
        """
        return self.type.kind in [TypeKind.CONSTANTARRAY, TypeKind.INCOMPLETEARRAY, TypeKind.VARIABLEARRAY, TypeKind.DEPENDENTSIZEDARRAY]

    @property
    def spelling(self):
        """
        :return: The cursor spelling.
        :rtype: str
        """
        return self.cursor.spelling

    @property
    def dname(self):
        """
        :return: The cursor display name.
        :rtype: str
        """
        return self.cursor.displayname

    @property
    def qname(self):
        """
        :return: The cursor fully qualified name.
        :rtype: str
        """
        return fully_qualified_name(self.cursor)

    @property
    def pname(self):
        """
        :return: The Python compatible fully qualified name.
        :rtype: str
        """
        if self.pname_override:
            return self.pname_override

        qname = self.qname
        if qname in _python_names:
            return _python_names[qname]

        name = qname.replace('::', '_')
        name = name.replace('<', '_')
        name = name.replace('>', '_')
        name = name.replace('__', '_')
        name = name.rstrip('_')
        return name

    @property
    def tname(self):
        """
        :return: The name of the template used.
        :rtype: str
        """
        name = self.underlying_typedef_type.get_canonical().spelling
        if '<' not in name:
            return ''
        return name.split('<')[0]

    @property
    def bases(self):
        """
        :return: Base classes.
        :rtype: list[Binder]
        """
        cursors = self.get_children_of_kind(CursorKind.CXX_BASE_SPECIFIER)
        return [Binder(c) for c in cursors]

    @property
    def all_bases(self):
        """
        :return: All base classes.
        :rtype: list[Binder]
        """

        def _get_bases(_cx):
            for c in _cx.get_children():
                if c.kind != CursorKind.CXX_BASE_SPECIFIER:
                    continue
                bases.append(Binder(c))
                cx = c.type.get_declaration()
                _get_bases(cx)

        bases = []
        _get_bases(self.cursor)
        return bases

    @property
    def has_public_ctor(self):
        """
        :return: Check to see if the binder has any public constructors.
        :rtype: bool
        """
        for ctor in self.ctors:
            if ctor.is_public:
                return True
        return False

    @property
    def ctors(self):
        """
        :return: Constructors.
        :rtype: list[Binder]
        """
        cursors = self.get_children_of_kind(CursorKind.CONSTRUCTOR)
        return [Binder(c) for c in cursors]

    @property
    def has_public_dtor(self):
        """
        :return: Check to see if the binder has any public destructors.
        :rtype: bool
        """
        no_dtor = True
        for dtor in self.dtors:
            no_dtor = False
            if dtor.is_public:
                return True
        return no_dtor

    @property
    def dtors(self):
        """
        :return: Destructors.
        :rtype: list[Binder]
        """
        cursors = self.get_children_of_kind(CursorKind.DESTRUCTOR)
        return [Binder(c) for c in cursors]

    @property
    def methods(self):
        """
        :return: Class methods.
        :rtype: list[Binder]
        """
        cursors = self.get_children_of_kind(CursorKind.CXX_METHOD)
        return [Binder(c) for c in cursors]

    @property
    def virtual_methods(self):
        """
        :return: Virtual class methods.
        :rtype: list[Binder]
        """
        return [m for m in self.methods if m.is_virtual_method]

    @property
    def pure_virtual_methods(self):
        """
        :return: Pure virtual class methods.
        :rtype: list[Binder]
        """
        return [m for m in self.methods if m.is_pure_virtual_method]

    @property
    def arguments(self):
        """
        :return: Parameter declarations.
        :rtype: list[Binder]
        """
        cursors = self.get_children_of_kind(CursorKind.PARM_DECL)
        return [Binder(c) for c in cursors]

    @property
    def const_args(self):
        """
        :return: Arguments that are "const" qualified.
        :rtype: list[Binder]
        """
        args = []
        for a in self.arguments:
            if a.is_const_parm:
                args.append(a)
        return args

    @property
    def has_non_const_arg(self):
        """
        :return: Check to see if any argument is not "const" qualified.
        :rtype: bool
        """
        for a in self.arguments:
            if not a.is_const_parm:
                return True
        return False

    @property
    def non_const_args(self):
        """
        :return: Arguments that are not "const" qualified.
        :rtype: list[Binder]
        """
        args = []
        for a in self.arguments:
            if not a.is_const_parm:
                args.append(a)
        return args

    @property
    def has_immutable_non_const(self):
        """
        :return: Check to see if the function has immutable types that are non-const.
        :rtype: bool
        """
        for a in self.arguments:
            if a.is_immutable and not a.is_const_parm:
                return True
        return False

    @property
    def has_array_args(self):
        """
        :return: Check to see if the function has any array arguments.
        :rtype: bool
        """
        for arg in self.arguments:
            if arg.is_array_like:
                return True
        return False

    @property
    def needs_inout_method(self):
        """
        :return: Check to see if the function should use a lambda to return non-const types.
        :rtype: bool
        """
        for a in self.arguments:
            if a.is_immutable and not a.is_const_parm and a.is_pointer_like:
                return True
        return False

    @property
    def interface_spelling(self):
        """
        :return: Interface spelling for binders with arguments.
        :rtype: str
        """
        interface = []
        for arg in self.arguments:
            interface.append(arg.type.spelling)
        return ', '.join(interface)

    @property
    def has_default_value(self):
        """
        :return: Check to see if argument has a default value.
        :rtype: bool
        """
        arg = ''
        for c in self.cursor.get_tokens():
            arg += c.spelling

        if '=' in arg:
            return True
        return False

    @property
    def default_value(self):
        """
        :return: The default value of an argument.
        :rtype: str
        """
        if not self.is_param:
            return ''

        arg = ''
        for c in self.cursor.get_tokens():
            arg += c.spelling
        if '=' not in arg:
            return ''

        arg = arg.replace(' ', '')
        default = arg.split('=')[-1]

        # FIXME DefaultBlockSize default value
        if default == 'DefaultBlockSize':
            default = '24600'

        # FIXME AIS_Manipulator::OptionsForAttach default value
        if default == 'OptionsForAttach()':
            default = 'AIS_Manipulator::OptionsForAttach()'

        # FIXME Nullptr for default value
        if default.lower() in ['null', '0l']:
            default = '({}) nullptr'.format(self.type.spelling)

        return default

    @property
    def enum_constants(self):
        """
        :return: Enumeration constant declarations.
        :rtype: list[Binder]
        """
        cursors = self.get_children_of_kind(CursorKind.ENUM_CONSTANT_DECL)
        return [Binder(c) for c in cursors]

    @property
    def parent(self):
        """
        :return: The semantic parent.
        :rtype: Binder
        """
        if self.parent_override is not None:
            return self.parent_override
        return Binder(self.cursor.semantic_parent)

    @property
    def has_children(self):
        """
        :return: Check if binder has any children.
        :rtype: bool
        """
        for c in self.cursor.get_children():
            return True
        return False

    @property
    def is_abstract(self):
        return len(get_remaining_pure_virtual_functions(self.cursor)) > 0

    @property
    def needs_default_ctor(self):
        if self.is_abstract:
            return False
        items = [self] + self.all_bases
        for item in items:
            item.get_definition()
            if item.ctors:
                return False
        return True

    @property
    def class_template(self):
        """
        :return: The class template declaration.
        :rtype: Binder
        """
        can = self.type.get_canonical()
        decl = can.get_declaration()
        spec = decl.get_specialization()
        if not spec or spec.kind != CursorKind.CLASS_TEMPLATE:
            msg = 'Could not find class template: {}\n'.format(self.dname)
            fwarn.write(msg)
            return None
        return Binder(spec)

    @property
    def n_template_args(self):
        """
        :return: The number of template arguments.
        :return int
        """
        return self.cursor.type.get_num_template_arguments()

    @property
    def template_parameters(self):
        """
        :return: List of template parameters.
        :rtype: list[Binder]
        """
        params = []
        for item in self.cursor.get_children():
            if item.kind in [CursorKind.TEMPLATE_TYPE_PARAMETER,
                             CursorKind.TEMPLATE_NON_TYPE_PARAMETER,
                             CursorKind.TEMPLATE_TEMPLATE_PARAMETER]:
                params.append(Binder(item))
        return params

    @property
    def template_arguments(self):
        """
        :return: List of template arguments.
        :rtype: list[clang.cindex.Type]
        """
        args = []
        nargs = self.n_template_args
        for i in range(0, nargs):
            t = self.cursor.type.get_template_argument_type(i)
            args.append(t)
        return args

    def get_definition(self):
        """
        Get definition.
        """
        self.cursor.get_definition()

    def get_children_of_kind(self, kind):
        """
        Get children of a specified kind.

        :param clang.cindex.CursorKind kind: The cursor kind.

        :return: List of children.
        :rtype: list[clang.cindex.Cursor]
        """
        children = []
        for c in self.cursor.get_children():
            if c.kind == kind:
                children.append(c)
        return children

    def generate(self):
        """
        Generate the binding text.
        """
        if self.is_enum:
            return generate_enum(self)

        if self.is_function or self.is_cxx_method:
            return generate_funtion(self)

        if self.is_class or self.is_class_template:
            return generate_class(self)

        if self.is_typedef:
            return generate_typedef(self)

    @property
    def args(self):
        """
        :return: The cursor(s) of the arguments.
        :rtype: list[clang.cindex.Cursor]
        """
        return [arg for arg in self.cursor.get_arguments()]

    @property
    def args_spelling(self):
        """
        :return: The names of the arguments.
        :rtype: list[str]
        """
        return [arg.spelling for arg in self.args]

    @property
    def args_type_spelling(self):
        """
        :return: The type names of the arguments.
        :rtype: list[str]
        """
        return [arg.type.spelling for arg in self.args]

    @property
    def filename(self):
        """
        :return: The filename containing the binder. Will return *None* if not found.
        :rtype: str or None
        """
        return include_file_of_cursor(self.cursor)

    @property
    def docs(self):
        """
        :return: The docstring.
        :rtype: str
        """
        docs = str(self.cursor.brief_comment)
        docs = docs.replace('\n', ' ')
        docs = docs.replace('\"', '\'')
        return docs

    @property
    def is_handle(self):
        """
        :return: Check to see if binder is derived from opencascade::handle<>.
        :rtype: bool
        """
        return False

    @property
    def can_bind(self):
        """
        :return: Check to see if function is able to be binded.
        :rtype: bool
        """
        # OCC memory mgmt operators
        if self.spelling in ['operator new', 'operator delete', 'operator new[]',
                             'operator delete[]', 'operator>>', 'operator<<']:
            return False

        # Only public items
        if self.cursor.access_specifier in [AccessSpecifier.PROTECTED, AccessSpecifier.PRIVATE]:
            return False

        return True

    @property
    def is_inline(self):
        """
        :return: Check if defined inline.
        :rtype: bool
        """
        for token in self.cursor.get_tokens():
            if token.spelling.lower() == 'inline':
                return True
        return False

    @property
    def nested_class_binders(self):
        """
        :return: Any nested class binders.
        :rtype: list[Binder]
        """
        nested_cursors = get_public_nested_classes(self.cursor)
        nested_classes = [Binder(c) for c in nested_cursors]
        return nested_classes

    @property
    def nested_enum_binders(self):
        """
        :return: Any nested enum binders.
        :rtype: list[Binder]
        """
        nested_enums = []
        for c in self.get_children_of_kind(CursorKind.ENUM_DECL):
            b = Binder(c)
            nested_enums.append(b)
        return nested_enums

    @property
    def module_name(self):
        return get_module_name_from_binder(self)

    def relevant_includes(self, mod):
        """
        Find the relevant include files for the binder.

        :param Module mod: The module.

        :return: None.
        """
        cursor = self.cursor

        # Get the underlying template if available
        type_ = cursor.underlying_typedef_type
        if type_.kind in [TypeKind.POINTER, TypeKind.LVALUEREFERENCE, TypeKind.RVALUEREFERENCE]:
            type_ = type_.get_pointee()
        decl = type_.get_declaration()
        template = decl.get_specialization()
        if template:
            cursor = template
            if not cursor.is_definition():
                cursor = cursor.get_definition()

        # Base class types
        for base in get_children_of_kind(cursor, CursorKind.CXX_BASE_SPECIFIER):
            files = include_files_of_type(base.type)
            for f in files:
                mod.add_include_file(f)

        # Constructor argument types
        for ctor in get_children_of_kind(cursor, CursorKind.CONSTRUCTOR):
            for arg in get_children_of_kind(ctor, CursorKind.PARM_DECL):
                files = include_files_of_type(arg.type)
                for f in files:
                    mod.add_include_file(f)

        # Public methods
        for method in get_children_of_kind(cursor, CursorKind.CXX_METHOD):
            # Return type
            files = include_files_of_type(method.result_type)
            for f in files:
                mod.add_include_file(f)
            # Arguments
            for arg in method.get_arguments():
                files = include_files_of_type(arg.type)
                for f in files:
                    mod.add_include_file(f)

        # Pure virtual methods that might show up in the trampoline callback
        pure_virtual_methods = get_remaining_pure_virtual_functions(cursor)
        for method in pure_virtual_methods:
            # Return type
            files = include_files_of_type(method.result_type)
            for f in files:
                mod.add_include_file(f)
            # Arguments
            for arg in method.get_arguments():
                files = include_files_of_type(arg.type)
                for f in files:
                    mod.add_include_file(f)

        # Function, return type and arguments of function
        if cursor.kind == CursorKind.FUNCTION_DECL:
            f = include_file_of_cursor(cursor)
            mod.add_include_file(f)
            files = include_files_of_type(cursor.result_type)
            for f in files:
                mod.add_include_file(f)
            for arg in cursor.get_arguments():
                files = include_files_of_type(arg.type)
                for f in files:
                    mod.add_include_file(f)

        # Location of this cursor
        files = include_files_of_type(self.cursor.type)
        for f in files:
            mod.add_include_file(f)

    def dump(self, max_depth=0):
        """
        Dump cursor info to the screen.

        :param int max_depth: Max depth.

        :return: None.
        """
        dump_cursor(self.cursor, max_depth)


def process_config(fn):
    """
    Process a configuration file.

    :param str fn: The filename.

    :return: None.
    """
    with open(fn, 'r') as f:
        for line in f:
            line = line.strip()

            # Line comment
            if line.startswith('#'):
                continue

            # Module comment
            if line.startswith('+comment'):
                line = line.replace('+comment', '')
                line = line.strip()
                mod, comment = line.split(':')
                mod = mod.strip()
                comment = comment.strip()
                _module_comments[mod].append(comment)
                continue

            # Module to exclude
            if line.startswith('-module'):
                line = line.replace('-module', '')
                mod = line.strip()
                _excluded_modules.add(mod)
                continue

            # Extra headers
            if line.startswith('+header'):
                line = line.replace('+header', '')
                line = line.strip()
                mod, comment = line.split(':')
                mod = mod.strip()
                header = comment.strip()
                _extra_headers[mod].append(header)
                continue

            # Excluded functions
            if line.startswith('-function'):
                line = line.replace('-function', '')
                func = line.strip()
                _excluded_functions.add(func)
                continue

            # Excluded classes
            if line.startswith('-class'):
                line = line.replace('-class', '')
                cls = line.strip()
                _excluded_classes.add(cls)
                continue

            # Sort order
            if line.startswith('+sort'):
                line = line.replace('+sort', '')
                line = line.strip()
                mod, loc = line.split(':')
                mod = mod.strip()
                loc = loc.strip()
                _sort_priotiry[mod] = int(loc)
                continue

            # Import guards
            if line.startswith('+iguard'):
                line = line.replace('+iguard', '')
                line = line.strip()
                mod, other = line.split(':')
                mod = mod.strip()
                other = other.strip()
                _import_guards[mod].add(other)
                continue

            # Call guard
            if line.startswith('+cguard'):
                line = line.replace('+cguard', '')
                line = line.strip()
                func, mod = line.split('-->')
                func = func.strip()
                mod = mod.strip()
                _call_guards[func].add(mod)
                continue

            # Python name override
            if line.startswith('+pname'):
                line = line.replace('+pname', '')
                line = line.strip()
                qname, name = line.split('-->')
                qname = qname.strip()
                name = name.strip()
                _python_names[qname] = name
                continue

            # Immutable types
            if line.startswith('+immutable'):
                line = line.replace('+immutable', '')
                type_ = line.strip()
                _immutable_types.add(type_)
                continue

            # No inout
            if line.startswith('-inout'):
                line = line.replace('-inout', '')
                qname = line.strip()
                _no_inout.add(qname)
                continue

            # py::nodelete
            if line.startswith('+nodelete'):
                line = line.replace('+nodelete', '')
                qname = line.strip()
                _no_delete.add(qname)
                continue


def include_file_of_cursor(cursor):
    """
    Try to find the relevant include file for the cursor.

    :param clang.cindex.Cursor cursor: The cursor.

    :return: The include file.
    :rtype: str or None
    """
    try:
        path = cursor.location.file.name
        path = path.replace('\\', '/')
        parts = path.split('/')
        return parts[-1]
    except (AttributeError, IndexError):
        return None


def include_files_of_type(type_):
    """
    Find relevant include files of the type.

    :param clang.cindex.Type type_: The type.

    :return: List of include files.
    :rtype: list[str]
    """

    include_files = []

    # Get cursor
    if type_.kind in [TypeKind.POINTER, TypeKind.LVALUEREFERENCE, TypeKind.RVALUEREFERENCE]:
        type_ = type_.get_pointee()
    cursor = type_.get_declaration()

    inc_file = include_file_of_cursor(cursor)
    include_files.append(inc_file)

    # Don't look for template parameter types in typedef's, just be sure to include its own header
    # file.
    if cursor.kind == CursorKind.TYPEDEF_DECL:
        return include_files

    # Check for template parameters of things like parameter declarations and return types that
    # may use opencascade::handle<T> template.

    # Hack to check for template since getting number explodes in some cases
    if not type_.get_template_argument_type(0).spelling:
        return include_files

    # Template parameters
    n = type_.get_num_template_arguments()
    for i in range(n):
        atype = type_.get_template_argument_type(i)
        atype._tu = BindOCCT.tu
        include_files += include_files_of_type(atype)

    return include_files


def get_module_name_from_str(name):
    """
    Get an OCCT module spelling from the string.

    :param str name: The string.

    :return: The module spelling.
    :rtype: str or None
    """
    if '_' in name:
        delim = '_'
    else:
        delim = '.'

    try:
        return name.split(delim)[0]
    except (IndexError, AttributeError):
        return None


def get_module_name_from_binder(binder):
    """
    Get an OCCT module spelling from the binding.

    :param Binder binder: The binder.

    :return: The module spelling.
    :rtype: str or None
    """
    name = binder.filename
    if '_' in name:
        delim = '_'
    else:
        delim = '.'

    try:
        return name.split(delim)[0]
    except (IndexError, AttributeError):
        return None


def fully_qualified_name(cursor):
    """
    Get the qualified spelling of the cursor.

    :param clang.cindex.Cursor cursor: The cursor.

    :return: The qualified spelling.
    :rtype: str
    """
    if cursor is None:
        return ''

    if cursor.kind == CursorKind.TRANSLATION_UNIT:
        return ''

    if cursor.kind == CursorKind.CLASS_TEMPLATE:
        txt = cursor.displayname
    elif '<' in cursor.displayname and cursor.kind in [CursorKind.STRUCT_DECL,
                                                       CursorKind.CLASS_DECL]:
        txt = cursor.displayname
    else:
        txt = cursor.spelling
    res = fully_qualified_name(cursor.semantic_parent)
    if res != '':
        return res + '::' + txt

    return txt


def all_base_cursors(cursor, bases):
    """
    Get a list of all base cursors.

    :param clang.cindex.Cursor cursor: The cursor.
    :param list[clang.cindex.Cursor] bases: Existing list of base cursors for
        recursive method. Should be empty to start.

    :return: List of base cursors.
    :rtype: list[clang.cindex.Cursor]
    """
    for c in cursor.get_children():
        if c.kind == CursorKind.CXX_BASE_SPECIFIER:
            base_cursor = c.type.get_declaration()
            bases.append(base_cursor)
            all_base_cursors(base_cursor, bases)


def cpp_to_python_operator(operator):
    """
    Find the equivalent Python operator from the C++ operator.

    :param operator: The C++ operator.

    :return: The Python operator if available or the input operator if not found.
    :rtype: str
    """
    try:
        return _py_operators[operator]
    except KeyError:
        return operator


def sort_class_binders(binders):
    """
    Sort a list of class binders so they are ordered based on base classes.

    :param list[Binder] binders: The binders.

    :return: Sorted list of binders in place.
    :rtype: None.
    """
    # List of all binder names
    binder_names = [b.qname for b in binders]
    if not binder_names:
        return None

    repeat = True
    while repeat:
        repeat = False

        for b in binders:
            if b.qname not in binder_names:
                continue
            i1 = binder_names.index(b.qname)
            for dep in b.all_bases:
                dep.get_definition()
                if dep.qname not in binder_names:
                    continue
                i2 = binder_names.index(dep.qname)
                if i1 < i2:
                    binders[i1], binders[i2] = binders[i2], binders[i1]
                    binder_names[i1], binder_names[i2] = binder_names[i2], binder_names[i1]
                    repeat = True


def get_public_nested_classes(cursor):
    """
    Get public nested classes.

    :param clang.cindex.Cursor cursor: The cursor.

    :return: List of nested class cursors.
    :rtype: list[clang.cindex.Cursor]
    """
    is_public = True
    nested_cursors = []
    for item in cursor.get_children():
        if item.kind == CursorKind.CXX_ACCESS_SPEC_DECL:
            if item.access_specifier == AccessSpecifier.PUBLIC:
                is_public = True
            else:
                is_public = False

        if item.kind not in [CursorKind.CLASS_DECL,
                             CursorKind.STRUCT_DECL]:
            continue

        if item.access_specifier in [AccessSpecifier.PROTECTED,
                                     AccessSpecifier.PRIVATE]:
            continue

        if is_public:
            nested_cursors.append(item)

    return nested_cursors


def add_class_fixme_txt(txt):
    """
    Comment out the text and add a FIXME note for a class.

    :param str txt: The text.

    :return: Commented text.
    :rtype: str
    """
    # if 'class_' not in txt:
    #     return txt
    new_line = '\n'
    if txt.endswith('\n'):
        new_line = ''
    return '\t/* FIXME\n' + txt + '{}\t*/\n'.format(new_line)


def add_func_fixme_txt(txt):
    """
    Comment out the text and add a FIXME note for a function.

    :param str txt: The text.

    :return: Commented text.
    :rtype: str
    """
    if '.def' not in txt:
        return txt
    return '\t// FIXME ' + txt


def is_type_pointer(type_):
    """
    Check if type is a pointer.

    :param type_:

    :return:
    """
    return type_.kind in [TypeKind.POINTER, TypeKind.LVALUEREFERENCE, TypeKind.RVALUEREFERENCE]


def get_remaining_pure_virtual_functions(cursor):
    """
    Given a class declaration cursor, try to find any pure virtual methods that have not been
    overriden.

    :param clang.cindex.Cursor cursor: The cursor.

    :return: List of remaining pure virtual methods.
    :rtype: list[clang.cindex.Cursor]
    """
    if cursor.kind not in [CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL]:
        return []

    # Get all bases
    bases = []
    all_base_cursors(cursor, bases)

    # Find all pure virtual methods
    pure_virtual_methods = OrderedDict()
    for base in bases + [cursor]:
        for item in base.get_children():
            if item.kind != CursorKind.CXX_METHOD:
                continue

            if item.is_pure_virtual_method():
                pure_virtual_methods[item.displayname] = item

    # See if all the pure virtual methods have been overriden somewhere.
    for base in bases + [cursor]:
        for item in base.get_children():
            if item.kind != CursorKind.CXX_METHOD:
                continue

            if item.is_pure_virtual_method():
                continue

            for key in pure_virtual_methods:
                if key == item.displayname:
                    del pure_virtual_methods[key]
                    break

    return pure_virtual_methods.values()


def get_children_of_kind(cursor, kind, only_public=True):
    """
    Get children of a specified kind.

    :param clang.cindex.Cursor cursor: The cursor.
    :param clang.cindex.CursorKind kind: The cursor kind.
    :param bool only_public: Return only cursor that are public.

    :return: List of children.
    :rtype: list[clang.cindex.Cursor]
    """
    children = []
    for c in cursor.get_children():
        if c.kind != kind:
            continue
        if only_public:
            if c.access_specifier in [AccessSpecifier.PROTECTED, AccessSpecifier.PRIVATE]:
                continue
        children.append(c)
    return children


def is_mod_dependent(dmod, imod):
    """
    Determine if the one module is dependent on another.

    :param Module dmod: The dependent module to check.
    :param Module imod: The independent module.

    :return: *True* if dmod is dependent on imod.
    :rtype: bool
    """
    if dmod.name == imod.name:
        return True

    for modname in dmod.import_mods:
        if modname == imod.name:
            return True
        try:
            mod = _all_mods[modname]
            if is_mod_dependent(mod, imod):
                return True
        except KeyError:
            return False

    return False


def generate_enum(enum):
    """
    Generate binding text for enumeration.

    :param Binder enum: The binder.
    """
    qname = enum.qname
    if qname in _python_names:
        name = _python_names[qname]
    else:
        name = enum.spelling

    txt = '\t// ' + enum.location + '\n'
    txt += '\tpy::enum_<{}>({}, \"{}\", \"{}\")\n'.format(qname, enum.binding_parent,
                                                          name, enum.docs)

    for e in enum.enum_constants:
        txt += '\t\t.value(\"{}\", {})\n'.format(e.spelling, e.qname)
    txt += '\t\t.export_values();\n'

    # Write anonymous enums as class attribute
    if '::::' in txt or not enum.spelling:
        txt = '\t// ' + enum.location + '\n'
        for e in enum.enum_constants:
            qname = e.qname
            qname = qname.replace('::::', '::')
            txt += '\t{}.attr(\"{}\") = py::cast(int({}));\n'.format(enum.binding_parent,
                                                                     e.spelling, qname)
        txt += '\n'

    enum.txt = txt


def generate_funtion(func):
    """
    Generate binding text for function or class method.

    :param Binder func: The binder.
    """

    fixme = False
    txt = ''

    if not func.can_bind:
        fixme = True

    # Header file
    if not func.is_cxx_method:
        txt += '\t// ' + func.location + '\n'

    # Prefix
    if func.is_cxx_method:
        prefix = '\t{}'.format(func.binding_parent)
    else:
        prefix = '\tmod'

    # Is static
    is_static = ''
    if func.is_static_method:
        is_static = '_static'

    # Function name
    name = func.spelling

    # FIXME operator new/delete
    if 'operator new' in name or 'operator delete' in name:
        return None

    # Convert name to Python operator
    is_operator = ''
    if func.is_operator:
        name = cpp_to_python_operator(name)
        if '__i' not in name:
            is_operator = 'py::is_operator(), '

    # Append underscore to avoid static and instance naming conflicts
    if is_static:
        name += '_'

    # Return type
    rname = func.rtype.spelling

    # Pointer
    ptr = '*'
    class_name = func.parent.qname
    if func.is_cxx_method and not is_static:
        ptr = '::'.join([class_name, ptr])

    # Qualified function name
    if func.is_cxx_method:
        qname = '::'.join([class_name, func.spelling])
    else:
        qname = func.qname

    # Check for excluded function
    if is_static:
        check_qname = qname + '_'
    else:
        check_qname = qname
    if check_qname in _excluded_functions:
        fixme = True

    # Is const
    is_const = ''
    if func.is_const_method:
        is_const = ' const '

    # Docs
    doc = func.docs

    # Call guards
    cguards = []
    for cguard in _call_guards[qname]:
        cguards.append('Import{}'.format(cguard))
    if cguards:
        cguard = ', py::call_guard<{}>()'.format(', '.join(cguards))
    else:
        cguard = ''

    # Special case for class methods with non-const immutable types
    if func.is_cxx_method and check_qname not in _no_inout and not func.is_operator and func.needs_inout_method:
        # Binding text
        bind_txt = generate_immutable_inout_function(func, qname)
        txt = '{}.def{}(\"{}\", {}, \"{}\"'.format(prefix, is_static, name, bind_txt, doc)

        # Arguments
        for arg in func.arguments:
            txt += ', py::arg(\"{}\")'.format(arg.spelling)

        # Call guard
        txt += cguard

        # End line
        txt += ');\n'

        if check_qname in _excluded_functions or func.has_array_args:
            txt = '\t// FIXME ' + txt

        func.txt = txt
        return None

    if not func.is_cxx_method:
        # Function binding text
        interface = func.interface_spelling

        txt += '{}.def{}(\"{}\", ({} ({})({}){}) &{}, {}\"{}\"'.format(prefix, is_static,
                                                                       name, rname, ptr,
                                                                       interface, is_const,
                                                                       qname, is_operator, doc)
        # Arguments and their defaults
        for arg in func.arguments:
            default = arg.default_value
            if default:
                default = ' = {}'.format(default)
            txt += ', py::arg(\"{}\"){}'.format(arg.spelling, default)

        # Call guard
        txt += cguard

        if _check_func_issues(func, interface):
            fixme = True

    else:
        # Class method use lambdas to override method and avoid unresolved default values
        prefix = func.binding_parent

        # Get number of arguments and number of default values
        args = func.arguments
        num_args = len(args)
        num_default = 0
        for arg in args:
            if arg.has_default_value:
                num_default += 1

        # For each default argument, write a function interface
        darg = num_args - num_default
        for i in range(darg, num_args + 1):

            if i == num_args:
                # Build interface
                arg_list = []
                args_spelling = []
                for j in range(0, i):
                    arg_list.append(args[j].type.spelling)
                    args_spelling.append(args[j].spelling)
                interface = ', '.join(arg_list)

                temp_txt = '{}.def{}(\"{}\", ({} ({})({}){}) &{}, {}\"{}\"'.format(prefix,
                                                                                   is_static,
                                                                                   name,
                                                                                   rname, ptr,
                                                                                   interface,
                                                                                   is_const, qname,
                                                                                   is_operator,
                                                                                   doc)

                # Comment out if needs fixed
                if _check_func_issues(func, interface) or fixme:
                    temp_txt = '\t// FIXME ' + temp_txt
                else:
                    temp_txt = '\t' + temp_txt
                txt += temp_txt

            else:
                # Use a lambda
                arg_list = []
                args_spelling = []
                for j in range(0, i):
                    arg_list.append(args[j].type.spelling)
                    args_spelling.append(args[j].spelling)

                # Build interface
                if is_static:
                    interface = ''
                else:
                    parts = qname.split('::')
                    parent_spelling = '::'.join(parts[:-1])
                    interface = parent_spelling + ' &self'
                k = 0
                call_args = []
                for arg_type_spelling in arg_list:
                    if not interface:
                        interface += '{} {}'.format(arg_type_spelling, 'a' + str(k))
                    else:
                        interface += ', {} {}'.format(arg_type_spelling, 'a' + str(k))
                    call_args.append('a' + str(k))
                    k += 1
                call = ', '.join(call_args)

                if is_static:
                    fname = qname
                else:
                    fname = 'self.' + func.spelling

                temp_txt = '{}.def{}(\"{}\", []({}) -> {} {{ return {}({}); }}'.format(prefix,
                                                                                       is_static,
                                                                                       name,
                                                                                       interface,
                                                                                       rname,
                                                                                       fname, call)

                # Comment out if needs fixed
                if _check_func_issues(func, interface) or fixme:
                    temp_txt = '\t// FIXME ' + temp_txt
                else:
                    temp_txt = '\t' + temp_txt
                txt += temp_txt

            # Arguments
            for arg in args_spelling:
                txt += ', py::arg(\"{}\")'.format(arg)

            # Call guard
            txt += cguard

            # End line
            txt += ');\n'

    # End function line
    if not func.is_cxx_method:
        if fixme:
            txt += ');\n'
        else:
            txt += ');\n\n'

    func.fixme, func.txt = fixme, txt


def _check_func_issues(func, txt):
    """
    Check known function issues.
    :param Binder func: The function binder.
    :param str txt: The binding text.

    :return: *True* if needs fixed, *False* if ok.
    :rtype: bool
    """

    # FIXME How to handle *& and && and **
    if '*&' in txt or '&&' in txt or '**' in txt:
        return True

    # FIXME operator->
    if 'operator->' == func.spelling:
        return True

    # FIXME How to handle arrays?
    if func.has_array_args:
        return True

    # FIXME Function Dump()
    if func.spelling == 'Dump':
        return True

    # FIXME Missing LDOM_NullPtr
    if 'LDOM_NullPtr' in txt:
        return True

    # FIXME ChangeNodes
    if func.spelling == 'ChangeNodes':
        return True

    return False


def generate_class(klass):
    """
    Generate binding text for a class.

    :param Binder klass: The binder.
    """
    fixme = False

    if not klass.can_bind:
        fixme = True

    # If a class has no children don't bind it
    if not klass.has_children:
        fixme = True

    # Callback for pure virtual methods that are not overridden and if class is constructable
    if klass.has_public_ctor:
        callback_name, txt = generate_callback(klass)
    else:
        callback_name, txt = '', ''

    # Header file
    txt += '\t// ' + klass.location + '\n'

    # Qualified name
    qname = klass.qname

    # Python name
    pname = klass.pname

    # Type spelling
    type_spelling = klass.type.spelling
    if not type_spelling:
        type_spelling = qname

    # Variable name in bindings
    if klass.binding_parent != 'mod' and not klass.is_nested:
        cls = '_'.join(['cls', klass.binding_parent, pname])
        cls = cls.replace('_cls_', '_')
    else:
        cls = '_'.join(['cls', pname])

    # Check for excluded class
    if qname in _excluded_classes:
        fixme = True

    # Holder type based on the following rules:
    # 1) If derived from Standard_Transient, use opencascade::handle<>, otherwise use std::unique_ptr<>
    # 2) If the the class does not have a public destructor, use py::nodelete option, otherwise use
    #    Deleter<> template for consistency.
    # 3) Since SMESH manages most objects on its side, any class derived from SMDS_MeshObject or
    #    SMESHDS_Hypothesis use the py::nodelete option.
    # 4) TODO If the klass is specified in the configuration file with the +nodelete option.
    is_transient = klass.is_standard_transient
    if is_transient:
        holder = 'opencascade::handle<{}>'.format(type_spelling)
    else:
        if qname in _no_delete or not klass.has_public_dtor or klass.is_smds_mesh_object or klass.is_smeshds_hypothesis:
            dtor = ', py::nodelete'
        else:
            dtor = ', Deleter<{}>'.format(type_spelling)
        holder = 'std::unique_ptr<{}{}>'.format(type_spelling, dtor)

    # Callback text
    if callback_name:
        callback_txt = ', ' + callback_name
    else:
        callback_txt = ''

    # Class definition and bases
    txt += '\tpy::class_<{}, {}{}'.format(type_spelling, holder, callback_txt)
    for base in klass.bases:
        if not base.is_public:
            continue

        # Check declaration
        decl = base.type.get_declaration()

        if decl.type.spelling in _excluded_classes:
            continue

        # FIXME Check the declaration is not nested
        if decl.semantic_parent and decl.semantic_parent.kind in [CursorKind.CLASS_DECL,
                                                                  CursorKind.CLASS_TEMPLATE,
                                                                  CursorKind.STRUCT_DECL]:
            continue

        # FIXME No NCollection_Vector<> as base since it's not yet registered.
        # if base.type.spelling.startswith('NCollection_Vector<'):
        #     continue

        if decl.kind == CursorKind.CLASS_TEMPLATE:
            base_name = base.dname
        else:
            base_name = base.type.spelling

        txt += ', {}'.format(base_name)

    # Class definition
    txt += '> {}({}, \"{}\", \"{}\");\n'.format(cls, klass.binding_parent, pname, klass.docs)

    # Constructors
    ctors = klass.ctors
    for ctor in ctors:
        if not ctor.is_public:
            continue
        ctor.binding_parent = cls
        generate_ctor(ctor)
        txt += ctor.txt

    # Callback constructor
    # if callback_name and has_copy_ctor:
    #     txt += '\t{}.def(py::init<{} const &>());\n'.format(cls, callback_name)

    # Default constructor if needed
    if klass.needs_default_ctor:
        txt += '\t{}.def(py::init<>());\n'.format(cls)

    # Methods
    methods = klass.methods
    for func in methods:
        if not func.is_public:
            continue
        func.binding_parent = cls
        generate_funtion(func)
        txt += func.txt

    # Special case for "using" methods (BRepAlgoAPI_Algo)
    for child in klass.cursor.get_children():
        if child.kind != CursorKind.USING_DECLARATION:
            continue

        if child.access_specifier in [AccessSpecifier.PROTECTED, AccessSpecifier.PRIVATE]:
            continue

        for next_child in child.get_children():
            if next_child.kind != CursorKind.OVERLOADED_DECL_REF:
                continue

            cursor = next_child.get_overloaded_decl(0)

            if cursor.kind != CursorKind.CXX_METHOD:
                continue

            func = Binder(cursor)
            func.binding_parent = cls
            func.parent_override = klass
            func.generate()
            txt += func.txt

    # Check for an iterable type and add __iter__
    if klass.is_maybe_iterable:
        txt += '\t{}.def(\"__iter__\", [](const {} &s) {{ return py::make_iterator(s.begin(), s.end()); }}, py::keep_alive<0, 1>());\n'.format(cls, type_spelling)

    # TODO Nested class types
    # Nested enums
    enums = klass.nested_enum_binders
    for enum in enums:
        if not enum.is_public:
            continue
        enum.binding_parent = cls
        enum.generate()
        txt += enum.txt

    # if self.nested_class_binders:
    #     for nested in self.nested_class_binders:
    #         nested_name = '_'.join([pname, nested.cursor.spelling])
    #         class_status, class_txt = nested.generate(parent=cls, pname=nested_name,
    #                                                   is_nested=True, is_local=is_local)
    #         if class_status:
    #             class_txt = add_class_fixme_txt(class_txt)
    #         txt += class_txt

    if txt and not fixme:
        txt += '\n'

    klass.fixme, klass.txt = fixme, txt


def generate_callback(klass):
    """
    Generate callback for virtual methods if needed.

    :param Binder klass: The binder.

    :return: The callback name and binding text
    :rtype: tuple(str)
    """
    # Get all virtual methods
    virtual_cursors = get_remaining_pure_virtual_functions(klass.cursor)
    if not virtual_cursors:
        return '', ''

    virtual_methods = [Binder(c) for c in virtual_cursors]
    txt = ''

    # Callback class
    name = klass.spelling
    qname = klass.qname

    py_name = qname
    if '::' in py_name:
        py_name = py_name.replace('::', '_')

    py_name = 'PyCallback_' + py_name
    txt += '\t// Callback for {}.\n'.format(qname)
    txt += '\tclass {} : public {} {{\n'.format(py_name, qname)
    txt += '\tpublic:\n'
    txt += '\t\tusing {}::{};\n\n'.format(qname, name)

    # Virtual methods
    has_methods = False
    for f in virtual_methods:

        # Check for excluding function
        if f.qname in _excluded_functions:
            continue

        # Function name
        f_name = f.spelling

        # Return type
        result = f.rtype.spelling

        # Is const
        if f.is_const_method:
            const = ' const '
        else:
            const = ''

        # Is pure
        if f.is_pure_virtual_method:
            overload = 'PYBIND11_OVERLOAD_PURE'
        else:
            overload = 'PYBIND11_OVERLOAD'

        # Argument names
        arg_names = []
        i = 0
        for arg in f.arguments:
            arg = arg.spelling
            if not arg:
                arg = ''.join(['a', str(i)])
                i += 1
            arg_names.append(arg)

        # Argument types
        arg_types = [arg.type.spelling for arg in f.arguments]

        interface = []
        for a, t, n in zip(f.arguments, arg_types, arg_names):
            temp = ' '.join([t, n])
            # Fix for arrays in callbacks
            if a.type.kind in [TypeKind.CONSTANTARRAY, TypeKind.INCOMPLETEARRAY, TypeKind.VARIABLEARRAY,
                               TypeKind.DEPENDENTSIZEDARRAY]:
                # Try to find [] and move it to end of string
                r = re.search(r'\[.*?\]', temp)
                if r:
                    arr = r.group(0)
                    temp = temp.replace(arr, '')
                    temp += arr
            interface.append(temp)
        interface = ', '.join(interface)

        # Input names
        inputs = ', '.join(arg_names)

        # Text
        txt += '\t\t{} {}({}){} override {{ {}({}, {}, {}, {}); }}\n'.format(
            result, f_name, interface, const, overload, result, qname,
            f_name, inputs)

        has_methods = True

    txt += '\t};\n\n'

    if not has_methods:
        return '', ''

    return py_name, txt


def generate_ctor(ctor):
    """
    Generate binding text for class constructor.

    :param Binder ctor: The binder.
    """
    interface = ctor.interface_spelling

    # Hack for copy constructors
    if ctor.is_copy_ctor and len(ctor.arguments) == 1:
        txt = '\t{}.def(py::init([] ({}other) {{return new {}(other);}}), \"Copy constructor\", py::arg(\"other\"));\n'.format(
            ctor.binding_parent, interface, ctor.parent.qname)
        ctor.txt = txt
        return None

    # FIXME Move constructors
    if ctor.is_move_ctor:
        args = ''
        for arg in ctor.arguments:
            args += ', py::arg(\"{}\")'.format(arg.spelling)
        fixme = '// FIXME '
        txt = '\t{}{}.def(py::init<{}>(){});\n'.format(fixme, ctor.binding_parent, interface, args)
        ctor.txt = txt
        return None

    # Declared constructors
    txt = ''

    # Call guards
    cguards = []
    for cguard in _call_guards[ctor.qname]:
        cguards.append('Import{}'.format(cguard))
    if cguards:
        cguard = ', py::call_guard<{}>()'.format(', '.join(cguards))
    else:
        cguard = ''

    # Qualified name
    qname = ctor.qname

    # Get number of arguments and number of default values.
    args = ctor.arguments
    num_args = len(args)
    num_default = 0
    for arg in args:
        if arg.has_default_value:
            num_default += 1

    # For each default argument, write a constructor
    darg = num_args - num_default
    for i in range(darg, num_args + 1):
        fixme = ''

        # Check for excluded constructor
        if qname in _excluded_functions:
            fixme = '// FIXME '

        # Build interface
        arg_list = []
        args_spelling = []
        for j in range(0, i):
            arg_list.append(args[j].type.spelling)
            args_spelling.append(args[j].spelling)
        interface = ', '.join(arg_list)

        # Arguments
        args_str = ''
        for arg in args_spelling:
            args_str += ', py::arg(\"{}\")'.format(arg)

        # FIXME How to handle arrays?
        r = re.search(r'\[.*?\]', interface)
        if r:
            fixme = '// FIXME '

        # FIXME How to handle *&
        if '*&' in interface:
            fixme = '// FIXME '

        txt += '\t{}{}.def(py::init<{}>(){}{});\n'.format(fixme, ctor.binding_parent, interface,
                                                          args_str, cguard)

    ctor.txt = txt


def generate_typedef(typedef):
    """
    Generate binding text for a typedef.

    :param Binder typedef: The binder.
    """
    fixme = False

    # Header file
    txt = '\t// ' + typedef.location + '\n'

    if not typedef.can_bind:
        fixme = True

    if typedef.dname in _excluded_classes:
        fixme = True

    # Check to see if this type is already registered and simply set module attribute if it is.
    alias = typedef.alias
    if alias is not None:
        typedef.fixme = fixme
        return generate_alias(typedef, alias)

    # Template instance
    if typedef.is_template_instance:
        name = typedef.underlying_typedef_type.get_canonical().spelling

        # Make sure the canonical type is a template by checking for ending in ">". If it doesn't
        # then it might be a nested type of the template. Bind that manually in the template bindings.
        if not name.endswith('>'):
            return None

        # Make sure template is available
        prefix = ''
        t = name.split('<')[0]
        if t not in _available_templates:
            prefix = '// FIXME '

        txt += '\t{}bind_{}({}, \"{}\");\n\n'.format(prefix, name, typedef.binding_parent, typedef.dname)

    typedef.fixme, typedef.txt = fixme, txt


def generate_alias(binder, alias):
    """
    Generate binding text for an alias.

    :param Binder binder: The binder.
    :param Binder alias: The alias.
    """
    other_mod = alias.module_name

    # Header file
    txt = '\t// ' + binder.location + '\n'

    # Use hasattr to get around some issues for now
    if other_mod == binder.module_name:
        txt += '\tif (py::hasattr(mod, \"{}\")) {{\n'.format(alias.pname)
        txt += '\t\tmod.attr(\"{}\") = mod.attr(\"{}\");\n'.format(binder.pname, alias.pname)
        txt += '\t}\n\n'
    else:
        txt += '\tother_mod = py::module::import(\"OCCT.{}\");\n'.format(other_mod)
        txt += '\tif (py::hasattr(other_mod, \"{}\")) {{\n'.format(alias.dname)
        txt += '\t\tmod.attr(\"{}\") = other_mod.attr(\"{}\");\n'.format(binder.pname, alias.pname)
        txt += '\t}\n\n'

    binder.txt = txt


def get_cursor(source, spelling):
    """Obtain a cursor from a source object.

    This provides a convenient search mechanism to find a cursor with specific
    spelling within a source. The first argument can be either a
    TranslationUnit or Cursor instance.

    If the cursor is not found, None is returned.
    """
    # Convenience for calling on a TU.
    root_cursor = source if isinstance(source, Cursor) else source.cursor

    for cursor in root_cursor.walk_preorder():
        if cursor.spelling == spelling:
            return cursor

    return None


def get_cursors(source, spelling, kind=None):
    """Obtain all cursors from a source object with a specific spelling.

    This provides a convenient search mechanism to find all cursors with
    specific spelling within a source. The first argument can be either a
    TranslationUnit or Cursor instance.

    If no cursors are found, an empty list is returned.
    """
    # Convenience for calling on a TU.
    root_cursor = source if isinstance(source, Cursor) else source.cursor

    cursors = []
    for cursor in root_cursor.walk_preorder():
        if kind is not None:
            if cursor.kind != kind:
                continue
        if cursor.spelling == spelling:
            cursors.append(cursor)

    return cursors


def get_info(node, depth=0, max_depth=None):
    if max_depth is not None and depth >= max_depth:
        children = []
    else:
        children = [get_info(c, depth + 1, max_depth)
                    for c in node.get_children()]

    try:
        def_hash = node.get_declaration().hash
    except AttributeError:
        def_hash = None

    try:
        underlying_cursor = node.underlying_typedef_type.get_declaration().hash
    except AssertionError:
        underlying_cursor = None

    try:
        underlying_type = node.underlying_typedef_type.spelling
    except AssertionError:
        underlying_type = None

    try:
        ref_hash = node.referenced.hash
    except AssertionError:
        ref_hash = None

    return {'kind': node.kind,
            'usr': node.get_usr(),
            'spelling': node.spelling,
            'display spelling': node.displayname,
            'location': node.location,
            # 'extent.start': node.extent.start,
            # 'extent.end': node.extent.end,
            'is_definition': node.is_definition(),
            'is_declaration': node.kind.is_declaration(),
            'children': children,
            'type spelling': node.type.spelling,
            'type hash': node.type.get_declaration().hash,
            'referenced': ref_hash,
            'this': node.hash,
            'definition hash': def_hash,
            'kind is reference': node.kind.is_reference(),
            'underlying type': underlying_type,
            'underlying cursor': underlying_cursor}


def dump_cursor(cursor, max_depth=None):
    print('-------------------------------------------------------------------------------')
    print('{}'.format(cursor.displayname.upper()))
    print('-------------------------------------------------------------------------------')
    pprint(('node', get_info(cursor, max_depth=max_depth)))
    print('-------------------------------------------------------------------------------\n\n')


def get_diag_info(diag):
    return {'severity': diag.severity,
            'location': diag.location,
            'spelling': diag.spelling,
            'ranges': diag.ranges,
            'fixits': diag.fixits}


def dump_diag_info(tu):
    """
    Dump diagnostic info.

    :param clang.cindex.TranslationUnit tu: The translation unit.

    :return:
    """
    print('-------------------------------------------------------------------------------')
    print('DIAGNOSTIC INFORMATION')
    print('-------------------------------------------------------------------------------')
    pprint(('diags', map(get_diag_info, tu.diagnostics)))
    print('-------------------------------------------------------------------------------\n\n')


def generate_class_template(klass):
    """
    Generate binding text for a class template.

    :param Binder klass: The binder.
    """
    fixme = False

    # Header file
    txt = '// ' + klass.location + '\n'

    if klass.qname in _excluded_classes:
        fixme = True

    # Template parameters. Bit of a hack since the qualified types are not present in the regular
    # cursor.type.spelling.
    template_params = klass.template_parameters
    template_interface = []
    for t in template_params:
        spelling = t.dname
        type_ = t.type.spelling
        if spelling == type_:
            type_ = 'typename'
        template_interface.append(type_ + ' ' + spelling)

    # Template binding function
    t = ', '.join(template_interface)
    txt += 'template <{}>\n'.format(t)
    txt += 'void bind_{}(py::object &mod, std::string const &name) {{\n\n'.format(klass.spelling)

    # Generate class template text as a class binder
    cls = Binder(klass.cursor)
    cls.pname_override = 'name.c_str()'
    cls.generate()
    t = cls.txt
    t = t.replace("cls_name.c_str()", 'cls')
    t = t.replace('\"name.c_str()\"', 'name.c_str()')

    # Replace name of underlying type with typedef name. This is sometimes needed for
    # nested classes like NCollection_Sequence::Iterator.
    t = t.replace(klass.spelling + '::', klass.dname + '::')

    txt += t
    txt += '};\n\n'

    klass.fixme, klass.txt = fixme, txt


def relevant_includes_of_template(cursor):
    """
    Find the relevant include files for a class template cursor.

    :param clang.cindex.Cursor cursor: The cursor.

    :return: List of include files.
    :rtype: list[str]
    """
    include_files = []

    def _add(files_):
        for f_ in files_:
            if not f_:
                continue
            if f_ not in include_files:
                include_files.append(f_)

    # Base class types
    for base in get_children_of_kind(cursor, CursorKind.CXX_BASE_SPECIFIER):
        files = include_files_of_type(base.type)
        _add(files)

    # Constructor argument types
    for ctor in get_children_of_kind(cursor, CursorKind.CONSTRUCTOR):
        for arg in get_children_of_kind(ctor, CursorKind.PARM_DECL):
            files = include_files_of_type(arg.type)
            _add(files)

    # Public methods
    for method in get_children_of_kind(cursor, CursorKind.CXX_METHOD):
        # Return type
        files = include_files_of_type(method.result_type)
        _add(files)
        # Arguments
        for arg in method.get_arguments():
            files = include_files_of_type(arg.type)
            _add(files)

    # Pure virtual methods that might show up in the trampoline callback
    pure_virtual_methods = get_remaining_pure_virtual_functions(cursor)
    for method in pure_virtual_methods:
        # Return type
        files = include_files_of_type(method.result_type)
        _add(files)
        # Arguments
        for arg in method.get_arguments():
            files = include_files_of_type(arg.type)
            _add(files)

    # Location of class template
    f = include_file_of_cursor(cursor)
    _add([f])

    return include_files


def generate_immutable_inout_function(func, qname):
    """
    Generate binding for a function that modifies immutable types in place.

    :param Binder func: The binder.
    :param str qname: The function fully qualified name.

    :return: The binding text.
    :rtype: str
    """
    fwarn.write('Inout: {}\n'.format(qname))

    # Separate const and non-const input arguments
    args = []
    non_const_immutable_args = []
    i = 0
    for arg in func.arguments:
        type_ = arg.type.spelling
        name = arg.spelling
        if not name:
            name = 'a{}'.format(str(i))
            i += 1
        if not arg.is_const_parm and arg.is_immutable and arg.is_pointer_like:
            non_const_immutable_args.append((type_, name))
        args.append((type_, name))

    # All arguments
    is_static = True
    if args:
        delimiter = ', '
    else:
        delimiter = ''
    if func.is_static_method:
        interface_txt = '(' + ', '.join([type_ + ' ' + name for type_, name in args]) + ')'
    else:
        interface_txt = '({} &self{}'.format(func.parent.type.spelling, delimiter) + ', '.join([type_ + ' ' + name for type_, name in args]) + ')'
        is_static = False

    # Function call
    is_void = False
    if func.rtype.spelling == 'void':
        is_void = True
    args_txt = ', '.join([name for _, name in args])
    if is_static:
        fcall = qname
    else:
        fcall = 'self.{}'.format(func.spelling)

    # Return type
    rtype = func.rtype.spelling

    if is_void:
        func_txt = '{{ {}({}); '.format(fcall, args_txt)
    else:
        func_txt = '{{ {} rv = {}({}); '.format(rtype, fcall, args_txt)

    return_args = ', '.join([name for _, name in non_const_immutable_args])
    return_types = ', '.join([type_ for type_, _ in non_const_immutable_args])
    if is_void:
        if len(non_const_immutable_args) > 1:
            return_txt = 'return std::tuple<{}>({}); }}'.format(return_types, return_args)
        else:
            return_txt = 'return ' + return_args + '; }'
    else:
        return_txt = 'return std::tuple<{}, {}>(rv, {}); }}'.format(rtype, return_types, return_args)

    # Binding text
    bind_txt = '[]' + interface_txt + func_txt + return_txt
    return bind_txt


def generate_docs(gen):
    """
    Generate sphinx docs.

    :param BindOCCT gen: The main generator.
    """
    mods = [mod.name for mod in gen.modules]
    mods.sort()

    fout = open('api.rst', 'w')
    fout.write('API\n')
    fout.write('===\n\n')
    for mod in mods:
        fout.write(mod + '\n')
        fout.write('-' * len(mod) + '\n')
        fout.write('.. automodule:: OCCT.{}\n\n'.format(mod))
    fout.close()
