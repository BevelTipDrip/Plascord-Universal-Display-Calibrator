"""--keep-awake / --sleep-after and wait_awake on fake backends: order of power calls, D6 polling, settle time,
release on every exit, the standby warning in scan, and that none of it writes a VCP code."""
import contextlib
import io
import unittest

from ddc.cli import main
from ddc.fake import DEMO_CAPS, DEMO_VALUES, FakeBackend, FakeMonitor, FakePower
from ddc.power import POLL_S, SETTLE_S, WAKE_TIMEOUT_S, Power, wait_awake


def run(argv, be, power):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = main(argv, backend=be, power=power)
    return status, out.getvalue(), err.getvalue()


def asleep():
    """A monitor in standby (D6 = 4) that turns on (D6 = 1) when woken."""
    mon = FakeMonitor("FAKE-DEMO", "fake:0", DEMO_VALUES, DEMO_CAPS)
    mon.values[0xD6] = [4, 255]
    be = FakeBackend([mon])

    def wake():
        mon.values[0xD6][0] = 1
    return be, mon, FakePower(on_wake=wake)


class WaitAwake(unittest.TestCase):
    def test_on_at_once_settles(self):
        be, mon, _ = asleep()
        mon.values[0xD6][0] = 1
        self.assertTrue(wait_awake(be, 0))
        self.assertEqual(be.waits, [SETTLE_S])

    def test_polls_until_on_then_settles(self):
        be, mon, _ = asleep()
        calls = []

        def turn_on_later(seconds):
            calls.append(seconds)
            if len(calls) == 3:
                mon.values[0xD6][0] = 1
        be.wait = turn_on_later
        self.assertTrue(wait_awake(be, 0))
        self.assertEqual(calls, [POLL_S, POLL_S, POLL_S, SETTLE_S])

    def test_gives_up_after_timeout(self):
        be, _, _ = asleep()
        logs = []
        self.assertFalse(wait_awake(be, 0, log=logs.append))
        self.assertAlmostEqual(sum(be.waits), WAKE_TIMEOUT_S)
        self.assertIn("WARNING", logs[-1])

    def test_failed_d6_read_counts_as_not_on(self):
        be, mon, _ = asleep()
        mon.fail_reads.add(0xD6)
        self.assertFalse(wait_awake(be, 0, timeout=1.0))


class KeepAwakeCli(unittest.TestCase):
    def test_keep_awake_holds_wakes_waits_and_releases(self):
        be, _, power = asleep()
        status, out, err = run(["get", "10", "--keep-awake"], be, power)
        self.assertEqual(status, 0)
        self.assertEqual(power.calls, ["wake", "hold", "release"])
        self.assertIn("display on (VCP D6 = 1)", err)
        self.assertIn(SETTLE_S, be.waits)
        self.assertEqual(be.writes, [])

    def test_sleep_after_turns_the_display_off_last(self):
        be, _, power = asleep()
        status, _, _ = run(["get", "10", "--keep-awake", "--sleep-after"], be, power)
        self.assertEqual(status, 0)
        self.assertEqual(power.calls, ["wake", "hold", "release", "display_off"])

    def test_sleep_after_alone(self):
        be, _, power = asleep()
        run(["get", "10", "--sleep-after"], be, power)
        self.assertEqual(power.calls, ["display_off"])

    def test_released_even_when_the_command_fails(self):
        be, mon, power = asleep()
        mon.fail_reads.add(0x10)
        status, _, _ = run(["get", "10", "--keep-awake", "--sleep-after"], be, power)
        self.assertEqual(status, 1)
        self.assertEqual(power.calls[-2:], ["release", "display_off"])

    def test_no_power_calls_without_the_options(self):
        be, _, power = asleep()
        run(["get", "10"], be, power)
        self.assertEqual(power.calls, [])

    def test_list_only_holds_and_wakes(self):
        be, _, power = asleep()
        status, _, _ = run(["list", "--keep-awake"], be, power)
        self.assertEqual(status, 0)
        self.assertEqual(power.calls, ["wake", "hold", "release"])
        self.assertEqual(be.reads, [])

    def test_unsupported_platform_warns_and_continues(self):
        be, _, _ = asleep()
        status, _, err = run(["get", "10", "--keep-awake", "--sleep-after"], be, Power())
        self.assertEqual(status, 0)
        self.assertIn("Windows only", err)

    def test_still_asleep_warns_and_runs(self):
        mon = FakeMonitor("FAKE-DEMO", "fake:0", DEMO_VALUES, DEMO_CAPS)
        mon.values[0xD6] = [4, 255]
        be, power = FakeBackend([mon]), FakePower()  # waking does nothing
        status, _, err = run(["get", "10", "--keep-awake"], be, power)
        self.assertEqual(status, 0)
        self.assertIn("not on after", err)


class ScanStandbyWarning(unittest.TestCase):
    def test_scan_warns_in_standby(self):
        be, _, power = asleep()
        status, out, _ = run(["scan", "D6", "10"], be, power)
        self.assertEqual(status, 0)
        self.assertIn("WARNING power mode VCP D6 read 4", out)

    def test_scan_keep_awake_has_no_warning(self):
        be, _, power = asleep()
        status, out, _ = run(["scan", "D6", "10", "--keep-awake"], be, power)
        self.assertEqual(status, 0)
        self.assertNotIn("WARNING", out)
        self.assertEqual(be.writes, [])


if __name__ == "__main__":
    unittest.main()
