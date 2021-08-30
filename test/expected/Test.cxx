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
#include <pyTest_Common.hxx>
#include <Test_Enum.h>
#include <Test_Class.h>
#include <Test_Params.h>

PYBIND11_MODULE(Test, mod) {


// ENUM: 
py::enum_<TaggedEnum>(mod, "TaggedEnum", "None")
	.value("TaggedEnum_A", TaggedEnum::TaggedEnum_A)
	.value("TaggedEnum_B", TaggedEnum::TaggedEnum_B)
	.export_values();

mod.attr("UnTaggedEnum_A") = py::cast(int(UnTaggedEnum_A));
mod.attr("UnTaggedEnum_B") = py::cast(int(UnTaggedEnum_B));


// CLASS: TEST_SIMPLECLASS
// Before type
// Testing +before_type line 1
// Testing +before_type line 2

py::class_<Test_SimpleClass> cls_Test_SimpleClass(mod, "Test_SimpleClass", "Test class");

// Constructors
cls_Test_SimpleClass.def(py::init<>());

// Methods
cls_Test_SimpleClass.def("TestReturnPolicy1", (int (Test_SimpleClass::*)()) &Test_SimpleClass::TestReturnPolicy1, "None");
cls_Test_SimpleClass.def("TestReturnPolicy2", (const int & (Test_SimpleClass::*)()) &Test_SimpleClass::TestReturnPolicy2, "None");
cls_Test_SimpleClass.def("TestReturnPolicy3", (int & (Test_SimpleClass::*)()) &Test_SimpleClass::TestReturnPolicy3, "None", py::return_value_policy::reference_internal);

// After type
// Testing +after_type line 1
// Testing +after_type line 2

// TYPEDEF: TAGGEDENUM

// TYPEDEF: UNTAGGEDENUM

// CLASS: TEST_ITEM
py::class_<Test_Item> cls_Test_Item(mod, "Test_Item", "None");

// Constructors
cls_Test_Item.def(py::init<>());

// CLASS: TEST_PARAMS
py::class_<Test_Params> cls_Test_Params(mod, "Test_Params", "None");

// Constructors
cls_Test_Params.def(py::init<>());

// Methods
cls_Test_Params.def("AddItems", (void (Test_Params::*)(const std::vector<const Test_Item *> &) const) &Test_Params::AddItems, "None", py::arg("items"));
cls_Test_Params.def("AddItems", (void (Test_Params::*)(const std::vector<const Test_Item *> &, const std::vector<int> &) const) &Test_Params::AddItems, "None", py::arg("items"), py::arg("indices"));


}
