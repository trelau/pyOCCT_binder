# This file is part of pyOCCT_binder which automatically generates Python
# bindings to the OpenCASCADE geometry kernel using pybind11.
#
# Copyright (C) 2016-2018  Laughlin Research, LLC (info@laughlinresearch.com)
# Copyright (C) 2019 Trevor Laughlin
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
src_prefix = """/*
This file is part of pyOCCT which provides Python bindings to the OpenCASCADE
geometry kernel.

Copyright (C) 2016-2018  Laughlin Research, LLC
Copyright (C) 2019 Trevor Laughlin and the pyOCCT contributors

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
"""

# C++ to Python operators
py_operators = {
    'operator+': '__add__',
    'operator-': '__sub__',
    'operator/': '__truediv__',
    'operator*': '__mul__',

    'operator+=': '__iadd__',
    'operator-=': '__isub__',
    'operator/=': '__itruediv__',
    'operator*=': '__imul__',

    # 'operator=': 'assign',
    'operator==': '__eq__',
    'operator()': '__call__',
    'operator!=': '__ne__',
    'operator[]': '__getitem__',
    'operator++': 'plus_plus',
    'operator--': 'minus_minus',
    'operator<': '__lt__',
    'operator<=': '__le__',
    'operator>': '__gt__',
    'operator>=': '__ge__',
    'operator>>': 'bits_right',
    'operator<<': 'bits_left'
}

# Available modules
available_mods = [
    'AIS',
    'APIHeaderSection',
    'Adaptor2d',
    'Adaptor3d',
    'AdvApp2Var',
    'AdvApprox',
    'AppBlend',
    'AppCont',
    'AppDef',
    'AppParCurves',
    'AppStd',
    'AppStdL',
    'Approx',
    'ApproxInt',
    'Aspect',
    'BOPAlgo',
    'BOPDS',
    'BOPTools',
    'BRep',
    'BRepAdaptor',
    'BRepAlgo',
    'BRepAlgoAPI',
    'BRepApprox',
    'BRepBlend',
    'BRepBndLib',
    'BRepBuilderAPI',
    'BRepCheck',
    'BRepClass',
    'BRepClass3d',
    'BRepExtrema',
    'BRepFeat',
    'BRepFill',
    'BRepFilletAPI',
    'BRepGProp',
    'BRepIntCurveSurface',
    'BRepLProp',
    'BRepLib',
    'BRepMAT2d',
    'BRepMesh',
    'BRepMeshData',
    'BRepOffset',
    'BRepOffsetAPI',
    'BRepPrim',
    'BRepPrimAPI',
    'BRepProj',
    'BRepSweep',
    'BRepToIGES',
    'BRepToIGESBRep',
    'BRepTools',
    'BRepTopAdaptor',
    'BSplCLib',
    'BSplSLib',
    'BVH',
    'BiTgte',
    'BinDrivers',
    'BinLDrivers',
    'BinMDF',
    'BinMDataStd',
    'BinMDataXtd',
    'BinMDocStd',
    'BinMFunction',
    'BinMNaming',
    'BinMXCAFDoc',
    'BinObjMgt',
    'BinTObjDrivers',
    'BinTools',
    'BinXCAFDrivers',
    'Bisector',
    'Blend',
    'BlendFunc',
    'Bnd',
    'BndLib',
    'CDF',
    'CDM',
    'CPnts',
    'CSLib',
    'ChFi2d',
    'ChFi3d',
    'ChFiDS',
    'ChFiKPart',
    'Cocoa',
    'Contap',
    'Convert',
    'Draft',
    'DsgPrs',
    'ElCLib',
    'ElSLib',
    'Expr',
    'ExprIntrp',
    'Extrema',
    'FEmTool',
    'FSD',
    'FairCurve',
    'FilletSurf',
    'Font',
    'GC',
    'GCE2d',
    'GCPnts',
    'GProp',
    'GccAna',
    'GccEnt',
    'GccInt',
    'Geom',
    'Geom2d',
    'Geom2dAPI',
    'Geom2dAdaptor',
    'Geom2dConvert',
    'Geom2dEvaluator',
    'Geom2dGcc',
    'Geom2dHatch',
    'Geom2dInt',
    'Geom2dLProp',
    'Geom2dToIGES',
    'GeomAPI',
    'GeomAbs',
    'GeomAdaptor',
    'GeomConvert',
    'GeomEvaluator',
    'GeomFill',
    'GeomInt',
    'GeomLProp',
    'GeomLib',
    'GeomPlate',
    'GeomProjLib',
    'GeomToIGES',
    'GeomToStep',
    'GeomTools',
    'Graphic3d',
    'HLRAlgo',
    'HLRAppli',
    'HLRBRep',
    'HLRTopoBRep',
    'Hatch',
    'HatchGen',
    'HeaderSection',
    'Hermit',
    'IFGraph',
    'IFSelect',
    'IGESAppli',
    'IGESBasic',
    'IGESCAFControl',
    'IGESControl',
    'IGESConvGeom',
    'IGESData',
    'IGESDefs',
    'IGESDimen',
    'IGESDraw',
    'IGESFile',
    'IGESGeom',
    'IGESGraph',
    'IGESSelect',
    'IGESSolid',
    'IGESToBRep',
    'IMeshData',
    'IMeshTools',
    'Image',
    'IntAna',
    'IntAna2d',
    'IntCurve',
    'IntCurveSurface',
    'IntCurvesFace',
    'IntImp',
    'IntImpParGen',
    'IntPatch',
    'IntPolyh',
    'IntRes2d',
    'IntStart',
    'IntSurf',
    'IntTools',
    'IntWalk',
    'Interface',
    'InterfaceGraphic',
    'Intf',
    'Intrv',
    'LDOM',
    'LDOMBasicString',
    'LDOMParser',
    'LDOMString',
    'LProp',
    'LProp3d',
    'Law',
    'LibCtl',
    'LocOpe',
    'LocalAnalysis',
    'MAT',
    'MAT2d',
    'MMgt',
    'Media',
    'MeshVS',
    'Message',
    'MoniTool',
    'NCollection',
    'NLPlate',
    'OSD',
    'OpenGl',
    'PCDM',
    'PLib',
    'Plate',
    'Plugin',
    'Poly',
    'Precision',
    'ProjLib',
    'Prs3d',
    'PrsMgr',
    'Quantity',
    'RWGltf',
    'RWHeaderSection',
    'RWMesh',
    'RWObj',
    'RWStepAP203',
    'RWStepAP214',
    'RWStepAP242',
    'RWStepBasic',
    'RWStepDimTol',
    'RWStepElement',
    'RWStepFEA',
    'RWStepGeom',
    'RWStepRepr',
    'RWStepShape',
    'RWStepVisual',
    'RWStl',
    'Resource',
    'STEPCAFControl',
    'STEPConstruct',
    'STEPControl',
    'STEPEdit',
    'STEPSelections',
    'Select3D',
    'SelectBasics',
    'SelectMgr',
    'ShapeAlgo',
    'ShapeAnalysis',
    'ShapeBuild',
    'ShapeConstruct',
    'ShapeCustom',
    'ShapeExtend',
    'ShapeFix',
    'ShapePersistent',
    'ShapeProcess',
    'ShapeProcessAPI',
    'ShapeUpgrade',
    'Standard',
    'StdDrivers',
    'StdFail',
    'StdLDrivers',
    'StdLPersistent',
    'StdObjMgt',
    'StdObject',
    'StdPersistent',
    'StdPrs',
    'StdSelect',
    'StdStorage',
    'StepAP203',
    'StepAP209',
    'StepAP214',
    'StepAP242',
    'StepBasic',
    'StepData',
    'StepDimTol',
    'StepElement',
    'StepFEA',
    'StepFile',
    'StepGeom',
    'StepRepr',
    'StepSelect',
    'StepShape',
    'StepToGeom',
    'StepToTopoDS',
    'StepVisual',
    'StlAPI',
    'Storage',
    'Sweep',
    'TColGeom',
    'TColGeom2d',
    'TColQuantity',
    'TColStd',
    'TColgp',
    'TCollection',
    'TDF',
    'TDataStd',
    'TDataXtd',
    'TDocStd',
    'TFunction',
    'TNaming',
    'TObj',
    'TPrsStd',
    'TShort',
    'TopAbs',
    'TopBas',
    'TopClass',
    'TopCnx',
    'TopExp',
    'TopLoc',
    'TopOpeBRep',
    'TopOpeBRepBuild',
    'TopOpeBRepDS',
    'TopOpeBRepTool',
    'TopTools',
    'TopTrans',
    'TopoDS',
    'TopoDSToStep',
    'Transfer',
    'TransferBRep',
    'UTL',
    'Units',
    'UnitsAPI',
    'UnitsMethods',
    'V3d',
    'Vrml',
    'VrmlAPI',
    'VrmlConverter',
    'VrmlData',
    'WNT',
    'XBRepMesh',
    'XCAFApp',
    'XCAFDimTolObjects',
    'XCAFDoc',
    'XCAFNoteObjects',
    'XCAFPrs',
    'XCAFView',
    'XSAlgo',
    'XSControl',
    'XmlDrivers',
    'XmlLDrivers',
    'XmlMDF',
    'XmlMDataStd',
    'XmlMDataXtd',
    'XmlMDocStd',
    'XmlMFunction',
    'XmlMNaming',
    'XmlMXCAFDoc',
    'XmlObjMgt',
    'XmlTObjDrivers',
    'XmlXCAFDrivers',
    'Xw',
    'gce',
    'glext',
    'gp',
    'igesread',
    'math',
    'step'
]
