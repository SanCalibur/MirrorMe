# MirrorMe Staged Implementation Path

## Product Thesis

A useful digital twin is built less from a single large model and more from a
long-running, high-quality personal data stream.

MirrorMe should start with the data I actively produce: messages, notes,
documents, searches, comments, emails, and later speech. My output already
contains a lot of implicit context: what I care about, how I judge things, how I
explain ideas, how I interact with different people, and what I repeatedly
return to.

However, output alone mostly creates an expression mirror. To create a better
decision and cognition mirror, MirrorMe should gradually add selected input
context: the prompt I replied to, the document I was reading, meeting context,
project labels, and explicit self-corrections.

The project should be local-first, privacy-first, and deletion-friendly from day
one.

## Stage 1: Personal Text Output Capture

### Goal

Build a reliable local system that captures my intentional text output and turns
it into daily structured memory candidates.

This stage should prove four things:

1. Text output can be collected with low friction.
2. Sensitive content can be excluded or redacted.
3. Daily output can be summarized into useful memory.
4. The stored data format is stable enough for future voice and context sources.

### Non-Goals

Stage 1 should not try to build a full system input method yet. A real input
method has high permissions, platform-specific complexity, and privacy risk.

Stage 1 should also avoid always-on screen recording, browser history scraping,
or full chat import. Those can come later after the data policy and memory model
are proven.

### Recommended First Implementation

Create a lightweight desktop text-capture app instead of a full input method.

The app should provide:

- A global hotkey to open a quick input panel.
- A clipboard/manual paste capture mode.
- A daily journal-style text box.
- Local storage for raw captures.
- Lightweight context fields: source app, source method, window/document title,
  and project label.
- Basic sensitive-data redaction.
- A daily summary generator.
- A memory-candidate extractor.

This gives most of the product learning value without taking on the riskiest
part of input-method development immediately.

### Data Model

Each captured item should be stored as an append-only event.

```json
{
  "id": "evt_20260625_224500_001",
  "type": "text_output",
  "source": {
    "method": "quick_input",
    "app": "manual",
    "window_title": null
  },
  "content": {
    "raw": "Today I decided...",
    "redacted": "Today I decided..."
  },
  "metadata": {
    "created_at": "2026-06-25T22:45:00+08:00",
    "language": "zh-CN",
    "tags": [],
    "project": null,
    "is_private": false
  },
  "processing": {
    "redaction_version": 1,
    "summary_status": "pending",
    "memory_status": "pending"
  }
}
```

Daily summary records should be separate from raw events.

```json
{
  "date": "2026-06-25",
  "summary": "Today I mainly discussed...",
  "topics": ["digital twin", "input method", "personal dataset"],
  "decisions": [],
  "commitments": [],
  "people": [],
  "memory_candidates": [
    {
      "kind": "preference",
      "content": "I prefer local-first personal data systems.",
      "confidence": 0.78,
      "evidence_event_ids": ["evt_20260625_224500_001"]
    }
  ]
}
```

### Privacy Rules

Stage 1 must include privacy controls before any model integration.

- Store data locally by default.
- Do not upload raw captures unless explicitly enabled.
- Redact common sensitive fields before summaries.
- Support manual delete by event, day, and tag.
- Support paused capture mode.
- Keep raw data and processed memory separate.
- Mark private items so they never enter long-term memory.

Initial implementation status:

- Events can be deleted individually or by date.
- Events can be shown and edited after capture.
- Updating an event can change its content, source context, tags, project, and
  private/public status.
- Saved daily summaries can be deleted by date or version.
- Memories can be archived or deleted.
- Deleting an event removes saved summaries that reference it.
- Deleting an event archives active memories that reference it, so they stop
  appearing in default memory views.
- A full local purge command exists and requires explicit `--yes`.
- Capture can be paused and resumed.
- When capture is paused, new text events are rejected unless explicitly saved
  with a force flag.
- Local data can be exported as JSON for backup, inspection, or downstream
  processing.
- Exports are redacted and public-only by default; raw and private data require
  explicit flags.
- A dedicated local backup command writes timestamped importable JSON backups;
  backups are complete by default and can be made redacted-only for sharing.
- JSON exports can be imported into another local database.
- Imports skip existing ids by default and require an explicit replace flag to
  overwrite existing records.
- Local keyword search exists for events and memories.
- Search is public-only and active-memory-only by default; private events and
  archived memories require explicit flags.
- Local statistics show capture status, event counts, date/project/tag
  distribution, saved summaries, memory status, and pending review count.
- A timeline view summarizes daily activity across a date range, including
  event counts, privacy split, projects, tags, saved summary versions, and
  pending memory candidates.
- A project index summarizes output by project, including activity, tags,
  related saved summaries, active memories, and pending memory candidates.
- A tag index summarizes cross-project themes, including activity, projects,
  related saved summaries, active memories, and pending memory candidates.
- A daily review dashboard combines daily event counts, project/tag activity,
  saved summaries, pending memory candidates, and active memories into one
  read-only command.
- A local Web dashboard can capture text events, show the daily review state,
  inspect project/tag activity, pause or resume capture, save summary versions,
  export redacted daily data, delete source events, and accept or reject memory
  candidates through local HTTP APIs.
- A human-readable Markdown daily report can be generated for review or
  archived to disk.
- Text can be batch-ingested from UTF-8 files or stdin, either as one event or
  split into blank-line-separated paragraph events.
- Text capture supports explicit ISO timestamps for historical backfill, so old
  notes can be summarized under their original day instead of the import day.
- A local health check reports data integrity issues such as invalid JSON,
  invalid timestamps, missing source references, invalid statuses, and private
  events referenced by saved summaries.

Initial redaction patterns:

- Password-like fields.
- Verification codes.
- Phone numbers.
- Email addresses.
- ID-card-like numbers.
- Bank-card-like numbers.
- API keys and tokens.

### Processing Pipeline

Stage 1 processing should be simple and inspectable.

1. Capture text.
2. Normalize text.
3. Redact sensitive information.
4. Save append-only raw event.
5. Generate daily summary.
6. Extract memory candidates.
7. Let me accept, reject, or edit memory candidates.

The important product behavior is the review loop: MirrorMe should not silently
decide what becomes long-term memory.

### Suggested Tech Shape

For the first build, prefer a small local app:

- Desktop shell: Tauri or Electron.
- UI: React or another simple frontend stack.
- Local database: SQLite.
- Embeddings/vector store: defer until Stage 2 or 3.
- Model calls: optional, behind a local/offline-first interface.

If the project starts from zero, Tauri is attractive because it is lightweight
and suitable for local-first desktop tools. Electron is acceptable if speed of
development matters more than package size.

### Stage 1 Milestones

#### Milestone 1.1: Local Capture Log

Deliver a basic app or CLI that can save text events locally.

Acceptance criteria:

- I can enter text manually.
- I can batch-ingest text from a file or stdin.
- Each entry gets an id and timestamp.
- Entries are saved locally.
- I can list entries by date.

Initial implementation status:

- The CLI supports `add` for one text event.
- The CLI supports `ingest` for UTF-8 files or stdin.
- `add --created-at` and `ingest --created-at` support historical backfill with
  an ISO datetime or date.
- `ingest --split-paragraphs` stores each blank-line-separated paragraph as a
  separate event while preserving shared tags, project, privacy, and source
  metadata.

#### Milestone 1.2: Redaction

Add sensitive-data detection before summary processing.

Acceptance criteria:

- Common sensitive fields are redacted.
- Raw and redacted content are stored separately.
- Redaction behavior is covered by tests.

#### Milestone 1.3: Daily Summary

Generate a daily summary from redacted entries.

Acceptance criteria:

- I can generate a summary for a selected date.
- The summary includes topics, decisions, commitments, and open questions.
- The summary points back to source event ids.

Initial implementation status:

- A local rule-based structured summary exists.
- It extracts topics, decisions, commitments, people, open questions, and memory
  candidates.
- Project labels are treated as strong topic signals.
- Daily summaries can be saved as versioned records in a dedicated
  `daily_summaries` table.
- The CLI supports real-time generation, saving a new version, reading the
  latest saved version, reading a specific version, and listing saved versions.
- The CLI can render a Markdown daily report that combines overview stats,
  structured summary fields, memory candidates, related memories, events, and
  saved summary versions.
- This rule-based layer is intentionally simple and should later become the
  fallback behind an LLM-powered summarizer.

#### Milestone 1.4: Memory Candidate Review

Extract candidate long-term memories and require human review.

Acceptance criteria:

- Candidate memories include type, confidence, and source evidence.
- I can accept, reject, or edit each candidate.
- Accepted memories are stored separately from raw events.

Initial implementation status:

- Accepted memories are stored in a dedicated `memories` table.
- Candidate review decisions are stored in a dedicated `memory_reviews` table.
- The CLI supports `review`, `accept`, `reject`, and `memories` commands.
- Candidate identities are stable hashes of kind, content, and evidence event ids.
- Accepted memories can be shown, edited, archived, restored, and deleted.

## Stage 2: Real Input-Method Prototype

Build a controlled input-method or keyboard extension only after Stage 1 proves
the value of the capture and memory pipeline.

Current candidate direction:

- Prefer `librime` as the built-in engine candidate because its upstream core is
  BSD-3-Clause licensed and designed as a reusable input-method engine.
- Treat GPL frontends such as Weasel as behavior references or optional external
  integrations, not as code to bundle directly into a commercial distribution.
- Keep a thin input-method abstraction in MirrorMe so the capture pipeline stores
  committed text instead of raw keystrokes or composition drafts.
- MirrorMe now exposes an input-method status/probe layer, including the
  selected engine, native adapter readiness, and committed-text-only capture
  policy.
- A deterministic sidecar protocol stub now exposes compose, candidates, commit,
  clear, and schema behavior for CLI/Web integration before the native `librime`
  binary is wired in.
- A JSON-stdio native sidecar client can call an external binary configured by
  `MIRRORME_RIME_BINARY`, allowing the stub to be replaced by a real `librime`
  process without changing the CLI/Web protocol.
- `MIRRORME_RIME_COMMAND` supports sidecar commands with arguments, and
  `ime sidecar` provides a built-in JSON-stdio stub process for integration
  testing.
- A native C++ sidecar skeleton now lives under `sidecars/librime-json-stdio`,
  with CMake discovery for `rime_api.h` and `librime`, protocol placeholder
  behavior, and marked integration points for real Rime sessions.
- `ime verify` smoke-tests the configured JSON-stdio sidecar and reports whether
  the active path is still the deterministic stub or a native adapter.
- A machine-readable IME compliance manifest tracks allowed, pending, and
  blocked bundling decisions for engines, GPL references, schemas, and
  dictionaries.
- The luna-pinyin schema package license is now recorded as LGPL-3.0 and allowed
  with notice in the compliance manifest.

Focus:

- App-level allowlist and blocklist.
- Password-field exclusion.
- Capture only committed text, not every keystroke.
- Pause/resume control.
- Local queue and sync into the Stage 1 data store.

## Stage 3: Selected Input Context

Add the minimum useful context around output.

Focus:

- Current app name.
- Window title.
- Conversation or document title.
- Optional previous-message summary.
- Project/tag inference.

The goal is not total surveillance. The goal is enough context to explain why a
piece of output happened.

## Stage 4: Voice Output

Add speech after the text pipeline is stable.

Focus:

- Manual recording.
- Meeting/audio import.
- Local or controlled transcription.
- Speaker labels when available.
- Same summary and memory-candidate pipeline as text.

## Stage 5: Personal Memory Layer

Turn accepted summaries and memories into a queryable personal knowledge base.

Focus:

- Long-term preferences.
- Stable facts.
- People and relationships.
- Projects.
- Decisions and commitments.
- Contradictions and updates over time.

## Stage 6: Digital Twin Interface

Expose the memory layer to an agent that can answer and act in my style, with
clear permission boundaries.

Focus:

- Ask MirrorMe questions about myself.
- Draft messages in my style.
- Recall decisions and commitments.
- Simulate my likely reaction to a proposal.
- Explain evidence behind any answer.

## Immediate Next Step

Start Stage 1 with a small local capture tool.

The first concrete deliverable should be:

- A local SQLite-backed text event store.
- A minimal command or UI to add entries.
- A command or view to list today's entries.
- A redaction module with tests.
