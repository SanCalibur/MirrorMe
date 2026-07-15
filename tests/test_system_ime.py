from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RIME_DIR = ROOT / "system-ime" / "rime"
INSTALL_SCRIPT = ROOT / "scripts" / "install-system-ime.ps1"


def test_system_ime_assets_define_a_mirrorme_pinyin_schema() -> None:
    schema = (RIME_DIR / "mirrorme_pinyin.schema.yaml").read_text(encoding="utf-8")
    dictionary = (RIME_DIR / "mirrorme_pinyin.dict.yaml").read_text(encoding="utf-8")
    default_patch = (RIME_DIR / "default.custom.yaml").read_text(encoding="utf-8")

    assert "schema_id: mirrorme_pinyin" in schema
    assert "name: MirrorMe Pinyin" in schema
    assert "dictionary: mirrorme_pinyin" in schema
    assert "import_tables:" in dictionary
    assert "schema: mirrorme_pinyin" in default_patch


def test_system_ime_install_script_keeps_weasel_external_and_deploys_schema() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")

    assert "WeaselSetup" in script
    assert "WeaselDeployer.exe" in script
    assert "mirrorme_pinyin.schema.yaml" in script
    assert "default.custom.yaml" in script
    assert "Copy-Item -LiteralPath $Path -Destination $backup" in script
    assert "& $deployer /deploy" in script
    assert "$null -ne $LASTEXITCODE" in script
    assert "Weasel writes a full schema_list" in script
    assert "schema: mirrorme_pinyin[ \\t]*" in script
