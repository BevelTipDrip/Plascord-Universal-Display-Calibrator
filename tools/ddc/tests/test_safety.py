"""The safety rules of plan-ddc-module.md, on the fake backend. No hardware is touched."""
import os
import re
import unittest

from ddc.backend import DdcError
from ddc.fake import FakeBackend, FakeMonitor
from ddc.safety import (DEFAULT_WRITE_WHITELIST, NEVER_WRITE, ReadbackMismatch, RestoreFailed, SafeDdc,
                        WriteRefused)

VALUES = {0x04: (0, 1), 0x10: (75, 100), 0x12: (75, 100), 0x14: (11, 12), 0x60: (15, 18), 0xCA: (1, 2),
          0xD6: (1, 5), 0xE1: (0, 1), 0x16: (100, 100), 0x18: (100, 100), 0x1A: (100, 100),
          0x6C: (50, 255), 0x6E: (50, 255), 0x70: (50, 255)}


def make():
    mon = FakeMonitor("TEST", "fake:0", VALUES)
    be = FakeBackend([mon])
    return be, mon, SafeDdc(be, 0)


class Whitelist(unittest.TestCase):
    def test_default_is_brightness_contrast_and_the_probes_six_codes(self):
        self.assertEqual(sorted(DEFAULT_WRITE_WHITELIST), [0x10, 0x12, 0x16, 0x18, 0x1A, 0x6C, 0x6E, 0x70])

    def test_brightness_and_contrast_writable_by_default(self):
        be, mon, ddc = make()
        self.assertEqual(ddc.set(0x10, 40), 40)
        self.assertEqual(ddc.set(0x12, 60), 60)
        self.assertEqual(be.writes, [(0, 0x10, 40), (0, 0x12, 60)])

    def test_code_outside_whitelist_is_refused_and_nothing_written(self):
        be, mon, ddc = make()
        with self.assertRaises(WriteRefused):
            ddc.set(0x14, 5)  # colour preset: readable, not writable by default
        self.assertEqual(be.writes, [])
        self.assertEqual(mon.values[0x14][0], 11)

    def test_reads_are_not_limited_by_the_whitelist(self):
        _, _, ddc = make()
        self.assertEqual(ddc.get(0x14).current, 11)
        self.assertEqual(ddc.get(0x60).current, 15)  # never-list codes are still readable

    def test_custom_whitelist(self):
        be, _, _ = make()
        ddc = SafeDdc(be, 0, whitelist={0x14: "colour preset"})
        self.assertEqual(ddc.set(0x14, 5), 5)
        with self.assertRaises(WriteRefused):
            ddc.set(0x6C, 49)

    def test_empty_whitelist_refuses_everything(self):
        be, _, _ = make()
        with self.assertRaises(WriteRefused):
            SafeDdc(be, 0, whitelist={}).set(0x6C, 49)
        self.assertEqual(be.writes, [])

    def test_whitelist_is_a_copy(self):
        _, _, ddc = make()
        ddc.whitelist[0x14] = "colour preset"
        self.assertNotIn(0x14, DEFAULT_WRITE_WHITELIST)


class RangeAndType(unittest.TestCase):
    def test_in_range_write_reads_back(self):
        be, mon, ddc = make()
        self.assertEqual(ddc.set(0x6C, 48), 48)
        self.assertEqual(be.writes, [(0, 0x6C, 48)])
        self.assertEqual(mon.values[0x6C][0], 48)

    def test_bounds_are_inclusive(self):
        be, _, ddc = make()
        ddc.set(0x6C, 0)
        ddc.set(0x6C, 255)
        self.assertEqual(be.writes, [(0, 0x6C, 0), (0, 0x6C, 255)])

    def test_out_of_range_refused(self):
        for v in (256, -1, 1000):
            be, _, ddc = make()
            with self.assertRaises(WriteRefused, msg=v):
                ddc.set(0x6C, v)
            self.assertEqual(be.writes, [])

    def test_max_comes_from_the_monitor(self):
        be, mon, ddc = make()
        mon.values[0x16] = [100, 100]
        with self.assertRaises(WriteRefused):
            ddc.set(0x16, 101)  # 101 is fine for a black level (max 255), not for this gain
        self.assertEqual(be.writes, [])

    def test_non_integers_refused(self):
        for v in (1.5, True, "48", None):
            be, _, ddc = make()
            with self.assertRaises(WriteRefused, msg=repr(v)):
                ddc.set(0x6C, v)
            self.assertEqual(be.writes, [])

    def test_failed_read_refuses_the_write(self):
        be, mon, ddc = make()
        mon.fail_reads.add(0x6C)
        with self.assertRaises(WriteRefused):
            ddc.set(0x6C, 48)
        self.assertEqual(be.writes, [])

    def test_check_write_writes_nothing(self):
        be, _, ddc = make()
        self.assertEqual(ddc.check_write(0x6C, 48).current, 50)
        self.assertEqual(be.writes, [])


class Readback(unittest.TestCase):
    def test_ignored_write_raises_mismatch(self):
        be, mon, ddc = make()
        mon.ignore_writes.add(0x16)
        with self.assertRaises(ReadbackMismatch) as cm:
            ddc.set(0x16, 96)
        self.assertEqual((cm.exception.code, cm.exception.written, cm.exception.read), (0x16, 96, 100))
        self.assertEqual(be.writes, [(0, 0x16, 96)])

    def test_quantized_write_raises_mismatch(self):
        _, mon, ddc = make()
        mon.transform = lambda code, value: value - value % 2
        self.assertEqual(ddc.set(0x6C, 48), 48)
        with self.assertRaises(ReadbackMismatch):
            ddc.set(0x6C, 47)

    def test_failed_write_raises_ddc_error_not_refused(self):
        _, mon, ddc = make()
        mon.fail_writes.add(0x6C)
        with self.assertRaises(DdcError) as cm:
            ddc.set(0x6C, 48)
        self.assertNotIsInstance(cm.exception, WriteRefused)


class Preserve(unittest.TestCase):
    def test_restores_on_normal_exit(self):
        be, mon, ddc = make()
        with ddc.preserve([0x6C, 0x6E]) as saved:
            self.assertEqual(saved, {0x6C: 50, 0x6E: 50})
            ddc.set(0x6C, 40)
            ddc.set(0x6E, 41)
        self.assertEqual((mon.values[0x6C][0], mon.values[0x6E][0]), (50, 50))
        self.assertEqual(be.writes[-2:], [(0, 0x6C, 50), (0, 0x6E, 50)])

    def test_restores_on_exception_and_reraises_it(self):
        _, mon, ddc = make()
        with self.assertRaises(ZeroDivisionError):
            with ddc.preserve([0x6C]):
                ddc.set(0x6C, 40)
                1 / 0
        self.assertEqual(mon.values[0x6C][0], 50)

    def test_restores_on_keyboard_interrupt(self):
        _, mon, ddc = make()
        with self.assertRaises(KeyboardInterrupt):
            with ddc.preserve([0x6C, 0x70]):
                ddc.set(0x70, 30)
                raise KeyboardInterrupt
        self.assertEqual(mon.values[0x70][0], 50)

    def test_restores_after_a_failed_set_inside(self):
        _, mon, ddc = make()
        with self.assertRaises(WriteRefused):
            with ddc.preserve([0x6C]):
                ddc.set(0x6C, 40)
                ddc.set(0x6C, 999)
        self.assertEqual(mon.values[0x6C][0], 50)

    def test_refuses_unlisted_code_before_reading_or_writing(self):
        be, mon, ddc = make()
        mon.fail_reads.add(0x6C)  # would raise if it were read
        with self.assertRaises(WriteRefused):
            with ddc.preserve([0x6C, 0x14]):
                self.fail("block must not run")
        self.assertEqual(be.writes, [])

    def test_failed_save_read_writes_nothing(self):
        be, mon, ddc = make()
        mon.fail_reads.add(0x6E)
        with self.assertRaises(DdcError):
            with ddc.preserve([0x6C, 0x6E]):
                self.fail("block must not run")
        self.assertEqual(be.writes, [])

    def test_restore_failure_reported_others_still_restored(self):
        _, mon, ddc = make()
        with self.assertRaises(RestoreFailed) as cm:
            with ddc.preserve([0x6C, 0x6E, 0x70]):
                for c in (0x6C, 0x6E, 0x70):
                    ddc.set(c, 40)
                mon.fail_writes.add(0x6E)
        self.assertEqual([c for c, _, _ in cm.exception.failures], [0x6E])
        self.assertIn("OSD", str(cm.exception))
        self.assertEqual((mon.values[0x6C][0], mon.values[0x6E][0], mon.values[0x70][0]), (50, 40, 50))

    def test_restore_failure_chained_to_the_original_exception(self):
        _, mon, ddc = make()
        with self.assertRaises(RestoreFailed) as cm:
            with ddc.preserve([0x6C]):
                ddc.set(0x6C, 40)
                mon.fail_writes.add(0x6C)
                raise ValueError("measurement failed")
        self.assertIsInstance(cm.exception.__cause__, ValueError)

    def test_restore_readback_mismatch_reported(self):
        _, mon, ddc = make()
        with self.assertRaises(RestoreFailed) as cm:
            with ddc.preserve([0x16]):
                ddc.set(0x16, 96)
                mon.ignore_writes.add(0x16)
        self.assertEqual(cm.exception.failures, [(0x16, 100, "read back 96")])

    def test_duplicate_codes_saved_once(self):
        be, _, ddc = make()
        with ddc.preserve([0x6C, 0x6C]) as saved:
            self.assertEqual(saved, {0x6C: 50})
        self.assertEqual(be.writes, [(0, 0x6C, 50)])


class NeverList(unittest.TestCase):
    """Safety rule 0: codes on the never-write list are refused by every route; nothing overrides it."""

    REQUIRED = (0x04, 0x05, 0x06, 0x08, 0x0A, 0x60, 0xD6)

    def test_required_codes_are_on_it(self):
        for c in self.REQUIRED:
            self.assertIn(c, NEVER_WRITE, "%02X" % c)

    def test_never_and_default_whitelist_do_not_overlap(self):
        self.assertEqual(set(NEVER_WRITE) & set(DEFAULT_WRITE_WHITELIST), set())

    def test_whitelist_naming_a_never_code_refuses_to_build(self):
        be, _, _ = make()
        for c in NEVER_WRITE:
            with self.assertRaises(WriteRefused, msg="%02X" % c):
                SafeDdc(be, 0, whitelist={c: "x", 0x6C: "red black level"})
        self.assertEqual(be.writes, [])

    def test_whitelist_edited_after_build_still_refuses(self):
        be, mon, ddc = make()
        ddc.whitelist[0x60] = "input source"
        ddc.whitelist[0xD6] = "power"
        with self.assertRaises(WriteRefused):
            ddc.set(0x60, 17)
        with self.assertRaises(WriteRefused):
            ddc.check_write(0xD6, 4)
        self.assertEqual(be.writes, [])
        self.assertEqual(mon.values[0x60][0], 15)

    def test_never_code_cannot_be_preserved_or_restored(self):
        be, mon, ddc = make()
        ddc.whitelist[0x04] = "x"
        mon.fail_reads.add(0x04)  # would raise DdcError (not WriteRefused) if it were read
        with self.assertRaises(WriteRefused):
            with ddc.preserve([0x6C, 0x04]):
                self.fail("block must not run")
        with self.assertRaises(WriteRefused):
            ddc.restore({0x6C: 50, 0x04: 1})
        self.assertEqual(be.writes, [])

    def test_display_module_never_codes_add_to_the_list(self):
        be, _, _ = make()
        ddc = SafeDdc(be, 0, never={0xE1: "power (Dell, inverted)"})
        with self.assertRaises(WriteRefused):
            ddc.set(0xE1, 1)
        with self.assertRaises(WriteRefused):
            SafeDdc(be, 0, whitelist={0xE1: "x"}, never={0xE1: "power"})
        self.assertIn(0x04, ddc.never)  # the standard list still applies
        self.assertEqual(be.writes, [])

    def test_never_codes_are_still_readable(self):
        _, _, ddc = make()
        self.assertEqual(ddc.get(0xD6).current, 1)


class Restore(unittest.TestCase):
    def test_restore_writes_back_and_reads_back(self):
        be, mon, ddc = make()
        ddc.set(0x6C, 40)
        self.assertEqual(ddc.restore({0x6C: 50}), [])
        self.assertEqual(mon.values[0x6C][0], 50)
        self.assertEqual(be.writes, [(0, 0x6C, 40), (0, 0x6C, 50)])

    def test_restore_reports_failures_instead_of_raising(self):
        _, mon, ddc = make()
        mon.ignore_writes.add(0x6E)
        self.assertEqual(ddc.restore({0x6E: 49}), [(0x6E, 49, "read back 50")])

    def test_restore_refuses_unlisted_codes_before_writing(self):
        be, _, ddc = make()
        with self.assertRaises(WriteRefused):
            ddc.restore({0x6C: 50, 0x14: 5})
        self.assertEqual(be.writes, [])


class OnlySafetyWrites(unittest.TestCase):
    """Safety rule 6: the raw Backend.set_vcp is called only from safety.py."""

    def test_no_other_module_calls_set_vcp(self):
        pkg = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        offenders = []
        for dirpath, _, files in os.walk(pkg):
            if os.path.basename(dirpath) == "tests":
                continue
            for f in files:
                if not f.endswith(".py") or f == "safety.py":
                    continue
                with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                    for n, line in enumerate(fh, 1):
                        if re.search(r"\.set_vcp\(", line):
                            offenders.append("%s:%d" % (f, n))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
