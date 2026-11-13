import unittest

from locker.generators import RandomWalkGenerator, candidate_commands, is_valid
from locker.metrics import calculate_coverage, redundancy
from locker.model import LockerModel
from locker.runner import SequenceRunner
from locker.types import Command, Operation


class TestRandomWalk(unittest.TestCase):
    def test_count_and_length_bounds(self):
        seqs = RandomWalkGenerator(seed=1, max_length=20).generate(100)
        self.assertEqual(len(seqs), 100)
        self.assertTrue(all(1 <= len(s) <= 20 for s in seqs))

    def test_reproducible_with_same_seed(self):
        a = RandomWalkGenerator(seed=7, max_length=20).generate(50)
        b = RandomWalkGenerator(seed=7, max_length=20).generate(50)
        self.assertEqual(a, b)

    def test_different_seeds_differ(self):
        a = RandomWalkGenerator(seed=1, max_length=20).generate(50)
        b = RandomWalkGenerator(seed=2, max_length=20).generate(50)
        self.assertNotEqual(a, b)

    def test_contains_valid_and_invalid_commands(self):
        seqs = RandomWalkGenerator(seed=3, max_length=20).generate(200)
        accepted = rejected = 0
        for s in seqs:
            m = LockerModel()
            for c in s:
                if m.step(c).accepted: accepted += 1
                else: rejected += 1
        self.assertGreater(accepted, 0)
        self.assertGreater(rejected, 0)

    def test_candidates_include_a_valid_command_in_every_state(self):
        for prefix in ([], [Command(Operation.RESERVE)],
                       [Command(Operation.RESERVE), Command(Operation.DEPOSIT, code="R-C1")],
                       [Command(Operation.DISABLE)]):
            m = LockerModel()
            for c in prefix: m.step(c)
            self.assertTrue(any(is_valid(m, c) for c in candidate_commands(m)))

    def test_reference_sut_passes_generated_tests(self):
        runner = SequenceRunner()
        for i, seq in enumerate(RandomWalkGenerator(seed=5, max_length=20).generate(500)):
            rec = runner.run(seq, f"A-{i}", "random_walk")
            self.assertEqual(rec.outcome, "PASS", rec.failure_details)


if __name__ == "__main__":
    unittest.main()