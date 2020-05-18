/*
This file is part of pyOCCT which provides Python bindings to the OpenCASCADE
geometry kernel.

Copyright (C) 2016-2018  Laughlin Research, LLC
Copyright (C) 2019-2020  Trevor Laughlin and the pyOCCT contributors

This library is free software; you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation; either
version 2.1 of the License, or (at your option) any later version.

This library is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with this library; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
*/
#include <pyOCCT_Common.hxx>
#include <Test_Class.h>

PYBIND11_MODULE(Test, mod) {


// CLASS: TEST_SIMPLECLASS
py::class_<Test_SimpleClass> cls_Test_SimpleClass(mod, "Test_SimpleClass", "Test class");

// Constructors
cls_Test_SimpleClass.def(py::init<>());

// Methods
cls_Test_SimpleClass.def("TestReturnPolicy1", (int (Test_SimpleClass::*)()) &Test_SimpleClass::TestReturnPolicy1, "None");
cls_Test_SimpleClass.def("TestReturnPolicy2", (const int & (Test_SimpleClass::*)()) &Test_SimpleClass::TestReturnPolicy2, "None");
cls_Test_SimpleClass.def("TestReturnPolicy3", (int & (Test_SimpleClass::*)()) &Test_SimpleClass::TestReturnPolicy3, "None", py::return_value_policy::reference_internal);


}
