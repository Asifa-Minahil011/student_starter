import unittest

from locker.metrics import CoverageTracker, calculate_coverage, mutation_summary, redundancy
from locker.model import LockerModel
from locker.runner import SequenceRunner
from locker.transitions import (TRANSITIONS, PAIRS, TARGET, OUTGOING, command_for,
                                model_in_state, shortest_path, describe)
from locker.types import Command, Operation, State


class TestCatalogue(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(len(TRANSITIONS), 35)
        self.assertEqual(len(PAIRS), sum(len(OUTGOING[TARGET[t]]) for t in TRANSITIONS))
        self.assertEqual(len(set(PAIRS)), len(PAIRS))

    def test_command_for_triggers_the_transition(self):
        for t in TRANSITIONS:
            m = model_in_state(t[0])
            cid = m.customer_id or "C1"
            self.assertEqual(m.classify(command_for(t, cid)), t, describe(t))

    def test_target_matches_model_step(self):
        for t in TRANSITIONS:
            m = model_in_state(t[0])
            m.step(command_for(t, m.customer_id or "C1"))
            self.assertEqual(m.state, TARGET[t])

    def test_shortest_paths_reach_states(self):
        for s in State:
            m = LockerModel()
            for c in shortest_path(s):
                m.step(c)
            self.assertEqual(m.state, s)


class TestCoverage(unittest.TestCase):
    def test_empty(self):
        s = calculate_coverage([])
        self.assertEqual(s["transitions_covered"], 0)
        self.assertEqual(s["states_covered"], 1)         # initial state only

    def test_lifecycle_trace(self):
        rec = SequenceRunner().run([Command(Operation.RESERVE),
                                    Command(Operation.DEPOSIT, code="R-C1"),
                                    Command(Operation.RETRIEVE, code="P-C1")])
        s = calculate_coverage([rec.trace])
        self.assertEqual(s["transitions_covered"], 3)
        self.assertEqual(s["pairs_covered"], 2)           # (RESERVE,DEPOSIT), (DEPOSIT,RETRIEVE)
        self.assertEqual(s["states_covered"], 3)          # AVAILABLE, RESERVED, OCCUPIED

    def test_pairs_do_not_span_sequences(self):
        t = TRANSITIONS[0]
        tr = CoverageTracker()
        tr.add_trace([t]); tr.add_trace([t])
        self.assertEqual(len(tr.pairs), 0)

    def test_full_coverage_reachable_by_construction(self):
        tr = CoverageTracker()
        for t in TRANSITIONS:
            tr.add_trace([t])                             # one single-transition trace each
        self.assertEqual(tr.summary()["transition_coverage"], 100.0)


class TestMutationAndRedundancy(unittest.TestCase):
    def test_mutation_score_excludes_equivalent(self):
        r = mutation_summary([{"name": "M1", "killed": True},
                              {"name": "M2", "killed": False},
                              {"name": "M3", "killed": False, "equivalent": True},
                              {"name": "M4", "killed": True}])
        self.assertEqual(r["mutation_score"], round(100 * 2 / 3, 2))
        self.assertEqual(r["equivalent"], ["M3"])
        self.assertEqual(r["survived"], ["M2"])

    def test_redundancy(self):
        a = [Command(Operation.RESERVE)]
        b = [Command(Operation.DISABLE)]
        self.assertEqual(redundancy([a, b, a])["duplicates"], 1)


if __name__ == "__main__":
    unittest.main()