"""Catalogue of model transitions and transition pairs.

A TRANSITION is identified by the triple (source_state, operation, outcome):
    outcome in {accepted, rejected_precondition, rejected_guard}
Rejected transitions are self-loops (Rule 12). The catalogue is GENERATED from
the model (never hard-coded), so a changed rule changes the denominators.

A TRANSITION PAIR (t1, t2) is an ordered pair of transitions that can occur
back-to-back: target_state(t1) == source_state(t2).
"""
from .model import LockerModel, ACCEPTED, REJECTED_PRECONDITION, REJECTED_GUARD
from .types import State, Operation, Command

INITIAL_STATE = State.AVAILABLE

# Canonical commands that drive a fresh model into each state (used for
# building the catalogue and as shortest paths for generators).
_PREFIX = {
    State.AVAILABLE:   [],
    State.RESERVED:    [Command(Operation.RESERVE, customer_id="C1")],
    State.OCCUPIED:    [Command(Operation.RESERVE, customer_id="C1"),
                        Command(Operation.DEPOSIT, code="R-C1")],
    State.MAINTENANCE: [Command(Operation.DISABLE)],
}


def model_in_state(state: State) -> LockerModel:
    m = LockerModel()
    for c in _PREFIX[state]:
        m.step(c)
    return m


def shortest_path(state: State) -> list:
    """Shortest command sequence from the initial state to `state` (model-derived)."""
    return list(_PREFIX[state])


def command_for(transition, customer_id: str = "C1") -> Command:
    """A concrete Command that triggers `transition` when the model is in its source state.

    `customer_id` must be the customer currently stored in the model (for code values).
    For precondition rejections we send the most 'tempting' input (valid-looking
    code / expired=True) so that a weakened guard in the SUT is actually exposed.
    """
    _, op, outcome = transition
    good = {Operation.DEPOSIT: "R-" + customer_id, Operation.RETRIEVE: "P-" + customer_id}
    if op == Operation.RESERVE:
        return Command(op, customer_id=customer_id)
    if op == Operation.EXPIRE:
        return Command(op, customer_id=customer_id, expired=(outcome != REJECTED_GUARD))
    if op in good:
        code = "WRONG" if outcome == REJECTED_GUARD else good[op]
        return Command(op, customer_id=customer_id, code=code)
    return Command(op, customer_id=customer_id, code="X" if op == Operation.INVALID_ACCESS else "")


def _build_catalogue():
    """Enumerate every reachable transition and its target state, using the model."""
    target = {}
    for state in State:
        for op in Operation:
            for outcome in (ACCEPTED, REJECTED_PRECONDITION, REJECTED_GUARD):
                m = model_in_state(state)
                t = (state, op, outcome)
                if m.classify(command_for(t, "C1")) != t:
                    continue                      # this combination cannot occur
                m.step(command_for(t, "C1"))
                target[t] = m.state
    return target


TARGET = _build_catalogue()                       # transition -> target state
TRANSITIONS = sorted(TARGET, key=lambda t: (t[0].value, t[1].value, t[2]))
STATES = list(State)

OUTGOING = {s: [t for t in TRANSITIONS if t[0] == s] for s in State}
PAIRS = [(t1, t2) for t1 in TRANSITIONS for t2 in OUTGOING[TARGET[t1]]]


def describe(t) -> str:
    return f"{t[0].value} --{t[1].value}[{t[2]}]--> {TARGET[t].value}"