# MirrorMe librime JSON-stdio sidecar

This directory contains the native sidecar boundary for replacing MirrorMe's
Python IME stub with a real `librime` process.

The sidecar is intentionally a separate executable:

- MirrorMe can keep its Python/Web capture loop simple.
- `librime` binaries, schemas, and dictionaries can be packaged and audited
  independently.
- The commercial-license boundary is clearer than copying GPL frontends into the
  main app.
- The same JSON-stdio protocol can be used from CLI, Web, and a future desktop
  shell.

## Current Status

The C++ sidecar has two build modes:

- With `rime_api.h` and the `librime` library available, CMake defines
  `MIRRORME_WITH_LIBRIME` and the executable creates a real Rime session,
  selects a schema, sets raw input, reads candidates, selects candidates for
  commit, and returns JSON-stdio responses.
- Without `librime`, the same executable builds as a protocol-only placeholder
  so CLI/Web integration can still be tested.

The built-in Python sidecar remains useful for deterministic integration tests:

```powershell
$env:MIRRORME_RIME_COMMAND = "uv run python -m mirrorme.cli ime sidecar"
uv run python -m mirrorme.cli ime compose "ni hao"
```

## Build Sketch

Recommended setup helper:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-librime-sidecar.ps1 `
  -RimeRoot D:\Tools\Rime `
  -RimeSharedDataDir D:\Tools\Rime\share `
  -PersistUserEnv
```

Manual CMake build:

```powershell
cmake -S sidecars\librime-json-stdio -B .mirrorme\build\librime-json-stdio `
  -DRIME_INCLUDE_DIR=D:\Tools\Rime\include `
  -DRIME_LIBRARY=D:\Tools\Rime\lib\rime.lib

cmake --build .mirrorme\build\librime-json-stdio --config Release
```

Optional runtime data paths:

```powershell
$env:MIRRORME_RIME_SHARED_DATA_DIR = "D:\Tools\Rime\share"
$env:MIRRORME_RIME_USER_DATA_DIR = "$env:USERPROFILE\AppData\Roaming\MirrorMe\rime"
$env:MIRRORME_RIME_PREBUILT_DATA_DIR = "D:\Tools\Rime\share\build"
$env:MIRRORME_RIME_STAGING_DIR = "$env:USERPROFILE\AppData\Roaming\MirrorMe\rime\build"
```

Then point MirrorMe at the resulting executable:

```powershell
$env:MIRRORME_RIME_BINARY = ".mirrorme\build\librime-json-stdio\mirrorme-librime-json-stdio.exe"
uv run python -m mirrorme.cli ime probe
uv run python -m mirrorme.cli ime compose "ni hao"
uv run python -m mirrorme.cli ime capture "ni hao" --project MirrorMe
```

Smoke-test the configured binary:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify-librime-sidecar.ps1 -InputText "ni hao"
```

## Protocol

Requests are one JSON object on stdin:

```json
{"method":"compose","params":{"text":"ni hao","schema":"luna_pinyin"}}
```

Responses are one JSON object on stdout:

```json
{"result":{"schema":"luna_pinyin","input":"ni hao","preedit":"ni hao","candidates":[],"committed":null}}
```

Errors use:

```json
{"error":"message"}
```

Required methods:

- `schema`
- `compose`
- `candidates`
- `commit`
- `clear`

## librime Integration Notes

The upstream C API exposes `rime_get_api()` and a `RimeApi` table. The wrapper
initializes traits, creates one session per request, selects the requested
schema, sets input through `set_input` when available, reads
`RimeContext.menu.candidates`, selects a candidate for commit, reads
`RimeCommit`, and frees all Rime-owned structs before finalizing.

Real commit mode intentionally fails if librime does not produce committed text;
MirrorMe should not store raw pinyin as an analyzed text event.

Important packaging reminders:

- Preserve librime's BSD license text and copyright notices.
- Review schema and dictionary licenses separately.
- Do not bundle GPL frontends directly into a commercial/proprietary build.
- Prefer shipping this sidecar as a clearly separated executable with its own
  notices.
