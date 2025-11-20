cmake_minimum_required(VERSION 3.18)
project(CoincFinder LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Core sources shared by everything
set(COINCFINDER_SOURCES
    src/Coincidences.cpp
    src/ReadCSV.cpp
    src/RollingSingles.cpp
)

add_library(coincfinder_core STATIC ${COINCFINDER_SOURCES})
target_include_directories(coincfinder_core
    PUBLIC
        ${PROJECT_SOURCE_DIR}/include
)

# Optional: OpenMP acceleration
find_package(OpenMP)
if(OpenMP_CXX_FOUND)
    target_link_libraries(coincfinder_core PUBLIC OpenMP::OpenMP_CXX)
    target_compile_definitions(coincfinder_core PUBLIC COINCFINDER_WITH_OPENMP=1)
endif()

# Python module via pybind11
find_package(pybind11 CONFIG QUIET)
if(NOT pybind11_FOUND)
    message(STATUS "pybind11 not found. Fetching via FetchContent.")
    include(FetchContent)
    FetchContent_Declare(
        pybind11
        GIT_REPOSITORY https://github.com/pybind/pybind11.git
        GIT_TAG        v2.12.0
    )
    FetchContent_MakeAvailable(pybind11)
endif()

pybind11_add_module(coincfinder MODULE src/bindings.cpp)
target_link_libraries(coincfinder PRIVATE coincfinder_core)

set_target_properties(coincfinder PROPERTIES OUTPUT_NAME "coincfinder")

install(TARGETS coincfinder DESTINATION .)
