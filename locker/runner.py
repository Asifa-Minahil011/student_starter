"""Automated test execution: run a sequence on the SUT and on the model in lockstep."""
from dataclasses import dataclass, field
from typing import Callable

from .model import LockerModel
from .oracle import check_state_invariants, check_step_invariants
from .sut import ParcelLocker
from .types import Command, Snapshot


def format_command(c: Command) -> str:
    """Compact, readable text form of one command (used in CSV/JSON/report)."""
    return f"{c.operation.value}(cid={c.customer_id!r},code={c.code!r},expired={c.expired})"


def format_sequence(seq) -> str:
    return " ; ".join(format_command(c) for c in seq)


@dataclass
class TestRecord:
    test_id: str
    strategy: str
    sequence: list
    initial_state: str
    expected_results: list = field(default_factory=list)   # [(accepted, message)] per step
    actual_results: list = field(default_factory=list)
    expected_final: Snapshot | None = None
    actual_final: Snapshot | None = None
    outcome: str = "PASS"                                   # "PASS" | "FAIL"
    failure_step: int | None = None                         # 0-based command index
    failure_details: str = ""
    trace: list = field(default_factory=list)               # model transitions executed

    def to_dict(self) -> dict:
        snap = lambda s: None if s is None else {
            "state": s.state.value, "customer_id": s.customer_id,
            "reservation_code": s.reservation_code, "retrieval_code": s.retrieval_code}
        return {
            "test_id": self.test_id, "strategy": self.strategy,
            "sequence": format_sequence(self.sequence), "length": len(self.sequence),
            "initial_state": self.initial_state,
            "expected_results": ";".join(str(a) for a, _ in self.expected_results),
            "actual_results": ";".join(str(a) for a, _ in self.actual_results),
            "expected_final": snap(self.expected_final), "actual_final": snap(self.actual_final),
            "outcome": self.outcome, "failure_step": self.failure_step,
            "failure_details": self.failure_details,
        }


class SequenceRunner:
    """Execute each sequence against a FRESH SUT and a FRESH model.

    After every command it checks:
      1. accepted flag equals the model's expectation,
      2. the complete snapshot equals the model's snapshot,
      3. model-independent invariants on the SUT snapshot,
      4. step invariants (rejected => no change, etc.) on the SUT.
    Message text is NOT compared (requirements do not define it; assumption 5).
    Stops at the first divergence and records it.
    """

    def __init__(self, sut_factory: Callable = ParcelLocker,
                 model_factory: Callable = LockerModel):
        self.sut_factory = sut_factory
        self.model_factory = model_factory

    def run(self, sequence, test_id: str = "T0", strategy: str = "manual") -> TestRecord:
        sut, model = self.sut_factory(), self.model_factory()
        rec = TestRecord(test_id, strategy, list(sequence), model.snapshot().state.value)

        for i, cmd in enumerate(sequence):
            rec.trace.append(model.classify(cmd))          # transition the MODEL expects
            before = sut.snapshot()
            exp = model.step(cmd)
            rec.expected_results.append((exp.accepted, exp.message))
            try:
                act = sut.execute(cmd)
            except Exception as e:                          # a crash is a failure, not a runner crash
                rec.actual_results.append((None, f"EXCEPTION {type(e).__name__}: {e}"))
                self._fail(rec, i, f"SUT raised {type(e).__name__}: {e}")
                break
            rec.actual_results.append((act.accepted, act.message))
            after = sut.snapshot()

            problems = []
            if act.accepted != exp.accepted:
                problems.append(f"result mismatch: expected accepted={exp.accepted}, "
                                f"actual accepted={act.accepted} (SUT msg '{act.message}')")
            if after != model.snapshot():
                problems.append(f"snapshot mismatch: expected {model.snapshot()}, actual {after}")
            problems += check_state_invariants(after)
            problems += check_step_invariants(cmd.operation, act.accepted, before, after)
            if problems:
                self._fail(rec, i, " | ".join(problems))
                break

        rec.expected_final, rec.actual_final = model.snapshot(), sut.snapshot()
        return rec

    @staticmethod
    def _fail(rec: TestRecord, step: int, details: str):
        rec.outcome, rec.failure_step = "FAIL", step
        rec.failure_details = f"step {step} ({format_command(rec.sequence[step])}): {details}"