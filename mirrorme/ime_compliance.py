from __future__ import annotations

import json
from pathlib import Path


DEFAULT_MANIFEST_PATH = Path("docs") / "ime-compliance-manifest.json"
BLOCKING_DECISIONS = {"do_not_bundle_directly"}
PENDING_DECISIONS = {"pending_review", "requires_linking_review"}


def load_manifest(path: Path = DEFAULT_MANIFEST_PATH) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def compliance_report(path: Path = DEFAULT_MANIFEST_PATH) -> dict[str, object]:
    manifest = load_manifest(path)
    components = list(manifest.get("components", []))
    data_packages = list(manifest.get("data_packages", []))
    entries = [*components, *data_packages]
    blockers = [_entry_summary(entry) for entry in entries if entry.get("bundle_decision") in BLOCKING_DECISIONS]
    pending = [_entry_summary(entry) for entry in entries if entry.get("bundle_decision") in PENDING_DECISIONS]
    allowed = [_entry_summary(entry) for entry in entries if entry.get("bundle_decision") == "allowed_with_notice"]
    required_actions = sorted(
        {
            str(action)
            for entry in entries
            for action in list(entry.get("required_actions", []))
        }
    )
    return {
        "ok_for_commercial_bundle": not blockers and not pending,
        "schema_version": manifest.get("schema_version"),
        "reviewed_at": manifest.get("reviewed_at"),
        "policy": manifest.get("policy", {}),
        "counts": {
            "components": len(components),
            "data_packages": len(data_packages),
            "allowed": len(allowed),
            "pending": len(pending),
            "blockers": len(blockers),
        },
        "allowed": allowed,
        "pending": pending,
        "blockers": blockers,
        "required_actions": required_actions,
    }


def _entry_summary(entry: object) -> dict[str, object]:
    data = dict(entry)
    return {
        "id": data.get("id"),
        "name": data.get("name"),
        "role": data.get("role"),
        "license": data.get("license"),
        "bundle_decision": data.get("bundle_decision"),
        "commercial_fit": data.get("commercial_fit"),
        "source_url": data.get("source_url"),
        "required_actions": list(data.get("required_actions", [])),
    }
