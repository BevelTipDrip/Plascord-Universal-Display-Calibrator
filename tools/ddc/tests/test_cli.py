"""The CLI end to end on fake backends: output, exit status, and that only `set --yes` writes."""
import contextlib
import io
import unittest

from ddc.cli import main
from ddc.fake import DEMO_CAPS, DEMO_VALUES, FakeBackend, FakeMonitor


def run(argv, be):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = main(argv, backend=be)
    return status, out.getvalue(), err.getvalue()


def one():
    mon = FakeMonitor("FAKE-DEMO", "fake:0", DEMO_VALUES, DEMO_CAPS)
    return FakeBackend([mon]), mon


class Cli(unittest.TestCase):
    def test_list(self):
        be, _ = one()
        status, out, _ = run(["list"], be)
        self.assertEqual(status, 0)
        self.assertIn("0  FAKE-DEMO  fake:0", out)

    def test_list_none_explains_skipped_displays(self):
        be = FakeBackend([])
        be.skipped = [("\\\\.\\WinDisc", "no physical monitor")]
        status, out, err = run(["list"], be)
        self.assertEqual(status, 1)
        self.assertIn("No monitors found", out)
        self.assertIn("skipped \\\\.\\WinDisc", err)
        status, _, err = run(["get", "10"], be)
        self.assertEqual(status, 1)
        self.assertIn("WinDisc", err)

    def test_get(self):
        be, _ = one()
        status, out, _ = run(["get", "10", "0x6C"], be)
        self.assertEqual(status, 0)
        self.assertRegex(out, r"VCP 10 brightness \(luminance\)\s+75 of 100")
        self.assertRegex(out, r"VCP 6C red black level\s+50 of 255")
        self.assertEqual(be.writes, [])

    def test_get_failure_continues_and_exits_1(self):
        be, mon = one()
        mon.fail_reads.add(0x10)
        status, out, err = run(["get", "10", "12"], be)
        self.assertEqual(status, 1)
        self.assertIn("ERROR", err)
        self.assertIn("VCP 12", out)

    def test_bad_code_is_a_usage_error(self):
        be, _ = one()
        with self.assertRaises(SystemExit) as cm:
            run(["get", "zz"], be)
        self.assertEqual(cm.exception.code, 2)

    def test_caps(self):
        be, _ = one()
        status, out, _ = run(["caps"], be)
        self.assertEqual(status, 0)
        self.assertIn("model FAKE-DEMO", out)
        self.assertRegex(out, r"6C  red black level\s+\[writable here\]")
        self.assertRegex(out, r"10  brightness.*\[writable here\]")
        self.assertNotRegex(out, r"14  colour preset.*writable")
        self.assertRegex(out, r"D6  power mode\s+\[never written\]")
        status, out, _ = run(["caps", "--raw"], be)
        self.assertEqual(out.strip(), DEMO_CAPS)

    def test_set_is_a_dry_run_without_yes(self):
        be, mon = one()
        status, out, _ = run(["set", "6C", "48"], be)
        self.assertEqual(status, 0)
        self.assertIn("Dry run: nothing written", out)
        self.assertEqual(be.writes, [])
        self.assertEqual(mon.values[0x6C][0], 50)

    def test_set_yes_writes_and_reads_back(self):
        be, mon = one()
        status, out, _ = run(["set", "6C", "48", "--yes"], be)
        self.assertEqual(status, 0)
        self.assertEqual(be.writes, [(0, 0x6C, 48)])
        self.assertEqual(mon.values[0x6C][0], 48)
        self.assertIn("read back 48", out)
        self.assertIn("set 6C 50 --index 0 --yes", out)  # how to put it back

    def test_set_refused_outside_whitelist(self):
        be, _ = one()
        status, _, err = run(["set", "60", "17", "--yes"], be)  # input source: never writable by default
        self.assertEqual(status, 2)
        self.assertIn("REFUSED", err)
        self.assertEqual(be.writes, [])

    def test_set_refused_out_of_range(self):
        be, _ = one()
        status, _, err = run(["set", "16", "101", "--yes"], be)
        self.assertEqual(status, 2)
        self.assertIn("0..100", err)
        self.assertEqual(be.writes, [])

    def test_set_readback_mismatch_exits_1(self):
        be, mon = one()
        mon.ignore_writes.add(0x16)
        status, _, err = run(["set", "16", "96", "--yes"], be)
        self.assertEqual(status, 1)
        self.assertIn("read back 100", err)

    def test_set_allow_writes_a_code_beyond_the_whitelist_only_with_yes(self):
        be, mon = one()
        status, out, _ = run(["set", "14", "5", "--allow", "14"], be)  # dry run
        self.assertEqual(status, 0)
        self.assertIn("Allowed for this call beyond the whitelist: VCP 14", out)
        self.assertIn("Dry run", out)
        self.assertEqual(be.writes, [])
        status, out, _ = run(["set", "14", "5", "--allow", "14", "--yes"], be)
        self.assertEqual(status, 0)
        self.assertEqual(be.writes, [(0, 0x14, 5)])
        self.assertEqual(mon.values[0x14][0], 5)
        self.assertIn("set 14 11 --index 0 --allow 14 --yes", out)  # the way back needs --allow too

    def test_set_without_allow_refuses_a_code_beyond_the_whitelist(self):
        be, _ = one()
        status, _, err = run(["set", "14", "5", "--yes"], be)
        self.assertEqual(status, 2)
        self.assertIn("not in the write whitelist", err)
        self.assertEqual(be.writes, [])

    def test_set_allow_only_widens_for_the_codes_named(self):
        be, _ = one()
        status, _, _ = run(["set", "DC", "2", "--allow", "14", "--yes"], be)
        self.assertEqual(status, 2)
        self.assertEqual(be.writes, [])

    def test_set_allow_takes_a_comma_list(self):
        be, _ = one()
        status, _, _ = run(["set", "DC", "2", "--allow", "14,0xDC", "--yes"], be)
        self.assertEqual(status, 0)
        self.assertEqual(be.writes, [(0, 0xDC, 2)])

    def test_never_list_cannot_be_allowed(self):
        for code, value in (("04", 1), ("05", 1), ("08", 1), ("60", 17), ("D6", 4), ("CA", 1)):
            be, mon = one()
            mon.values.setdefault(int(code, 16), [0, 255])
            status, _, err = run(["set", code, str(value), "--allow", code, "--yes"], be)
            self.assertEqual(status, 2, code)
            self.assertIn("never-write list", err)
            self.assertEqual(be.writes, [], code)

    def test_never_code_in_allow_refuses_even_another_code(self):
        be, _ = one()
        status, _, err = run(["set", "6C", "48", "--allow", "14,D6", "--yes"], be)
        self.assertEqual(status, 2)
        self.assertIn("never-write list", err)
        self.assertEqual(be.writes, [])

    def test_bad_allow_is_a_usage_error(self):
        be, _ = one()
        for bad in ("zz", ",", "100"):
            with self.assertRaises(SystemExit, msg=bad):
                run(["set", "14", "5", "--allow", bad], be)

    def test_mismatch_puts_the_old_value_back(self):
        be, mon = one()
        mon.transform = lambda code, value: value - value % 2  # quantizes: 47 is stored as 46
        status, _, err = run(["set", "6C", "47", "--yes"], be)
        self.assertEqual(status, 1)
        self.assertIn("read back 46", err)
        self.assertIn("back at 50", err)
        self.assertEqual(be.writes, [(0, 0x6C, 47), (0, 0x6C, 50)])
        self.assertEqual(mon.values[0x6C][0], 50)

    def test_failed_write_tries_to_put_the_old_value_back_and_reports_if_it_cannot(self):
        be, mon = one()
        mon.fail_writes.add(0x6C)
        status, _, err = run(["set", "6C", "47", "--yes"], be)
        self.assertEqual(status, 1)
        self.assertIn("could not restore", err)
        self.assertIn("OSD", err)
        self.assertEqual(be.writes, [])

    def test_several_monitors_need_a_choice(self):
        be = FakeBackend([FakeMonitor("A", "fake:0", DEMO_VALUES), FakeMonitor("B", "fake:1", {0x6C: (20, 255)})])
        status, _, err = run(["get", "6C"], be)
        self.assertEqual(status, 1)
        self.assertIn("2 monitors", err)
        status, out, _ = run(["get", "6C", "--monitor", "b"], be)
        self.assertEqual(status, 0)
        self.assertIn("20 of 255", out)
        status, out, _ = run(["get", "6C", "--index", "0"], be)
        self.assertIn("50 of 255", out)


if __name__ == "__main__":
    unittest.main()
