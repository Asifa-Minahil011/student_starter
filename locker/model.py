"""Independent executable model of one parcel-locker compartment.

Derived ONLY from data/requirements.md and report/behaviour_table.md.
It never imports or calls locker.sut.

Design: table-driven. RULES lists every ACCEPTED (state, operation) case.
Anything not in the table is rejected (Rule 12: rejected => no change).
"""
from dataclasses import dataclass
from typing import Callable

from .types import State, Operation, Command, Result, Snapshot

# Outcome labels used for transition identification (coverage, reporting)
ACCEPTED = "accepted"
REJECTED_PRECONDITION = "rejected_precondition"  # operation not allowed in this state
REJECTED_GUARD = "rejected_guard"                # state ok, but guard failed


@dataclass(frozen=True)
class Rule:
    source: State
    operation: Operation
    target: State
    guard: Callable[["LockerModel", Command], bool]
    effect: Callable[["LockerModel", Command], None]
    message: str


# --- guards -----------------------------------------------------------------
def _always(m, c):
    return True

def _reservation_code_ok(m, c):
    return c.code == m.reservation_code

def _retrieval_code_ok(m, c):
    return c.code == m.retrieval_code

def _expired_flag_true(m, c):
    return c.expired is True

# --- effects ----------------------------------------------------------------
def _nothing(m, c):
    pass

def _set_reservation(m, c):                 # Rules 1, 2
    m.customer_id = c.customer_id
    m.reservation_code = "R-" + c.customer_id

def _set_retrieval_code(m, c):              # Rule 5
    m.retrieval_code = "P-" + m.customer_id

def _clear_all(m, c):                       # Rules 3, 7, 8 (+ assumption 3)
    m.customer_id = None
    m.reservation_code = None
    m.retrieval_code = None


# --- the behaviour table: ONLY the accepted cases ---------------------------
RULES = [
    Rule(State.AVAILABLE,   Operation.RESERVE,  State.RESERVED,    _always,               _set_reservation,     "reserved"),
    Rule(State.RESERVED,    Operation.CANCEL,   State.AVAILABLE,   _always,               _clear_all,           "cancelled"),
    Rule(State.RESERVED,    Operation.DEPOSIT,  State.OCCUPIED,    _reservation_code_ok,  _set_retrieval_code,  "deposited"),
    Rule(State.OCCUPIED,    Operation.RETRIEVE, State.AVAILABLE,   _retrieval_code_ok,    _clear_all,           "retrieved"),
    Rule(State.RESERVED,    Operation.EXPIRE,   State.AVAILABLE,   _expired_flag_true,    _clear_all,           "expired"),
    Rule(State.AVAILABLE,   Operation.DISABLE,  State.MAINTENANCE, _always,               _nothing,             "disabled"),
    Rule(State.MAINTENANCE, Operation.ENABLE,   State.AVAILABLE,   _always,               _nothing,             "enabled"),
]
_RULE_INDEX = {(r.source, r.operation): r for r in RULES}


class LockerModel:
    """Expected behaviour of a single locker compartment."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.state = State.AVAILABLE
        self.customer_id = None
        self.reservation_code = None
        self.retrieval_code = None

    def snapshot(self) -> Snapshot:
        return Snapshot(self.state, self.customer_id,
                        self.reservation_code, self.retrieval_code)

    def classify(self, command: Command):
        """Return (source_state, operation, outcome) WITHOUT changing the model.

        This triple identifies a model transition (used for coverage).
        """
        rule = _RULE_INDEX.get((self.state, command.operation))
        if rule is None:
            outcome = REJECTED_PRECONDITION
        elif rule.guard(self, command):
            outcome = ACCEPTED
        else:
            outcome = REJECTED_GUARD
        return (self.state, command.operation, outcome)

    def step(self, command: Command) -> Result:
        """Compute the expected result and update the model state."""
        rule = _RULE_INDEX.get((self.state, command.operation))
        if rule is None:
            return Result(False, "rejected_precondition")   # Rule 12: no change
        if not rule.guard(self, command):
            return Result(False, "rejected_guard")          # Rule 12: no change
        rule.effect(self, command)
        self.state = rule.target
        return Result(True, rule.message)