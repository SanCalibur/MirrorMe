cmake_minimum_required(VERSION 3.20)

project(mirrorme_librime_json_stdio LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(mirrorme-librime-json-stdio
    src/main.cpp
)

target_compile_definitions(mirrorme-librime-json-stdio PRIVATE
    MIRRORME_SIDECAR_VERSION="0.1.0"
)

find_path(RIME_INCLUDE_DIR
    NAMES rime_api.h
    HINTS
        ENV RIME_INCLUDE_DIR
        ENV RIME_ROOT
    PATH_SUFFIXES include src
)

find_library(RIME_LIBRARY
    NAMES rime librime
    HINTS
        ENV RIME_LIBRARY_DIR
        ENV RIME_ROOT
    PATH_SUFFIXES lib bin
)

if(RIME_INCLUDE_DIR AND RIME_LIBRARY)
    target_compile_definitions(mirrorme-librime-json-stdio PRIVATE MIRRORME_WITH_LIBRIME=1)
    target_include_directories(mirrorme-librime-json-stdio PRIVATE ${RIME_INCLUDE_DIR})
    target_link_libraries(mirrorme-librime-json-stdio PRIVATE ${RIME_LIBRARY})
else()
    message(WARNING "librime was not found. Building protocol-only placeholder.")
endif()
