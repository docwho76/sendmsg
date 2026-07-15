"""Unit tests for the sendmsg CLI.

The script has no .py extension, so it's loaded via SourceFileLoader.
Environment variables are pinned before import so a developer's real
~/.sendmsg.conf or env can't leak into test results.
"""

import importlib.util
import io
import json
import os
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "sendmsg"

# Pin config to known values BEFORE the module-level load_config() runs.
os.environ["SIGNAL_REST_URL"] = "http://localhost:8080"
os.environ["SIGNAL_ACCOUNT"] = "+15550001111"

loader = SourceFileLoader("sendmsg_module", str(SCRIPT_PATH))
spec = importlib.util.spec_from_loader("sendmsg_module", loader)
sendmsg = importlib.util.module_from_spec(spec)
loader.exec_module(sendmsg)


# ---------------------------------------------------------------------------
# Phone-number handling
# ---------------------------------------------------------------------------

class TestPhoneNumbers:
    @pytest.mark.parametrize("raw,expected", [
        ("+18005551212", "+18005551212"),
        ("18005551212", "+18005551212"),
        ("+1 (800) 555-1212", "+18005551212"),   # formatted (bug fix)
        ("555-867-5309", "+5558675309"),
        ("+1.800.555.1212", "+18005551212"),
        ("  +18005551212  ", "+18005551212"),
        ("group.ZzBHd3NZ", "group.ZzBHd3NZ"),    # groups pass through
        ("", ""),
        (None, None),
    ])
    def test_normalize_account(self, raw, expected):
        assert sendmsg.normalize_account(raw) == expected

    @pytest.mark.parametrize("value,expected", [
        ("+18005551212", True),
        ("18005551212", True),
        ("+1 (800) 555-1212", True),   # bug fix: formatted numbers
        ("555-867-5309", True),
        ("+1.800.555.1212", True),
        ("group.ZzBHd3NZ", False),
        ("ZzBHd3NZOWlrY2xrpB==", False),  # raw base64 group key
        ("+", False),
        ("", False),
        (None, False),
        ("()- .", False),               # separators only is not a number
    ])
    def test_looks_like_phone_number(self, value, expected):
        assert sendmsg.looks_like_phone_number(value) is expected

    @pytest.mark.parametrize("value,expected", [
        ("group.ZzBHd3NZ", True),
        ("ZzBHd3NZOWlrY2xrpB==", True),   # raw base64 key is a group
        ("+18005551212", False),
        ("18005551212", False),
        ("+1 (800) 555-1212", False),     # bug fix: NOT a group
        ("555-867-5309", False),          # bug fix: NOT a group
        ("", False),
        (None, False),
    ])
    def test_is_group_id(self, value, expected):
        assert sendmsg.is_group_id(value) is expected

    def test_detectors_agree(self):
        """A value must never be both a phone number and a group ID."""
        for v in ["+18005551212", "555-867-5309", "group.abc", "Zz09==", "+1 (800) 555-1212"]:
            assert not (sendmsg.looks_like_phone_number(v) and sendmsg.is_group_id(v))

    def test_normalize_recipient(self):
        assert sendmsg.normalize_recipient("800-555-1212") == "+8005551212"
        assert sendmsg.normalize_recipient("group.abc") == "group.abc"


# ---------------------------------------------------------------------------
# Path expansion / attachment validation
# ---------------------------------------------------------------------------

class TestPaths:
    def test_expand_path_tilde(self, monkeypatch):
        monkeypatch.setenv("HOME", "/home/tester")
        assert sendmsg.expand_path("~/pic.jpg") == "/home/tester/pic.jpg"

    def test_expand_path_env_var(self, monkeypatch):
        monkeypatch.setenv("PICDIR", "/data/pics")
        assert sendmsg.expand_path("$PICDIR/a.png") == "/data/pics/a.png"

    def test_expand_path_empty(self):
        assert sendmsg.expand_path("") == ""
        assert sendmsg.expand_path(None) is None

    def test_validate_attachment_missing(self, capsys):
        assert sendmsg.validate_attachment("/nope/missing.bin") is None
        assert "not found" in capsys.readouterr().err

    def test_validate_attachment_ok(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("hi")
        assert sendmsg.validate_attachment(str(f)) == str(f)

    def test_validate_attachment_too_large(self, tmp_path, monkeypatch, capsys):
        f = tmp_path / "big.bin"
        f.write_bytes(b"x" * 10)
        monkeypatch.setattr(sendmsg, "MAX_ATTACHMENT_BYTES", 5)
        assert sendmsg.validate_attachment(str(f)) is None
        assert "too large" in capsys.readouterr().err

    def test_validate_voice_format_warning(self, tmp_path, capsys):
        f = tmp_path / "clip.txt"
        f.write_text("not audio")
        # Unrecognized format warns but still returns the path.
        assert sendmsg.validate_attachment(str(f), as_voice=True) == str(f)
        assert "not a recognized voice/audio format" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Accounts response shape tolerance
# ---------------------------------------------------------------------------

class TestExtractAccounts:
    def test_none(self):
        assert sendmsg._extract_accounts(None) == []

    def test_bare_list(self):
        assert sendmsg._extract_accounts(["+1", "+2"]) == ["+1", "+2"]

    def test_accounts_dict(self):
        assert sendmsg._extract_accounts({"accounts": ["+1"]}) == ["+1"]

    def test_number_dict(self):
        assert sendmsg._extract_accounts({"number": "+1"}) == ["+1"]

    def test_unknown_shape(self):
        assert sendmsg._extract_accounts({"weird": 1}) == []
        assert sendmsg._extract_accounts("string") == []


# ---------------------------------------------------------------------------
# Signal payload construction (voice fix)
# ---------------------------------------------------------------------------

class TestSignalPayloads:
    @pytest.fixture
    def captured_posts(self, monkeypatch):
        calls = []

        def fake_post(endpoint, payload=None, files=None):
            calls.append({"endpoint": endpoint, "payload": dict(payload or {}), "files": files})
            return {}

        monkeypatch.setattr(sendmsg, "signal_rest_post", fake_post)
        return calls

    def test_voice_flag_not_sent(self, captured_posts, tmp_path):
        """/v2/send has no 'voice' field upstream; we must not send one."""
        clip = tmp_path / "note.m4a"
        clip.write_bytes(b"\x00\x01")
        ok = sendmsg.send_one_signal("+15550001111", "+15550002222",
                                     message=None, voice=str(clip))
        assert ok is True
        assert len(captured_posts) == 1
        call = captured_posts[0]
        assert call["endpoint"] == "/v2/send"
        assert "voice" not in call["payload"]
        assert call["files"] == str(clip) or call["files"] == [str(clip)]

    def test_voice_carries_text_when_no_attachments(self, captured_posts, tmp_path):
        clip = tmp_path / "note.m4a"
        clip.write_bytes(b"\x00")
        sendmsg.send_one_signal("+15550001111", "+15550002222",
                                message="hi", voice=str(clip))
        assert len(captured_posts) == 1
        assert captured_posts[0]["payload"].get("message") == "hi"

    def test_voice_plus_attachment_two_sends_text_once(self, captured_posts, tmp_path):
        clip = tmp_path / "note.m4a"
        clip.write_bytes(b"\x00")
        doc = tmp_path / "doc.pdf"
        doc.write_bytes(b"%PDF")
        sendmsg.send_one_signal("+15550001111", "+15550002222",
                                message="hi", voice=str(clip), attach=[str(doc)])
        assert len(captured_posts) == 2
        voice_call, attach_call = captured_posts
        assert "message" not in voice_call["payload"]
        assert attach_call["payload"].get("message") == "hi"

    def test_formatted_number_routed_direct_not_group(self, captured_posts):
        sendmsg.send_one_signal("+15550001111", "+1 (555) 000-2222", message="hi")
        assert captured_posts[0]["payload"]["recipients"] == ["+15550002222"]

    def test_empty_send_skipped(self, captured_posts, capsys):
        ok = sendmsg.send_one_signal("+15550001111", "+15550002222", message=None)
        assert ok is False
        assert captured_posts == []
        assert "skipped" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# CSV behavior (run through cmd_csv with sends stubbed out)
# ---------------------------------------------------------------------------

def run_csv(monkeypatch, tmp_path, csv_bytes, argv_extra=(), signal_result=True, sms_result=True):
    """Write csv_bytes to a file, run cmd_csv with stubbed senders.

    Returns (exit_code, stdout, stderr, signal_calls, sms_calls).
    """
    csv_file = tmp_path / "batch.csv"
    csv_file.write_bytes(csv_bytes)

    signal_calls, sms_calls = [], []
    monkeypatch.setattr(sendmsg, "send_one_signal",
                        lambda **kw: signal_calls.append(kw) or signal_result)
    monkeypatch.setattr(sendmsg, "send_one_sms",
                        lambda **kw: sms_calls.append(kw) or sms_result)
    monkeypatch.setattr(sendmsg.time, "sleep", lambda s: None)

    argv = ["sendmsg", "--csv", str(csv_file), *argv_extra]
    monkeypatch.setattr(sys, "argv", argv)

    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)

    code = 0
    try:
        sendmsg.main()
    except SystemExit as e:
        code = e.code or 0
    return code, out.getvalue(), err.getvalue(), signal_calls, sms_calls


HEADER = b"method,recipient,name,message,account,service,file,voice,delay\n"


class TestCsv:
    def test_bom_does_not_misroute_sms_rows(self, monkeypatch, tmp_path):
        """A UTF-8 BOM previously blanked the method column, silently
        sending explicit 'sms' rows via Signal."""
        data = b"\xef\xbb\xbf" + HEADER + b"sms,+15550003333,Bob,Hi,,imessage,,,\n"
        code, out, err, sig, sms = run_csv(monkeypatch, tmp_path, data)
        assert code == 0
        assert sig == []
        assert len(sms) == 1
        assert sms[0]["service"] == "imessage"

    def test_missing_recipient_skipped(self, monkeypatch, tmp_path):
        data = HEADER + b"signal,,NoOne,Hello,,,,,\n"
        code, out, err, sig, sms = run_csv(monkeypatch, tmp_path, data)
        assert sig == [] and sms == []
        assert "missing recipient" in err
        assert code == 0  # a skip is not a failure

    def test_json_stdout_is_pure_json(self, monkeypatch, tmp_path):
        data = HEADER + (b"signal,+15550003333,A,Hello,,,,,\n"
                         b"signal,+15550004444,B,World,,,,,\n")
        code, out, err, sig, sms = run_csv(monkeypatch, tmp_path, data,
                                           argv_extra=["--json"])
        summary = json.loads(out)  # would raise if progress lines leaked in
        assert summary["success"] == 2
        assert summary["failed"] == 0
        assert "[1/2]" in err  # progress went to stderr

    def test_dry_run_counts_and_flags_missing_files(self, monkeypatch, tmp_path):
        data = HEADER + b"signal,+15550003333,A,Hello,,,/definitely/missing.jpg,,\n"
        code, out, err, sig, sms = run_csv(monkeypatch, tmp_path, data,
                                           argv_extra=["--dry-run", "--json"])
        assert sig == [] and sms == []
        summary = json.loads(out)
        assert summary["would_send"] == 1
        assert any("attachment not found" in n for n in summary["notes"])

    def test_blank_rows_accounted(self, monkeypatch, tmp_path):
        data = HEADER + (b"signal,+15550003333,A,Hello,,,,,\n"
                         b",,,,,,,,\n")
        code, out, err, sig, sms = run_csv(monkeypatch, tmp_path, data,
                                           argv_extra=["--json"])
        summary = json.loads(out)
        assert summary["total"] == 2
        assert summary["blank"] == 1
        assert summary["blank"] + summary["success"] + summary["skipped"] + summary["failed"] == summary["total"]

    def test_failed_send_sets_exit_code(self, monkeypatch, tmp_path):
        data = HEADER + b"signal,+15550003333,A,Hello,,,,,\n"
        code, *_ = run_csv(monkeypatch, tmp_path, data, signal_result=False)
        assert code == 1

    def test_sms_row_requires_service(self, monkeypatch, tmp_path):
        data = HEADER + b"sms,+15550003333,A,Hello,,,,,\n"
        code, out, err, sig, sms = run_csv(monkeypatch, tmp_path, data)
        assert sms == []
        assert "requires service" in err

    def test_voice_on_sms_row_skipped(self, monkeypatch, tmp_path):
        data = HEADER + b"sms,+15550003333,A,Hello,,imessage,,~/note.m4a,\n"
        code, out, err, sig, sms = run_csv(monkeypatch, tmp_path, data)
        assert sms == []
        assert "voice" in err

    def test_group_recipient_routed_as_group(self, monkeypatch, tmp_path):
        data = HEADER + b"signal,group.ZzBHd3NZ,Team,Hi all,,,,,\n"
        code, out, err, sig, sms = run_csv(monkeypatch, tmp_path, data)
        assert sig[0]["group_id"] == "group.ZzBHd3NZ"

    def test_formatted_phone_row_not_group(self, monkeypatch, tmp_path):
        data = HEADER + b'signal,555-867-5309,Jenny,Hi,,,,,\n'
        code, out, err, sig, sms = run_csv(monkeypatch, tmp_path, data)
        assert sig[0]["group_id"] is None

    def test_bad_delay_rejected_cleanly(self, monkeypatch, tmp_path):
        """--delay abc previously crashed with a ValueError traceback."""
        data = HEADER + b"signal,+15550003333,A,Hello,,,,,\n"
        code, out, err, sig, sms = run_csv(monkeypatch, tmp_path, data,
                                           argv_extra=["--delay", "abc"])
        assert code == 2  # argparse usage error
        assert "invalid float value" in err
        assert sig == []

    # -- commas in the message field ------------------------------------

    def test_quoted_commas_in_message(self, monkeypatch, tmp_path):
        """Standard CSV quoting must pass commas through untouched."""
        data = HEADER + b'signal,+15550003333,Al,"Hi, there, friend",,,,,2\n'
        code, out, err, sig, sms = run_csv(monkeypatch, tmp_path, data)
        assert code == 0
        assert sig[0]["message"] == "Hi, there, friend"
        assert "unquoted commas" not in err  # no repair needed

    def test_unquoted_commas_merged_into_message(self, monkeypatch, tmp_path):
        """Unquoted commas previously shifted every column after 'message'
        (text leaked into 'account', etc.); they are now merged back."""
        data = HEADER + b"signal,+15550003333,Al,Hey, how are you, friend,,,,,\n"
        code, out, err, sig, sms = run_csv(monkeypatch, tmp_path, data)
        assert code == 0
        assert sig[0]["message"] == "Hey, how are you, friend"
        assert sig[0]["account"] == "+15550001111"  # default, not leaked text
        assert "unquoted commas" in err

    def test_unquoted_commas_preserve_trailing_columns(self, monkeypatch, tmp_path):
        """Columns after the message (service, voice, delay...) must still
        land in the right place after the merge."""
        data = HEADER + b"sms,+15550003333,Al,Hi, there,,imessage,,,2\n"
        code, out, err, sig, sms = run_csv(monkeypatch, tmp_path, data)
        assert code == 0
        assert sms[0]["message"] == "Hi, there"
        assert sms[0]["service"] == "imessage"

    def test_unquoted_comma_repair_noted_in_json(self, monkeypatch, tmp_path):
        data = HEADER + b"signal,+15550003333,Al,One, two,,,,,\n"
        code, out, err, sig, sms = run_csv(monkeypatch, tmp_path, data,
                                           argv_extra=["--json"])
        summary = json.loads(out)
        assert summary["success"] == 1
        assert any("unquoted commas" in n for n in summary["notes"])

    def test_short_rows_tolerated(self, monkeypatch, tmp_path):
        """Rows with fewer fields than the header must not crash."""
        data = HEADER + b"signal,+15550003333,Al,Hello\n"
        code, out, err, sig, sms = run_csv(monkeypatch, tmp_path, data)
        assert code == 0
        assert sig[0]["message"] == "Hello"


# ---------------------------------------------------------------------------
# CLI argument validation
# ---------------------------------------------------------------------------

class TestCli:
    def run_main(self, monkeypatch, argv):
        monkeypatch.setattr(sys, "argv", ["sendmsg", *argv])
        out, err = io.StringIO(), io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        monkeypatch.setattr(sys, "stderr", err)
        code = 0
        try:
            sendmsg.main()
        except SystemExit as e:
            code = e.code or 0
        return code, out.getvalue(), err.getvalue()

    def test_no_action_errors(self, monkeypatch):
        code, out, err = self.run_main(monkeypatch, [])
        assert code == 1
        assert "--list-groups" in err  # new command advertised

    def test_multiple_actions_rejected(self, monkeypatch):
        code, out, err = self.run_main(monkeypatch, ["--list-signal", "--link-signal"])
        assert code == 1
        assert "only one action" in err

    def test_sms_fans_out_to_all_recipients(self, monkeypatch):
        calls = []
        monkeypatch.setattr(sendmsg, "send_one_sms",
                            lambda **kw: calls.append(kw) or True)
        code, out, err = self.run_main(
            monkeypatch,
            ["--sms", "--to", "+15550001111", "+15550002222",
             "--text", "hi", "--service", "sms"],
        )
        assert code == 0
        assert [c["to"] for c in calls] == ["+15550001111", "+15550002222"]

    def test_list_groups_refuses_placeholder_account(self, monkeypatch):
        monkeypatch.setattr(sendmsg, "SIGNAL_DEFAULT_ACCOUNT", "+1234567890")
        code, out, err = self.run_main(monkeypatch, ["--list-groups"])
        assert code == 1
        assert "placeholder" in err

    def test_list_groups_output(self, monkeypatch):
        monkeypatch.setattr(sendmsg, "signal_rest_get", lambda ep: [
            {"name": "Ops", "id": "group.QWJj", "members": ["+1", "+2"], "blocked": False},
            {"name": None, "internal_id": "Zz09"},
        ])
        code, out, err = self.run_main(
            monkeypatch, ["--list-groups", "--account", "+15550001111"])
        assert code == 0
        assert "Ops" in out
        assert "group.QWJj" in out
        assert "2 member(s)" in out
        assert "(unnamed)" in out

    def test_list_groups_url_encodes_account(self, monkeypatch):
        seen = {}

        def fake_get(endpoint):
            seen["endpoint"] = endpoint
            return []

        monkeypatch.setattr(sendmsg, "signal_rest_get", fake_get)
        self.run_main(monkeypatch, ["--list-groups", "--account", "+15550001111"])
        assert seen["endpoint"] == "/v1/groups/%2B15550001111"
