"""Test oracle: invariant checks that do NOT depend on the model.

These are evaluated on the SUT's own snapshots, so they can catch faults even if
the model shared the same misunderstanding (reduces oracle/SUT 'common mode' errors).
"""
from .types import State, Operation, Snapshot


def check_state_invariants(s: Snapshot) -> list[str]:
    """Return a list of violated invariants for one snapshot (empty list = OK)."""
    problems = []
    if s.state in (State.AVAILABLE, State.MAINTENANCE):
        if (s.customer_id, s.reservation_code, s.retrieval_code) != (None, None, None):
            problems.append(f"INV1: {s.state.value} must hold no customer/credentials, got {s}")
    elif s.state == State.RESERVED:
        if s.customer_id is None or s.reservation_code != "R-" + s.customer_id:
            problems.append(f"INV2: RESERVED needs customer and R-<cid> code, got {s}")
        if s.retrieval_code is not None:
            problems.append(f"INV2: RESERVED must not hold a retrieval code, got {s}")
    elif s.state == State.OCCUPIED:
        if (s.customer_id is None or s.reservation_code != "R-" + s.customer_id
                or s.retrieval_code != "P-" + s.customer_id):
            problems.append(f"INV3: OCCUPIED needs customer, R-<cid> and P-<cid>, got {s}")
    else:
        problems.append(f"INV6: unknown state {s.state}")
    return problems


def check_step_invariants(op: Operation, accepted: bool,
                          before: Snapshot, after: Snapshot) -> list[str]:
    """Invariants relating the SUT snapshot before and after ONE command."""
    problems = []
    if not accepted and before != after:                      # INV5 (Rule 12)
        problems.append(f"INV5: rejected {op.value} changed state: {before} -> {after}")
    if accepted and op in (Operation.CANCEL, Operation.EXPIRE, Operation.RETRIEVE):
        if after != Snapshot(State.AVAILABLE, None, None, None):   # INV4
            problems.append(f"INV4: accepted {op.value} must leave empty AVAILABLE, got {after}")
    return problems