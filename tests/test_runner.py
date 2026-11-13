import random
import unittest

from locker.runner import SequenceRunner
from locker.sut import ParcelLocker
from locker.types import Command, Operation, State


def C(op, cid="C1", code="", expired=False):
    return Command(Operation[op], customer_id=cid, code=code, expired=expired)

FULL_LIFECYCLE = [C("RESERVE"), C("DEPOSIT", code="R-C1"), C("RETRIEVE", code="P-C1")]


class StaleCredential(ParcelLocker):            # demo mutant: retrieval code not cleared
    def _clear(self):
        keep = self.retrieval_code
        super()._clear()
        self.retrieval_code = keep


class CrashingSUT(ParcelLocker):
    def execute(self, command):
        raise RuntimeError("boom")


class TestRunner(unittest.TestCase):
    def test_reference_sut_passes_lifecycle(self):
        rec = SequenceRunner().run(FULL_LIFECYCLE, "T1", "manual")
        self.assertEqual(rec.outcome, "PASS", rec.failure_details)
        self.assertEqual(len(rec.trace), 3)

    def test_reference_sut_passes_many_random_sequences(self):
        rng = random.Random(0)
        ops = list(Operation)
        runner = SequenceRunner()
        for n in range(300):
            seq = [Command(rng.choice(ops), rng.choice(["C1", "C2"]),
                           rng.choice(["", "R-C1", "P-C1", "R-C2", "P-C2", "X"]),
                           rng.choice([True, False])) for _ in range(rng.randint(1, 20))]
            rec = runner.run(seq, f"R{n}", "random")
            self.assertEqual(rec.outcome, "PASS", rec.failure_details)

    def test_detects_stale_credential_mutant(self):
        rec = SequenceRunner(sut_factory=StaleCredential).run(FULL_LIFECYCLE, "T2", "manual")
        self.assertEqual(rec.outcome, "FAIL")
        self.assertEqual(rec.failure_step, 2)
        self.assertIn("snapshot mismatch", rec.failure_details)

    def test_sut_exception_is_a_failure_not_a_crash(self):
        rec = SequenceRunner(sut_factory=CrashingSUT).run(FULL_LIFECYCLE, "T3", "manual")
        self.assertEqual(rec.outcome, "FAIL")
        self.assertIn("RuntimeError", rec.failure_details)

    def test_record_serialises(self):
        d = SequenceRunner().run(FULL_LIFECYCLE, "T4", "manual").to_dict()
        for key in ("test_id", "strategy", "sequence", "initial_state", "expected_results",
                    "actual_results", "expected_final", "actual_final", "outcome", "failure_details"):
            self.assertIn(key, d)


if __name__ == "__main__":
    unittest.main()