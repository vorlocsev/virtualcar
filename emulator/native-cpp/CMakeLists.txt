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


add_library(VirtualCarTransport STATIC src/transport.cpp)
target_include_directories(VirtualCarTransport PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_options(VirtualCarTransport PRIVATE /W4 /WX /permissive- /sdl)

add_executable(vc_transport_checks tests/transport_checks.cpp)
target_link_libraries(vc_transport_checks PRIVATE VirtualCarTransport)
target_compile_options(vc_transport_checks PRIVATE /W4 /WX /permissive- /sdl)
add_test(NAME m4a_bounded_isotp_transport_8_groups COMMAND vc_transport_checks)

# M4B-1: isolated ISO15765/J2534 RX compatibility layer, not linked
# into the fail-closed adapter DLL until the later M5 authenticated host.
add_library(VirtualCarIsoRx STATIC src/isotp_rx.cpp)
target_include_directories(VirtualCarIsoRx PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_options(VirtualCarIsoRx PRIVATE /W4 /WX /permissive- /sdl)

add_executable(vc_isotp_rx_checks tests/isotp_rx_checks.cpp)
target_link_libraries(vc_isotp_rx_checks PRIVATE VirtualCarIsoRx)
target_compile_options(vc_isotp_rx_checks PRIVATE /W4 /WX /permissive- /sdl)
add_test(NAME m4b1_isotp_rx_metadata_8_groups COMMAND vc_isotp_rx_checks)
