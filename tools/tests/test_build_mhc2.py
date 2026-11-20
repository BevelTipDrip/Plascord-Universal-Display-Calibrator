"""build_mhc2.py --anchors (Q-1): anchor scoring (dE ITP), picking, per-channel output codes, LUT encoding, and that
the MHC2 writer is unchanged for a single LUT. Run from tools/: python -m unittest discover -s tests -t ."""
import csv
import math
import os
import tempfile
import unittest

import build_mhc2 as b


def staircase():
    """A start profile like v2 near black: inputs 0-9 send their own code, 10-13 send 10, 14-17 send 12, then
    identity minus one (v2's i/1023 truncation)."""
    sent = list(range(10)) + [10] * 4 + [12] * 4 + [i - 1 for i in range(18, 1024)]
    lut = [k / 1023 for k in sent]  # i/1023 truncates to k (the +1e-4 in sent_codes)
    return [lut, lut, lut], sent


class Score(unittest.TestCase):
    def test_d65_at_target_scores_zero(self):
        pen, tot, ratio = b.anchor_score(0.05, 0.05, *b.D65)
        self.assertAlmostEqual(tot, 0.0, places=6)
        self.assertAlmostEqual(pen, 0.0, places=6)
        self.assertAlmostEqual(ratio, 1.0)

    def test_too_bright_costs_more_than_its_dE(self):
        pen, tot, _ = b.anchor_score(0.05, 0.06, *b.D65, raised_weight=2.0)
        self.assertGreater(pen, tot * 1.9)
        pen, tot, _ = b.anchor_score(0.05, 0.04, *b.D65, raised_weight=2.0)
        self.assertAlmostEqual(pen, tot, places=6)

    def test_tint_counts(self):
        _, grey, _ = b.anchor_score(0.05, 0.05, *b.D65)
        _, purple, _ = b.anchor_score(0.05, 0.05, 0.27, 0.24)
        self.assertGreater(purple, grey + 3)


class Pick(unittest.TestCase):
    # anchor 1's best is (10, 12, 8); anchor 2's best (9, 13, 9) lowers red, its second best (10, 13, 9) does not
    C = {1: {(10, 12, 8): (0.02, 0.02, 0.3127, 0.3290, 1), (10, 10, 10): (0.02, 0.02, 0.27, 0.24, 1)},
         2: {(9, 13, 9): (0.03, 0.03, 0.3127, 0.3290, 1), (10, 13, 9): (0.03, 0.026, 0.3127, 0.3290, 1)}}

    def test_independent_takes_each_best(self):
        self.assertEqual(b.pick_anchors(self.C, monotone=False), {1: (10, 12, 8), 2: (9, 13, 9)})

    def test_monotone_keeps_channels_non_decreasing(self):
        self.assertEqual(b.pick_anchors(self.C), {1: (10, 12, 8), 2: (10, 13, 9)})


class OutputCodes(unittest.TestCase):
    def setUp(self):
        self.start, self.sent = staircase()

    def test_anchor_inputs_send_the_picks_and_steps_share_them(self):
        picks = {12: (11, 12, 9), 16: (12, 14, 11), 100: (100, 102, 97)}
        out = b.anchor_output_codes(self.start, picks)
        for i in (10, 11, 12, 13):  # the start's step 10
            self.assertEqual([out[c][i] for c in range(3)], [11, 12, 9])
        for i in (14, 15, 16, 17):
            self.assertEqual([out[c][i] for c in range(3)], [12, 14, 11])

    def test_below_first_anchor_capped_at_its_codes(self):
        out = b.anchor_output_codes(self.start, {12: (11, 12, 9), 100: (99, 99, 99)})
        self.assertEqual([out[c][9] for c in range(3)], [9, 9, 9])
        self.assertEqual(out[2][9], 9)
        out = b.anchor_output_codes(self.start, {12: (11, 12, 5), 100: (99, 99, 99)}, monotone=False)
        self.assertEqual(out[2][9], 5)  # capped at the anchor's blue

    def test_above_last_anchor_holds_its_offsets(self):
        out = b.anchor_output_codes(self.start, {12: (10, 10, 10), 100: (100, 103, 96)})
        for i in (200, 500, 900):
            self.assertEqual([out[c][i] for c in range(3)], [self.sent[i] + 1, self.sent[i] + 4, self.sent[i] - 3])
        self.assertEqual(out[1][1023], 1023)  # clamped

    def test_between_anchors_offsets_follow_log_luminance(self):
        picks = {100: (99, 99, 99), 400: (399, 409, 399)}  # green offset 0 at 100, +10 at 400
        out = b.anchor_output_codes(self.start, picks)
        lo, hi = math.log(b.nits_from_pq(100 / 1023)), math.log(b.nits_from_pq(400 / 1023))
        i = 250
        t = (math.log(b.nits_from_pq(i / 1023)) - lo) / (hi - lo)
        self.assertEqual(out[1][i], self.sent[i] + round(10 * t))
        self.assertEqual(out[0][i], self.sent[i])

    def test_monotone_pass(self):
        picks = {12: (11, 12, 15), 16: (12, 14, 11), 100: (99, 99, 99)}  # blue would drop 15 -> 11
        out = b.anchor_output_codes(self.start, picks, monotone=True)
        self.assertTrue(all(out[2][i] >= out[2][i - 1] for i in range(1, 1024)))
        out = b.anchor_output_codes(self.start, picks, monotone=False)
        self.assertLess(out[2][16], out[2][12])


class Encoding(unittest.TestCase):
    def test_codes_survive_truncation(self):
        codes = list(range(1024))
        lut = b.codes_to_lut(codes)
        self.assertEqual(b.sent_codes(lut), codes)
        self.assertEqual(lut[0], 0.0)
        self.assertEqual(lut[1023], 1.0)
        self.assertAlmostEqual(lut[40] * 1023, 40.25)

    def test_mhc2_three_identical_lists_equal_one_list(self):
        _, tags = b.read_icc(b.DEFAULT_START)
        old = next(d for s, d, _ in tags if s == b"MHC2")
        lut = [i / 1023 for i in range(1024)]
        self.assertEqual(b.mhc2(old, lut, None)[0], b.mhc2(old, [lut, lut, lut], None)[0])

    def test_mhc2_per_channel_round_trip(self):
        _, tags = b.read_icc(b.DEFAULT_START)
        old = next(d for s, d, _ in tags if s == b"MHC2")
        luts = [b.codes_to_lut([min(i + d, 1023) for i in range(1024)]) for d in (0, 2, 5)]
        data, _ = b.mhc2(old, luts, None, neutral=True)
        with tempfile.TemporaryDirectory() as tmp:
            header, tags = b.read_icc(b.DEFAULT_START)
            path = os.path.join(tmp, "t.icc")
            b.write_icc(header, [(s, data if s == b"MHC2" else d, o) for s, d, o in tags], path)
            back = b.read_mhc2_luts(path)
        for c, d in enumerate((0, 2, 5)):
            self.assertEqual(b.sent_codes(back[c])[100], 100 + d)

    def test_mhc2_rejects_unequal_lengths(self):
        _, tags = b.read_icc(b.DEFAULT_START)
        old = next(d for s, d, _ in tags if s == b"MHC2")
        with self.assertRaises(ValueError):
            b.mhc2(old, [[0.0, 1.0], [0.0, 1.0], [0.0, 0.5, 1.0]], None)


class LoadCandidates(unittest.TestCase):
    def test_only_anchor_runs_averaged(self):
        rows = [
            ["anchor_31", "hdr", "", "31", "0.02", "0.010", "0", "0.30", "0.30", "2", "32", "34", "29"],
            ["anchor_31", "hdr", "", "31", "0.02", "0.020", "0", "0.32", "0.32", "2", "32", "34", "29"],
            ["best", "hdr", "", "31", "0.02", "0.020", "0", "0.32", "0.32", "2", "32", "34", "29"],
            ["settle", "hdr", "", "36", "0.03", "0.050", "0", "0.27", "0.24", "2", "36", "36", "36"],
            ["anchor_31", "hdr", "", "31", "0.02", "0", "0", "0", "0", "2", "31", "31", "31"],
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.csv")
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["run", "mode", "requested", "code", "target_cdm2", "Y_cdm2", "Y_sd", "x", "y", "reads",
                            "r", "g", "b"])
                w.writerows(rows)
            c = b.load_anchor_candidates([path])
        self.assertEqual(list(c), [31])
        self.assertEqual(list(c[31]), [(32, 34, 29)])
        T, Y, x, y, n = c[31][(32, 34, 29)]
        self.assertAlmostEqual(Y, 0.015)
        self.assertEqual(n, 2)


if __name__ == "__main__":
    unittest.main()
