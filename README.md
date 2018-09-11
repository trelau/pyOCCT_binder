# pyOCCT_binder — Binding generator for pyOCCT

This is a work in progress and is not yet fully functional. The goal of the
current iteration is to make the process fully automated. In the last
iteration, currently used in pyOCCT, the process was ~98% automated with some
manual work needed for a few edge cases. This also breaks out each type into
its own source file in hopes to decrease memory usage during build.

For now, the current state of the process is:

* Generate bindings for enums, functions, and classes

* Be able to **compile** these bindings (I'm almost here)

* Generate bindings for class templates

* Be able to **compile** all types (including typedefs)

* Check for proper order of base and derived types (i.e., sort so that base
  types come before derived types).
  
* Check for circular imports and add import guards as necessary

* Fix any uknowns...

For now, the `run2.py` file in the `generate` folder is the main starting
point. The OpenCASCADE header files are assumed to be in a
`./include/opencascade` folder.

Dependencies include:

 * OpenCASCADE header files (using OCCT 7.3.0)
 
 * libclang (using clangdev from Anaconda locally)
 
 * Python bindings to libclang are provided in `binder.clang`
 
 * cymbal package for extending libclang is provided in `binder.cymbal`
