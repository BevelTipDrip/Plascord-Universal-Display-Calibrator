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
        self.assertNotRegex(out, r"10  brightness.*writable")
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
