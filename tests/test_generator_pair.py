import unittest

from locker.generators import (CoverageGuidedGenerator, RandomWalkGenerator,
                               TransitionPairGenerator)
from locker.metrics import CoverageTracker, calculate_coverage
from locker.runner import SequenceRunner
from locker.transitions import PAIRS


def cover(seqs):
    tracker, runner, first_full = CoverageTracker(), SequenceRunner(), None
    for i, s in enumerate(seqs, 1):
        tracker.add_trace(runner.run(s).trace)
        if first_full is None and not tracker.uncovered_pairs():
            first_full = i
    return tracker.summary(), first_full


class TestTransitionPair(unittest.TestCase):
    def test_count_length_and_reproducibility(self):
        a = TransitionPairGenerator(seed=3, max_length=20).generate(80)
        b = TransitionPairGenerator(seed=3, max_length=20).generate(80)
        self.assertEqual(len(a), 80)
        self.assertTrue(all(1 <= len(s) <= 20 for s in a))
        self.assertEqual(a, b)

    def test_reaches_full_pair_coverage(self):
        for seed in range(1, 6):
            summary, first_full = cover(TransitionPairGenerator(seed, 20).generate(500))
            self.assertEqual(summary["pairs_covered"], len(PAIRS), f"seed {seed}")
            self.assertEqual(summary["transition_coverage"], 100.0)
            self.assertEqual(summary["state_coverage"], 100.0)
            self.assertIsNotNone(first_full)

    def test_better_pair_coverage_than_a_and_b(self):
        for seed in range(1, 6):
            c, _ = cover(TransitionPairGenerator(seed, 20).generate(500))
            a, _ = cover(RandomWalkGenerator(seed, 20).generate(500))
            b, _ = cover(CoverageGuidedGenerator(seed, 20).generate(500))
            self.assertGreater(c["pair_coverage"], a["pair_coverage"])
            self.assertGreater(c["pair_coverage"], b["pair_coverage"])

    def test_works_with_short_max_length(self):
        seqs = TransitionPairGenerator(seed=1, max_length=4).generate(50)
        self.assertTrue(all(1 <= len(s) <= 4 for s in seqs))

    def test_reference_sut_passes(self):
        runner = SequenceRunner()
        for i, s in enumerate(TransitionPairGenerator(seed=2, max_length=20).generate(500)):
            rec = runner.run(s, f"C-{i}", "transition_pair")
            self.assertEqual(rec.outcome, "PASS", rec.failure_details)


if __name__ == "__main__":
    unittest.main()