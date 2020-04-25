import os

# Generate all_includes.h and output modules
all_includes = []

occt_mods = set()
for fin in os.listdir('C:/Miniconda/envs/occt740/Library/include/opencascade'):
    if fin.endswith('.hxx'):
        all_includes.append(fin)
    if '_' in fin:
        mod = fin.split('_')[0]
    else:
        mod = fin.split('.')[0]
    occt_mods.add(mod)

# OCCT modules
occt_mods = list(occt_mods)
occt_mods.sort()
for mod in occt_mods:
    print('\'{}\','.format(mod))

# all_includes.h
fout = open('all_includes.h', 'w')
for header in all_includes:
    fout.write('#include <{}>\n'.format(header))
fout.close()
