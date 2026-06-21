vcpkg_from_github(
    OUT_SOURCE_PATH SOURCE_PATH
    REPO higan-emu/libco
    REF e18e09d634d612a01781168ad4d76be10a7e3bad
    SHA512 8a2abd60289d366197400c87f5a94d2555031e3ebd880be21e222df2e85f27cd644bc4969601f139e7f4c798c4d93a1e2e7ab0a941fe916f0a4639401b046859
    HEAD_REF master
)

# Create CMakeLists.txt for libco
file(WRITE "${SOURCE_PATH}/CMakeLists.txt"
[[cmake_minimum_required(VERSION 3.10)
project(libco LANGUAGES C)

# Only static library is supported / recommended for libco because of assembly/section code.
add_library(libco STATIC libco.c)
target_include_directories(libco PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}> $<INSTALL_INTERFACE:include>)

install(TARGETS libco
    EXPORT libco-config
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin
)

install(FILES libco.h DESTINATION include)

install(EXPORT libco-config
    NAMESPACE libco::
    DESTINATION share/libco
)
]])

vcpkg_cmake_configure(
    SOURCE_PATH "${SOURCE_PATH}"
)

vcpkg_cmake_install()

vcpkg_cmake_config_fixup(PACKAGE_NAME libco)

file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/include")
file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/share")

vcpkg_install_copyright(FILE_LIST "${SOURCE_PATH}/LICENSE")
