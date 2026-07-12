# MirrorMe Dogfood Validation

Use this checklist to validate whether the current Stage 1 product is useful
with real daily data, not only synthetic tests.

## Seven-Day Trial

For seven consecutive days:

- Capture at least three intentional text outputs per day.
- Tag each capture with one project or context label.
- Save one daily summary version at the end of the day.
- Accept, edit, or reject every pending memory candidate.
- Export a redacted daily backup before deleting or rewriting any data.

## Product Signals

MirrorMe is working if:

- Daily summaries make yesterday easier to review in under two minutes.
- Memory candidates are worth accepting at least 30% of the time.
- Redaction catches obvious emails, phone numbers, passwords, and tokens.
- Private captures stay out of public summaries and default exports.
- Deleting a source event removes or archives derived records that relied on it.

## Release Gate

Do not move Stage 2 input-method work into a daily-driver release until:

- The Web UI can pause/resume capture, save summaries, delete events, and export
  redacted data.
- `uv run pytest` passes.
- `uv run python -m mirrorme.cli doctor` reports no errors.
- Chinese UI strings and IME candidates render as UTF-8 in browser and tests.
- Native librime sidecar configuration is either ready or clearly labelled as a
  stub in the UI.
