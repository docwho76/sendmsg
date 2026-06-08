# sendmsg

**Universal message sender for Signal and SMS/iMessage.**

`sendmsg` is a command-line tool for sending messages via the [Signal REST API](https://github.com/bbernhard/signal-cli-rest-api) or locally via macOS [Messages](https://apps.apple.com/app/messages/id1092291483) (iMessage/SMS) through the [`imsg`](https://github.com/DocWho76/imsg) CLI.

It supports individual direct messages, Signal group broadcasts, file attachments, and bulk sending from CSV files — all with a single, consistent interface.

---

## Table of Contents

- [Architecture](#architecture)
- [Dependencies](#dependencies)
- [Installation](#installation)
- [Usage](#usage)
  - [Signal Messages](#signal-messages)
  - [SMS / iMessage](#sms--imessage)
  - [Bulk Send from CSV](#bulk-send-from-csv)
  - [Management Commands](#management-commands)
- [CSV Format](#csv-format)
- [Configuration](#configuration)
- [Examples](#examples)

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
│  │  POST to     │        │  Call `imsg send` CLI    │   │
│  │  Signal REST │        │  (macOS Messages)        │   │
│  │  API         │        │                          │   │
│  └──────┬───────┘        └──────────┬───────────────┘   │
│         │                           │                   │
│         ▼                           ▼                   │
│  ┌──────────────────────────────────────────────────┐   │
│  │  signal-cli-rest-api  (Docker)                   │   │
│  │  http://localhost:8080 (or SIGNAL_REST_URL)      │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Docker Container                                │   │
│  │  signal-cli-rest-api				              │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**Signal path:** `sendmsg` → HTTP POST → `signal-cli-rest-api` → Docker container → Signal network.

**SMS/iMessage path:** `sendmsg` → subprocess call → `imsg` CLI → macOS Messages framework → carrier/Apple.

---

## Dependencies

### Required

| Dependency | Version | Purpose |
|---|---|---|
| Python 3 | 3.9+ | Script runtime |
| macOS 12+ | Monterey or later | Required for iMessage/SMS support |

### Signal (optional — only needed for `--signal`)

| Dependency | Version | Purpose |
|---|---|---|
| Docker | 24+ (Colima on Apple Silicon) | Container runtime |
| `signal-cli-rest-api` | latest | Signal REST API server |
| `signal-cli` (via container) | latest | Signal protocol implementation |

### SMS/iMessage (optional — only needed for `--sms`)

| Dependency | Version | Purpose |
|---|---|---|
| `imsg` CLI | latest | macOS Messages / SMS bridge |

### System

- **macOS** — The script is designed for macOS; SMS/iMessage uses the native Messages app.
- **Network access** — Required to reach the Signal REST API endpoint.

---

## Installation

1. **Place the script:**

   ```bash
   cp sendmsg /usr/local/bin/sendmsg
   chmod +x /usr/local/bin/sendmsg
   ```

2. **Ensure dependencies are installed:**

   **For Signal:**
   ```bash
   # Verify signal-cli-rest-api is running
   curl -s http://localhost:8080/v1/accounts | python3 -m json.tool
   ```

   **For SMS/iMessage:**
   ```bash
   # Verify imsg is installed and available
   imsg send --help
   ```

3. **Test the script:**

   ```bash
   sendmsg --help
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
```

### Signal Messages

```bash
# Send a text message
sendmsg --signal --to +18885551212 --text "Hello from Signal!"

# Send to a group
sendmsg --signal --recipients group.TestGroupHash --text "Hello everyone!"

# Send with an attachment
sendmsg --signal --to +18885551212 --text "Check this out" --attach ~/photo.jpg

# Send multiple messages (concatenated with newlines)
sendmsg --signal --to +18885551212 --text "Line 1" --text "Line 2"
```

### SMS / iMessage

```bash
# Send via iMessage (auto-detected)
sendmsg --sms --to +18885551212 --text "Hello via iMessage!"

# Force SMS service
sendmsg --sms --to +18885551212 --text "Hello via SMS!" --service sms

# Send with an attachment
sendmsg --sms --to +18885551212 --text "Photo attached" --file ~/photo.jpg
```

### Bulk Send from CSV

```bash
sendmsg --csv messages.csv              # Send all rows
sendmsg --csv messages.csv --delay 2    # Wait 2 seconds between sends
```

### Management Commands

```bash
# List linked Signal accounts
sendmsg --list-signal

# Link a new device
sendmsg --link-signal
sendmsg --link-signal --name "my-laptop"
```

---

## CSV Format

Create a CSV file with the following columns:

| Column | Required | Description |
|---|---|---|
| `method` | Yes | `signal` or `sms` |
| `recipient` | Yes | Phone number, group ID (for Signal), or empty for group sends |
| `name` | No | Display name shown during status output (e.g., "Alice", "Marketing Group") |
| `message` | Yes | The message text to send |
| `account` | No | Signal account phone number (defaults to `+156****1603` or `$SIGNAL_ACCOUNT`) |
| `service` | No | SMS service: `imessage`, `sms`, or `auto` (SMS only) |
| `file` | No | Path to an attachment file (relative or absolute) |
| `delay` | No | Seconds to wait after this row is sent (e.g., `3`) |

### Example CSV

```csv
method,recipient,name,message,account,service,file,delay
signal,+156****1603,Alice,Hello via Signal,+156****1603,,,
signal,group.ZzBHd3NZO...,Team Alert,,,,-1
sms,+123****7890,Bob,SMS test,,,~/pic.jpg,
signal,+156****1603,Carol,With delay,,,-3
```

### Status Output

During a bulk send, each row prints its name (if provided):

```
[1/4] SIGNAL → Alice (+156****1603)
[2/4] SIGNAL → Team Alert (group.ZzBHd3NZO...)
[3/4] SMS → Bob (+123****7890)
[4/4] SIGNAL → Carol (+156****1603)
```

If no `name` is provided, the recipient is shown instead.

---

## Configuration

### Load settings from sendmsg config file in ~/.sendmsg.conf, with env var fallback.

    Config file format (INI-style):
        [settings]
        signal_rest_url = http://localhost:8080
        signal_default_account = +1234567890

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SIGNAL_REST_URL` | `http://localhost:8080` | URL of the Signal REST API server |
| `SIGNAL_ACCOUNT` | `+1234567890` | Default Signal account phone number |

### Override Example

```bash
export SIGNAL_REST_URL=http://localhost:8082
export SIGNAL_ACCOUNT=+18885551212
sendmsg --csv messages.csv
```

---

## Examples

### Daily Broadcast

```csv
method,recipient,name,message,account,service,file,delay
signal,group.ZzBHd3NZO...,Daily Update,Good morning team! Here's your daily briefing.,+18002222222,,,
```

### Personalized Outreach

```csv
method,recipient,name,message,account,service,file,delay
signal,+18885551111,John,Hi John, hope you're doing well!
sms,+18885552222,Jane,Hey Jane, just checking in!
signal,+18885553333,Alex,Alex, don't forget about the meeting tomorrow at 3pm!
```

### With Attachments

```csv
method,recipient,name,message,account,service,file,delay
signal,+18885551111,John,Here's the report you asked for,+18002222222,,,~/Downloads/report.pdf
sms,+18885552222,Jane,Photo from the event,,,~/Photos/event.jpg,
```

### With Delays

```csv
method,recipient,name,message,account,service,file,delay
signal,+18885551111,Alice,First message,,,
signal,+18885552222,Bob,Second message,,,3
signal,+18885553333,Charlie,Third message,,,
```

---

## Error Handling

- **Unknown method:** Rows with invalid `method` values are skipped and reported in the summary.
- **Empty message:** Rows without a `message` are skipped and reported.
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

*For support or issues, see https://xkcd.com/627/*
