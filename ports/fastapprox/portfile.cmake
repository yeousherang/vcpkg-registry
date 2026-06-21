vcpkg_from_github(
    OUT_SOURCE_PATH SOURCE_PATH
    REPO romeric/fastapprox
    REF ccc534400ec3e0f67de4eafb53377334962d9db6
    SHA512 f5db544dc32e83482dc0381b4083fbab2e5d3af5e4b06f60afe8ba03f448512b2bdbac8de76c77a7eb823898554b561021d3f729ae20fe077f780dc0e37d922e
    HEAD_REF master
)

# Create CMakeLists.txt to define the header-only interface library
file(WRITE "${SOURCE_PATH}/CMakeLists.txt"
[[cmake_minimum_required(VERSION 3.14)
project(fastapprox NONE)

add_library(fastapprox INTERFACE)
target_include_directories(fastapprox INTERFACE $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/fastapprox/src> $<INSTALL_INTERFACE:include>)

file(GLOB HEADERS "fastapprox/src/*.h")
install(FILES ${HEADERS} DESTINATION include/fastapprox)

install(TARGETS fastapprox
    EXPORT fastapprox-config
)

install(EXPORT fastapprox-config
    NAMESPACE fastapprox::
    DESTINATION share/fastapprox
)
]])

vcpkg_cmake_configure(
    SOURCE_PATH "${SOURCE_PATH}"
)

vcpkg_cmake_install()

vcpkg_cmake_config_fixup(PACKAGE_NAME fastapprox)

# Clean up debug files and folders for header-only library
file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug")

vcpkg_install_copyright(FILE_LIST "${SOURCE_PATH}/fastapprox/COPYING")
