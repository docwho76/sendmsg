# Changelog

All notable changes to `sendmsg` are documented here.

## 5.2.0

### Added
- **`--list-groups`:** Lists the Signal groups the account belongs to, with their names, IDs, member counts, and blocked status (via `GET /v1/groups/{number}`). This is the sanctioned way to discover the group IDs that `--recipients` and CSV rows expect. Errors out clearly when no real account is configured.
- **Test suite and CI:** A pytest suite (`tests/`) covering phone/group detection, path expansion, attachment validation, Signal payload construction, CSV dispatch (BOM, blank rows, skips, dry run, `--json`), and CLI argument validation, plus a GitHub Actions workflow running it on Python 3.10–3.13.
- **Commas in CSV messages:** Quoted message fields (`"Hi, there"`) are parsed per standard CSV rules as before, and messages with *unquoted* commas are now repaired automatically — the extra fragments are merged back into the `message` column (columns before and after it are preserved) with a warning recommending quoting. Previously an unquoted comma silently shifted every subsequent column, leaking message text into `account`, `service`, etc. Rows with fewer fields than the header are also tolerated (missing trailing columns are treated as empty).
- **Dry-run validation:** `--dry-run` now flags rows with missing recipients and verifies that `file`/`voice` paths exist (reported as `[NOT FOUND]` and listed in the summary notes), so problems surface before a real run.

### Fixed
- **Voice messages: removed the non-existent `voice` API flag.** signal-cli-rest-api's `/v2/send` has no voice-note field; the flag sent since 5.0.0 was silently ignored and the audio was always delivered as a regular audio attachment. The payload and documentation now reflect reality. (`--voice` still works — the audio is sent as its own message — but whether it renders as a playable voice note depends on the receiving client.)
- **UTF-8 BOM no longer misroutes CSV rows.** CSVs are read with `utf-8-sig`. Previously a BOM (written by Excel and many editors) corrupted the first header to `\ufeffmethod`, making every row's method appear empty — which defaulted to `signal` and silently sent explicit `sms` rows via Signal.
- **Formatted phone numbers are no longer misdetected as group IDs.** Spaces, dashes, dots, and parentheses are stripped before phone-vs-group detection and before sending, so `+1 (800) 555-1212` and `555-867-5309` are routed as direct messages in E.164 form instead of down the group path.
- **`--delay abc` no longer crashes.** The global `--delay` is parsed by argparse as a float, producing a clean usage error instead of a `ValueError` traceback.
- **`--json` output is machine-parseable.** Per-row progress lines now go to stderr when `--json` is set, so stdout contains only the JSON summary and can be piped to `jq` etc. The summary also gains a `blank` count.
- **`--sms` sends to every `--to` recipient.** Previously only the first was sent and the rest were silently dropped; the SMS path now fans out like the Signal path and recipients are `+`-normalized.
- **Rows without a recipient are skipped and reported** instead of being POSTed with an empty recipient and failing with a confusing API error.
- **CSV summary accounting is exact.** Blank rows are counted and reported (`blank` in `--json`, a `Blank` line in the text summary), and the blank/actionable test is shared between the pre-flight count and the row loop, so a row containing only a `file` value can no longer be counted as actionable yet silently skipped. `Total = blank + success + skipped + failed` always holds.
- **SMS retries only on timeout.** Non-zero `imsg` exits (bad recipient, Messages not signed in, ...) are permanent and now fail fast instead of being retried three times with backoff.
- **`--link-signal` timeout exits non-zero**, so scripts can detect a failed link.
- **`--list-signal` and other GET calls now retry** transient failures (429/5xx, network errors) with backoff, matching the send path.

## 5.1.1

### Added
- **Updated README.md:** Exposes docker compose sample config for signal-rest-api setup along with notes on Traefik and Pullio usage and integration

## 5.1.0

### Added
- **Multiple recipients per Signal send:** `--recipients` now accepts more than one value, and `--to` accepts multiple numbers, so a single invocation can fan out to several groups and/or direct recipients. Each target is sent independently and reported individually; the command exits non-zero if any target fails.
- **`--json` CSV summary:** Emits a machine-readable JSON summary (totals, per-bucket counts, and notes) for unattended runs, as an alternative to the formatted text summary.
- **SMS timeout and retry:** `imsg` invocations now run with a 60-second timeout and are retried up to 3 times with backoff on timeout or transient failure, matching the resilience of the Signal REST path. Previously a hung Messages app could stall an entire batch and SMS sends had no retry.
- **Startup configuration warnings:** A `signal_rest_url` that is not a well-formed `http(s)://` URL now warns at startup, and attempting a Signal send from the built-in placeholder account (`+1234567890`) warns that no real account is configured.

### Changed
- **Skip vs. fail accounting corrected.** Intentional skips — unknown `method`, missing/invalid SMS `service`, `voice` on an SMS row, and empty messages — are now counted under **Skipped** rather than **Failed**. The process exit code is `1` only when a genuine send fails, so deliberate skips no longer cause unattended runs to report failure.
- **Dry runs no longer report sends as successful.** A `--dry-run` now reports a separate "would send" count instead of incrementing the success total for rows that were never sent.
- Empty-message skip notes now distinguish SMS rows (which always require text) from Signal rows (which may be attachment- or voice-only).

### Fixed
- **`--link-signal` false success:** The account snapshot used for new-link detection now tolerates all response shapes returned by the REST API (bare list, `{"accounts": [...]}`, and `{"number": ...}`). Previously a dict-shaped response produced an empty baseline, so any pre-existing account could be misreported as a newly linked device. Account listing and link detection now share one shape-tolerant helper.
- The `--help` epilog and module docstring CSV column lists now include the `voice` column, matching the documented CSV format and the code.

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
