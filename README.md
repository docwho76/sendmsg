# sendmsg

**Universal message sender for Signal and SMS/iMessage.**

`sendmsg` is a command-line tool for sending messages via the [Signal REST API](https://github.com/bbernhard/signal-cli-rest-api) or locally via macOS [Messages](https://apps.apple.com/app/messages/id1092291483) (iMessage/SMS) through the [`imsg`] CLI.

It supports individual direct messages, Signal group broadcasts, file attachments, Signal voice messages, and bulk sending from CSV files — all with a single, consistent interface.

---

## Table of Contents

- [Architecture](#architecture)
- [Dependencies](#dependencies)
- [Installation](#installation)
- [Usage](#usage)
  * [Signal Messages](#signal-messages)
  * [Voice Messages](#voice-messages)
  * [SMS / iMessage](#sms--imessage)
  * [Bulk Send from CSV](#bulk-send-from-csv)
  * [Management Commands](#management-commands)
- [CSV Format](#csv-format)
- [Configuration](#configuration)
- [Examples](#examples)
- [Error Handling](#error-handling)
- [Summary Output](#summary-output)
- [Changelog](#changelog)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      sendmsg (CLI)                      │
│  Python 3 script with argparse-based argument parsing   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐        ┌──────────────────────────┐   │
│  │ --signal     │        │ --sms                    │   │
│  │              │        │                          │   │
│  │  POST JSON   │        │  Call `imsg send` CLI    │   │
│  │  to Signal   │        │                          │   │
│  │  REST API    │        │                          │   │
│  └──────┬───────┘        └────────────┬─────────────┘   │
│         │                             │                 │
│         ▼                             │                 │
│      (Docker)                         ▼                 │
│  ┌───────────────────────┐  ┌─────────────────────┐     │
│  │ signal-cli-rest-api   │  │                     │     │
│  │ http://localhost:8080 │  │   macOS Messages    │     │
│  │ (or SIGNAL_REST_URL)  │  │                     │     │
│  └───────────────────────┘  └─────────────────────┘     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Signal path:** `sendmsg` → JSON HTTP POST → `signal-cli-rest-api` → Docker container → Signal network. Attachments are base64-encoded inline in the JSON request body (the API does not accept multipart uploads). Voice messages are sent the same way with the API's `voice` flag set so they render as playable voice notes.

**SMS/iMessage path:** `sendmsg` → subprocess call → `imsg` CLI → macOS Messages framework → carrier/Apple.

---

## Dependencies

### Required

| Dependency | Version | Purpose        |
| ---------- | ------- | -------------- |
| Python 3   | 3.9+    | Script runtime |

> `sendmsg` uses only the Python standard library — no third-party packages to install.

### Signal (optional — only needed for `--signal`)

| Dependency                   | Version | Purpose                        |
| ---------------------------- | ------- | ------------------------------ |
| Docker                       | 24+     | Container runtime              |
| `signal-cli-rest-api`        | latest  | Signal REST API server         |
| `signal-cli` (via container) | latest  | Signal protocol implementation |

> Signal sends only need network access to the REST API endpoint — they do
> not require macOS.

### SMS/iMessage (optional — only needed for `--sms`)

| Dependency | Version           | Purpose                     |
| ---------- | ----------------- | --------------------------- |
| macOS 12+  | Monterey or later | Native Messages app         |
| `imsg` CLI | latest            | macOS Messages / SMS bridge |

> SMS/iMessage uses the native macOS Messages app, so macOS 12+ is required
> for the `--sms` path only.

---

## Installation

1. **Place the script:**

```
cp sendmsg /usr/local/bin/sendmsg
chmod +x /usr/local/bin/sendmsg
```

2. **Ensure dependencies are installed:**

   **For Signal:**

```
# Verify signal-cli-rest-api is running
curl -s http://localhost:8080/v1/accounts | python3 -m json.tool
```

   **For SMS/iMessage:**

```
# Verify imsg is installed and available
imsg send --help
```

3. **Test the script:**

```
sendmsg --help
sendmsg --show-config      # confirm where settings are being read from
```

---

## Usage

```
sendmsg [OPTIONS]

Messaging methods (choose one):
  --signal              Send via Signal
  --sms                 Send via SMS/iMessage (macOS Messages)
  --csv FILE            Bulk send from a CSV file

Management commands (choose one):
  --list-signal         List linked Signal accounts
  --link-signal         Link a new device to your Signal account
  --show-config         Print resolved configuration and where each value came from
```

### Signal Messages

```
# Send a text message
sendmsg --signal --to +18885551212 --text "Hello from Signal!"

# Send to a group
sendmsg --signal --recipients group.TestGroupHash --text "Hello everyone!"

# Send with an attachment
sendmsg --signal --to +18885551212 --text "Check this out" --attach ~/photo.jpg

# Send multiple messages (concatenated with newlines)
sendmsg --signal --to +18885551212 --text "Line 1" --text "Line 2"

# Send multiple attachments
sendmsg --signal --to +18885551212 --text "Files" --attach ~/doc.pdf ~/pic.jpg

# Send an attachment with no text
sendmsg --signal --to +18885551212 --attach ~/report.pdf
```

> Attachments are read, base64-encoded, and sent inside the JSON request to
> the Signal REST API. The original filename and detected MIME type are
> preserved so recipients see the correct file name and type. Attachments
> larger than 100 MB are rejected with a warning.

### Voice Messages

Send an audio file as a Signal **voice note** (a playable voice message,
not a file attachment) with `--voice`:

```
# Send a voice message
sendmsg --signal --to +18885551212 --voice ~/note.m4a

# Send a voice message to a group
sendmsg --signal --recipients group.TestGroupHash --voice ~/briefing.ogg

# Voice message with accompanying text
sendmsg --signal --to +18885551212 --voice ~/note.m4a --text "Listen to this"
```

> Recognized audio formats: `.m4a`, `.aac`, `.ogg`, `.opus`, `.mp3`, `.wav`.
> A voice note is sent as its own message; if you combine `--voice` with
> `--attach`, the voice note and the file attachments are delivered as
> separate messages.

### SMS / iMessage

The `--service` flag is **required** and must be either `imessage` or `sms`.

```
# Send via iMessage
sendmsg --sms --to +18885551212 --text "Hello via iMessage!" --service imessage

# Send via SMS
sendmsg --sms --to +18885551212 --text "Hello via SMS!" --service sms

# Send with an attachment
sendmsg --sms --to +18885551212 --text "Photo attached" --service imessage --file ~/photo.jpg
```

> SMS/iMessage supports a single attachment per message; if multiple files
> are supplied, the first valid one is used and the rest are skipped with a
> warning.

### Bulk Send from CSV

```
sendmsg --csv messages.csv              # Send all rows
sendmsg --csv messages.csv --delay 2    # Wait 2 seconds between every send
sendmsg --csv messages.csv --dry-run    # Preview every row without sending
sendmsg --csv messages.csv --yes        # Skip the large-batch confirmation
```

> Batches of more than 50 rows prompt for confirmation before sending. Use
> `--yes` / `-y` to skip the prompt for unattended runs, or `--dry-run` to
> preview exactly what would be sent first.

### Management Commands

```
# List linked Signal accounts
sendmsg --list-signal

# Link a new device
sendmsg --link-signal
sendmsg --link-signal --name "my-laptop"

# Show the active configuration and its sources
sendmsg --show-config
sendmsg --show-config -v   # also checks whether the Signal REST API is reachable
```

---

## CSV Format

Create a CSV file with the following columns:

| Column      | Required | Description                                                                          |
| ----------- | -------- | ------------------------------------------------------------------------------------ |
| `method`    | Yes      | `signal` or `sms` (defaults to `signal` if left blank)                               |
| `recipient` | Yes      | Phone number, or a Signal group ID (`group.XXXX` or a raw group key)                 |
| `name`      | No       | Display name shown during status output (e.g., "Alice", "Marketing Group")           |
| `message`   | Varies   | Message text. Required for `sms` rows and for `signal` rows without a `file`/`voice`. |
| `account`   | No       | Signal account phone number (defaults to `$SIGNAL_ACCOUNT` / config value)           |
| `service`   | Varies   | SMS service: `imessage` or `sms`. **Required** on `sms` rows; ignored for `signal`.  |
| `file`      | No       | Path to an attachment file. `~` and environment variables are expanded.              |
| `voice`     | No       | Path to an audio file to send as a Signal **voice note**. Signal only.               |
| `delay`     | No       | Seconds to wait after this row is sent (overrides the global `--delay`).             |

**Notes**

- `signal` rows may be **attachment-only** or **voice-only**: if a `file` or `voice` is present, the `message` may be left blank. `sms` rows always require a `message`.
- The `voice` column is **Signal only**. An `sms` row with a `voice` value is skipped and reported, since SMS/iMessage has no voice-note concept.
- A voice note is sent as its own message; if a row has both `voice` and `file`, they are delivered as separate messages.
- Recognized voice formats: `.m4a`, `.aac`, `.ogg`, `.opus`, `.mp3`, `.wav`.
- `sms` rows require a `service` of `imessage` or `sms`; rows with a missing or invalid service are skipped and reported.
- Group recipients are auto-detected: any `recipient` that is not a phone number is treated as a Signal group ID. Bare (no `+`) phone numbers are recognized as numbers, not groups.
- File paths starting with `~` are expanded to the home directory of the user running the script. If a named attachment cannot be found, a warning is printed and the message is still sent without it.

### Example CSV

```
method,recipient,name,message,account,service,file,voice,delay
signal,+18885551111,Alice,Hello via Signal,+18885551111,,,,
signal,group.ZzBHd3NZO...,Team Alert,Morning update for the team,,,,,
signal,+18885552222,Report,,,,~/report.pdf,,
signal,+18885556666,Briefing,,,,,~/briefing.m4a,
sms,+18885553333,Bob,SMS test,,imessage,~/pic.jpg,,
signal,+18885554444,Carol,With a delay after this row,,,,,3
```

### Status Output

During a bulk send, each row prints its name (if provided):

```
[1/5] SIGNAL → Alice (+18885551111)
[2/5] SIGNAL → Team Alert (group.ZzBHd3NZO...)
[3/5] SIGNAL → Report (+18885552222)
[4/5] SMS → Bob (+18885553333)
[5/5] SIGNAL → Carol (+18885554444)
```

If no `name` is provided, the recipient is shown instead. A `--dry-run`
prefixes each line with `[DRY]` and notes group/file/service details
without sending.

---

## Configuration

Settings are read from a config file at `~/.sendmsg.conf`, with environment
variable and built-in fallbacks.

**Resolution order:** environment variable → config file → built-in default.

### Config file format (INI-style)

```
[settings]
signal_rest_url = http://localhost:8080
signal_default_account = +1234567890
```

### Environment Variables

| Variable          | Default                 | Description                         |
| ----------------- | ----------------------- | ----------------------------------- |
| `SIGNAL_REST_URL` | `http://localhost:8080` | URL of the Signal REST API server   |
| `SIGNAL_ACCOUNT`  | `+1234567890`           | Default Signal account phone number |

### Inspecting the active configuration

Use `--show-config` to print the resolved values and exactly where each one
came from (environment, config file, or built-in default):

```
$ sendmsg --show-config
==================================================
⚙️  sendmsg configuration
==================================================
  Version:        5.1.0

  Config file:    /Users/you/.sendmsg.conf (found)

  signal_rest_url:        http://localhost:8080
    └─ source:            config (/Users/you/.sendmsg.conf)

  signal_default_account: +18885551212
    └─ source:            env ($SIGNAL_ACCOUNT)

  Resolution order: env var > config file > built-in default
==================================================
```

Add `-v` to also probe whether the Signal REST API is currently reachable.

### Override Example

```
export SIGNAL_REST_URL=http://localhost:8082
export SIGNAL_ACCOUNT=+18885551212
sendmsg --csv messages.csv
```

---

## Examples

### Daily Broadcast

```
method,recipient,name,message,account,service,file,voice,delay
signal,group.ZzBHd3NZO...,Daily Update,Good morning team! Here's your daily briefing.,+18002222222,,,,
```

### Personalized Outreach

```
method,recipient,name,message,account,service,file,voice,delay
signal,+18885551111,John,Hi John hope you're doing well,,,,,
sms,+18885552222,Jane,Hey Jane just checking in,,imessage,,,
signal,+18885553333,Alex,Alex don't forget the meeting tomorrow at 3pm,,,,,
```

> Avoid commas inside the `message` field unless the field is quoted, since
> commas are the CSV column separator.

### With Attachments

```
method,recipient,name,message,account,service,file,voice,delay
signal,+18885551111,John,Here's the report you asked for,+18002222222,,~/Downloads/report.pdf,,
sms,+18885552222,Jane,Photo from the event,,imessage,~/Photos/event.jpg,,
```

### With Voice Messages

```
method,recipient,name,message,account,service,file,voice,delay
signal,+18885551111,John,Listen to this update,,,,~/recordings/update.m4a,
signal,group.ZzBHd3NZO...,Team,,,,,~/recordings/standup.ogg,
```

> The `voice` column is Signal only and may be used with or without
> `message` text.

### With Delays

```
method,recipient,name,message,account,service,file,voice,delay
signal,+18885551111,Alice,First message,,,,,
signal,+18885552222,Bob,Second message after a 3s pause,,,,,3
signal,+18885553333,Charlie,Third message,,,,,
```

A per-row `delay` value takes precedence over the global `--delay` flag for
that row.

---

## Error Handling

- **Unknown method:** Rows with invalid `method` values are skipped and reported in the summary.
- **Missing SMS service:** `sms` rows without a valid `service` (`imessage` or `sms`) are skipped and reported.
- **Voice on SMS:** `sms` rows that specify a `voice` file are skipped and reported, since voice notes are Signal-only.
- **Empty message:** Rows without a `message` are skipped and reported — except `signal` rows that carry an attachment or a voice note, which are allowed.
- **Missing attachment:** If a named file cannot be found, a warning is printed and the message is sent without the attachment.
- **Oversized attachment:** Files larger than 100 MB are rejected with a warning before sending.
- **Transient REST failures:** Rate-limit and server errors (HTTP 429/5xx) and network blips are retried up to 3 times with backoff.
- **Failed sends:** Failed attempts are counted and listed in the summary.
- **Exit codes:** The script exits with `1` if any rows fail, `0` on full success.

---

## Summary Output

After processing all rows, a summary is printed:

```
==================================================
📊 CSV Send Summary
==================================================
  Total rows:   5
  ✅ Success:    3
  ⏭️  Skipped:    1
  ❌ Failed:     1

  Notes:
    • Row 4: invalid/missing SMS service
    • Row 5: failed to send
==================================================
```

> Intentional skips — unknown method, missing/invalid SMS service, voice on
> an SMS row, and empty messages — are counted under **Skipped**, not
> **Failed**. Only genuine send failures count as **Failed**, and the exit
> code is `1` only when something actually failed to send. Add `--json` for a
> machine-readable summary in unattended runs.

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full version history.

---

*For support or issues, see <https://xkcd.com/627/>*
