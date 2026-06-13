# sendmsg

**Universal message sender for Signal and SMS/iMessage.**

`sendmsg` is a command-line tool for sending messages via the [Signal REST API](https://github.com/bbernhard/signal-cli-rest-api) or locally via macOS [Messages](https://apps.apple.com/app/messages/id1092291483) (iMessage/SMS) through the [`imsg`] CLI.

It supports individual direct messages, Signal group broadcasts, file attachments, and bulk sending from CSV files — all with a single, consistent interface.

---

## Table of Contents

- [Architecture](#architecture)
- [Dependencies](#dependencies)
- [Installation](#installation)
- [Usage](#usage)
  * [Signal Messages](#signal-messages)
  * [SMS / iMessage](#sms--imessage)
  * [Bulk Send from CSV](#bulk-send-from-csv)
  * [Management Commands](#management-commands)
- [CSV Format](#csv-format)
- [Configuration](#configuration)
- [Examples](#examples)
- [Error Handling](#error-handling)
- [Summary Output](#summary-output)

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

**Signal path:** `sendmsg` → JSON HTTP POST → `signal-cli-rest-api` → Docker container → Signal network. Attachments are base64-encoded inline in the JSON request body (the API does not accept multipart uploads).

**SMS/iMessage path:** `sendmsg` → subprocess call → `imsg` CLI → macOS Messages framework → carrier/Apple.

---

## Dependencies

### Required

| Dependency | Version           | Purpose                           |
| ---------- | ----------------- | --------------------------------- |
| Python 3   | 3.9+              | Script runtime                    |
| macOS 12+  | Monterey or later | Required for iMessage/SMS support |

> `sendmsg` uses only the Python standard library — no third-party packages to install.

### Signal (optional — only needed for `--signal`)

| Dependency                   | Version                       | Purpose                        |
| ---------------------------- | ----------------------------- | ------------------------------ |
| Docker                       | 24+                           | Container runtime              |
| `signal-cli-rest-api`        | latest                        | Signal REST API server         |
| `signal-cli` (via container) | latest                        | Signal protocol implementation |

### SMS/iMessage (optional — only needed for `--sms`)

| Dependency | Version | Purpose                     |
| ---------- | ------- | --------------------------- |
| `imsg` CLI | latest  | macOS Messages / SMS bridge |

### System

- **macOS** — The script is designed for macOS; SMS/iMessage uses the native Messages app.
- **Network access** — Required to reach the Signal REST API endpoint.

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
```

> Attachments are read, base64-encoded, and sent inside the JSON request to
> the Signal REST API. The original filename and detected MIME type are
> preserved so recipients see the correct file name and type.

### SMS / iMessage

```
# Send via iMessage (auto-detected)
sendmsg --sms --to +18885551212 --text "Hello via iMessage!"

# Force SMS service
sendmsg --sms --to +18885551212 --text "Hello via SMS!" --service sms

# Send with an attachment
sendmsg --sms --to +18885551212 --text "Photo attached" --file ~/photo.jpg
```

### Bulk Send from CSV

```
sendmsg --csv messages.csv              # Send all rows
sendmsg --csv messages.csv --delay 2    # Wait 2 seconds between every send
```

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

| Column      | Required | Description                                                                   |
| ----------- | -------- | ----------------------------------------------------------------------------- |
| `method`    | Yes      | `signal` or `sms` (defaults to `signal` if left blank)                        |
| `recipient` | Yes      | Phone number, or a Signal group ID (`group.XXXX` or a raw group key)          |
| `name`      | No       | Display name shown during status output (e.g., "Alice", "Marketing Group")    |
| `message`   | Yes      | The message text to send                                                      |
| `account`   | No       | Signal account phone number (defaults to `$SIGNAL_ACCOUNT` / config value)    |
| `service`   | No       | SMS service: `imessage`, `sms`, or `auto` (SMS only)                          |
| `file`      | No       | Path to an attachment file. `~` and environment variables are expanded.       |
| `delay`     | No       | Seconds to wait after this row is sent (overrides the global `--delay`).      |

**Notes**

- A `message` is required on every row; rows with no message are skipped and reported.
- Group recipients are auto-detected: any `recipient` that is not a `+`-prefixed phone number is treated as a Signal group ID.
- File paths starting with `~` are expanded to the home directory of the user running the script. If a named attachment cannot be found, a warning is printed and the message is still sent without it.

### Example CSV

```
method,recipient,name,message,account,service,file,delay
signal,+18885551111,Alice,Hello via Signal,+18885551111,,,
signal,group.ZzBHd3NZO...,Team Alert,Morning update for the team,,,,
sms,+18885552222,Bob,SMS test,,,~/pic.jpg,
signal,+18885553333,Carol,With a delay after this row,,,,3
```

### Status Output

During a bulk send, each row prints its name (if provided):

```
[1/4] SIGNAL → Alice (+18885551111)
[2/4] SIGNAL → Team Alert (group.ZzBHd3NZO...)
[3/4] SMS → Bob (+18885552222)
[4/4] SIGNAL → Carol (+18885553333)
```

If no `name` is provided, the recipient is shown instead.

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
  Version:        4.3.0

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
method,recipient,name,message,account,service,file,delay
signal,group.ZzBHd3NZO...,Daily Update,Good morning team! Here's your daily briefing.,+18002222222,,,
```

### Personalized Outreach

```
method,recipient,name,message,account,service,file,delay
signal,+18885551111,John,Hi John hope you're doing well,,,,
sms,+18885552222,Jane,Hey Jane just checking in,,,,
signal,+18885553333,Alex,Alex don't forget the meeting tomorrow at 3pm,,,,
```

> Avoid commas inside the `message` field unless the field is quoted, since
> commas are the CSV column separator.

### With Attachments

```
method,recipient,name,message,account,service,file,delay
signal,+18885551111,John,Here's the report you asked for,+18002222222,,~/Downloads/report.pdf,
sms,+18885552222,Jane,Photo from the event,,,~/Photos/event.jpg,
```

### With Delays

```
method,recipient,name,message,account,service,file,delay
signal,+18885551111,Alice,First message,,,,
signal,+18885552222,Bob,Second message after a 3s pause,,,,3
signal,+18885553333,Charlie,Third message,,,,
```

A per-row `delay` value takes precedence over the global `--delay` flag for
that row.

---

## Error Handling

- **Unknown method:** Rows with invalid `method` values are skipped and reported in the summary.
- **Empty message:** Rows without a `message` are skipped and reported.
- **Missing attachment:** If a named file cannot be found, a warning is printed and the message is sent without the attachment.
- **Failed sends:** Failed attempts are counted and listed in the summary.
- **Exit codes:** The script exits with `1` if any rows fail, `0` on full success.

---

## Summary Output

After processing all rows, a summary is printed:

```
==================================================
📊 CSV Send Summary
==================================================
  Total rows:   4
  ✅ Success:    3
  ❌ Failed:     1

  Errors:
    • Row 2: failed to send
==================================================
```

---

## Changelog

### 4.3.0
- **Fixed:** Signal attachments now send correctly. Files are base64-encoded and delivered in the JSON request body via `base64_attachments`; the previous multipart upload was rejected by the Signal REST API with HTTP 400.
- Attachment filename and MIME type are now preserved using a data-URI form.

### 4.2.0
- **Added:** `--show-config` to report resolved settings and their sources (`-v` also checks REST API reachability).
- Config resolution rewritten to correctly source-track values and avoid empty values silently falling through to defaults.

### 4.1.0
- **Fixed:** CSV attachment paths using `~` are now expanded, so Signal/SMS attachments from CSV rows are no longer silently dropped.
- **Fixed (issue #3):** Group messages are detected robustly; raw (non-`group.`) group IDs are no longer mis-sent down the direct-message path.
- **Fixed:** Multipart text/bytes join crash; consistent `+` normalization of account numbers; global `--delay` now applies between rows; missing files are skipped with a warning instead of being passed to the sender; duplicate/dead Signal send branches collapsed.

---

*For support or issues, see <https://xkcd.com/627/>*
