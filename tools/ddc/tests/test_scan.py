"""Read-only discovery (ddc.scan, `python -m ddc scan`) and the MCCS name table, on fake backends."""
import contextlib
import csv
import io
import json
import os
import tempfile
import unittest

from ddc.backend import DdcError, vcp_name
from ddc.cli import main
from ddc.fake import DEMO_CAPS, DEMO_VALUES, FakeBackend, FakeMonitor
from ddc.mccs import MCCS_NAMES, WRITE_ONLY, mccs_name
from ddc.scan import CSV_COLUMNS, MIN_INTERVAL, scan, summary, table, to_json, write_csv, write_json

# A monitor whose capabilities list 10, 12 and 14 only, but which also answers E2 and F0 (hidden) and lists 52
# without answering it.
HIDDEN_CAPS = "(prot(monitor)type(LCD)model(HIDDEN-TEST)vcp(10 12 14(01 05) 52)mccs_ver(2.1))"
HIDDEN_VALUES = {0x10: (75, 100), 0x12: (75, 100), 0x14: (5, 12), 0xE2: (20, 255), 0xF0: (0, 54)}


class NoWrites(FakeBackend):
    """A fake backend that fails the test on any write, and records the order of every request."""

    def __init__(self, monitors):
        super().__init__(monitors)
        self.events = []

    def set_vcp(self, index, code, value):
        raise AssertionError("scan wrote VCP %02X" % code)

    def capabilities(self, index):
        self.events.append("caps")
        return super().capabilities(index)

    def get_vcp(self, index, code):
        self.events.append("get %02X" % code)
        return super().get_vcp(index, code)

    def wait(self, seconds):
        self.events.append("wait %.3f" % seconds)
        super().wait(seconds)


def hidden_backend():
    return NoWrites([FakeMonitor("HIDDEN-TEST", "fake:0", HIDDEN_VALUES, HIDDEN_CAPS)])


def run(argv, be):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = main(argv, backend=be)
    return status, out.getvalue(), err.getvalue()


class Scan(unittest.TestCase):
    def test_reads_every_code_once_and_never_writes(self):
        be = hidden_backend()
        result = scan(be, 0)
        self.assertEqual([r.code for r in result.rows], list(range(256)))
        self.assertEqual([c for _, c in be.reads], list(range(256)))
        self.assertEqual(be.writes, [])

    def test_waits_at_least_50_ms_before_every_request_after_the_first(self):
        be = hidden_backend()
        scan(be, 0, codes=[0x10, 0x12, 0xE2])
        self.assertEqual(be.events, ["caps", "wait 0.050", "get 10", "wait 0.050", "get 12", "wait 0.050",
                                     "get E2"])
        self.assertTrue(all(w >= MIN_INTERVAL for w in be.waits))

    def test_interval_below_50_ms_refused(self):
        with self.assertRaises(ValueError):
            scan(hidden_backend(), 0, interval=0.01)
        scan(hidden_backend(), 0, codes=[0x10], interval=0.2)  # longer is fine

    def test_hidden_codes_found(self):
        result = scan(hidden_backend(), 0)
        self.assertEqual([r.code for r in result.hidden], [0xE2, 0xF0])
        e2 = result.rows[0xE2]
        self.assertEqual((e2.replied, e2.current, e2.maximum, e2.in_caps), (True, 20, 255, False))
        self.assertIn("hidden", e2.note)
        self.assertEqual(result.rows[0x14].caps_values, [0x01, 0x05])
        silent = result.rows[0x52]
        self.assertEqual((silent.replied, silent.in_caps), (False, True))
        self.assertIn("in caps, no reply", silent.note)
        self.assertFalse(result.rows[0x10].hidden)
        self.assertEqual(result.caps.model, "HIDDEN-TEST")

    def test_summary_names_hidden_and_silent_codes(self):
        text = summary(scan(hidden_backend(), 0))
        self.assertIn("Hidden-setting candidates (reply, not in caps): E2 F0", text)
        self.assertIn("In caps but no reply: 52", text)
        self.assertIn("5 replied", text)

    def test_no_capabilities_means_unknown_not_hidden(self):
        mon = FakeMonitor("NOCAPS", "fake:0", HIDDEN_VALUES, "")
        result = scan(NoWrites([mon]), 0)
        self.assertEqual(result.hidden, [])
        self.assertIsNone(result.rows[0xE2].in_caps)
        self.assertIn("not available", summary(result))

    def test_capabilities_request_failure_does_not_stop_the_scan(self):
        class CapsFail(NoWrites):
            def capabilities(self, index):
                raise DdcError("capabilities request failed (fake)")
        result = scan(CapsFail([FakeMonitor("X", "fake:0", HIDDEN_VALUES)]), 0)
        self.assertEqual(len(result.replied), 5)
        self.assertIn("capabilities request failed", result.caps_error)

    def test_zero_of_zero_reply_is_flagged(self):
        mon = FakeMonitor("ZERO", "fake:0", {0x10: (75, 100)}, "(vcp(10))")
        mon.zero_unsupported = True
        result = scan(NoWrites([mon]), 0, codes=[0x10, 0xE7])
        self.assertTrue(result.rows[1].replied)
        self.assertIn("0 of 0", result.rows[1].note)

    def test_vcp_type_recorded(self):
        mon = FakeMonitor("T", "fake:0", {0x02: (1, 2)}, "(vcp(02))")
        mon.types[0x02] = 0
        result = scan(NoWrites([mon]), 0, codes=[0x02])
        self.assertEqual(result.rows[0].vcp_type, 0)
        self.assertIn("momentary", table(result))

    def test_display_names_override_mccs_names(self):
        result = scan(hidden_backend(), 0, codes=[0x10, 0xE2], names={0xE2: "preset mode (read only)"})
        self.assertEqual([r.name for r in result.rows], ["brightness (luminance)", "preset mode (read only)"])

    def test_table_shows_replied_and_listed_codes_unless_all(self):
        result = scan(hidden_backend(), 0)
        lines = table(result).splitlines()
        codes = [l[:2] for l in lines[1:] if l[:2].strip() and l[2:4] == "  "]
        self.assertEqual(codes, ["10", "12", "14", "52", "E2", "F0"])
        self.assertEqual(len([l for l in table(result, all_rows=True).splitlines() if l[2:4] == "  "]), 256)


class Files(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_csv_one_row_per_code(self):
        path = os.path.join(self.tmp.name, "scan.csv")
        write_csv(scan(hidden_backend(), 0), path)
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(list(rows[0]), CSV_COLUMNS)
        self.assertEqual(len(rows), 256)
        e2 = rows[0xE2]
        self.assertEqual((e2["vcp"], e2["replied"], e2["current"], e2["maximum"], e2["in_caps"], e2["hidden"]),
                         ("E2", "True", "20", "255", "False", "True"))
        self.assertEqual(rows[0x14]["caps_values"], "01 05")
        self.assertEqual(rows[0xFF]["current"], "")

    def test_json(self):
        path = os.path.join(self.tmp.name, "scan.json")
        result = scan(hidden_backend(), 0)
        write_json(result, path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data, json.loads(json.dumps(to_json(result))))
        self.assertEqual(data["hidden"], ["E2", "F0"])
        self.assertEqual(data["capabilities"]["raw"], HIDDEN_CAPS)
        self.assertEqual(len(data["codes"]), 256)

    def test_files_never_overwritten(self):
        result = scan(hidden_backend(), 0, codes=[0x10])
        for writer, name in ((write_csv, "a.csv"), (write_json, "a.json")):
            path = os.path.join(self.tmp.name, name)
            with open(path, "w") as f:
                f.write("keep")
            with self.assertRaises(FileExistsError):
                writer(result, path)
            with open(path) as f:
                self.assertEqual(f.read(), "keep")

    def test_cli_scan_writes_both_files(self):
        csv_path, json_path = os.path.join(self.tmp.name, "s.csv"), os.path.join(self.tmp.name, "s.json")
        be = hidden_backend()
        status, out, _ = run(["scan", "--csv", csv_path, "--json", json_path], be)
        self.assertEqual(status, 0)
        self.assertIn("Hidden-setting candidates (reply, not in caps): E2 F0", out)
        self.assertTrue(os.path.exists(csv_path) and os.path.exists(json_path))
        self.assertEqual(be.writes, [])

    def test_cli_refuses_an_existing_file_before_reading_anything(self):
        path = os.path.join(self.tmp.name, "old.csv")
        open(path, "w").close()
        be = hidden_backend()
        status, _, err = run(["scan", "--csv", path], be)
        self.assertEqual(status, 2)
        self.assertIn("never overwrites", err)
        self.assertEqual(be.reads, [])


class CliScan(unittest.TestCase):
    def test_some_codes_only(self):
        be = hidden_backend()
        status, out, _ = run(["scan", "10", "E2"], be)
        self.assertEqual(status, 0)
        self.assertEqual([c for _, c in be.reads], [0x10, 0xE2])
        self.assertRegex(out, r"E2\s+manufacturer specific\s+yes")

    def test_interval_too_short_refused(self):
        be = hidden_backend()
        status, _, err = run(["scan", "--interval", "0.02"], be)
        self.assertEqual(status, 2)
        self.assertEqual(be.reads, [])

    def test_demo_backend_has_a_hidden_code(self):
        be = NoWrites([FakeMonitor("FAKE-DEMO", "fake:0", DEMO_VALUES, DEMO_CAPS)])
        status, out, _ = run(["scan"], be)
        self.assertEqual(status, 0)
        self.assertIn("Hidden-setting candidates (reply, not in caps): E2", out)


class Names(unittest.TestCase):
    def test_table_covers_the_standard_range_only(self):
        self.assertTrue(all(0 <= c <= 0xDF for c in MCCS_NAMES))
        self.assertGreater(len(MCCS_NAMES), 150)
        for c in (0x10, 0x12, 0x14, 0x16, 0x60, 0x6C, 0x87, 0xB0, 0xC9, 0xCA, 0xD6, 0xDC, 0xDF):
            self.assertIn(c, MCCS_NAMES, "%02X" % c)

    def test_manufacturer_and_undefined(self):
        self.assertEqual(mccs_name(0xE2), "manufacturer specific")
        self.assertEqual(mccs_name(0xFF), "manufacturer specific")
        self.assertEqual(mccs_name(0x07), "not defined in MCCS 2.2a")
        self.assertEqual(vcp_name(0x87), "sharpness")

    def test_write_only_codes(self):
        self.assertEqual(WRITE_ONLY, {0x01, 0x04, 0x05, 0x06, 0x08, 0x0A})

    def test_get_and_caps_print_names(self):
        be = hidden_backend()
        status, out, _ = run(["get", "10", "E2"], be)
        self.assertEqual(status, 0)
        self.assertRegex(out, r"VCP 10 brightness \(luminance\)\s+75 of 100")
        self.assertRegex(out, r"VCP E2 manufacturer specific\s+20 of 255")
        status, out, _ = run(["caps"], be)
        self.assertRegex(out, r"14  colour preset\s+values 01 05")
        self.assertRegex(out, r"52  active control")


if __name__ == "__main__":
    unittest.main()
