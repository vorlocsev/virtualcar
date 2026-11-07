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

# M5B/M5D-2b: bounded native C++20 Named Pipe client. Supports
# authenticated HELLO/KEEPALIVE/GOODBYE and a strictly synthetic
# allowlisted read-only VCRD verb. Never a generic CAN/J2534 API.
add_library(VirtualCarIpcClient STATIC src/ipc_client.cpp)
target_include_directories(VirtualCarIpcClient PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_options(VirtualCarIpcClient PRIVATE /W4 /WX /permissive- /sdl)

add_executable(vc_ipc_client_checks tests/ipc_client_checks.cpp)
target_compile_options(vc_ipc_client_checks PRIVATE /W4 /WX /permissive- /sdl)
add_test(NAME m5b_native_ipc_client_8_groups COMMAND vc_ipc_client_checks)

# M5C-1: isolated, deterministic, fail-closed session/channel lease
# bookkeeping; not linked to the J2534 DLL or any CAN/ECU data plane.
add_library(VirtualCarLifecycle STATIC src/lifecycle.cpp)
target_include_directories(VirtualCarLifecycle PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_options(VirtualCarLifecycle PRIVATE /W4 /WX /permissive- /sdl)

add_executable(vc_lifecycle_checks tests/lifecycle_checks.cpp)
target_link_libraries(vc_lifecycle_checks PRIVATE VirtualCarLifecycle)
target_compile_options(vc_lifecycle_checks PRIVATE /W4 /WX /permissive- /sdl)
add_test(NAME m5c1_bounded_session_lifecycle_8_groups COMMAND vc_lifecycle_checks)

# M5C-2: bind lifecycle tokens to the authenticated Named Pipe host process
# instance (PID + creation FILETIME), including PID-reuse protection.
add_executable(vc_lifecycle_identity_checks tests/lifecycle_identity_checks.cpp)
target_link_libraries(vc_lifecycle_identity_checks PRIVATE VirtualCarLifecycle)
target_compile_options(vc_lifecycle_identity_checks PRIVATE /W4 /WX /permissive- /sdl)
add_test(NAME m5c2_host_process_identity_4_groups COMMAND vc_lifecycle_identity_checks)

add_library(VirtualCarAuthenticatedSession STATIC src/authenticated_session.cpp)
target_include_directories(VirtualCarAuthenticatedSession PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(VirtualCarAuthenticatedSession PUBLIC VirtualCarIpcClient VirtualCarLifecycle)
target_compile_options(VirtualCarAuthenticatedSession PRIVATE /W4 /WX /permissive- /sdl)
target_link_libraries(vc_ipc_client_checks PRIVATE VirtualCarAuthenticatedSession)


# M5D-1: isolated synthetic READ-only VCRD envelope + correlation ledger.
# This does NOT link to VirtualCarJ2534Cpp, IPC or CAN transmission.
add_library(VirtualCarReadonlyContract STATIC src/readonly_contract.cpp)
target_include_directories(VirtualCarReadonlyContract PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_options(VirtualCarReadonlyContract PRIVATE /W4 /WX /permissive- /sdl)
# M5D-2b: authenticated synthetic fixture reads, still NOT linked to
# VirtualCarJ2534Cpp or any hardware/CAN transport.
target_link_libraries(VirtualCarIpcClient PUBLIC VirtualCarReadonlyContract)
target_link_libraries(VirtualCarAuthenticatedSession PUBLIC VirtualCarReadonlyContract)


add_executable(vc_readonly_contract_checks tests/readonly_contract_checks.cpp)
target_link_libraries(vc_readonly_contract_checks PRIVATE VirtualCarReadonlyContract)
target_compile_options(vc_readonly_contract_checks PRIVATE /W4 /WX /permissive- /sdl)
add_test(NAME m5d1_synthetic_readonly_contract_8_groups COMMAND vc_readonly_contract_checks)

# M4B-1: isolated ISO15765/J2534 RX compatibility layer, not linked
# into the fail-closed adapter DLL until the later M5 authenticated host.
add_library(VirtualCarIsoRx STATIC src/isotp_rx.cpp)
target_include_directories(VirtualCarIsoRx PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_options(VirtualCarIsoRx PRIVATE /W4 /WX /permissive- /sdl)

add_executable(vc_isotp_rx_checks tests/isotp_rx_checks.cpp)
target_link_libraries(vc_isotp_rx_checks PRIVATE VirtualCarIsoRx)
target_compile_options(vc_isotp_rx_checks PRIVATE /W4 /WX /permissive- /sdl)
add_test(NAME m4b1_isotp_rx_metadata_8_groups COMMAND vc_isotp_rx_checks)

# M4B-2: this runner is deliberately Win32 only. It dynamically loads the
# existing *independently cross-built C* x86 J2534 DLL, not the new M3
# fail-closed C++ DLL, and compares read-only synthetic J2534 RX outputs.
if(CMAKE_SIZEOF_VOID_P EQUAL 4)
  add_executable(vc_legacy_c_cpp_parity tests/legacy_c_cpp_parity.cpp)
  target_link_libraries(vc_legacy_c_cpp_parity PRIVATE VirtualCarIsoRx)
  target_compile_options(vc_legacy_c_cpp_parity PRIVATE /W4 /WX /permissive- /sdl)
endif()
