# Chinese Input Method Research

Last checked: 2026-07-02

## Recommendation

Use Rime's core engine, `librime`, as the preferred long-term candidate for
MirrorMe's built-in Chinese input method layer.

Rationale:

- `librime` is the engine rather than only a desktop frontend.
- The upstream repository identifies the project as BSD-3-Clause licensed.
- Rime supports phonetic and shape-based Chinese input methods, Simplified and
  Traditional conversion through OpenCC, and YAML-based input schemas.
- The official Windows frontend, Weasel, proves Windows viability, but it is
  GPLv3 and should be treated as a reference or optional external integration,
  not as code to bundle directly into a commercial/proprietary distribution.

## Candidate Review

| Candidate | Role | License signal | Commercial bundling fit | Notes |
| --- | --- | --- | --- | --- |
| `rime/librime` | Cross-platform input method engine | BSD-3-Clause | Strong | Best candidate for an embedded engine. Requires native build and schema/data packaging. |
| `rime/weasel` | Windows Rime frontend | GPLv3 | Weak for direct bundling | Useful as Windows behavior/reference. Avoid copying/bundling code unless the product can comply with GPLv3. |
| `fcitx/fcitx5` | Linux/BSD input method framework | LGPL-2.1+ | Medium | Good Linux ecosystem option, but less directly aligned with a Windows-first local app. |
| `fcitx/libime` | Generic input-method implementation library | LGPL-2.1-or-later files present | Medium | Worth tracking for Linux/Fcitx integration; confirm per-file REUSE metadata before bundling. |
| `libpinyin/libpinyin` | Pinyin algorithm library | GPL-3.0 | Weak for direct bundling | Useful reference, but GPL-3.0 is not ideal for embedding in a commercial/proprietary app. |

## Integration Plan

1. Keep Stage 1 focused on MirrorMe's own capture UI and review loop.
2. Add an input-method abstraction before binding to any engine:
   - composition text
   - committed text
   - candidate list
   - schema/profile id
   - privacy pause state
3. Prototype `librime` as a native sidecar or dynamic library behind that
   abstraction.
4. Store only committed text events in MirrorMe by default.
5. Never record password fields, raw keystroke streams, or composition drafts
   unless the user explicitly enables a debug mode.

Initial implementation status:

- `mirrorme.ime` defines the current input-method candidate registry.
- `librime` is marked as the selected native prototype candidate.
- The capture policy is explicit: MirrorMe should capture committed text only,
  not raw keystrokes or composition drafts.
- The CLI exposes `ime status` and `ime engines`.
- The local Web API exposes `/api/ime/status`, and the dashboard displays the
  selected engine, license, commercial fit, and capture policy.
- The native adapter probe checks `MIRRORME_RIME_COMMAND`, `MIRRORME_RIME_BINARY`,
  and `MIRRORME_RIME_DATA_DIR`, then reports whether a future `librime` sidecar
  is ready, missing files, or not configured.
- `mirrorme.ime_sidecar` implements a deterministic sidecar protocol stub with
  `compose`, `candidates`, `commit`, `clear`, and `schema` behavior. This is not
  a real Rime engine; it locks the API contract so the native `librime` sidecar
  can replace it later.
- `NativeRimeSidecar` can call an external JSON-stdio process when
  `MIRRORME_RIME_COMMAND` or `MIRRORME_RIME_BINARY` points to a ready adapter.
  Each request is one JSON object on stdin and each response is a JSON object on
  stdout.
- `uv run python -m mirrorme.cli ime sidecar` runs the built-in JSON-stdio stub
  sidecar as a separate process for integration testing.
- `sidecars/librime-json-stdio` contains the native C++ sidecar skeleton,
  including CMake discovery for `rime_api.h` and the `librime` library.
- `docs/ime-compliance-manifest.json` records the current commercial bundling
  decisions for engine code, GPL reference components, and schema/dictionary
  packages.
- The CLI exposes `ime compliance` to summarize allowed, pending, and blocking
  items before any binary distribution.
- The CLI exposes `ime compose`, `ime commit`, and `ime schema`.
- The local Web API exposes `/api/ime/compose`, `/api/ime/commit`, and
  `/api/ime/schema`.

Native sidecar protocol:

```json
{"method":"compose","params":{"text":"ni hao","schema":"luna_pinyin"}}
```

Expected response:

```json
{"result":{"schema":"luna_pinyin","input":"ni hao","preedit":"ni hao","candidates":[],"committed":null}}
```

Prototype environment variables:

```powershell
$env:MIRRORME_RIME_COMMAND = "uv run python -m mirrorme.cli ime sidecar"
uv run python -m mirrorme.cli ime compose "ni hao"
uv run python -m mirrorme.cli ime compliance

$env:MIRRORME_RIME_BINARY = "D:\Tools\Rime\librime-sidecar.exe"
$env:MIRRORME_RIME_DATA_DIR = "D:\Tools\Rime\data"
uv run python -m mirrorme.cli ime probe
```

Schema package review:

- `rime/rime-luna-pinyin` is marked by GitHub as LGPL-3.0 licensed.
- The repository contains a `LICENSE` file with LGPL-3.0 text.
- The repository README points users to `LICENSE` for authorization terms.
- MirrorMe may treat the luna-pinyin schema package as allowed with notice, but
  distribution must preserve the LGPL-3.0 license text and related notices.

## Compliance Checklist

- Preserve upstream license text and copyright notices.
- Track third-party dictionaries/schemas separately; their licenses may differ
  from the engine license.
- Prefer dynamic linking or sidecar packaging for copyleft components.
- Do not bundle GPL frontends directly unless the distribution model is
  compatible with GPL obligations.
- Re-run license review before shipping binaries.

## Sources

- <https://github.com/rime/librime>
- <https://github.com/rime/rime-luna-pinyin>
- <https://github.com/rime/weasel>
- <https://github.com/fcitx/fcitx5>
- <https://github.com/fcitx/libime>
- <https://github.com/libpinyin/libpinyin>
