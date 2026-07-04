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

The C++ file is a buildable protocol placeholder. When `rime_api.h` and the
`librime` library are available, the build defines `MIRRORME_WITH_LIBRIME` and
the marked adapter points can be filled with real Rime session calls.

Until that implementation is complete, use the built-in Python sidecar for
integration testing:

```powershell
$env:MIRRORME_RIME_COMMAND = "uv run python -m mirrorme.cli ime sidecar"
uv run python -m mirrorme.cli ime compose "ni hao"
```

## Build Sketch

```powershell
cmake -S sidecars\librime-json-stdio -B .mirrorme\build\librime-json-stdio `
  -DRIME_INCLUDE_DIR=D:\Tools\Rime\include `
  -DRIME_LIBRARY=D:\Tools\Rime\lib\rime.lib

cmake --build .mirrorme\build\librime-json-stdio --config Release
```

Then point MirrorMe at the resulting executable:

```powershell
$env:MIRRORME_RIME_BINARY = ".mirrorme\build\librime-json-stdio\Release\mirrorme-librime-json-stdio.exe"
uv run python -m mirrorme.cli ime probe
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
should initialize traits, create a session, select the requested schema, process
input, read context/candidates/commit text, and free all Rime-owned structs.

Important packaging reminders:

- Preserve librime's BSD license text and copyright notices.
- Review schema and dictionary licenses separately.
- Do not bundle GPL frontends directly into a commercial/proprietary build.
- Prefer shipping this sidecar as a clearly separated executable with its own
  notices.
