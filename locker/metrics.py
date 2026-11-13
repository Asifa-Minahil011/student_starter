"""Coverage and mutation metrics, with explicit denominators."""
from .runner import format_sequence
from .transitions import TARGET, TRANSITIONS, PAIRS, STATES, INITIAL_STATE


class CoverageTracker:
    """Incrementally records covered states, transitions and transition pairs.

    Used both for final measurement and by coverage-directed generators.
    A trace is the list of model transitions executed by ONE sequence.
    Pairs are counted only between consecutive transitions of the same trace.
    """

    def __init__(self):
        self.states = {INITIAL_STATE}            # the initial state is visited by every test
        self.transitions = set()
        self.pairs = set()
        self.transition_counts = {t: 0 for t in TRANSITIONS}

    def add_trace(self, trace):
        prev = None
        for t in trace:
            self.states.add(TARGET[t])
            self.transitions.add(t)
            self.transition_counts[t] += 1
            if prev is not None:
                self.pairs.add((prev, t))
            prev = t

    def uncovered_transitions(self):
        return [t for t in TRANSITIONS if t not in self.transitions]

    def uncovered_pairs(self):
        return [p for p in PAIRS if p not in self.pairs]

    def summary(self) -> dict:
        pct = lambda n, d: round(100.0 * n / d, 2) if d else 0.0
        return {
            "states_covered": len(self.states), "states_total": len(STATES),
            "state_coverage": pct(len(self.states), len(STATES)),
            "transitions_covered": len(self.transitions), "transitions_total": len(TRANSITIONS),
            "transition_coverage": pct(len(self.transitions), len(TRANSITIONS)),
            "pairs_covered": len(self.pairs), "pairs_total": len(PAIRS),
            "pair_coverage": pct(len(self.pairs), len(PAIRS)),
        }


def calculate_coverage(executed_traces) -> dict:
    """State, transition and transition-pair coverage for a collection of traces."""
    tracker = CoverageTracker()
    for trace in executed_traces:
        tracker.add_trace(trace)
    return tracker.summary()


def mutation_summary(mutant_results) -> dict:
    """mutant_results: list of dicts {name, killed: bool, equivalent: bool (optional)}.

    mutation score = killed / (total - equivalent) * 100  (equivalent mutants excluded).
    """
    equivalent = [m["name"] for m in mutant_results if m.get("equivalent", False)]
    considered = [m for m in mutant_results if not m.get("equivalent", False)]
    killed = [m["name"] for m in considered if m["killed"]]
    survived = [m["name"] for m in considered if not m["killed"]]
    score = round(100.0 * len(killed) / len(considered), 2) if considered else 0.0
    return {"total": len(mutant_results), "non_equivalent_considered": len(considered),
            "detected": killed, "survived": survived, "equivalent": equivalent,
            "mutation_score": score}


def redundancy(sequences) -> dict:
    """Count exact duplicate sequences (identical command lists)."""
    keys = [format_sequence(s) for s in sequences]
    unique = len(set(keys))
    return {"total": len(keys), "unique": unique, "duplicates": len(keys) - unique}