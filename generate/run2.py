from binder.core2 import Generator

main = Generator('../include/opencascade')

main.process_config('config.txt')

print('Parsing headers...')
main.parse('all_includes.h')
# main.parse('test_all_includes.h')
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
print('Binding...')
main.bind('C:/Users/Trevor/Work/Products/pyOCCT/src/modules')
# main.bind()
