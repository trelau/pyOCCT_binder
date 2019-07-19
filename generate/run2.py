from binder.core2 import Generator

main = Generator('../include/opencascade')

# For debugging and dev
main.bind_enums = True
main.bind_functions = True
main.bind_classes = True
main.bind_typedefs = True
main.bind_class_templates = True

main.process_config('config.txt')

print('Generate common header file...')
main.generate_common_header('C:/Users/Trevor/Work/Products/pyOCCT/inc')

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
