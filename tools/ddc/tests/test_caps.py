"""The capabilities-string parser, on made-up strings in the shapes real monitors send."""
import unittest

from ddc.caps import parse_capabilities
from ddc.fake import DEMO_CAPS

TYPICAL = ("(prot(monitor)type(LCD)model(TESTMON)cmds(01 02 03 07 0C E3 F3)vcp(02 04 05 08 10 12 14(05 08 0B) "
           "16 18 1A 52 60(0F 11 12) AC AE B2 B6 C6 C8 C9 D6(01 04 05) DC(00 02 03 05) DF)mccs_ver(2.1)mswhql(1))")


class Parse(unittest.TestCase):
    def test_typical(self):
        c = parse_capabilities(TYPICAL)
        self.assertEqual((c.model, c.type, c.mccs_ver), ("TESTMON", "LCD", "2.1"))
        self.assertEqual(c.cmds, [0x01, 0x02, 0x03, 0x07, 0x0C, 0xE3, 0xF3])
        self.assertIsNone(c.vcp[0x10])
        self.assertEqual(c.vcp[0x14], [0x05, 0x08, 0x0B])
        self.assertEqual(c.vcp[0x60], [0x0F, 0x11, 0x12])
        self.assertEqual(c.vcp[0xDC], [0x00, 0x02, 0x03, 0x05])
        self.assertIn(0xDF, c.vcp)
        self.assertEqual(len(c.vcp), 22)
        self.assertEqual(c.groups["mswhql"], "1")

    def test_demo_caps_parse(self):
        c = parse_capabilities(DEMO_CAPS)
        self.assertEqual(c.model, "FAKE-DEMO")
        for code in (0x16, 0x18, 0x1A, 0x6C, 0x6E, 0x70):
            self.assertIn(code, c.vcp)

    def test_without_outer_brackets(self):
        c = parse_capabilities("prot(monitor)model(X)vcp(10 12)mccs_ver(2.2)")
        self.assertEqual((c.model, c.mccs_ver, sorted(c.vcp)), ("X", "2.2", [0x10, 0x12]))

    def test_spaces_before_brackets_and_lower_case(self):
        c = parse_capabilities("(model (x) vcp (10 14 (05 06) 6c))")
        self.assertEqual(c.model, "x")
        self.assertEqual(c.vcp, {0x10: None, 0x14: [0x05, 0x06], 0x6C: None})

    def test_codes_run_together(self):
        c = parse_capabilities("(vcp(101216(01 02)))")
        self.assertEqual(c.vcp, {0x10: None, 0x12: None, 0x16: [0x01, 0x02]})

    def test_vcpname_group_does_not_confuse_vcp(self):
        c = parse_capabilities("(vcp(10 E0)vcpname(E0(Custom Thing)))")
        self.assertEqual(sorted(c.vcp), [0x10, 0xE0])
        self.assertEqual(c.groups["vcpname"], "E0(Custom Thing)")

    def test_trailing_nul_and_unclosed(self):
        c = parse_capabilities("(model(Y)vcp(10 12\x00")
        self.assertEqual(c.model, "Y")
        self.assertEqual(sorted(c.vcp), [0x10, 0x12])

    def test_empty(self):
        for raw in ("", None, "   "):
            c = parse_capabilities(raw)
            self.assertEqual((c.model, c.vcp, c.cmds), ("", {}, []))


if __name__ == "__main__":
    unittest.main()
