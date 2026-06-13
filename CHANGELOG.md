# Changelog

All notable changes to `sendmsg` are documented here.

## 5.0.0

### Added
- **Voice messages:** `--voice <audio>` sends an audio file (`.m4a`, `.aac`, `.ogg`, `.opus`, `.mp3`, `.wav`) as a Signal voice note. Delivered with the REST API's `voice` flag so it renders as a playable voice note rather than a file attachment. Also supported in CSV bulk sends via a new `voice` column (Signal rows only; voice-only rows with no message text are allowed).
- **`--dry-run`:** Preview a CSV batch — every row is reported (group/file/service noted) without anything being sent.
- **Large-batch confirmation:** CSV sends of more than 50 rows now prompt for confirmation. `--yes` / `-y` skips the prompt for unattended runs.
- **Retry with backoff:** Transient Signal REST failures (HTTP 429/500/502/503/504 and network errors) are retried up to 3 times with increasing delay.
- **Attachment size guard:** Attachments larger than 100 MB are rejected before encoding, with a warning.

### Changed
- **SMS service is now explicit.** The `auto` service option has been removed. `--service` accepts only `imessage` or `sms`, and is **required** for `--sms`. CSV `sms` rows must specify a valid `service` or they are skipped and reported.
- CSV `signal` rows may now be **attachment-only** (no message text). Previously any row without a `message` was skipped, which silently dropped valid attachment-only Signal sends. SMS rows still require text.
- Signal attachments can now be sent **multiple at a time** from any path, including CSV.
- The CSV summary now distinguishes **skipped** rows from **failed** rows.

### Fixed
- Bare (no `+`) phone numbers are no longer mis-detected as Signal group IDs; group detection and phone-number detection now agree.
- Recipients are consistently normalized with a leading `+` on both the direct `--to` path and CSV rows.
- Multi-attachment Signal sends now report overall success/failure correctly instead of reflecting only the last file's result.
- Choosing more than one action (e.g. `--list-signal --link-signal`) is now rejected instead of silently running the first.
- `--link-signal` snapshots existing accounts and only reports success when a genuinely new account appears, fixing the false "Device linked!" when a primary account was already present.
- `imsg` presence is checked before invocation, producing a clean error instead of an uncaught `FileNotFoundError`.
- Removed a redundant internal assignment in the REST POST helper.

## 4.3.0
- **Fixed:** Signal attachments now send correctly. Files are base64-encoded and delivered in the JSON request body via `base64_attachments`; the previous multipart upload was rejected by the Signal REST API with HTTP 400.
- Attachment filename and MIME type are now preserved using a data-URI form.

## 4.2.0
- **Added:** `--show-config` to report resolved settings and their sources (`-v` also checks REST API reachability).
- Config resolution rewritten to correctly source-track values and avoid empty values silently falling through to defaults.

## 4.1.0
- **Fixed:** CSV attachment paths using `~` are now expanded, so Signal/SMS attachments from CSV rows are no longer silently dropped.
- **Fixed (issue #3):** Group messages are detected robustly; raw (non-`group.`) group IDs are no longer mis-sent down the direct-message path.
- **Fixed:** Multipart text/bytes join crash; consistent `+` normalization of account numbers; global `--delay` now applies between rows; missing files are skipped with a warning instead of being passed to the sender; duplicate/dead Signal send branches collapsed.

### 4.0.0
- First public release, MVP status. Earlier versions were internal only builds.
