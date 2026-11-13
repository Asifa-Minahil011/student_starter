"""Mutation testing: run generated sequences against each mutant."""
import time

from .mutants import MUTANTS
from .runner import SequenceRunner, format_sequence


def evaluate_mutant(spec, sequences, strategy: str = "manual") -> dict:
    """Run `sequences` (in order) against one mutant; stop at the first failing test (kill)."""
    runner = SequenceRunner(sut_factory=spec.cls)
    start = time.perf_counter()
    result = {"mutant_id": spec.mutant_id, "mutant": spec.name, "strategy": strategy,
              "equivalent": spec.equivalent, "killed": False, "tests_run": 0,
              "killing_test_id": None, "killing_sequence": "", "failure_details": ""}
    for i, seq in enumerate(sequences):
        rec = runner.run(seq, f"{strategy}-{i}", strategy)
        result["tests_run"] = i + 1
        if rec.outcome == "FAIL":
            result.update(killed=True, killing_test_id=rec.test_id,
                          killing_sequence=format_sequence(rec.sequence),
                          failure_details=rec.failure_details)
            break
    result["seconds"] = round(time.perf_counter() - start, 4)
    return result


def evaluate_all(sequences, strategy: str = "manual", mutants=MUTANTS) -> list:
    return [evaluate_mutant(spec, sequences, strategy) for spec in mutants]