from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SIDECAR_DIR = ROOT / "sidecars" / "librime-json-stdio"
SCRIPTS_DIR = ROOT / "scripts"


def test_librime_sidecar_skeleton_files_exist() -> None:
    assert (SIDECAR_DIR / "CMakeLists.txt").is_file()
    assert (SIDECAR_DIR / "README.md").is_file()
    assert (SIDECAR_DIR / "src" / "main.cpp").is_file()
    assert (SCRIPTS_DIR / "setup-librime-sidecar.ps1").is_file()
    assert (SCRIPTS_DIR / "verify-librime-sidecar.ps1").is_file()


def test_librime_sidecar_cmake_exposes_librime_hooks() -> None:
    cmake = (SIDECAR_DIR / "CMakeLists.txt").read_text(encoding="utf-8")

    assert "mirrorme-librime-json-stdio" in cmake
    assert "find_path(RIME_INCLUDE_DIR" in cmake
    assert "find_library(RIME_LIBRARY" in cmake
    assert "MIRRORME_WITH_LIBRIME=1" in cmake


def test_librime_sidecar_source_documents_protocol_and_api_hooks() -> None:
    source = (SIDECAR_DIR / "src" / "main.cpp").read_text(encoding="utf-8")

    assert "rime_get_api" in source
    assert "RimeTraits" in source
    assert "create_session" in source
    assert "select_schema" in source
    assert "set_input" in source
    assert "get_context" in source
    assert "select_candidate" in source
    assert "get_commit" in source
    assert "free_context" in source
    assert "free_commit" in source
    assert "destroy_session" in source
    assert "finalize" in source
    assert '"compose"' in source
    assert '"commit"' in source
    assert '"schema"' in source


def test_librime_sidecar_json_field_parser_matches_keys_not_values() -> None:
    source = (SIDECAR_DIR / "src" / "main.cpp").read_text(encoding="utf-8")

    assert "key_colon_pos" in source
    assert "std::isspace" in source
    assert 'source.find(marker, search_from)' in source


def test_librime_setup_scripts_wire_build_and_runtime_env() -> None:
    setup_script = (SCRIPTS_DIR / "setup-librime-sidecar.ps1").read_text(encoding="utf-8")
    verify_script = (SCRIPTS_DIR / "verify-librime-sidecar.ps1").read_text(encoding="utf-8")

    assert "-DRIME_INCLUDE_DIR=$RimeIncludeDir" in setup_script
    assert "-DRIME_LIBRARY=$RimeLibrary" in setup_script
    assert "MIRRORME_RIME_BINARY" in setup_script
    assert "MIRRORME_RIME_SHARED_DATA_DIR" in setup_script
    assert "MIRRORME_RIME_USER_DATA_DIR" in setup_script
    assert "ime probe" in verify_script
    assert "ime capture" in verify_script
    assert "--require-native" in verify_script


def test_librime_sidecar_readme_mentions_license_and_configuration() -> None:
    readme = (SIDECAR_DIR / "README.md").read_text(encoding="utf-8")

    assert "BSD" in readme
    assert "MIRRORME_RIME_BINARY" in readme
    assert "JSON-stdio" in readme
    assert "schema and dictionary licenses" in readme
