import argparse
import json
import os
import sys
from os.path import join, abspath, exists

# If running outside this folder we need to add this to the syspath
BINDER_ROOT = os.path.dirname(os.path.dirname(__file__))
if BINDER_ROOT not in sys.path:
    sys.path.append(BINDER_ROOT)

from binder.core import Generator


def get_search_paths():
    """ Generate a list of paths to search for clang and opencascade

    """
    for env_var in ('PREFIX', 'CONDA_PREFIX', 'CONDA_ROOT', 'BUILD_PREFIX',
                    'LIBRARY_PREFIX', 'LIBRARY_LIB', 'LIBRARY_INC'):
        path = os.environ.get(env_var)
        if path:
            yield path
            if sys.platform == 'win32':
                yield join(path, 'Library')
    return '.'


# Use conda instead of system lib/includes
def find_occt_include_dir():
    for path in get_search_paths():
        occt_include_dir = abspath(join(path, 'include', 'opencascade'))
        if exists(occt_include_dir):
            print("Found {}".format(occt_include_dir))
            return occt_include_dir


def find_clang_include_dir():
    for path in get_search_paths():
        clang_include_path = join(path, 'lib', 'clang', '10.0.0', 'include')
        if exists(clang_include_path):
            print("Found {}".format(clang_include_path))
            return clang_include_path


def find_vtk_include_dir():
    for path in get_search_paths():
        vtk_include_path = join(path, 'include', 'vtk-8.2')
        if exists(vtk_include_path):
            print("Found {}".format(vtk_include_path))
            return vtk_include_path


def find_tbb_include_dir():
    for path in get_search_paths():
        tbb_include_path = join(path, 'Library', 'include')
        if exists(tbb_include_path):
            print("Found {}".format(tbb_include_path))
            return tbb_include_path


def gen_includes(opencascade_include_path='../include/opencascade',
                 output_dir='.'):
    output_dir = abspath(output_dir)

    # Generate all_includes.h and output modules
    all_includes = []

    occt_mods = set()
    for fin in os.listdir(opencascade_include_path):
        if fin.endswith('.hxx'):
            all_includes.append(fin)
        if '_' in fin:
            mod = fin.split('_')[0]
        else:
            mod = fin.split('.')[0]
        occt_mods.add(mod)

    # OCCT modules
    occt_mods = list(occt_mods)
    occt_mods.sort(key=str.lower)
    with open(join(output_dir, 'all_modules.json'), 'w') as fout:
        json.dump(occt_mods, fout, indent=4)

    # Sort ignoring case
    all_includes.sort(key=str.lower)

    # all_includes.h
    with open(join(output_dir, 'all_includes.h'), 'w') as fout:
        fout.write("/*****************************************************/\n")
        fout.write("/* Do not edit! This file is automatically generated */\n")
        fout.write("/*****************************************************/\n")
        fout.write("#ifdef _WIN32\n")
        fout.write('    #include <Windows.h>\n')
        fout.write("#endif\n")

        fout.write("\n// OCCT\n")
        for header in all_includes:
            fout.write('#include <{}>\n'.format(header))

    return occt_mods


def main():
    parser = argparse.ArgumentParser()
    print('=' * 100)
    print("pyOCCT Binder")
    print('=' * 100)

    parser.add_argument(
        '-c',
        help='Path to config.txt',
        dest='config_path',
        default=join(BINDER_ROOT, 'generate', 'config.txt'))

    parser.add_argument(
        '-i',
        help='Path to opencascade includes',
        dest='opencascade_include_path',
        default='')

    parser.add_argument(
        '-o',
        help='Path to pyOCCT',
        default='.',
        dest='pyocct_path')

    parser.add_argument(
        '--clang',
        help='Path to clang includes',
        dest='clang_include_path',
        default='')

    args = parser.parse_args()

    opencascade_include_path = args.opencascade_include_path or find_occt_include_dir()
    clang_include_path = args.clang_include_path or find_clang_include_dir()

    vtk_include_path = find_vtk_include_dir()
    tbb_include_path = find_tbb_include_dir()

    extra_includes = abspath(join(BINDER_ROOT, 'generate', 'extra_includes'))

    if not opencascade_include_path or not exists(opencascade_include_path):
        print(f"ERROR: OpenCASCADE include path does not exist:"
              f"{opencascade_include_path}")
        sys.exit(1)

    if not exists(args.pyocct_path):
        print(f"ERROR: pyOCCT path is does not exist: "
              f"{args.pyocct_path}")
        sys.exit(1)

    if not exists(args.config_path):
        print(f"ERROR: binder config path is does not exist: "
              f"{args.config_path}")
        sys.exit(1)

    # Force using conda's clangdev includes
    # TODO: This may not be needed on other systems but was getting errors
    # on linux.
    if not exists(clang_include_path):
        print(f"ERROR: libclang include path is does not exist:"
              f"{clang_include_path}")
        sys.exit(1)

    # TODO: Move this to the binder?
    print('Collecting OpenCASCADE headers...')
    gen_dir = abspath(join(BINDER_ROOT, 'generate'))
    occt_mods = gen_includes(opencascade_include_path, gen_dir)

    gen = Generator(occt_mods, opencascade_include_path, clang_include_path,
                    extra_includes, vtk_include_path, tbb_include_path)

    pyocct_inc = abspath(join(args.pyocct_path, 'inc'))
    pyocct_src = abspath(join(args.pyocct_path, 'src', 'occt'))

    if not exists(pyocct_inc):
        os.makedirs(pyocct_inc)

    if not exists(pyocct_src):
        os.makedirs(pyocct_src)

    print(f"Writing inc files to: {pyocct_inc}")
    print(f"Writing src files to: {pyocct_src}")

    # For debugging and dev
    gen.bind_enums = True
    gen.bind_functions = True
    gen.bind_classes = True
    gen.bind_typedefs = True
    gen.bind_class_templates = True

    gen.process_config(args.config_path)

    print('Generate common header file...')
    gen.generate_common_header(pyocct_inc)

    print('Parsing headers...')
    gen.parse(join(gen_dir, 'all_includes.h'))
    gen.dump_diagnostics()

    print('Traversing headers...')
    gen.traverse()

    print('Sorting binders...')
    gen.sort_binders()

    print('Building includes...')
    gen.build_includes()

    print('Building imports...')
    gen.build_imports()

    print('Checking circular imports...')
    gen.check_circular()

    print('Binding templates...')
    gen.bind_templates(pyocct_src)

    print('Binding...')
    gen.bind(pyocct_src)
    print('Done!')
    print('=' * 100)


if __name__ == '__main__':
    main()
