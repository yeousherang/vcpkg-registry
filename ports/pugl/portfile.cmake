vcpkg_from_gitlab(
    OUT_SOURCE_PATH SOURCE_PATH
    GITLAB_URL https://gitlab.com
    REPO lv2/pugl
    REF b7637149ebe53124e5be90559e02a0185bbcbd73
    SHA512 1bd8cb547b902a0eedd54a9c58dfaf2f7eccea2579a7ebcf45f75b2c70ce7c8066bbd6d77c87921eb18f97e3799ccf2b4190e8bc7f5db78fbc3b6942eae62062
)

set(FEATURE_OPTIONS "")
if("cairo" IN_LIST FEATURES)
    list(APPEND FEATURE_OPTIONS "-Dcairo=enabled")
else()
    list(APPEND FEATURE_OPTIONS "-Dcairo=disabled")
endif()

if("opengl" IN_LIST FEATURES)
    list(APPEND FEATURE_OPTIONS "-Dopengl=enabled")
else()
    list(APPEND FEATURE_OPTIONS "-Dopengl=disabled")
endif()

if("vulkan" IN_LIST FEATURES)
    list(APPEND FEATURE_OPTIONS "-Dvulkan=enabled")
else()
    list(APPEND FEATURE_OPTIONS "-Dvulkan=disabled")
endif()

vcpkg_configure_meson(
    SOURCE_PATH "${SOURCE_PATH}"
    OPTIONS
        ${FEATURE_OPTIONS}
        -Ddocs=disabled
        -Dexamples=disabled
        -Dtests=disabled
        -Dbindings_cpp=disabled
)

vcpkg_install_meson()
vcpkg_copy_pdbs()

file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/share")
file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/include")

vcpkg_install_copyright(FILE_LIST "${SOURCE_PATH}/COPYING")
