cmake_minimum_required(VERSION 3.10)

# set the project name
project(pyBinderTest)

message(STATUS "Searching for Python and pybind11...")
find_package(Python COMPONENTS Interpreter Development REQUIRED)
find_package(pybind11 CONFIG REQUIRED)


include_directories(${CMAKE_CURRENT_SOURCE_DIR}/include)

# Add pybind11 module
pybind11_add_module(pyBinderTest output/Test.cxx)
target_link_libraries(pyBinderTest PUBLIC ${Python_LIBRARIES})
