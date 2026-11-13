"""Test-generation strategies.

Every generator:
  * is constructed with (seed, max_length) and uses its own random.Random(seed),
    so results are reproducible and independent of global randomness;
  * uses ONLY the model (never the SUT) to decide which commands to emit;
  * returns generate(count) -> list of sequences, each a list[Command] of length
    1..max_length.

Shared helper: candidate_commands() builds every command variant worth trying in
the model's current state (valid and invalid), tagged by the model's expectation.
"""
import random
from collections import deque

from .metrics import CoverageTracker
from .model import LockerModel, ACCEPTED
from .transitions import OUTGOING, PAIRS, TARGET, command_for
from .types import Command, Operation

CUSTOMERS = ("C1", "C2", "C3")


def candidate_commands(model: LockerModel) -> list:
    """All command variants for the model's current state, in a fixed (deterministic) order.

    Inputs cover: correct credentials, wrong credentials, empty credentials,
    credentials of the wrong kind (R-code where P-code is needed and vice versa),
    another customer's credentials, expired=True/False, and invalid access.
    """
    cid = model.customer_id or "C1"
    other = "C2" if cid != "C2" else "C3"
    cmds = [Command(Operation.RESERVE, customer_id=c) for c in CUSTOMERS]
    cmds += [Command(Operation.CANCEL)]
    cmds += [Command(Operation.DEPOSIT, code=code)
             for code in ("R-" + cid, "WRONG", "", "P-" + cid, "R-" + other)]
    cmds += [Command(Operation.RETRIEVE, code=code)
             for code in ("P-" + cid, "WRONG", "", "R-" + cid, "P-" + other)]
    cmds += [Command(Operation.EXPIRE, expired=True), Command(Operation.EXPIRE, expired=False)]
    cmds += [Command(Operation.DISABLE), Command(Operation.ENABLE)]
    cmds += [Command(Operation.INVALID_ACCESS, code="BAD"), Command(Operation.INVALID_ACCESS)]
    return cmds


def is_valid(model: LockerModel, command: Command) -> bool:
    """True if the model would ACCEPT this command in its current state."""
    return model.classify(command)[2] == ACCEPTED


class RandomWalkGenerator:
    """Strategy A: model-guided random walk.

    Algorithm (per sequence):
      1. Draw length uniformly from [1, max_length].
      2. Start a fresh model. For each step:
           - with probability p_valid, choose uniformly among the commands the
             model would currently ACCEPT (keeps the walk moving through states,
             so OCCUPIED etc. are reachable);
           - otherwise choose uniformly among ALL candidate variants, which
             includes invalid operations, wrong/empty/cross-kind codes and
             expired=False (this exercises rejection paths);
           - advance the model with the chosen command.
    Reproducibility: all randomness comes from random.Random(seed).
    """

    name = "random_walk"

    def __init__(self, seed: int, max_length: int, p_valid: float = 0.6):
        self.seed, self.max_length, self.p_valid = seed, max_length, p_valid

    def generate(self, count: int):
        rng = random.Random(self.seed)
        sequences = []
        for _ in range(count):
            model = LockerModel()
            seq = []
            for _ in range(rng.randint(1, self.max_length)):
                candidates = candidate_commands(model)
                valid = [c for c in candidates if is_valid(model, c)]
                pool = valid if (valid and rng.random() < self.p_valid) else candidates
                cmd = rng.choice(pool)
                model.step(cmd)
                seq.append(cmd)
            sequences.append(seq)
        return sequences


class CoverageGuidedGenerator:
    """Strategy B: coverage-directed generation (states and transitions).

    One CoverageTracker is shared by ALL sequences of a generate() call, so every
    new sequence is steered by what earlier sequences already covered.

    At each step the generator applies three priority levels:
      1. LOCAL: if some command available right now would exercise a transition
         that is still uncovered, choose one (random tie-break).
      2. DIRECTED: otherwise, if uncovered transitions remain somewhere in the
         model, run a breadth-first search over the model's state graph to the
         NEAREST state that has an uncovered transition, and take the first step
         of that path (the walk is re-planned after every step).
      3. BALANCING: when everything is covered, choose the command whose
         transition has been executed the FEWEST times (random tie-break), so the
         remaining sequences keep exploring less-exercised behaviour.
    Visiting uncovered states is a by-product: a state is entered through one of
    its incoming transitions, which level 1/2 always prioritise.

    Sequence length is drawn uniformly from [min(5, max_length), max_length]
    (longer than strategy A's minimum so that directed paths can finish).
    Randomness (tie-breaking, customer ids) comes from random.Random(seed).
    """

    name = "coverage_guided"

    def __init__(self, seed: int, max_length: int):
        self.seed, self.max_length = seed, max_length

    # -- helper: first step of the shortest path to the nearest uncovered transition
    @staticmethod
    def _step_toward_uncovered(model, tracker, rng):
        start = model.state
        dist, first = {start: 0}, {start: None}
        queue = deque([start])
        while queue:
            state = queue.popleft()
            for t in OUTGOING[state]:
                nxt = TARGET[t]
                if nxt not in dist:
                    dist[nxt] = dist[state] + 1
                    first[nxt] = first[state] or t
                    queue.append(nxt)
        targets = [t for t in tracker.uncovered_transitions() if t[0] in dist]
        if not targets:
            return None
        nearest = min(dist[t[0]] for t in targets)
        goal = rng.choice([t for t in targets if dist[t[0]] == nearest])
        return first[goal[0]]            # None when the goal is in the current state

    def generate(self, count: int):
        rng = random.Random(self.seed)
        tracker = CoverageTracker()
        min_len = min(5, self.max_length)
        sequences = []
        for _ in range(count):
            model = LockerModel()
            seq = []
            for _ in range(rng.randint(min_len, self.max_length)):
                candidates = candidate_commands(model)
                classified = [(c, model.classify(c)) for c in candidates]
                uncovered = [c for c, t in classified if t not in tracker.transitions]
                if uncovered:                                           # level 1
                    cmd = rng.choice(uncovered)
                else:
                    step = (self._step_toward_uncovered(model, tracker, rng)
                            if tracker.uncovered_transitions() else None)
                    if step is not None:                                # level 2
                        cid = (rng.choice(CUSTOMERS) if step[1] == Operation.RESERVE
                               else (model.customer_id or "C1"))
                        cmd = command_for(step, cid)
                    else:                                               # level 3
                        least = min(tracker.transition_counts[t] for _, t in classified)
                        cmd = rng.choice([c for c, t in classified
                                          if tracker.transition_counts[t] == least])
                tracker.add_trace([model.classify(cmd)])
                model.step(cmd)
                seq.append(cmd)
            sequences.append(seq)
        return sequences


class TransitionPairGenerator:
    """Strategy C: transition-pair (path-based) generation.

    A transition pair (t1, t2) means: t1 immediately followed by t2, where
    target_state(t1) == source_state(t2). The model has len(PAIRS) such pairs.

    Algorithm: repeatedly choose a TARGET PAIR, build the path that reaches it,
    and append [prefix path] + t1 + t2 to the current sequence, packing as many
    pairs as fit into max_length. After every appended command the pair
    (previous transition, this transition) is recorded as covered, so pairs
    reached incidentally (inside prefixes or at joins) also count.

    Choosing the target pair:
      PHASE 1 (some pairs still uncovered): among uncovered pairs that FIT in the
        remaining length, take those with the cheapest total cost
        (len(shortest prefix to t1's source state) + 2); random tie-break.
      PHASE 2 (all pairs covered): among pairs that fit, take the pair executed
        the fewest times so far (random tie-break), so later sequences keep
        exploring pair combinations in different contexts.
    Prefix paths are shortest paths over ACCEPTED transitions (BFS). Transition
    order is shuffled with the seeded RNG, so equally short alternatives
    (e.g. CANCEL vs EXPIRE to leave RESERVED) are both exercised.

    Randomness only affects tie-breaking, customer ids and alternative prefixes;
    the pair-targeting logic itself is deterministic.
    """

    name = "transition_pair"

    def __init__(self, seed: int, max_length: int):
        self.seed, self.max_length = seed, max_length

    @staticmethod
    def _shortest_paths(start_state, rng):
        """BFS over accepted transitions: state -> list of transitions from start_state."""
        paths, queue = {start_state: []}, deque([start_state])
        while queue:
            state = queue.popleft()
            outgoing = list(OUTGOING[state])
            rng.shuffle(outgoing)
            for t in outgoing:
                nxt = TARGET[t]
                if nxt not in paths:
                    paths[nxt] = paths[state] + [t]
                    queue.append(nxt)
        return paths

    def generate(self, count: int):
        rng = random.Random(self.seed)
        covered, counts = set(), {p: 0 for p in PAIRS}
        sequences = []
        for _ in range(count):
            model, seq, prev = LockerModel(), [], None
            while len(seq) < self.max_length:
                remaining = self.max_length - len(seq)
                paths = self._shortest_paths(model.state, rng)
                fits = [(len(paths[p[0][0]]) + 2, p) for p in PAIRS
                        if p[0][0] in paths and len(paths[p[0][0]]) + 2 <= remaining]
                if not fits:
                    break
                uncovered = [(c, p) for c, p in fits if p not in covered]
                if uncovered:                                           # phase 1
                    best = min(c for c, _ in uncovered)
                    pair = rng.choice([p for c, p in uncovered if c == best])
                else:                                                   # phase 2
                    least = min(counts[p] for _, p in fits)
                    pair = rng.choice([p for _, p in fits if counts[p] == least])
                for t in paths[pair[0][0]] + [pair[0], pair[1]]:
                    cid = (rng.choice(CUSTOMERS) if t[1] == Operation.RESERVE
                           else (model.customer_id or "C1"))
                    cmd = command_for(t, cid)
                    current = model.classify(cmd)
                    if prev is not None:
                        covered.add((prev, current))
                        counts[(prev, current)] += 1
                    model.step(cmd)
                    seq.append(cmd)
                    prev = current
            sequences.append(seq)
        return sequences