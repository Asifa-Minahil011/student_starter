import unittest

from locker.generators import CoverageGuidedGenerator, RandomWalkGenerator, candidate_commands
from locker.metrics import CoverageTracker, calculate_coverage
from locker.runner import SequenceRunner
from locker.transitions import TRANSITIONS, model_in_state
from locker.types import State


def sequences_to_full_transition_coverage(seqs):
    tracker = CoverageTracker()
    runner = SequenceRunner()
    for i, s in enumerate(seqs, 1):
        tracker.add_trace(runner.run(s).trace)
        if not tracker.uncovered_transitions():
            return i
    return None


class TestCoverageGuided(unittest.TestCase):
    def test_every_transition_has_a_candidate_command(self):
        """Prerequisite: the candidate pool can trigger all 35 transitions."""
        reachable = set()
        for state in State:
            m = model_in_state(state)
            reachable |= {m.classify(c) for c in candidate_commands(m)}
        self.assertEqual(reachable, set(TRANSITIONS))

    def test_count_length_and_reproducibility(self):
        a = CoverageGuidedGenerator(seed=4, max_length=20).generate(60)
        b = CoverageGuidedGenerator(seed=4, max_length=20).generate(60)
        self.assertEqual(len(a), 60)
        self.assertTrue(all(1 <= len(s) <= 20 for s in a))
        self.assertEqual(a, b)

    def test_reaches_full_state_and_transition_coverage(self):
        seqs = CoverageGuidedGenerator(seed=1, max_length=20).generate(500)
        recs = [SequenceRunner().run(s) for s in seqs]
        cov = calculate_coverage([r.trace for r in recs])
        self.assertEqual(cov["state_coverage"], 100.0)
        self.assertEqual(cov["transition_coverage"], 100.0)

    def test_covers_all_transitions_faster_than_random(self):
        for seed in range(1, 6):
            b = sequences_to_full_transition_coverage(
                CoverageGuidedGenerator(seed, 20).generate(500))
            a = sequences_to_full_transition_coverage(
                RandomWalkGenerator(seed, 20).generate(500))
            self.assertIsNotNone(b)
            self.assertLessEqual(b, a, f"seed {seed}: B={b} A={a}")

    def test_reference_sut_passes(self):
        runner = SequenceRunner()
        for i, s in enumerate(CoverageGuidedGenerator(seed=2, max_length=20).generate(500)):
            rec = runner.run(s, f"B-{i}", "coverage_guided")
            self.assertEqual(rec.outcome, "PASS", rec.failure_details)


if __name__ == "__main__":
    unittest.main()