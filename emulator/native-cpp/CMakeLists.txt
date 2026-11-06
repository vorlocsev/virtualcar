cmake_minimum_required(VERSION 3.21)
project(VirtualCarNativeJ2534 LANGUAGES CXX)

# M3 is Windows-only. This is an ABI validation DLL, NOT a working
# diagnostic adapter; it is not registered or packaged for end-users.
if(NOT WIN32)
  message(FATAL_ERROR "J2534 M3 DLL may only be built for Windows")
endif()
if(NOT MSVC)
  message(FATAL_ERROR "M3 requires MSVC to verify x86 stdcall / Windows ABI")
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(VirtualCarJ2534Cpp SHARED src/j2534_fail_closed.cpp)
target_include_directories(VirtualCarJ2534Cpp PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_options(VirtualCarJ2534Cpp PRIVATE /W4 /WX /permissive- /sdl)
set_target_properties(VirtualCarJ2534Cpp PROPERTIES
  OUTPUT_NAME VirtualCarJ2534Cpp
  PREFIX "")

# Windows x86 __stdcall requires decorated *internal* symbols.
# The exports themselves must be the 14 undecorated PassThru names.
if(CMAKE_SIZEOF_VOID_P EQUAL 4)
  target_sources(VirtualCarJ2534Cpp PRIVATE src/exports_x86.def)
else()
  target_sources(VirtualCarJ2534Cpp PRIVATE src/exports_x64.def)
endif()

add_executable(vc_j2534_native_checks tests/j2534_native_windows_checks.cpp)
target_include_directories(vc_j2534_native_checks PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_options(vc_j2534_native_checks PRIVATE /W4 /WX /permissive- /sdl)
enable_testing()
add_test(NAME m3_j2534_fail_closed_8_groups
  COMMAND vc_j2534_native_checks "$<TARGET_FILE:VirtualCarJ2534Cpp>")
