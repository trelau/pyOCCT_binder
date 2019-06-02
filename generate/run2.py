from binder.core2 import Generator

main = Generator('../include/opencascade')

# For debugging and dev
main.bind_enums = True
main.bind_functions = True
main.bind_classes = False
main.bind_typedefs = False
main.bind_class_templates = False

main.process_config('config.txt')

print('Parsing headers...')
main.parse('all_includes.h')
main.dump_diagnostics()

print('Traversing headers...')
main.traverse()

print('Sorting binders...')
main.sort_binders()

print('Building includes...')
main.build_includes()

print('Building imports...')
main.build_imports()

print('Binding templates...')
main.bind_templates('C:/Users/Trevor/Work/Products/pyOCCT/src/include')

print('Binding...')
main.bind('C:/Users/Trevor/Work/Products/pyOCCT/src/modules')

# TODO Iterators
# TODO Immutable i/o
# TODO Import and call guards
# TODO -import NCollection: gp (build imports during include)
# TODO Exclude base types with different holders
# TODO Exclude NCollection_BaseList::Iterator as base
# TODO Exclude opencascade::handle<Standard_Transient> as base
