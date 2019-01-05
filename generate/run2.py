from binder.core2 import Generator

main = Generator('../include/opencascade')

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

# print('Building imports...')
# main.build_imports()
#
print('Binding templates...')
main.bind_templates('C:/Users/Trevor/Work/Products/pyOCCT/src/include')

print('Binding...')
main.bind('C:/Users/Trevor/Work/Products/pyOCCT/src/modules')

# TODO Graphic3d file in Prs3d
# TODO Iterators
# TODO Immutable i/o
# TODO Import and call guards
