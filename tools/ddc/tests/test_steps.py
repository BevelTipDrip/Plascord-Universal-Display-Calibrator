"""ddc.steps.parse_ddc_steps behaves like tools/nearblack_probe.py's parse_ddc_steps.

GOLDEN was recorded on 2026-11-19 by calling the probe's own function (tools/nearblack_probe.py, git blob 221f64c,
branch feature/ddc-module at 43fc609) on each input; the probe is not imported here (it needs Windows at import).
"""
import argparse
import unittest

from ddc.safety import DEFAULT_WRITE_WHITELIST, NEVER_WRITE
from ddc.steps import PROBE_VCPS, parse_ddc_steps

ATE = "ArgumentTypeError"
GOLDEN = [
    ("16=96;16=100,1A=96;1A=100", [{0x16: 96}, {0x16: 100, 0x1A: 96}, {0x1A: 100}]),
    ("6C=50", [{0x6C: 50}]),
    (" 6c=50 , 6E=48 ;; 70=40", [{0x6C: 50, 0x6E: 48}, {0x70: 40}]),
    ("16=96;", [{0x16: 96}]),
    ("0x16=5", [{0x16: 5}]),
    ("16=96,16=97", [{0x16: 97}]),
    ("16=-5", [{0x16: -5}]),
    ("18=1000", [{0x18: 1000}]),
    ("1a=0;1A=100", [{0x1A: 0}, {0x1A: 100}]),
    ("10=5", (ATE, "VCP 10 is not one of 16, 18, 1A, 6C, 6E, 70")),
    ("60=17", (ATE, "VCP 60 is not one of 16, 18, 1A, 6C, 6E, 70")),
    ("D6=4", (ATE, "VCP D6 is not one of 16, 18, 1A, 6C, 6E, 70")),
    ("", (ATE, "no DDC steps given")),
    (";", (ATE, "no DDC steps given")),
    (";;", (ATE, "no DDC steps given")),
    (" , ", (ATE, "no DDC steps given")),
    ("zz=1", ("ValueError", "invalid literal for int() with base 16: 'zz'")),
    ("16=abc", ("ValueError", "invalid literal for int() with base 10: 'abc'")),
    ("16", ("ValueError", "invalid literal for int() with base 10: ''")),
    ("16=1=2", ("ValueError", "invalid literal for int() with base 10: '1=2'")),
    ("=5", ("ValueError", "invalid literal for int() with base 16: ''")),
    ("16=", ("ValueError", "invalid literal for int() with base 10: ''")),
    ("6C=50;10=5", (ATE, "VCP 10 is not one of 16, 18, 1A, 6C, 6E, 70")),
]


class SameAsTheProbe(unittest.TestCase):
    def test_golden_table(self):
        for text, want in GOLDEN:
            if isinstance(want, list):
                self.assertEqual(parse_ddc_steps(text), want, repr(text))
            else:
                kind, message = want
                with self.assertRaises(Exception, msg=repr(text)) as cm:
                    parse_ddc_steps(text)
                self.assertEqual((type(cm.exception).__name__, str(cm.exception)), (kind, message), repr(text))

    def test_argparse_reports_it_as_a_usage_error(self):
        ap = argparse.ArgumentParser()
        ap.add_argument("--ddc-steps", type=parse_ddc_steps)
        self.assertEqual(ap.parse_args(["--ddc-steps", "6C=48"]).ddc_steps, [{0x6C: 48}])


class Codes(unittest.TestCase):
    def test_probe_codes_are_the_probes_six(self):
        self.assertEqual(sorted(PROBE_VCPS), [0x16, 0x18, 0x1A, 0x6C, 0x6E, 0x70])

    def test_probe_codes_are_writable_by_the_package(self):
        for c in PROBE_VCPS:
            self.assertIn(c, DEFAULT_WRITE_WHITELIST)
            self.assertNotIn(c, NEVER_WRITE)

    def test_other_code_list(self):
        self.assertEqual(parse_ddc_steps("10=40;12=60", codes=[0x10, 0x12]), [{0x10: 40}, {0x12: 60}])
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_ddc_steps("16=96", codes=[0x10])


if __name__ == "__main__":
    unittest.main()
