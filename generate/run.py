from binder.core import Generator

main = Generator()

main.process_config('config.txt')

print('Parsing headers...')
# main.parse('all_includes.h')
main.parse('test_all_includes.h')
# main.dump_diagnostics()

print('Building modules...')
main.build_modules()

print('Grouping binders...')
main.group_binders()

print('Sorting binders...')
main.sort_binders()

print('Building includes...')
main.build_includes()

print('Building imports...')
main.build_imports()

print('Building aliases...')
main.build_aliases()

print('Checking circular imports...')
# main.build_include_guards()
main.check_circular()

print('Binding templates...')
main.bind_templates(r'C:\Users\Trevor\Work\Products\pyOCCT\src\include')

print('Binding types...')
main.bind(r'C:\Users\Trevor\Work\Products\pyOCCT\src\modules')

# Bind a specific module
# mod = main.get_module('Standard')
# mod.bind(r'C:\Users\Trevor\Work\Products\pyOCCT\src')

"""
BRepFill
BVH
BinMXCAFDoc
Cocoa
FSD
Font
IntPatch
IntSurf
LDOM
LDOMBasicString
MeshVS
PCDM
PrsMgr
ShapeFix
ShapePersistent
TDF
TDocStd
TNaming
TObj
TopOpeBRep
TopOpeBRepBuild
TopOpeBRepDS
V3d
VrmlData
XmlMCAFDoc
"""