"""Backend-level pieces: VCP code parsing, monitor selection, backend choice, the Windows backend's import."""
import sys
import unittest

from ddc.backend import DdcError, open_backend, parse_vcp_code
from ddc.fake import FakeBackend, FakeMonitor


class VcpCode(unittest.TestCase):
    def test_hex_forms(self):
        for text in ("6C", "6c", "0x6C", "0X6c", " 6C ", 0x6C):
            self.assertEqual(parse_vcp_code(text), 0x6C, text)
        self.assertEqual(parse_vcp_code("10"), 0x10)  # hex, not decimal ten

    def test_bad(self):
        for text in ("", "0x", "G1", "100", "-1", 256, "6C=5"):
            with self.assertRaises(ValueError, msg=repr(text)):
                parse_vcp_code(text)


def three():
    return FakeBackend([FakeMonitor("Dell AW3225QF", "\\\\.\\DISPLAY1"),
                        FakeMonitor("Generic PnP Monitor", "\\\\.\\DISPLAY2"),
                        FakeMonitor("Generic PnP Monitor", "\\\\.\\DISPLAY3")])


class Find(unittest.TestCase):
    def test_single_monitor_needs_no_hint(self):
        self.assertEqual(FakeBackend([FakeMonitor()]).find(), 0)

    def test_several_need_a_hint(self):
        with self.assertRaises(DdcError):
            three().find()

    def test_substring_case_insensitive(self):
        self.assertEqual(three().find("aw3225"), 0)
        self.assertEqual(three().find("DISPLAY3"), 2)

    def test_ambiguous_substring(self):
        with self.assertRaises(DdcError):
            three().find("generic")

    def test_no_match(self):
        with self.assertRaises(DdcError):
            three().find("S95B")

    def test_index(self):
        self.assertEqual(three().find(1), 1)
        self.assertEqual(three().find("2"), 2)
        with self.assertRaises(DdcError):
            three().find(5)

    def test_no_monitors(self):
        with self.assertRaises(DdcError):
            FakeBackend([]).find()


class OpenBackend(unittest.TestCase):
    def test_fake(self):
        with open_backend("fake") as be:
            self.assertEqual(be.name, "fake")
            self.assertEqual(be.get_vcp(0, 0x6C).maximum, 255)
        self.assertTrue(be.closed)

    def test_unknown(self):
        with self.assertRaises(DdcError):
            open_backend("serial")

    def test_linux_not_built(self):
        with self.assertRaises(DdcError):
            open_backend("linux")


class WindowsBackend(unittest.TestCase):
    def test_module_imports_on_any_platform(self):
        import ddc.windows  # noqa: F401  (must not touch Windows APIs at import)

    def test_error_text_takes_hresult_style_codes(self):
        # 0xC02625E5, seen 2026-11-19 with the display off: ctypes.FormatError raised OverflowError on it unsigned.
        from ddc.windows import error_text
        self.assertIsInstance(error_text(0xC02625E5), str)
        self.assertIsInstance(error_text(5), str)

    @unittest.skipIf(sys.platform == "win32", "on Windows this would enumerate the real monitors")
    def test_refuses_off_windows(self):
        from ddc.windows import Dxva2Backend
        with self.assertRaises(DdcError):
            Dxva2Backend()


if __name__ == "__main__":
    unittest.main()
