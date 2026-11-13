import unittest

from locker.generators import (CoverageGuidedGenerator, RandomWalkGenerator,
                               TransitionPairGenerator)
from locker.metrics import mutation_summary
from locker.mutants import MUTANTS
from locker.mutation import evaluate_all, evaluate_mutant
from locker.runner import SequenceRunner
from locker.sut import ParcelLocker

REAL = [m for m in MUTANTS if not m.equivalent]
EQUIV = [m for m in MUTANTS if m.equivalent]


class TestMutants(unittest.TestCase):
    def test_at_least_eight_distinct_non_equivalent_mutants(self):
        self.assertGreaterEqual(len(REAL), 8)
        self.assertEqual(len({m.name for m in MUTANTS}), len(MUTANTS))

    def test_witness_kills_each_real_mutant_but_not_the_reference(self):
        for spec in REAL:
            self.assertTrue(spec.witness, spec.mutant_id)
            ref = SequenceRunner(sut_factory=ParcelLocker).run(spec.witness)
            self.assertEqual(ref.outcome, "PASS", f"{spec.mutant_id} reference: {ref.failure_details}")
            mut = SequenceRunner(sut_factory=spec.cls).run(spec.witness)
            self.assertEqual(mut.outcome, "FAIL", f"{spec.mutant_id} not killed by its witness")

    def test_equivalent_mutants_survive_a_large_search(self):
        seqs = []
        for G in (RandomWalkGenerator, CoverageGuidedGenerator, TransitionPairGenerator):
            seqs += G(seed=11, max_length=20).generate(300)
        for spec in EQUIV:
            self.assertFalse(evaluate_mutant(spec, seqs)["killed"], spec.mutant_id)

    def test_mutation_summary_over_a_strategy(self):
        seqs = TransitionPairGenerator(seed=1, max_length=20).generate(500)
        results = evaluate_all(seqs, "transition_pair")
        s = mutation_summary([{"name": r["mutant_id"], "killed": r["killed"],
                               "equivalent": r["equivalent"]} for r in results])
        self.assertEqual(s["equivalent"], ["M13", "M14"])
        self.assertGreater(s["mutation_score"], 0)


if __name__ == "__main__":
    unittest.main()