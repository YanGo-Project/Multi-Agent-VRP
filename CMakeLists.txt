cmake_minimum_required(VERSION 3.10)
project(app VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

find_package(nlohmann_json REQUIRED)

# add_compile_options(-O3)
add_compile_options(-O0 -g)

set(UTILS_DIR "${CMAKE_CURRENT_SOURCE_DIR}/utils")
set(UTILS_SOURCES
        "${UTILS_DIR}/json_parser.cpp"
        "${UTILS_DIR}/problem_arguments.cpp"
)

set(SRC_DIR "${CMAKE_CURRENT_SOURCE_DIR}/src")
set(SRC_SOURCES
        "${SRC_DIR}/first_step.cpp"
)

add_library(utils STATIC ${UTILS_SOURCES} ${SRC_SOURCES})
target_include_directories(utils PUBLIC ${UTILS_DIR})
target_link_libraries(utils PUBLIC nlohmann_json::nlohmann_json)

set(SOURCES main.cpp)

add_executable(app ${SOURCES})
target_link_libraries(app PRIVATE utils)

if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    add_definitions(-DDEBUG)
endif()

option(SAVE_STEPS "save each 5 seconds" OFF)
if (SAVE_STEPS)
    add_definitions(-DSAVE_STEPS)
endif()
