from pathlib import Path

from mirrorme.ime_compliance import compliance_report, load_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs" / "ime-compliance-manifest.json"


def test_ime_compliance_manifest_loads() -> None:
    manifest = load_manifest(MANIFEST_PATH)

    assert manifest["schema_version"] == 1
    assert manifest["policy"]["commercial_distribution_target"] is True
    assert any(component["id"] == "rime-librime" for component in manifest["components"])


def test_ime_compliance_report_flags_pending_and_blocking_items() -> None:
    report = compliance_report(MANIFEST_PATH)

    assert report["ok_for_commercial_bundle"] is False
    assert report["counts"]["allowed"] == 2
    assert report["counts"]["pending"] >= 1
    assert report["counts"]["blockers"] >= 1
    assert {entry["id"] for entry in report["allowed"]} == {"rime-librime", "rime-schema-luna-pinyin"}
    assert "fcitx5" in {entry["id"] for entry in report["pending"]}
    assert "rime-weasel" in {entry["id"] for entry in report["blockers"]}
    assert "preserve_upstream_license_text" in report["required_actions"]


def test_ime_compliance_manifest_mentions_dictionary_review() -> None:
    manifest_text = MANIFEST_PATH.read_text(encoding="utf-8")

    assert "preserve_lgpl_3_license_text" in manifest_text
    assert "do_not_bundle_directly" in manifest_text
