vcpkg_download_distfile(ARCHIVE
    URLS "https://github.com/herumi/xbyak/archive/refs/tags/v6.00.tar.gz"
    FILENAME "v6.00.tar.gz"
    SHA512 8bea95ddb44be39312083173cd4401039bd402c4732d97f9ff63174f6db29793f80dc1f1589d64bd96b4b13af819133897cd9843523662d13d57158c3837a778
)

vcpkg_extract_source_archive(
    SOURCE_PATH
    ARCHIVE "${ARCHIVE}"
)

vcpkg_cmake_configure(
    SOURCE_PATH "${SOURCE_PATH}"
)

vcpkg_cmake_install()
vcpkg_cmake_config_fixup()

file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/include")
vcpkg_install_copyright(FILE_LIST "${SOURCE_PATH}/LICENSE" "${SOURCE_PATH}/COPYING")
