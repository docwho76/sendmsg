# Testing sendmsg

The test suite lives in `tests/test_sendmsg.py` and covers phone/group
detection, path expansion, attachment validation, Signal payload
construction, CSV parsing and dispatch (BOM handling, comma repair, blank
rows, skips, dry run, `--json` output), and CLI argument validation.

## Requirements

- Python 3.10 or newer
- `pytest` (the only test dependency — sendmsg itself is stdlib-only)

```bash
pip install pytest
# or on a system where pip refuses to touch system packages (Homebrew, Debian):
pip install pytest --break-system-packages
# or keep it isolated:
python3 -m venv .venv && source .venv/bin/activate && pip install pytest
```

## Running the tests

Run from the repository root (the tests locate the `sendmsg` script
relative to their own path, so the working directory doesn't actually
matter — but the root is the natural place):

```bash
python3 -m pytest tests/
```

Expected output looks like:

```
.....................................................................    [100%]
69 passed in 0.14s
```

### Useful variations

```bash
python3 -m pytest tests/ -v                      # one line per test, with names
python3 -m pytest tests/ -q                      # terse summary only
python3 -m pytest tests/ -k csv                  # only tests matching "csv"
python3 -m pytest tests/ -k "bom or comma"       # match multiple keywords
python3 -m pytest tests/test_sendmsg.py::TestPhoneNumbers   # one test class
python3 -m pytest tests/test_sendmsg.py::TestCsv::test_quoted_commas_in_message  # one test
python3 -m pytest tests/ -x                      # stop at the first failure
python3 -m pytest tests/ --lf                    # re-run only what failed last time
```

## What the tests do NOT need

- **No running signal-cli-rest-api container.** All network calls
  (`signal_rest_post`, `signal_rest_get`) are replaced with fakes; the
  suite asserts on the payloads sendmsg *would* send.
- **No macOS / no `imsg`.** SMS sends are stubbed the same way, so the
  suite runs identically on Linux and macOS.
- **No real config.** The suite pins `SIGNAL_REST_URL` and
  `SIGNAL_ACCOUNT` environment variables *before* importing the script,
  so your real `~/.sendmsg.conf` and shell environment can't leak into
  (or be touched by) test runs. Nothing is ever actually sent.

## How the script gets imported

`sendmsg` has no `.py` extension, so the suite loads it with
`importlib`'s `SourceFileLoader` (see the top of `tests/test_sendmsg.py`).
The loaded module is a normal Python module — tests call its functions
(`normalize_account`, `send_one_signal`, `cmd_csv` via `main()`, ...)
directly and monkeypatch its globals.

Two consequences worth knowing:

1. Module-level code (config loading) runs at import time — that's why
   the env vars are pinned first.
2. If you rename or move the `sendmsg` script, update `SCRIPT_PATH` at
   the top of the test file.

## Continuous integration

`.github/workflows/ci.yml` runs on every push and pull request:
a compile check (`python -m py_compile sendmsg`) followed by the full
suite on Python 3.10, 3.11, 3.12, and 3.13. A green run on your branch
means the same command that CI uses passed:

```bash
python -m py_compile sendmsg && python3 -m pytest tests/ -v
```

## Adding tests

- Pure helpers (parsing, normalization, validation) get direct
  parametrized tests — see `TestPhoneNumbers` for the pattern.
- Anything that would send goes through the stubbing helpers:
  `run_csv()` for CSV behavior (returns exit code, stdout, stderr, and
  the captured Signal/SMS calls) and the `captured_posts` fixture for
  payload-level assertions.
- When fixing a bug, add a test that fails on the old behavior first —
  most tests in the suite carry a comment naming the bug they pin down.