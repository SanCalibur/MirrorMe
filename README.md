# MirrorMe

MirrorMe is a local-first personal digital-twin data foundation. It starts with
capturing intentional text output, turning daily fragments into structured
summaries and reviewable memory candidates, and gradually grows toward voice,
selected context, and a permissioned agent interface.

The project is deliberately not an always-on surveillance tool. The current
design favors explicit capture, local SQLite storage, redaction, deletion,
pause/resume controls, and human review before anything becomes long-term
memory.

## Status

Current build:

- Local SQLite-backed text event store.
- CLI capture, ingest, list, search, export, import, backup, delete, and purge.
- Sensitive-data redaction for common secrets and identifiers.
- Rule-based daily summaries with topics, decisions, commitments, questions, and
  memory candidates.
- Versioned saved daily summaries and Markdown daily reports.
- Review loop for accepting, rejecting, editing, archiving, restoring, and
  deleting long-term memories.
- Timeline, project, tag, and daily dashboard views.
- Local Web UI with capture, daily review, event stream, memory candidate review,
  and IME integration panel.
- Chinese IME integration track based on `librime`, with a JSON-stdio sidecar
  protocol, Python stub sidecar, native C++ sidecar adapter, and commercial
  compliance manifest.

## Repository Map

```text
mirrorme/                       Python package and CLI
mirrorme/web_static/            Local Web UI assets
docs/roadmap.md                 Staged implementation plan
docs/input-method-research.md   Chinese IME research and integration notes
docs/ime-compliance-manifest.json
                                Machine-readable IME bundling checklist
sidecars/librime-json-stdio/    Native librime JSON-stdio sidecar adapter
tests/                          Pytest suite
```

## Quick Start

Create the local virtual environment and install dependencies:

```powershell
$env:UV_CACHE_DIR='.uv-cache'
uv venv --python D:\Tools\Python\python.exe
uv sync
```

Run tests:

```powershell
$env:UV_CACHE_DIR='.uv-cache'
uv run pytest
```

Run the local Web UI:

```powershell
$env:UV_CACHE_DIR='.uv-cache'
uv run python -m mirrorme.cli serve
```

Open `http://127.0.0.1:8765`.

## Core CLI

Capture a text event:

```powershell
uv run python -m mirrorme.cli add "Today I decided to capture text output first." --tag stage1
uv run python -m mirrorme.cli add "Captured from notes." --method quick_input --app Obsidian --window-title "MirrorMe Notes" --project MirrorMe --tag context
uv run python -m mirrorme.cli add "Backfilled historical output." --created-at 2026-06-25T21:15:00+08:00
```

Ingest a file or stdin:

```powershell
uv run python -m mirrorme.cli ingest .\daily-note.txt --project MirrorMe --tag journal
uv run python -m mirrorme.cli ingest .\daily-note.txt --split-paragraphs --project MirrorMe
Get-Content .\daily-note.txt | uv run python -m mirrorme.cli ingest --stdin --method pipe
```

Daily review and analysis:

```powershell
uv run python -m mirrorme.cli daily
uv run python -m mirrorme.cli daily --date 2026-06-25 --json
uv run python -m mirrorme.cli report --date 2026-06-25 --output .mirrorme\reports\2026-06-25.md
uv run python -m mirrorme.cli timeline --start 2026-06-01 --end 2026-06-30
uv run python -m mirrorme.cli projects --include-private --json
uv run python -m mirrorme.cli tags --include-private --json
```

Memory review:

```powershell
uv run python -m mirrorme.cli review --date 2026-06-25
uv run python -m mirrorme.cli accept 1 --date 2026-06-25 --content "Edited long-term memory."
uv run python -m mirrorme.cli reject 1 --date 2026-06-25 --note "Not stable enough."
uv run python -m mirrorme.cli memories
```

Privacy, health, and portability:

```powershell
uv run python -m mirrorme.cli pause
uv run python -m mirrorme.cli resume
uv run python -m mirrorme.cli status
uv run python -m mirrorme.cli stats
uv run python -m mirrorme.cli doctor
uv run python -m mirrorme.cli search MirrorMe
uv run python -m mirrorme.cli backup --redacted-only --output .mirrorme\backups\public.json
uv run python -m mirrorme.cli export --include-private --include-raw --output .mirrorme\exports\full.json
uv run python -m mirrorme.cli import .mirrorme\exports\full.json --replace
```

Delete or archive local data:

```powershell
uv run python -m mirrorme.cli delete event evt_20260625_224500_0800_001
uv run python -m mirrorme.cli delete date 2026-06-25
uv run python -m mirrorme.cli delete tag private-project
uv run python -m mirrorme.cli delete summary 2026-06-25 --version 1
uv run python -m mirrorme.cli delete purge --yes
```

## Chinese IME Track

MirrorMe is preparing for a built-in Chinese input method without copying GPL
desktop frontend code into the main app.

Current decision:

- Preferred engine candidate: `librime`
- Engine license signal: BSD-3-Clause
- Windows frontend `Weasel`: GPL-3.0, reference or external integration only
- `luna_pinyin` schema package: LGPL-3.0, allowed with notice in the current
  compliance manifest

IME commands:

```powershell
uv run python -m mirrorme.cli ime status
uv run python -m mirrorme.cli ime engines
uv run python -m mirrorme.cli ime probe
uv run python -m mirrorme.cli ime compliance
uv run python -m mirrorme.cli ime compose "ni hao"
uv run python -m mirrorme.cli ime commit "zhong wen"
uv run python -m mirrorme.cli ime capture "wo jue de mirrorme xian zuo shu ju fen xi" --project MirrorMe --tag analysis
uv run python -m mirrorme.cli ime sidecar
```

`ime compose` and `ime commit` use the deterministic stub by default. Set
`MIRRORME_RIME_COMMAND` to a JSON-stdio command, or `MIRRORME_RIME_BINARY` to a
single executable path, to route those commands to an external native adapter:

```powershell
$env:MIRRORME_RIME_COMMAND = "uv run python -m mirrorme.cli ime sidecar"
uv run python -m mirrorme.cli ime compose "ni hao"
```

`ime capture` commits one candidate, stores only the committed text as a
`source_method=ime_commit` event, and returns an `analysis` payload with the
updated daily summary, topics, source event ids, and pending memory candidates.
This is the direct bridge from input-method output into the MirrorMe analysis
engine.

Native sidecar adapter:

```powershell
cmake -S sidecars\librime-json-stdio -B .mirrorme\build\librime-json-stdio `
  -DRIME_INCLUDE_DIR=D:\Tools\Rime\include `
  -DRIME_LIBRARY=D:\Tools\Rime\lib\rime.lib
cmake --build .mirrorme\build\librime-json-stdio --config Release
```

At runtime, set `MIRRORME_RIME_SHARED_DATA_DIR` and
`MIRRORME_RIME_USER_DATA_DIR` when your librime package does not use default
Rime data locations.

See:

- [docs/input-method-research.md](docs/input-method-research.md)
- [docs/ime-compliance-manifest.json](docs/ime-compliance-manifest.json)
- [sidecars/librime-json-stdio](sidecars/librime-json-stdio)

## Privacy Model

MirrorMe's Stage 1 privacy rules:

- Store data locally by default.
- Keep raw captures and processed memories separate.
- Redact common sensitive fields before summaries.
- Mark private events so they are excluded from summaries and long-term memory.
- Support pause/resume capture.
- Support deletion by event, date, tag, summary, memory, and full purge.
- Require human review before memory candidates become long-term memories.

## Roadmap

See [docs/roadmap.md](docs/roadmap.md) for the staged implementation path:

1. Personal text output capture.
2. Real input-method prototype.
3. Selected input context.
4. Voice output capture and transcription.
5. Personal memory layer.
6. Digital twin interface.

## License

Project license has not been selected yet. Do not assume the repository is
licensed for reuse until a `LICENSE` file is added.
