# This file is part of pyOCCT_binder which automatically generates Python
# bindings to the OpenCASCADE geometry kernel using pybind11.
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
# TODO Error handling types
# TODO stdout types
# TODO Immutable types
# TODO Unscoped enums?
# TODO AdvApp2Var binding all kinds of stuff
import os
from collections import OrderedDict, defaultdict
from ctypes import c_uint

from binder import cymbal
from binder.clang.cindex import (AccessSpecifier, Index, TranslationUnit,
                                 CursorKind, TypeKind, Cursor)
from binder.common import src_prefix, available_mods, py_operators

# Patches for libclang
cymbal.monkeypatch_cursor('get_specialization',
                          'clang_getSpecializedCursorTemplate',
                          [Cursor], Cursor)

cymbal.monkeypatch_cursor('get_template_kind',
                          'clang_getTemplateCursorKind',
                          [Cursor], c_uint)

cymbal.monkeypatch_cursor('get_num_overloaded_decl',
                          'clang_getNumOverloadedDecls',
                          [Cursor], c_uint)

cymbal.monkeypatch_cursor('get_overloaded_decl',
                          'clang_getOverloadedDecl',
                          [Cursor, c_uint], Cursor)

# cymbal.monkeypatch_type('get_num_template_arguments',
#                         'clang_Type_getNumTemplateArguments',
#                         [Type], c_uint)

# cymbal.monkeypatch_type('get_template_argument_type',
#                         'clang_Type_getTemplateArgumentAsType',
#                         [Type, c_uint], Type)

logger = open('log.txt', 'w')


class Generator(object):
    """
    Main class for OCCT header parsing and binding generation.

    :ivar str name: Name of the main package.
    """

    package_name = 'OCCT'

    all_types = defaultdict(set)

    available_mods = set()
    available_incs = set()
    available_templates = set()

    excluded_classes = set()
    excluded_functions = set()
    excluded_enums = set()
    excluded_fnames = set()
    excluded_mods = set()
    excluded_bases = dict()
    excluded_typedefs = set()

    import_guards = dict()
    extra_headers = dict()
    python_names = dict()
    nodelete = set()

    _mods = OrderedDict()

    def __init__(self, occt_include_dir):
        self._indx = Index.create()

        # Primary include directories
        self._main_includes = [occt_include_dir]

        # Include directories
        self.include_dirs = []

        # Compiler arguments
        self.compiler_args = []

        # Sort priority
        self._sort = {}

        # Translation unit and main cursor
        self._tu = None
        self._tu_binder = None

        # Build available include files
        occt_incs = os.listdir(occt_include_dir)
        Generator.available_incs = set(occt_incs)

    @property
    def tu(self):
        """
        :return: The translation unit.
        :rtype: clang.cindex.TranslationUnit
        """
        return self._tu

    @property
    def tu_binder(self):
        """
        :return: The translation unit binder.
        :rtype: binder.core.CursorBinder
        """
        return self._tu_binder

    @property
    def modules(self):
        """
        :return: The modules.
        :rtype: list(binder.core.Module)
        """
        return list(self._mods.values())

    def process_config(self, fn):
        """
        Process a configuration file.

        :param str fn: The file.

        :return: None.
        """
        logger.write('Processing configuration file: {}.\n'.format(fn))
        with open(fn, 'r') as f:
            for line in f:
                line = line.strip()

                # Line comment
                if line.startswith('#'):
                    continue

                # Include directory
                if line.startswith('+include'):
                    line = line.replace('+include', '')
                    line = line.strip()
                    self.include_dirs.append(line)
                    continue

                # Compiler argument
                if line.startswith('+arg'):
                    line = line.replace('+arg', '')
                    line = line.strip()
                    self.compiler_args.append(line)
                    continue

                # Sort order
                if line.startswith('+sort'):
                    line = line.replace('+sort', '')
                    line = line.strip()
                    mod, loc = line.split(':')
                    mod = mod.strip()
                    loc = loc.strip()
                    self._sort[mod] = int(loc)
                    continue

                # Excluded classes
                if line.startswith('-class'):
                    line = line.replace('-class', '')
                    line = line.strip()
                    self.excluded_classes.add(line)
                    continue

                # Excluded typedefs
                if line.startswith('-typedef'):
                    line = line.replace('-typedef', '')
                    line = line.strip()
                    self.excluded_typedefs.add(line)
                    continue

                # Excluded functions
                if line.startswith('-function*'):
                    line = line.replace('-function*', '')
                    line = line.strip()
                    self.excluded_fnames.add(line)
                    continue

                if line.startswith('-function'):
                    line = line.replace('-function', '')
                    line = line.strip()
                    self.excluded_functions.add(line)
                    continue

                # Excluded enums
                if line.startswith('-enum'):
                    line = line.replace('-enum', '')
                    line = line.strip()
                    self.excluded_enums.add(line)
                    continue

                # Excluded modules
                if line.startswith('-module'):
                    line = line.replace('-module', '')
                    line = line.strip()
                    self.excluded_mods.add(line)
                    continue

                # Import guards
                if line.startswith('+iguard'):
                    line = line.replace('+iguard', '')
                    line = line.strip()
                    mod, other = line.split(':')
                    mod = mod.strip()
                    other = other.strip()
                    if mod in self.import_guards:
                        self.import_guards[mod].add(other)
                    else:
                        self.import_guards[mod] = {other}
                    continue

                # Extra headers
                if line.startswith('+header'):
                    line = line.replace('+header', '')
                    line = line.strip()
                    type_, header = line.split(':')
                    type_ = type_.strip()
                    header = header.strip()
                    if type_ in self.extra_headers:
                        self.extra_headers[type_].append(header)
                    else:
                        self.extra_headers[type_] = [header]
                    continue

                # Python names
                if line.startswith('+pname'):
                    line = line.replace('+pname', '')
                    line = line.strip()
                    type_, name = line.split(':')
                    type_ = type_.strip()
                    name = name.strip()
                    self.python_names[type_] = name
                    continue

                # nodelete
                if line.startswith('+nodelete'):
                    line = line.replace('+nodelete', '')
                    line = line.strip()
                    self.nodelete.add(line)
                    continue

                # Excluded bases
                if line.startswith('-base'):
                    line = line.replace('-base', '')
                    line = line.strip()
                    qname, base = line.split(':', 1)
                    qname = qname.strip()
                    base = base.strip()
                    if qname in self.excluded_bases:
                        self.excluded_bases[qname].append(base)
                    else:
                        self.excluded_bases[qname] = [base]
                    continue

    def parse(self, file_, *args):
        """
        Parse the main include file.

        :param str file_: The main include file to parse.
        :param str args: Extra arguments to pass to the compiler.

        :return: None
        """
        logger.write('Parsing headers...\n')

        args = list(args)
        for arg in self.compiler_args:
            args.append(arg)
            logger.write('\tCompiler argument: {}\n'.format(arg))

        for path in self.include_dirs + self._main_includes:
            args += [''.join(['-I', path])]
            logger.write('\tInclude path: {}\n'.format(path))

        self._tu = self._indx.parse(file_, args,
                                    options=TranslationUnit.PARSE_INCOMPLETE)
        logger.write('done.\n\n')

        self._tu_binder = CursorBinder(self.tu.cursor)

    def dump_diagnostics(self):
        """
        Dump diagnostic information.

        :return: None.
        """
        print('----------------------')
        print('DIAGNOSTIC INFORMATION')
        print('----------------------')
        for diag in self.tu.diagnostics:
            print('---')
            print('SEVERITY: {}'.format(diag.severity))
            print('LOCATION: {}'.format(diag.location))
            print('MESSAGE: {}'.format(diag.spelling))
            print('---')
        print('----------------------')

    def save(self, fname):
        """
        Save the TranslationUnit to a file.

        :param str fname: The filename.

        :return: None.
        """
        self.tu.save(fname)

    def load(self, fname):
        """
        Load a TranslationUnit from a saved AST file.

        :param str fname: The filename.

        :return: None.
        """
        self._tu = TranslationUnit.from_ast_file(fname, self._indx)

    def traverse(self):
        """
        Traverse parsed headers and gather binders.

        :return: None.
        """
        logger.write('Traversing...\n')
        # Traverse the translation unit and group the binders into modules
        for binder in self.tu_binder.get_children():
            # Only bind definitions
            if not binder.is_definition:
                continue

            # Bind only these types of cursors
            if binder.kind not in [CursorKind.CLASS_DECL,
                                   CursorKind.STRUCT_DECL,
                                   CursorKind.FUNCTION_DECL,
                                   CursorKind.ENUM_DECL,
                                   CursorKind.TYPEDEF_DECL,
                                   CursorKind.CLASS_TEMPLATE]:
                continue

            # Skip if it's a "Handle_*" definition
            if binder.spelling.startswith('Handle_'):
                continue

            # Add binder only if it's in an OCCT header file.
            inc = binder.filename
            if inc not in self.available_incs:
                continue

            # Add binder if it's in an available module
            mod_name = binder.module_name
            if mod_name not in available_mods:
                continue

            # Add to module
            mod = self.get_module(mod_name)
            if not mod:
                continue

            qname = binder.qualified_name
            if binder.is_enum:
                mod.enums.append(binder)
                logger.write('\tFound enum: {}\n'.format(qname))
            elif binder.is_function:
                mod.funcs.append(binder)
                logger.write('\tFound function: {}\n'.format(qname))
            elif binder.is_class:
                mod.classes.append(binder)
                logger.write('\tFound class: {}\n'.format(qname))
            elif binder.is_typedef:
                mod.typedefs.append(binder)
                logger.write('\tFound typedef: {}\n'.format(qname))
            elif binder.is_class_template:
                mod.templates.append(binder)
                logger.write('\tFound class template: {}\n'.format(qname))
            else:
                logger.write('\tFound unknown cursor: {}\n'.format(qname))

        logger.write('done.\n\n')

    def build_includes(self):
        """
        Build include files for the modules.

        :return: None.
        """
        for mod in self.modules:
            mod.build_includes()

    def build_imports(self):
        """
        Build module imports.

        :return: None.
        """
        for mod in self.modules:
            for inc_file in mod.includes:
                if inc_file is None:
                    continue
                if '_' in inc_file:
                    delim = '_'
                else:
                    delim = '.'
                try:
                    other_name = inc_file.split(delim)[0]
                except (IndexError, AttributeError):
                    continue

                other = self.get_module(other_name)
                if not other:
                    continue

                # Don't add this module
                if mod.name == other.name:
                    continue

                # Add import
                if other not in mod.imports:
                    mod.imports.append(other)

    def sort_binders(self):
        """
        Sort class binders so they are ordered based on their base
        classes.

        :return: None.
        """
        logger.write('Sorting binders...\n')
        for mod in self.modules:
            mod.sort_binders()
        logger.write('done.\n\n')

    def bind(self, path='./output/src'):
        """
        Bind the library.

        :param str path: Path to write sub-folders.

        :return:
        """
        logger.write('Binding types...\n')
        for mod in self.modules:
            mod.bind(path)
        logger.write('done.\n\n')

    def is_module(self, name):
        """
        Check if the name is an available module.

        :param str name: The name.

        :return: *True* if an available module, *False* otherwise.
        :rtype: bool
        """
        return name in self._mods

    @classmethod
    def get_module(cls, name):
        """
        Get a module by name or return a new one.

        :param str name: Module name.

        :return: The existing module or new one.
        :rtype: binder.core.Module
        """
        if name not in available_mods:
            return None

        try:
            return cls._mods[name]
        except KeyError:
            mod = Module(name)
            cls._mods[name] = mod
            return mod


class Module(object):
    """
    Module class containing binders.

    :param str name: Module name.

    :ivar str name: Module name.
    :ivar list(str) includes: List of relevant include files for this module.
    :ivar list(binder.core.CursorBinder) enums: List of binders around
        enumerations.
    :ivar list(binder.core.CursorBinder) funcs: List of binders around
        functions.
    :ivar list(binder.core.CursorBinder) classes: List of binders around
        classes.
    :ivar list(binder.core.CursorBinder) typedefs: List of binders around
        typedefs.
    :ivar list(binder.core.CursorBinder) templates: List of binders around
        class templates.
    :ivar list(binder.core.Module) imports: List of other modules to import.
    :ivar list(binder.core.CursorBinder) sorted_binders: List of binders after
        sorting.
    """

    def __init__(self, name):
        self.name = name

        self.enums = []
        self.funcs = []
        self.classes = []
        self.typedefs = []
        self.templates = []

        self.sorted_binders = []

        self.includes = []
        self.imports = []

    def __repr__(self):
        return 'Module: {}'.format(self.name)

    def sort_binders(self):
        """
        Sort class binders so they are ordered based on their base
        classes.

        :return: None.
        """
        self.sorted_binders = self.enums  # + self.funcs + self.classes

        # TODO Sort types
        # binders1 = list(self.classes)
        # canonical2original = {}
        # # Use canonical for typedefs
        # for binder in self.typedefs:
        #     ut = binder.underlying_typedef_type
        #     binders1.append(ut.get_canonical().get_declaration())
        #     canonical2original[binders1[-1]] = binder
        #
        # binders2 = [b.qualified_name for b in binders1]
        # if not binders2:
        #     return None
        #
        # repeat = True
        # while repeat:
        #     repeat = False
        #
        #     for b in binders1:
        #         if b.qualified_name not in binders2:
        #             continue
        #         i1 = binders2.index(b.qualified_name)
        #         for dep in b.all_bases:
        #             dep = dep.get_definition()
        #             if dep.qualified_name not in binders2:
        #                 continue
        #             i2 = binders2.index(dep.qualified_name)
        #             if i1 < i2:
        #                 binders1[i1], binders1[i2] = (binders1[i2],
        #                                               binders1[i1])
        #                 binders2[i1], binders2[i2] = (binders2[i2],
        #                                               binders2[i1])
        #                 repeat = True
        #
        #                 n1 = binders1[i2].spelling
        #                 n2 = binders1[i1].spelling
        #                 msg = '\tSwapping {}<-->{}.\n'.format(n1, n2)
        #                 logger.write(msg)
        #
        # for binder in binders1:
        #     if binder in canonical2original:
        #         self.sorted_binders.append(canonical2original[binder])
        #     else:
        #         self.sorted_binders.append(binder)

    def build_includes(self):
        """
        Build list of include files for the module.

        :return: None.
        """
        for binder in self.sorted_binders:
            # TODO Handle overloads in include generation
            # binders = self.get_overloaded(binder.spelling)
            # if not binders:
            binders = [binder]
            for obinder in binders:
                temp = obinder.build_includes()
                for f in temp:
                    if f not in self.includes:
                        self.includes.append(f)

    def is_dependent(self, other):
        """
        Check to see if the this module is dependent on the other module based on their imports.

        :param binder.core.Module other: The other module.

        :return: *True* if dependent, *False* otherwise.
        :rtype: bool
        """
        if not self.imports and not other.imports:
            return False

        visited, stack = set(), list(self.imports)
        while stack:
            mod = stack.pop()
            if mod in visited:
                continue
            visited.add(mod)
            if mod.name == other.name:
                return True
            stack += list(mod.imports)
        return False

    def is_circular(self, other):
        """
        Check if this module and the other try to import each other.

        :param binder.core.Module other: The other module.

        :return: *True* if circular, *False* otherwise.
        :rtype: bool
        """
        return self.is_dependent(other) and other.is_dependent(self)

    def bind_templates(self, path='./inc'):
        """
        Bind templates.

        :param str path: Path to write templates.

        :return:
        """
        # Create module folder
        folder = '/'.join([path])
        if not os.path.isdir(folder):
            os.makedirs(folder)

        # Get ordered binders and generate source
        binders = self.templates
        for binder in binders:
            binder.bind(folder)

    def bind(self, path='.'):
        """
        Bind the module.

        :param str path: Path to write sub-directory.

        :return: None.
        """
        # Create module folder and main source file
        folder = '/'.join([path, self.name])
        if not os.path.isdir(folder):
            os.makedirs(folder)
        fname = '/'.join([folder, self.name + '.cxx'])
        fout = open(fname, 'w')

        # Get ordered binders and generate source
        binders = self.sorted_binders
        for binder in binders:
            binder.bind(folder)

        # File header
        fout.write(src_prefix)

        # Include common header
        fout.write('#include <pyOCCT_Common.hxx>\n\n')

        # Interface definitions
        for binder in binders:
            interface = binder.bind_name
            if interface is None:
                continue
            fout.write('void {}(py::module &);\n'.format(interface))
        fout.write('\n')

        # Initialize
        fout.write('PYBIND11_MODULE({}, mod) {{\n\n'.format(self.name))

        # Stop here if module is excluded

        # Import other modules
        has_guards = self.name in Generator.import_guards
        guarded = set()
        if has_guards:
            guarded = Generator.import_guards[self.name]
        for mod in self.imports:
            if mod.name in guarded:
                continue
            if mod.name != self.name:
                fout.write('py::module::import(\"{}.{}\");\n'.format(
                    Generator.package_name, mod.name))
        fout.write('\n')

        # Import guards
        for mod_name in guarded:
            fout.write('struct Import{}{{\n'.format(mod_name))
            fout.write(
                '\tImport{}() {{ py::module::import(\"{}.{}\"); }}\n'.format(
                    mod_name, Generator.package_name, mod_name))
            fout.write('};\n\n')

        # Call bind functions
        for binder in binders:
            interface = binder.bind_name
            if interface is None:
                continue
            fout.write('{}(mod);\n'.format(interface))
        fout.write('\n')

        # End module
        fout.write('}\n')
        fout.close()


class CursorBinder(object):
    """
    Binder for cursors.

    :param clang.cindex.Cursor cursor: The underlying cursor.

    :ivar clang.cindex.Cursor cursor: The underlying cursor.
    :ivar binder.core.CursorBinder alias: The alias of this binder if applicable.
    :ivar str parent_name: The name of the binding parent.
    :ivar str python_name: Name for binder in Python if different than spelling.
    :ivar str bind_name: Function name for binding.
    :ivar list(str) includes: List of relevant include files for this binder.
    :ivar str module_name: The module name for this binder.
    :ivar str filename: The file where this binder is located.
    """

    def __init__(self, cursor):
        self.cursor = cursor
        self.alias = None
        self.parent_name = 'mod'
        self._pname = None
        self.bind_name = None
        self.includes = []

        # Filename
        try:
            fname = cursor.location.file.name
            fname = fname.replace('\\', '/').split('/')[-1]
        except AttributeError:
            fname = None
        self.filename = fname

        # Module name based on filename
        name = '__None__'
        if fname is not None:
            name = fname
            delimiter = '.'
            if '_' in name:
                delimiter = '_'
            name = name.split(delimiter)[0]
        self.module_name = name

    def __hash__(self):
        return self.cursor.hash

    def __eq__(self, other):
        return self.cursor.hash == other.cursor.hash

    def __repr__(self):
        return 'Cursor: {} ({})'.format(self.qualified_name, self.kind)

    @property
    def kind(self):
        """
        :return: The cursor kind.
        :rtype: clang.cindex.CursorKind
        """
        try:
            return self.cursor.kind
        except AttributeError:
            return CursorKind.NO_DECL_FOUND

    @property
    def type(self):
        """
        :return: The cursor type.
        :rtype: binder.core.TypeBinder
        """
        return TypeBinder(self.cursor.type)

    @property
    def canonical(self):
        """
        :return: The canonical cursor.
        :rtype: binder.core.CursorBinder
        """
        return CursorBinder(self.cursor.canonical)

    @property
    def underlying_typedef_type(self):
        """
        :return: The cursor underlying typedef type.
        :rtype: binder.core.TypeBinder
        """
        return TypeBinder(self.cursor.underlying_typedef_type)

    @property
    def rtype(self):
        """
        :return: The cursor result type.
        :rtype: binder.core.TypeBinder
        """
        return TypeBinder(self.cursor.result_type)

    @property
    def display_name(self):
        """
        :return: The display name.
        :rtype: str
        """
        try:
            return self.cursor.displayname
        except AttributeError:
            return 'NULL'

    @property
    def spelling(self):
        """
        :return: The spelling.
        :rtype: str
        """
        return self.cursor.spelling

    @property
    def no_decl(self):
        return self.kind == CursorKind.NO_DECL_FOUND

    @property
    def is_null(self):
        return self.cursor is None or self.kind == CursorKind.NO_DECL_FOUND

    @property
    def is_tu(self):
        return self.kind == CursorKind.TRANSLATION_UNIT

    @property
    def is_enum(self):
        return self.kind == CursorKind.ENUM_DECL

    @property
    def is_enum_constant(self):
        return self.kind == CursorKind.ENUM_CONSTANT_DECL

    @property
    def is_function(self):
        return self.kind == CursorKind.FUNCTION_DECL

    @property
    def is_class(self):
        return self.kind in [CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL]

    @property
    def is_typedef(self):
        return self.kind == CursorKind.TYPEDEF_DECL

    @property
    def is_cxx_base(self):
        return self.kind == CursorKind.CXX_BASE_SPECIFIER

    @property
    def is_constructor(self):
        return self.kind == CursorKind.CONSTRUCTOR

    @property
    def is_destructor(self):
        return self.kind == CursorKind.DESTRUCTOR

    @property
    def is_cxx_method(self):
        return self.kind == CursorKind.CXX_METHOD

    @property
    def is_param(self):
        return self.kind == CursorKind.PARM_DECL

    @property
    def is_field(self):
        return self.kind == CursorKind.FIELD_DECL

    @property
    def is_template_ref(self):
        return self.kind == CursorKind.TEMPLATE_REF

    @property
    def is_class_template(self):
        return self.kind == CursorKind.CLASS_TEMPLATE

    @property
    def is_function_template(self):
        return self.kind == CursorKind.FUNCTION_TEMPLATE

    @property
    def is_template_type_param(self):
        return self.kind == CursorKind.TEMPLATE_TYPE_PARAMETER

    @property
    def is_using_decl(self):
        return self.kind == CursorKind.USING_DECLARATION

    @property
    def is_overloaded_decl_ref(self):
        return self.kind == CursorKind.OVERLOADED_DECL_REF

    @property
    def is_cxx_access_spec(self):
        return self.kind == CursorKind.CXX_ACCESS_SPEC_DECL

    @property
    def is_type_ref(self):
        return self.kind == CursorKind.TYPE_REF

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
    def is_definition(self):
        return self.cursor.is_definition()

    @property
    def is_virtual_method(self):
        return self.cursor.is_virtual_method()

    @property
    def is_pure_virtual_method(self):
        return self.cursor.is_pure_virtual_method()

    @property
    def is_abstract(self):
        return self.cursor.is_abstract_record()

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
    def is_excluded(self):
        """
        :return: Check if the cursor is excluded.
        :rtype: bool
        """
        if self.is_enum:
            return self.qualified_name in Generator.excluded_enums
        elif self.is_function or self.is_constructor:
            return self.qualified_name in Generator.excluded_functions
        elif self.is_class or self.is_class_template:
            return self.qualified_name in Generator.excluded_classes
        elif self.is_typedef:
            return self.qualified_name in Generator.excluded_typedefs
        elif self.is_cxx_method:
            # Check if method name or qualified name is excluded
            name, fname = self.qualified_name, self.spelling
            if self.is_static_method:
                name += '_'
                fname += '_'
            return (name in Generator.excluded_functions or
                    fname in Generator.excluded_fnames)

        return False

    @property
    def is_transient(self):
        """
        :return: Check if cursor is either Standard_Transient type or derived
            from it.
        :rtype: bool
        """
        return (self.spelling == 'Standard_Transient' or
                self.is_derived_from('Standard_Transient'))

    @property
    def is_operator(self):
        if self.is_function or self.is_cxx_method:
            return self.spelling in py_operators
        return False

    @property
    def is_nested(self):
        """
        Check if binder is nested in a class, struct, or class template.

        :return: *True* if nested, *False* otherwise.
        :rtype: bool
        """
        parent = self.parent
        if parent.is_tu:
            return False
        # if parent.is_class or parent.is_class_template:
        #     return True
        return True

    @property
    def qualified_name(self):
        """
        :return: The fully qualified displayed name.
        :rtype: str
        """
        names = []
        b = self
        while not b.is_null and not b.is_tu:
            name = b.display_name
            if name:
                names.append(b.display_name)
            else:
                break
            b = b.parent
        names.reverse()
        qname = '::'.join(names)

        if 'operator()' in qname:
            # Hack for call operator...
            qname = qname.split('()')[0]
            return ''.join([qname, '()'])
        # Don't return function interface portion
        elif '(' in qname:
            return qname.split('(')[0]
        else:
            return qname

    @property
    def qualified_spelling(self):
        """
        :return: The fully qualified spelling.
        :rtype: str
        """
        names = []
        b = self
        while not b.is_null and not b.is_tu:
            name = b.spelling
            if name:
                names.append(b.spelling)
            else:
                break
            b = b.parent
        names.reverse()
        return '::'.join(names)

    @property
    def python_name(self):
        """
        :return: The Python name. If *None* then the spelling is returned.
        :rtype: str
        """
        if self._pname is not None:
            return self._pname
        name = self.qualified_spelling
        name = name.replace('::', '_')
        name = name.replace('::', '<')
        name = name.replace('::', '>')
        return name

    @python_name.setter
    def python_name(self, pname):
        self._pname = pname

    @property
    def parent(self):
        """
        :return: The parent binder.
        :rtype: binder.core.CursorBinder
        """
        return CursorBinder(self.cursor.semantic_parent)

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
    def bases(self):
        """
        :return: List of base classes.
        :rtype: list(binder.core.CursorBinder)
        """
        return self.get_children_of_kind(CursorKind.CXX_BASE_SPECIFIER)

    @property
    def all_bases(self):
        """
        :return: All base classes.
        :rtype: list(binder.core.CursorBinder)
        """

        def _get_bases(_c):
            for base in _c.bases:
                bases.append(base)
                _c = base.type.get_declaration()
                _get_bases(_c)

        bases = []
        _get_bases(self)
        return bases

    @property
    def ctors(self):
        """
        :return: List of constructors.
        :rtype: list(binder.core.CursorBinder)
        """
        return self.get_children_of_kind(CursorKind.CONSTRUCTOR)

    @property
    def dtors(self):
        """
        :return: List of destructors.
        :rtype: list(binder.core.CursorBinder)
        """
        return self.get_children_of_kind(CursorKind.DESTRUCTOR)

    @property
    def has_public_dtor(self):
        """
        :return: Check if the binder has a public destructor.
        :rtype: bool
        """
        dtors = self.get_children_of_kind(CursorKind.DESTRUCTOR, True)
        return len(dtors) > 0

    @property
    def fields(self):
        """
        :return: List of fields.
        :rtype: list(binder.core.CursorBinder)
        """
        return self.get_children_of_kind(CursorKind.FIELD_DECL)

    @property
    def enums(self):
        """
        :return: List of enums.
        :rtype: list(binder.core.CursorBinder)
        """
        return self.get_children_of_kind(CursorKind.ENUM_DECL)

    @property
    def methods(self):
        """
        :return: List of class methods.
        :rtype: list(binder.core.CursorBinder)
        """
        return self.get_children_of_kind(CursorKind.CXX_METHOD)

    @property
    def parameters(self):
        """
        :return: List of parameters.
        :rtype: list(binder.core.CursorBinder)
        """
        return self.get_children_of_kind(CursorKind.PARM_DECL)

    @property
    def default_value(self):
        """
        :return: A string representation of the default value if available
            (e.g., "=0"). If not available returns an empty string.
        :rtype: str
        """
        if not self.is_param:
            return ''
        txt = ''
        for t in self.cursor.get_tokens():
            txt += t.spelling
        if not txt or '=' not in txt:
            return ''
        return txt.split('=')[-1]

    @property
    def enum_constants(self):
        """
        :return: List of enum constant binders.
        :type: list(binder.core.CursorBinder)
        """
        return self.get_children_of_kind(CursorKind.ENUM_CONSTANT_DECL)

    @property
    def template_parameters(self):
        """
        :return: List of template parameters.
        :type: list(binder.core.CursorBinder)
        """
        params = []
        for child in self.get_children():
            if (child.kind == CursorKind.TEMPLATE_TYPE_PARAMETER or
                    child.kind == CursorKind.TEMPLATE_NON_TYPE_PARAMETER):
                params.append(child)
        return params

    @property
    def needs_nodelete(self):
        """
        :return: Check to see if class needs py::nodelete
        :rtype: bool
        """
        # Check for hidden destructor of this class
        for dtor in self.dtors:
            if not dtor.is_public:
                return True
        return False

    def get_definition(self):
        """
        If the binder is a reference to a declaration or a declaration of
        some entity, return a binder that points to the definition of that
        entity.

        :return: The definition.
        :rtype: binder.core.CursorBinder
        """
        return CursorBinder(self.cursor.get_definition())

    def get_specialization(self):
        """
        If the binder is a specialization of a template, attempt to get the
        cursor of the template.

        :return: The definition.
        :rtype: binder.core.CursorBinder
        """
        return CursorBinder(self.cursor.get_specialization())

    def get_children(self):
        """
        Get children of binder.

        :return: The children.
        :rtype: list(binder.core.CursorBinder)
        """
        children = []
        for child in self.cursor.get_children():
            children.append(CursorBinder(child))
        return children

    def get_children_of_kind(self, kind, only_public=False):
        """
        Get children of a specified kind.

        :param clang.cindex.CursorKind kind: The cursor kind.
        :param bool only_public: Return only cursor that are public.

        :return: List of children.
        :rtype: list(binder.core.CursorBinder)
        """
        children = []
        for c in self.get_children():
            if c.kind != kind:
                continue
            if only_public and not c.is_public:
                continue
            children.append(c)
        return children

    def dfs(self):
        """
        Depth-first walk of all descendants.

        :return: List of descendants.
        :rtype: Generator(binder.core.CursorBinder)
        """
        for cursor in self.cursor.walk_preorder():
            if not cursor.kind.is_translation_unit():
                yield CursorBinder(cursor)

    def build_includes(self):
        """
        Get a list of relevant files to include for the binder.

        :return: List of include files.
        :rtype: list(str)
        """
        includes = ['pyOCCT_Common.hxx']

        # Extra headers
        qname = self.qualified_name
        if qname in Generator.extra_headers:
            for inc in Generator.extra_headers[qname]:
                includes.append(inc)

        # Traverse the binder and look for any type references.
        for item in self.dfs():
            if not item.is_type_ref and not item.is_template_ref:
                continue

            f = item.get_definition().filename
            if f is None:
                continue

            if f not in Generator.available_incs:
                continue

            if f not in includes:
                includes.append(f)

        # Add file for this type
        f = self.filename
        if f not in includes:
            includes.append(f)

        # Replace any .lxx or .gxx with .hxx
        for inc in includes:
            if '.lxx' in inc:
                inc = inc.replace('.lxx', '.hxx')
            elif '.gxx' in inc:
                inc = inc.replace('.gxx', '.hxx')
            self.includes.append(inc)

        return includes

    def is_derived_from(self, name):
        """
        Check to see if this binder is derived from the named type.

        :param str name: The base name.

        :return: *True* if derived from base, *False* otherwise.
        :rtype: bool
        """
        bases = self.all_bases
        for base in bases:
            # Hack in case base is a template
            try:
                base_spelling = base.get_definition().spelling
            except AttributeError:
                base_spelling = base.spelling
            if base_spelling == name:
                return True
        return False

    def bind(self, path):
        """
        Bind the type.

        :return: None.
        """
        logger.write('\tBinding {}.\n'.format(self.qualified_spelling))
        if self.is_enum:
            bind_enum(self, path)
        elif self.is_function:
            bind_function(self, path)
        elif self.is_class:
            bind_class(self, path)
        elif self.is_typedef:
            bind_typedef(self, path)
        elif self.is_class_template:
            bind_class_template(self, path)
        else:
            logger.write('\tUnsupported {}.\n'.format(self.qualified_spelling))

    def generate(self):
        """
        Generate the source text for the binder.

        :return: The source text.
        :rtype: list(str)
        """
        if self.is_enum:
            return generate_enum(self)
        elif self.is_function:
            return generate_function(self)
        elif self.is_class:
            return generate_class(self)
        elif self.is_typedef:
            return generate_typedef(self)
        elif self.is_class_template:
            return generate_class_template(self)
        elif self.is_cxx_method:
            return generate_method(self)
        elif self.is_field:
            return generate_field(self)
        elif self.is_constructor:
            return generate_ctor(self)

        return []


class TypeBinder(object):
    """
    Binder for types.

    :param clang.cindex.Type type_: The type.

    :ivar clang.cindex.Type type: The underlying type.
    """

    def __init__(self, type_):
        self.type = type_

    def __repr__(self):
        return 'Type: {} ({})'.format(self.spelling, self.kind)

    @property
    def spelling(self):
        """
        :return: The spelling.
        :rtype: str
        """
        return self.type.spelling

    @property
    def kind(self):
        """
        :return: The cursor kind.
        :rtype: clang.cindex.CursorKind
        """
        return self.type.kind

    @property
    def is_null(self):
        return self.type is None or self.kind == TypeKind.INVALID

    @property
    def is_record(self):
        return self.kind == TypeKind.RECORD

    @property
    def is_typedef(self):
        return self.kind == TypeKind.TYPEDEF

    @property
    def is_pointer(self):
        return self.kind == TypeKind.POINTER

    @property
    def is_lvalue(self):
        return self.kind == TypeKind.LVALUEREFERENCE

    @property
    def is_rvalue(self):
        return self.kind == TypeKind.RVALUEREFERENCE

    @property
    def is_pointer_like(self):
        return self.is_pointer or self.is_lvalue or self.is_rvalue

    @property
    def is_array_like(self):
        return self.kind in [TypeKind.CONSTANTARRAY, TypeKind.INCOMPLETEARRAY,
                             TypeKind.VARIABLEARRAY,
                             TypeKind.DEPENDENTSIZEDARRAY]

    @property
    def is_const_qualified(self):
        return self.type.is_const_qualified()

    def get_declaration(self):
        """
        Get the declaration of the type.

        :return: The declaration.
        :rtype: binder.core.CursorBinder
        """
        return CursorBinder(self.type.get_declaration())

    def get_canonical(self):
        """
        Get the canonical type.

        :return: The canonical type.
        :rtype: binder.core.TypeBinder
        """
        return TypeBinder(self.type.get_canonical())

    def get_pointee(self):
        """
        For pointer types, returns the type of the pointee.

        :return: The pointee.
        :rtype: binder.core.TypeBinder
        """
        return TypeBinder(self.type.get_pointee())


def bind_enum(binder, path):
    """
    Bind an enum.

    :param binder.core.CursorBinder binder: The binder.
    :param str path: The path to write the source file.

    :return: None.
    """
    src = []

    # Include files
    for inc in binder.includes:
        src.append('#include <{}>\n'.format(inc))
    src.append('\n')

    # Bind function name
    python_name = binder.python_name
    # Hack for "anonymous" enums
    if not python_name or python_name.startswith('(anonymous enum'):
        msg = '\tFound anonymous enum: {}\n'.format(binder.type.spelling)
        logger.write(msg)
        python_name = binder.enum_constants[0].spelling
    bind_name = '_'.join(['bind', python_name])
    binder.bind_name = bind_name

    # Bind function
    src.append('void {}(py::module &mod){{\n\n'.format(bind_name))

    # Generate source
    src += generate_enum(binder)
    src.append('\n')

    # End function
    src.append('}')

    # Write file
    fname = ''.join([path, '/', bind_name, '.cxx'])
    fout = open(fname, 'w')
    fout.write(src_prefix)
    fout.writelines(src)


def bind_function(binder, path):
    """
    Bind a function.

    :param binder.core.CursorBinder binder: The binder.
    :param str path: The path to write the source file.

    :return: None.
    """
    src = []

    # Get list of binders if function is overloaded
    binders = [binder]
    mod = Generator.get_module(binder.module_name)
    if mod:
        overloaded = mod.get_overloaded(binder.spelling)
        if overloaded:
            binders = overloaded

    # Include files
    used_includes = set()
    for binder in binders:
        for inc in binder.includes:
            if inc not in used_includes:
                src.append('#include <{}>\n'.format(inc))
                used_includes.add(inc)
    src.append('\n')

    # Bind function name
    for binder in binders:
        bind_name = '_'.join(['bind', binder.python_name])
        binder.bind_name = bind_name
    bind_name = binders[0].bind_name

    # Bind function
    src.append('void {}(py::module &mod){{\n\n'.format(bind_name))

    # Generate source
    for binder in binders:
        src += generate_function(binder)

    # End function
    src.append('}')

    # Write file
    fname = ''.join([path, '/', bind_name, '.cxx'])
    try:
        fout = open(fname, 'w')
        fout.write(src_prefix)
        fout.writelines(src)
    except IOError:
        logger.write('\tFailed to write file for {}.\n'.format(fname))
        for binder in binders:
            binder.bind_name = None


def bind_class(binder, path):
    """
    Bind a class.

    :param binder.core.CursorBinder binder: The binder.
    :param str path: The path to write the source file.

    :return: None.
    """
    src = []

    for inc in binder.includes:
        src.append('#include <{}>\n'.format(inc))
    src.append('\n')

    # Bind function name
    bind_name = '_'.join(['bind', binder.python_name])
    binder.bind_name = bind_name

    # Bind function
    src.append('void {}(py::module &mod){{\n\n'.format(bind_name))

    # Generate source
    src += generate_class(binder)
    src.append('\n')

    # End function
    src.append('}')

    # Write file
    fname = ''.join([path, '/', bind_name, '.cxx'])
    fout = open(fname, 'w')
    fout.write(src_prefix)
    fout.writelines(src)


def bind_typedef(binder, path):
    """
    Bind a typedef.

    :param binder.core.CursorBinder binder: The binder.
    :param str path: The path to write the source file.

    :return: None.
    """
    # Include files
    includes = []
    for inc in binder.includes:
        includes.append('#include <{}>\n'.format(inc))
    includes.append('\n')

    # Bind function name
    bind_name = '_'.join(['bind', binder.python_name])
    binder.bind_name = bind_name

    # Bind function
    src = ['void {}(py::module &mod){{\n\n'.format(bind_name)]

    # Generate source
    other_src, bind_template = generate_typedef(binder)

    # Comment if excluded
    if binder.is_excluded:
        other_src.insert(0, '/*\n')
        other_src.append('*/\n')
    src += other_src

    # Include template if needed
    if bind_template is None:
        includes = ['#include <pyOCCT_Common.hxx>\n']
        bind_template = []
    for template in bind_template:
        if template in Generator.available_templates:
            includes.append('#include <{}.hxx>\n'.format(template))
    if bind_template:
        includes.append('\n')

    src = includes + src
    src.append('\n')

    # End function
    src.append('}')

    # Write file
    fname = ''.join([path, '/', bind_name, '.cxx'])
    fout = open(fname, 'w')
    fout.write(src_prefix)
    fout.writelines(src)


def bind_class_template(binder, path):
    """
    Bind a class template.

    :param binder.core.CursorBinder binder: The binder.
    :param str path: The path to write the source file.

    :return: None.
    """

    # Include guard
    src = [
        '#ifndef __{}__\n'.format(binder.spelling),
        '#define __{}__\n\n'.format(binder.spelling)
    ]

    # Include files
    for inc in binder.includes:
        src.append('#include <{}>\n'.format(inc))
    src.append('\n')

    # Bind function name
    bind_name = '_'.join(['bind', binder.python_name])
    binder.bind_name = bind_name
    Generator.available_templates.add(binder.bind_name)

    # Function template
    template_params = ['typename ' + b.display_name for b in
                       binder.template_parameters]
    src.append('template <{}>\n'.format(', '.join(template_params)))

    # Bind function
    src.append(
        'void {}(py::module &mod, std::string const &name){{\n\n'.format(
            bind_name))

    # Generate source
    src += generate_class_template(binder)
    src.append('\n')

    # End function
    src.append('}\n\n')

    # End include guard
    src.append('#endif')

    # Write file
    fname = ''.join([path, '/', bind_name, '.hxx'])
    fout = open(fname, 'w')
    fout.write(src_prefix)
    fout.writelines(src)


def generate_enum(binder):
    """
    Generate source for enumeration.

    :param binder.core.CursorBinder binder: The binder.

    :return: List of binder source lines.
    :rtype: list(str)
    """
    src = []

    # Names
    qname = binder.qualified_name
    name = binder.python_name
    parent = binder.parent_name
    docs = binder.docs

    # Cast anonymous enum to int
    if binder.type.spelling.startswith('(anonymous enum'):
        for e in binder.enum_constants:
            name, qname = e.spelling, e.qualified_name
            txt = '{}.attr(\"{}\") = py::cast(int({}));\n'.format(parent,
                                                                  name,
                                                                  qname)
            src.append(txt)
    else:
        # Hack to handle ::enum_constant
        if not qname:
            qname = binder.type.spelling

        # Source
        txt = 'py::enum_<{}>({}, \"{}\", \"{}\")\n'.format(qname, parent, name,
                                                           docs)
        src.append(txt)
        for e in binder.enum_constants:
            # Hack to handle ::enum_constant
            qname = e.qualified_name
            if qname.startswith('::'):
                qname = ''.join([binder.type.spelling, qname])
            txt = '\t.value(\"{}\", {})\n'.format(e.spelling, qname)
            src.append(txt)
        src.append('\t.export_values();\n')

    # Comment if excluded
    if binder.is_excluded:
        src.insert(0, '/*\n')
        src.append('*/\n')

    return src


def generate_function(binder):
    """
    Generate source for function.

    :param binder.core.CursorBinder binder: The binder.

    :return: Binder source as a list of lines.
    :rtype: list(str)
    """
    # Names
    fname = binder.spelling
    qname = binder.qualified_name
    docs = binder.docs

    rtype = binder.rtype.spelling
    _, _, _, signature, _, is_array_like = function_signature(binder)
    if signature:
        signature = ', '.join(signature)
    else:
        signature = ''

    # Variable names and default values
    args = []
    for arg in binder.parameters:
        default_value = arg.default_value
        if default_value:
            default_value = '=' + default_value
        args.append('py::arg(\"{}\"){}'.format(arg.spelling, default_value))
    if args:
        args = ', ' + ', '.join(args)
    else:
        args = ''

    # Source
    interface = '({} (*) ({}))'.format(rtype, signature)
    src = ['mod.def(\"{}\", {} &{}, \"{}\"{});\n\n'.format(fname, interface,
                                                           qname, docs,
                                                           args)]

    # TODO How to handle arrays
    if True in is_array_like:
        src[0] = ' '.join(['//', src[0]])

    return src


def generate_class(binder):
    """
    Generate source for class.

    :param binder.core.CursorBinder binder: The binder.

    :return: Binder source as a list of lines.
    :rtype: list(str)
    """
    # Names
    name = binder.python_name
    qname = binder.qualified_name
    docs = binder.docs

    # Source variable
    cls = '_'.join(['cls', name])

    # Holder
    holder = ''
    if binder.is_transient:
        holder = ', opencascade::handle<{}>'.format(qname)
    elif binder.needs_nodelete or qname in Generator.nodelete:
        holder = ', std::unique_ptr<{}, py::nodelete>'.format(qname)

    base_names = []
    bases_classes = binder.bases
    try:
        excluded_bases = Generator.excluded_bases[qname]
    except KeyError:
        excluded_bases = []
    for base in bases_classes:
        if not base.is_public:
            continue
        name = base.qualified_spelling
        name = name.replace('class ', '')
        if name not in excluded_bases:
            base_names.append(name)
    if base_names:
        bases = ', ' + ', '.join(base_names)
    else:
        bases = ''

    # Figure out if py::multiple_inheritance is needed
    multi_base = ''
    if len(bases_classes) > 1 >= len(base_names):
        multi_base = ', py::multiple_inheritance()'

    # Name will be given if binding a class template
    if binder.is_class_template:
        name_ = 'name.c_str()'
    else:
        name_ = '\"{}\"'.format(binder.python_name)
    if qname in Generator.python_names:
        name_ = '\"{}\"'.format(Generator.python_names[qname])

    # Source
    src = ['py::class_<{}{}{}> {}(mod, {}, \"{}\"{});\n'.format(qname, holder,
                                                                bases, cls,
                                                                name_, docs,
                                                                multi_base)]

    # Constructors
    if not binder.is_abstract:
        src.append('\n// Constructors\n')
        for item in binder.ctors:
            if item.is_public:
                item.parent_name = cls
                src += generate_ctor(item)
        # TODO Default constructor

    # Fields
    src.append('\n// Fields\n')
    for item in binder.fields:
        if item.is_public:
            item.parent_name = cls
            src += generate_field(item)

    # Methods
    src.append('\n// Methods\n')
    for item in binder.methods:
        if item.is_public:
            item.parent_name = cls
            src += generate_method(item)

    # Enums
    src.append('\n// Enums\n')
    for item in binder.enums:
        if item.is_public:
            item.parent_name = cls
            src += generate_enum(item)

    # Comment if excluded
    if binder.is_excluded:
        src.insert(0, '/*\n')
        src.append('*/\n')

    return src


def generate_ctor(binder):
    """
    Generate source for class constructor.

    :param binder.core.CursorBinder binder: The binder.

    :return: Binder source as a list of lines.
    :rtype: list(str)
    """
    # TODO Copy ctor, call guards, abstract classes
    # TODO How to handle move constructor?

    ctors = []

    sig = function_signature(binder)
    nargs, ndefaults, args_name, args_type, defaults, is_array_like = sig

    for i in range(nargs - ndefaults, nargs + 1):
        names = args_name[0:i]
        types = args_type[0:i]

        signature = ', '.join(types)

        py_args = []
        for name in names:
            py_args.append(', py::arg(\"{}\")'.format(name))
        py_args = ''.join(py_args)

        src = '{}.def(py::init<{}>(){});\n'.format(binder.parent_name,
                                                   signature, py_args)
        # Comment if excluded
        if binder.is_excluded or binder.is_move_ctor:
            src = ' '.join(['//', src])
        ctors.append(src)

    return ctors


def generate_field(binder):
    """
    Generate source for class member fields.

    :param binder.core.CursorBinder binder: The binder.

    :return: Binder source as a list of lines.
    :rtype: list(str)
    """
    prefix = binder.parent_name
    name = binder.spelling
    qname = binder.qualified_name
    docs = binder.docs
    type_ = 'readwrite'
    if binder.type.is_const_qualified:
        type_ = 'readonly'

    src = [
        '{}.def_{}(\"{}\", &{}, \"{}\");\n'.format(prefix, type_, name, qname,
                                                   docs)]

    if binder.type.is_array_like:
        src[0] = ' '.join(['//', src[0]])

    return src


def generate_method(binder):
    """
    Generate source for class member function.

    :param binder.core.CursorBinder binder: The binder.

    :return: Binder source as a list of lines.
    :rtype: list(str)
    """
    # TODO Call guards, using declarations, immutable types, lambdas

    methods = []

    prefix = '{}'.format(binder.parent_name)

    if binder.is_static_method:
        is_static = '_static'
    else:
        is_static = ''

    fname = binder.spelling
    if is_static:
        fname += '_'

    # Comment if excluded or returns a pointer
    # TODO How to handle pointers?
    if binder.is_excluded or binder.rtype.is_pointer:
        prefix = '// {}'.format(prefix)

    rtype = binder.rtype.spelling
    qname = binder.qualified_name

    ptr = '*'
    if not binder.is_static_method:
        ptr = '::'.join([binder.parent.qualified_name, '*'])

    if binder.is_const_method:
        is_const = ' const'
    else:
        is_const = ''

    docs = binder.docs

    # Operators
    is_operator = ''
    if binder.is_operator:
        fname = py_operators[fname]
        # if '__i' not in name:
        is_operator = 'py::is_operator(), '

    sig = function_signature(binder)
    nargs, ndefaults, args_name, args_type, defaults, is_array_like = sig

    for i in range(nargs - ndefaults, nargs + 1):
        if i == nargs:
            names = args_name[0:i]
            types = args_type[0:i]

            signature = ', '.join(types)

            py_args = []
            for name in names:
                py_args.append(', py::arg(\"{}\")'.format(name))
            py_args = ''.join(py_args)

            src = '{}.def{}(\"{}\", ({} ({})({}){}) &{}, {}\"{}\"{});\n'.format(
                prefix, is_static,
                fname, rtype, ptr,
                signature, is_const,
                qname, is_operator,
                docs, py_args)

        else:
            arg_list = []
            args_spelling = []
            for j in range(0, i):
                arg_list.append(args_type[j])
                args_spelling.append(args_name[j])

            if is_static:
                signature = ''
            else:
                parts = qname.split('::')
                parent_spelling = '::'.join(parts[:-1])
                signature = parent_spelling + ' &self'

            k = 0
            call_args = []
            for arg_type_spelling in arg_list:
                if not signature:
                    signature += '{} {}'.format(arg_type_spelling,
                                                'a' + str(k))
                else:
                    signature += ', {} {}'.format(arg_type_spelling,
                                                  'a' + str(k))
                call_args.append('a' + str(k))
                k += 1
            call = ', '.join(call_args)

            if not is_static:
                qname_ = 'self.' + fname
            else:
                qname_ = qname

            src = '{}.def{}(\"{}\", []({}) -> {} {{ return {}({}); }});\n'.format(
                prefix, is_static, fname, signature, rtype, qname_, call)

        if True in is_array_like:
            src = ' '.join(['//', src])

        methods.append(src)

    return methods


def generate_typedef(binder):
    """
    Generate source for a typedef.

    :param binder.core.CursorBinder binder: The binder.

    :return: Binder source as a list of lines and extra headers if needed.
    :rtype: tuple(list(str), list(str))
    """
    if binder.spelling == 'BOPDS_DataMapIteratorOfDataMapOfPaveBlockListOfInteger':
        print()

    # Bind an alias
    alias = binder.alias
    this_module = binder.module_name
    if alias is not None:
        other_mod = alias.module_name
        if other_mod == this_module:
            # TODO What name to use? Python name?
            src = [
                'if (py::hasattr(mod, \"{}\")) {{\n'.format(alias.python_name),
                '\tmod.attr(\"{}\") = mod.attr(\"{}\");\n'.format(
                    binder.python_name, alias.python_name),
                '}\n'
            ]
        else:
            src = [
                'py::module other_mod = py::module::import(\"{}.{}\");\n'.format(
                    Generator.package_name, other_mod),
                'if (py::hasattr(other_mod, \"{}\")) {{\n'.format(
                    alias.python_name),
                '\tmod.attr(\"{}\") = other_mod.attr(\"{}\");\n'.format(
                    binder.python_name, alias.python_name),
                '}\n'
            ]
        return src, None

    # Bind class
    type_ = binder.underlying_typedef_type.get_canonical()
    decl = type_.get_declaration()
    template = decl.get_specialization()
    if type_.is_record and template.is_class_template:
        src = ['bind_{}({}, \"{}\");\n'.format(type_.spelling,
                                               binder.parent_name,
                                               binder.python_name)]
        return src, ['bind_{}'.format(decl.spelling)]

    elif type_.is_record and decl.is_class:
        decl.python_name = binder.spelling
        src = generate_class(decl)
        return src, []

    logger.write(
        '\tNot binding typedef: {}\n'.format(binder.qualified_spelling))
    return [], []


def generate_class_template(binder):
    """
    Generate source for a class template.

    :param binder.core.CursorBinder binder: The binder.

    :return: Binder source as a list of lines.
    :rtype: list(str)
    """
    src = generate_class(binder)

    # Hack to correct spelling of some types that miss the template parameters
    # like NCollection_List::iterator
    src_out = []
    qname = binder.qualified_name
    spelling = binder.qualified_spelling
    for line in src:
        line = line.replace(spelling + '::', qname + '::')
        src_out.append(line)
    return src_out


def function_signature(binder):
    """
    Generate data for the function signature.

    :param binder.core.CursorBinder binder: The binder.

    :return: Number of arguments, number of default values, list of names,
        list of types, their default values, and if their type is array-like.
    :rtype: tuple(int, int, list(str), list(str), list(str), list(bool))
    """
    args_name, args_type, defaults, is_array = [], [], [], []
    nargs, ndefaults = 0, 0

    for arg in binder.parameters:
        nargs += 1
        args_name.append(arg.spelling)
        args_type.append(arg.type.spelling)
        default = arg.default_value
        defaults.append(default)
        if default:
            ndefaults += 1
        if arg.type.is_array_like:
            is_array.append(True)
        else:
            is_array.append(False)

    return nargs, ndefaults, args_name, args_type, defaults, is_array
