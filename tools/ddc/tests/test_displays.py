"""Display modules (ddc.displays): the AW3225QF skeleton's data rules, and how the CLI uses a module."""
import contextlib
import io
import unittest

from ddc import displays
from ddc.cli import main
from ddc.displays import ASK, NEVER, SAFE, aw3225qf
from ddc.fake import FakeBackend, FakeMonitor
from ddc.safety import DEFAULT_WRITE_WHITELIST, NEVER_WRITE, SafeDdc, WriteRefused

MOD = aw3225qf.MODULE
AW_VALUES = {0x10: (75, 100), 0x14: (5, 12), 0x16: (100, 100), 0x60: (0x0F0F, 0x1212), 0x6C: (50, 255),
             0xE1: (0, 1), 0xE2: (39, 255)}
AW_CAPS = "(prot(monitor)type(LCD)model(AW3225QF)vcp(10 14(01 05 08 0B 0C) 16 60(0F 11 12) E1 E2)mccs_ver(2.1))"


def aw(description="Dell AW3225QF(DisplayPort)"):
    mon = FakeMonitor(description, "fake:0", AW_VALUES, AW_CAPS)
    return FakeBackend([mon]), mon


def run(argv, be=None):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = main(argv, backend=be)
    return status, out.getvalue(), err.getvalue()


class Lookup(unittest.TestCase):
    def test_found_by_description_or_model(self):
        self.assertIs(displays.for_monitor("Dell AW3225QF(DisplayPort)"), MOD)
        self.assertIs(displays.for_monitor("Generic PnP Monitor", "AW3225QF"), MOD)
        self.assertIsNone(displays.for_monitor("Generic PnP Monitor"))
        self.assertIsNone(displays.for_monitor("AW3423DWF"))
        self.assertIs(displays.by_key("AW3225QF"), MOD)
        self.assertIsNone(displays.by_key("u3421we"))


class Aw3225qfData(unittest.TestCase):
    """Rules every entry keeps: a module adds never codes, it never makes a code writable."""

    def test_safety_classes_are_known(self):
        for c, ctl in MOD.controls.items():
            self.assertIn(ctl.safety, (SAFE, ASK, NEVER), "%02X" % c)
            self.assertEqual(ctl.code, c)

    def test_safe_is_exactly_the_default_whitelist(self):
        self.assertEqual(MOD.by_safety(SAFE), sorted(DEFAULT_WRITE_WHITELIST))

    def test_core_never_codes_stay_never(self):
        for c in MOD.controls:
            if c in NEVER_WRITE:
                self.assertEqual(MOD.controls[c].safety, NEVER, "%02X" % c)

    def test_module_never_codes_do_not_touch_the_whitelist(self):
        self.assertEqual(set(MOD.never()) & set(DEFAULT_WRITE_WHITELIST), set())
        SafeDdc(FakeBackend([FakeMonitor()]), 0, never=MOD.never())  # builds: no overlap with the default list

    def test_dell_power_and_identification_codes_are_never(self):
        for c in (0xE1, 0xC8, 0xC9):
            self.assertEqual(MOD.controls[c].safety, NEVER, "%02X" % c)

    def test_no_manufacturer_code_is_safe(self):
        self.assertFalse([c for c in MOD.by_safety(SAFE) if c >= 0xE0])

    def test_unconfirmed_entries_say_so(self):
        for c, ctl in MOD.controls.items():
            self.assertTrue(ctl.source, "%02X" % c)
            if not ctl.confirmed:
                self.assertIn("not confirmed on this monitor", ctl.source, "%02X" % c)

    def test_confirmed_entries_are_the_2026_11_18_reads(self):
        confirmed = sorted(c for c, ctl in MOD.controls.items() if ctl.confirmed)
        self.assertEqual(confirmed, [0x16, 0x18, 0x1A, 0x6C, 0x6E, 0x70])

    def test_black_levels_marked_missing_from_caps(self):
        for c in (0x6C, 0x6E, 0x70):
            self.assertIs(MOD.controls[c].in_caps, False)

    def test_every_source_named_in_an_entry_is_listed(self):
        keys = set(MOD.sources)
        for c, ctl in MOD.controls.items():
            for word in ctl.source.replace(",", " ").replace(";", " ").split():
                if word in ("vdu84", "aw3423dwf-map", "u3421we", "dell-pbp", "m1ddc-codes", "nearblack-tint"):
                    self.assertIn(word, keys, "%02X" % c)


class CliWithModule(unittest.TestCase):
    def test_module_never_code_refused_even_with_allow(self):
        be, _ = aw()
        status, _, err = run(["set", "E1", "1", "--allow", "E1", "--yes"], be)
        self.assertEqual(status, 2)
        self.assertIn("never-write list", err)
        self.assertEqual(be.writes, [])

    def test_display_none_does_not_lift_the_modules_never_codes(self):
        for opt in ("none", "auto"):
            be, _ = aw()
            status, _, _ = run(["set", "E1", "1", "--allow", "E1", "--yes", "--display", opt], be)
            self.assertEqual(status, 2, opt)
            self.assertEqual(be.writes, [], opt)

    def test_named_module_applies_to_a_generic_description(self):
        be, _ = aw("Generic PnP Monitor")
        status, _, _ = run(["set", "E1", "1", "--allow", "E1", "--yes", "--display", "aw3225qf"], be)
        self.assertEqual(status, 2)
        self.assertEqual(be.writes, [])

    def test_ask_first_code_writable_with_allow(self):
        be, mon = aw()
        status, _, _ = run(["set", "E2", "40", "--allow", "E2", "--yes"], be)
        self.assertEqual(status, 0)
        self.assertEqual(be.writes, [(0, 0xE2, 40)])

    def test_get_prints_module_names_and_value_meanings(self):
        be, _ = aw()
        status, out, _ = run(["get", "14", "60", "E2"], be)
        self.assertEqual(status, 0)
        self.assertRegex(out, r"VCP 14 colour preset\s+5 of 12\s+\(6500 K\)")
        self.assertRegex(out, r"VCP 60 input source\s+3855 of 4626\s+\(DisplayPort 1\)")  # low byte, as vdu84
        self.assertRegex(out, r"VCP E2 preset mode \(report\)\s+39 of 255\s+\(Desktop \(HDR\)\)")
        status, out, _ = run(["get", "E2", "--display", "none"], be)
        self.assertRegex(out, r"VCP E2 manufacturer specific\s+39 of 255$")

    def test_caps_marks_module_never_codes(self):
        be, _ = aw()
        status, out, _ = run(["caps"], be)
        self.assertIn("display module AW3225QF", out)
        self.assertRegex(out, r"E1  Dell power \(inverted\)\s+\[never written\]")
        self.assertRegex(out, r"E2  preset mode \(report\)")

    def test_scan_uses_module_names(self):
        be, _ = aw("Generic PnP Monitor")  # found from the capabilities model instead
        status, out, _ = run(["scan", "E2", "6C"], be)
        self.assertEqual(status, 0)
        self.assertRegex(out, r"E2\s+preset mode \(report\)\s+yes")
        self.assertRegex(out, r"6C\s+red black level\s+yes.*hidden")
        self.assertIn("Display module: AW3225QF", out)
        self.assertEqual(be.writes, [])

    def test_display_command(self):
        status, out, _ = run(["display", "--display", "aw3225qf"])  # no backend opened
        self.assertEqual(status, 0)
        self.assertRegex(out, r"6C  red black level\s+safe\s+NOT in caps\s+read 50 of 255")
        self.assertRegex(out, r"E1  Dell power \(inverted\)\s+never")
        status, _, err = run(["display", "--display", "nosuch"], FakeBackend([FakeMonitor()]))
        self.assertEqual(status, 2)
        status, out, _ = run(["display"], FakeBackend([FakeMonitor("OTHER")]))
        self.assertIn("No display module", out)


if __name__ == "__main__":
    unittest.main()
